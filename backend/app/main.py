import random
import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import psutil

from .config import settings
from .cpu_stress import stress_controller

app = FastAPI(title="Number Guess Game", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Game state
game_state = {
    "secret_number": None,
    "attempts": 0,
    "game_started": False,
}

scale_state = {
    "enabled": False,
    "threshold": 75.0,
    "seconds": 20,
    "poll_seconds": 1,
    "project_id": "",
    "vm_name": "guess-game-vm",
    "zone": "us-central1-a",
    "machine_type": "e2-medium",
    "repo_url": "",
    "status": "idle",
    "message": "Monitor disabled (set GCP_PROJECT_ID).",
    "above_threshold_seconds": 0,
    "last_cpu_percent": 0.0,
    "last_triggered_at": None,
    "remote_url": "",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def scale_monitor_loop() -> None:
    """Simple CPU threshold monitor that triggers one-time VM deployment."""
    while True:
        await asyncio.sleep(scale_state["poll_seconds"])

        if not scale_state["enabled"]:
            continue

        if scale_state["status"] in {"deploying", "scaled_up"}:
            continue

        cpu_percent = psutil.cpu_percent(interval=0.1)
        scale_state["last_cpu_percent"] = cpu_percent

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

        if scale_state["above_threshold_seconds"] < scale_state["seconds"]:
            continue

        scale_state["status"] = "deploying"
        scale_state["message"] = "CPU threshold met. Triggering remote VM deployment..."

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
            remote_url = ""
            for line in output.splitlines():
                if "Game URL:" in line:
                    remote_url = line.split("Game URL:", 1)[1].strip()
                    break

            scale_state["status"] = "scaled_up"
            scale_state["above_threshold_seconds"] = scale_state["seconds"]
            scale_state["last_triggered_at"] = _utc_now()
            scale_state["remote_url"] = remote_url
            if remote_url:
                scale_state["message"] = f"Scale-up complete: {remote_url}"
            else:
                scale_state["message"] = (
                    "Scale-up complete. Check script output/logs for IP."
                )
        except subprocess.CalledProcessError as exc:
            scale_state["status"] = "error"
            scale_state["above_threshold_seconds"] = 0
            stderr = (exc.stderr or "").strip()
            scale_state["message"] = (
                f"Scale-up failed: {stderr[:200] or 'unknown error'}"
            )


@app.on_event("startup")
async def startup_event() -> None:
    project_id = (settings.gcp_project_id or "").strip()
    if project_id:
        scale_state["enabled"] = True
        scale_state["project_id"] = project_id
        scale_state["threshold"] = settings.scale_up_cpu_threshold
        scale_state["seconds"] = settings.scale_up_seconds
        scale_state["poll_seconds"] = settings.scale_poll_seconds
        scale_state["vm_name"] = settings.gcp_vm_name
        scale_state["zone"] = settings.gcp_zone
        scale_state["machine_type"] = settings.gcp_machine_type
        scale_state["repo_url"] = settings.repo_url
        scale_state["status"] = "watching"
        scale_state["message"] = "Monitor active. Waiting for high CPU."
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


@app.post("/api/game/start")
async def start_game() -> dict:
    global game_state
    game_state = {
        "secret_number": random.randint(1, 100),
        "attempts": 0,
        "game_started": True,
    }
    return {
        "message": "Game started! Guess a number between 1 and 100.",
        "game_started": True,
    }


@app.post("/api/game/guess")
async def make_guess(payload: dict) -> dict:
    if not game_state["game_started"]:
        return {
            "error": "Game not started. Start a new game first.",
            "game_over": False,
        }

    try:
        guess = int(payload.get("guess"))
    except (ValueError, TypeError):
        return {"error": "Invalid guess. Please enter a number.", "game_over": False}

    if guess < 1 or guess > 100:
        return {"error": "Please guess between 1 and 100.", "game_over": False}

    game_state["attempts"] += 1
    secret = game_state["secret_number"]

    if guess == secret:
        return {
            "result": "correct",
            "message": f"🎉 Correct! You got it in {game_state['attempts']} attempts!",
            "game_over": True,
            "attempts": game_state["attempts"],
        }
    elif guess < secret:
        return {
            "result": "too_low",
            "message": f"Too low! Try again. (Attempt {game_state['attempts']})",
            "game_over": False,
            "attempts": game_state["attempts"],
        }
    else:
        return {
            "result": "too_high",
            "message": f"Too high! Try again. (Attempt {game_state['attempts']})",
            "game_over": False,
            "attempts": game_state["attempts"],
        }


@app.get("/api/metrics")
async def metrics() -> dict:
    stress = stress_controller.status()
    cpu_percent = psutil.cpu_percent(interval=0.1)
    scale_state["last_cpu_percent"] = cpu_percent
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
        "scale_remote_url": scale_state["remote_url"],
        "scale_last_triggered_at": scale_state["last_triggered_at"],
    }


@app.get("/api/stress/status")
async def stress_status() -> dict:
    return stress_controller.status()


@app.post("/api/stress/start")
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

    result = stress_controller.start(workers=workers)
    return result


@app.post("/api/stress/stop")
async def stress_stop() -> dict:
    result = stress_controller.stop()
    return result
