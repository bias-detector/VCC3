import asyncio
import subprocess
import sys
import math
import os
import logging
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import psutil

from .config import settings
from .cpu_stress import stress_controller

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("scale-demo")

app = FastAPI(title="Autoscale Lifecycle Demo", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scale_state = {
    "enabled": False,
    "threshold": 75.0,
    "seconds": 20,
    "down_threshold": 75.0,
    "down_seconds": 10,
    "poll_seconds": 1,
    "project_id": "",
    "vm_name": "guess-game-vm",
    "zone": "us-central1-a",
    "machine_type": "e2-medium",
    "repo_url": "",
    "status": "idle",
    "message": "Monitor disabled.",
    "above_threshold_seconds": 0,
    "below_threshold_seconds": 0,
    "last_cpu_percent": 0.0,
    "last_triggered_at": None,
    "remote_url": "",
    "vm_active": False,
    "scale_down_armed": False,
    "deploy_log_path": "scripts/deploy_gcp.log",
}

event_log = deque(maxlen=300)


def _add_event(message: str, level: str = "info", source: str = "system") -> None:
    entry = {
        "timestamp": _utc_now(),
        "level": level,
        "source": source,
        "message": message,
    }
    event_log.append(entry)
    logger.info(
        f"[{entry['timestamp']}] [{source.upper()}] [{level.upper()}] {message}"
    )


def _resolve_deploy_log_path() -> Path:
    path = Path(scale_state["deploy_log_path"])
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _read_deploy_log_tail(limit: int = 20) -> List[str]:
    path = _resolve_deploy_log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit <= 0:
        return lines
    return lines[-limit:]


def _reset_runtime_logs() -> None:
    """Clear in-memory and file-based logs on service startup."""
    event_log.clear()
    path = _resolve_deploy_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _emit_deploy_stage_events(output: str) -> None:
    """Translate deploy script output into UI-friendly lifecycle events."""
    if not output:
        return

    important = (
        "Starting deployment to GCP",
        "Project:",
        "VM:",
        "Zone:",
        "Creating VM",
        "already exists",
        "Configuring firewall",
        "Uploading startup script",
        "Resetting existing VM",
        "Getting external IP",
        "Startup script will sync code from",
        "Startup script flow",
        "Deployment started",
        "Game URL:",
        "Health:",
        "Wait 1-2 minutes",
        "Remote app logs:",
        "Local deploy logs:",
        "CMD:",
        "STDOUT:",
        "STDERR:",
        "ERROR CODE:",
        "Deployment failed",
    )

    for line in output.splitlines():
        clean = line.strip()
        if not clean:
            continue

        # Strip embedded deploy-script timestamp, keep details for the UI feed.
        if clean.startswith("[") and "] " in clean:
            clean = clean.split("] ", 1)[1].strip()

        if not any(token in clean for token in important):
            continue

        level = "info"
        if "ERROR CODE:" in clean or "Deployment failed" in clean:
            level = "error"
        elif "STDERR:" in clean or "WARNING" in clean:
            level = "warning"
        elif "Game URL:" in clean or "Health:" in clean:
            level = "success"

        _add_event(clean, level=level, source="deploy")

    if "Deployment failed" in output or "ERROR CODE:" in output:
        _add_event(
            "Deployment command reported an error. Check deployment events for details.",
            level="error",
            source="deploy",
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _refresh_vm_state_from_gcp(reason: str) -> bool:
    """Sync in-memory VM state with actual GCP instance status."""
    project_id = (scale_state.get("project_id") or "").strip()
    vm_name = (scale_state.get("vm_name") or "").strip()
    zone = (scale_state.get("zone") or "").strip()
    if not project_id or not vm_name or not zone:
        return scale_state["vm_active"]

    cmd = [
        "gcloud",
        "compute",
        "instances",
        "describe",
        vm_name,
        f"--zone={zone}",
        f"--project={project_id}",
        "--format=json(status,networkInterfaces)",
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        _add_event(
            f"VM status check failed during {reason}: {exc}",
            level="warning",
            source="scale",
        )
        return scale_state["vm_active"]

    if result.returncode != 0:
        err = ((result.stderr or "") + " " + (result.stdout or "")).lower()
        if "was not found" in err or "could not fetch resource" in err:
            if scale_state["vm_active"]:
                _add_event(
                    f"VM no longer exists in GCP ({reason}). Local state updated.",
                    level="warning",
                    source="scale",
                )
            scale_state["vm_active"] = False
            scale_state["remote_url"] = ""
            return False
        _add_event(
            f"Could not verify VM state during {reason}. Using local state.",
            level="warning",
            source="scale",
        )
        return scale_state["vm_active"]

    payload = (result.stdout or "").strip()
    try:
        data = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        data = {}

    status = str(data.get("status") or "").upper()
    active = status in {"PROVISIONING", "STAGING", "RUNNING", "REPAIRING"}
    scale_state["vm_active"] = active

    if active:
        nics = data.get("networkInterfaces") or []
        if nics:
            access = nics[0].get("accessConfigs") or []
            if access:
                nat_ip = access[0].get("natIP")
                if nat_ip:
                    scale_state["remote_url"] = f"http://{nat_ip}:8000"

    return active


async def scale_monitor_loop() -> None:
    """CPU monitor for scale-up and armed scale-down lifecycle."""
    while True:
        await asyncio.sleep(scale_state["poll_seconds"])

        # Single source of truth: both UI and scaling use this sampled value.
        cpu_percent = psutil.cpu_percent(interval=0.1)
        scale_state["last_cpu_percent"] = cpu_percent

        if not scale_state["enabled"]:
            continue

        if scale_state["status"] in {"deploying", "deleting"}:
            continue

        if not scale_state["vm_active"]:
            if cpu_percent >= scale_state["threshold"]:
                scale_state["above_threshold_seconds"] += scale_state["poll_seconds"]
                scale_state["status"] = "watching"
                scale_state["message"] = (
                    f"CPU high for {scale_state['above_threshold_seconds']}s "
                    f"(target {scale_state['seconds']}s)"
                )
            else:
                if scale_state["above_threshold_seconds"] > 0:
                    scale_state["message"] = "CPU dropped below threshold; reset timer."
                else:
                    scale_state["message"] = "Watching CPU for sustained high usage."
                scale_state["above_threshold_seconds"] = 0
                scale_state["status"] = "watching"

            if scale_state["above_threshold_seconds"] >= scale_state["seconds"]:
                scale_state["status"] = "deploying"
                scale_state["message"] = (
                    "CPU threshold met. Triggering remote VM deployment..."
                )
                _add_event(
                    "CPU threshold reached, running remote deployment.",
                    source="scale",
                )

                deploy_script = PROJECT_ROOT / "scripts" / "deploy_gcp.py"
                cmd = [
                    sys.executable,
                    str(deploy_script),
                    scale_state["project_id"],
                    scale_state["vm_name"],
                    scale_state["zone"],
                    scale_state["machine_type"],
                ]
                if scale_state["repo_url"]:
                    cmd.append(scale_state["repo_url"])

                try:
                    result = await asyncio.to_thread(
                        subprocess.run,
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    output = (result.stdout or "") + "\n" + (result.stderr or "")
                    _emit_deploy_stage_events(output)
                    remote_url = ""
                    for line in output.splitlines():
                        if "Game URL:" in line:
                            remote_url = line.split("Game URL:", 1)[1].strip()
                            break

                    scale_state["status"] = "scaled_up"
                    scale_state["vm_active"] = True
                    scale_state["above_threshold_seconds"] = scale_state["seconds"]
                    scale_state["last_triggered_at"] = _utc_now()
                    scale_state["remote_url"] = remote_url
                    scale_state["scale_down_armed"] = False
                    scale_state["below_threshold_seconds"] = 0

                    if remote_url:
                        scale_state["message"] = f"Scale-up complete: {remote_url}"
                        _add_event(
                            f"Scale-up complete. Remote app: {remote_url}",
                            level="success",
                            source="scale",
                        )
                    else:
                        scale_state["message"] = (
                            "Scale-up complete. Check script output/logs for IP."
                        )
                        _add_event(
                            "Scale-up complete, but no URL was parsed from script output.",
                            level="warning",
                            source="scale",
                        )
                except subprocess.CalledProcessError as exc:
                    scale_state["status"] = "error"
                    scale_state["above_threshold_seconds"] = 0
                    stderr = (exc.stderr or "").strip()
                    stdout = (exc.stdout or "").strip()
                    _emit_deploy_stage_events(f"{stdout}\n{stderr}")
                    snippet = stderr or stdout or "unknown error"
                    scale_state["message"] = (
                        "Scale-up failed: "
                        f"{snippet[:220]}. See {scale_state['deploy_log_path']} for full logs."
                    )
                    _add_event(
                        f"Scale-up failed: {snippet[:220]}",
                        level="error",
                        source="scale",
                    )

        if scale_state["scale_down_armed"]:
            if cpu_percent < scale_state["down_threshold"]:
                scale_state["below_threshold_seconds"] += scale_state["poll_seconds"]
                scale_state["message"] = (
                    f"Low CPU for {scale_state['below_threshold_seconds']}s "
                    f"(target {scale_state['down_seconds']}s) before VM delete"
                )
            else:
                if scale_state["below_threshold_seconds"] > 0:
                    _add_event(
                        "Scale-down timer reset because CPU rose above threshold.",
                        level="warning",
                        source="scale",
                    )
                scale_state["below_threshold_seconds"] = 0
                scale_state["message"] = "Scale-down armed. Waiting for low CPU window."

            if scale_state["below_threshold_seconds"] >= scale_state["down_seconds"]:
                if not scale_state["vm_active"]:
                    scale_state["scale_down_armed"] = False
                    scale_state["below_threshold_seconds"] = 0
                    scale_state["status"] = "watching"
                    scale_state["message"] = (
                        "Low CPU sustained. No active VM found, delete skipped."
                    )
                    _add_event(
                        "Low CPU sustained, but no active VM to delete. Timer reset.",
                        level="warning",
                        source="scale",
                    )
                    continue

                scale_state["status"] = "deleting"
                scale_state["message"] = "Low CPU sustained. Deleting VM..."
                _add_event(
                    "Low CPU sustained after stop; deleting remote VM.",
                    source="scale",
                )

                delete_cmd = [
                    "gcloud",
                    "compute",
                    "instances",
                    "delete",
                    scale_state["vm_name"],
                    f"--zone={scale_state['zone']}",
                    f"--project={scale_state['project_id']}",
                    "--quiet",
                ]

                try:
                    result = await asyncio.to_thread(
                        subprocess.run,
                        delete_cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    output = (result.stdout or "") + "\n" + (result.stderr or "")
                    snippet = " ".join(output.splitlines())[:220].strip()
                    scale_state["status"] = "watching"
                    scale_state["vm_active"] = False
                    scale_state["remote_url"] = ""
                    scale_state["scale_down_armed"] = False
                    scale_state["below_threshold_seconds"] = 0
                    scale_state["above_threshold_seconds"] = 0
                    scale_state["message"] = "Scale-down complete. VM deleted."
                    _add_event(
                        f"Scale-down complete. VM deleted. {snippet}",
                        level="success",
                        source="scale",
                    )
                except subprocess.CalledProcessError as exc:
                    stderr = (exc.stderr or "").strip()
                    stdout = (exc.stdout or "").strip()
                    combined = f"{stderr} {stdout}".strip().lower()
                    if "was not found" in combined:
                        scale_state["status"] = "watching"
                        scale_state["vm_active"] = False
                        scale_state["remote_url"] = ""
                        scale_state["scale_down_armed"] = False
                        scale_state["below_threshold_seconds"] = 0
                        scale_state["above_threshold_seconds"] = 0
                        scale_state["message"] = (
                            "VM already deleted. Monitor returned to watching."
                        )
                        _add_event(
                            "Delete requested, but VM was already missing. State normalized.",
                            level="warning",
                            source="scale",
                        )
                    else:
                        scale_state["status"] = "error"
                        snippet = (stderr or stdout or "unknown error")[:220]
                        scale_state["message"] = f"Scale-down failed: {snippet}"
                        _add_event(
                            f"Scale-down failed: {snippet}",
                            level="error",
                            source="scale",
                        )


@app.on_event("startup")
async def startup_event() -> None:
    _reset_runtime_logs()
    scale_state["last_cpu_percent"] = psutil.cpu_percent(interval=0.1)
    _add_event("Scale demo service booting.", source="system")
    project_id = (settings.gcp_project_id or "").strip()
    if project_id:
        scale_state["enabled"] = True
        scale_state["project_id"] = project_id
        scale_state["threshold"] = settings.scale_up_cpu_threshold
        scale_state["seconds"] = settings.scale_up_seconds
        scale_state["down_threshold"] = settings.scale_up_cpu_threshold
        scale_state["poll_seconds"] = settings.scale_poll_seconds
        scale_state["vm_name"] = settings.gcp_vm_name
        scale_state["zone"] = settings.gcp_zone
        scale_state["machine_type"] = settings.gcp_machine_type
        scale_state["repo_url"] = settings.repo_url
        scale_state["status"] = "watching"
        scale_state["message"] = f"Monitor active on project: {project_id}"
        vm_exists = await _refresh_vm_state_from_gcp("startup")
        if vm_exists:
            _add_event(
                "Detected an already-running VM in GCP; scale-down can act on it.",
                level="success",
                source="scale",
            )
        _add_event(
            f"Monitor active for project {project_id}. Threshold {scale_state['threshold']}%.",
            level="success",
            source="scale",
        )
    else:
        scale_state["enabled"] = False
        scale_state["status"] = "idle"
        scale_state["message"] = "Monitor disabled (project id is empty)."
        _add_event(
            "Monitor disabled because project id is empty.",
            level="warning",
            source="scale",
        )
    asyncio.create_task(scale_monitor_loop())


# Serve static files from frontend/public
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "public"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.service_name,
    }


@app.get("/api/scale/metrics")
async def metrics() -> dict:
    stress = stress_controller.status()
    cpu_percent = float(scale_state["last_cpu_percent"])
    events = list(event_log)[-80:]
    deploy_tail = _read_deploy_log_tail(limit=18)
    return {
        "service": settings.service_name,
        "cpu_percent": cpu_percent,
        "stress_active": stress["active"],
        "stress_workers": stress["workers"],
        "scale_monitor_enabled": scale_state["enabled"],
        "scale_status": scale_state["status"],
        "scale_message": scale_state["message"],
        "scale_above_threshold_seconds": scale_state["above_threshold_seconds"],
        "scale_threshold": scale_state["threshold"],
        "scale_target_seconds": scale_state["seconds"],
        "scale_down_threshold": scale_state["down_threshold"],
        "scale_down_target_seconds": scale_state["down_seconds"],
        "scale_below_threshold_seconds": scale_state["below_threshold_seconds"],
        "scale_down_armed": scale_state["scale_down_armed"],
        "scale_vm_active": scale_state["vm_active"],
        "scale_remote_url": scale_state["remote_url"],
        "scale_last_triggered_at": scale_state["last_triggered_at"],
        "scale_deploy_log_path": scale_state["deploy_log_path"],
        "event_log": events,
        "deploy_log_tail": deploy_tail,
    }


@app.get("/api/scale/stress/status")
async def stress_status() -> dict:
    return stress_controller.status()


@app.post("/api/scale/stress/start")
async def stress_start(payload: dict = None) -> dict:
    if payload is None:
        payload = {}
    workers_raw = payload.get("workers")
    workers = None
    if workers_raw is not None:
        try:
            workers = int(workers_raw)
        except (TypeError, ValueError):
            workers = None
    else:
        # Auto-pick workers to better match scale threshold on high-core machines.
        cpu_count = os.cpu_count() or 1
        threshold_ratio = max(0.1, min(scale_state["threshold"] / 100.0, 1.0))
        workers = max(10, math.ceil(cpu_count * threshold_ratio) + 1)

    result = stress_controller.start(workers=workers)
    if result.get("started"):
        scale_state["scale_down_armed"] = False
        scale_state["below_threshold_seconds"] = 0
        _add_event(
            f"CPU stress started with {result.get('workers', 0)} workers.",
            source="stress",
        )
    else:
        _add_event(result.get("message", "CPU stress start skipped."), source="stress")
    return result


@app.post("/api/scale/stress/stop")
async def stress_stop() -> dict:
    result = stress_controller.stop()
    _add_event(result.get("message", "CPU stress stop invoked."), source="stress")
    await _refresh_vm_state_from_gcp("stop")
    scale_state["scale_down_armed"] = True
    scale_state["below_threshold_seconds"] = 0
    if scale_state["vm_active"]:
        _add_event(
            "Scale-down armed. VM will be deleted after sustained low CPU.",
            level="warning",
            source="scale",
        )
        scale_state["message"] = "Scale-down armed. Waiting for low CPU window."
    else:
        _add_event(
            "Stop pressed. Low-CPU timer armed, but no active remote VM to delete.",
            level="warning",
            source="scale",
        )
        scale_state["message"] = (
            "Scale-down armed. No active VM currently; timer will auto-reset."
        )
    return result
