#!/usr/bin/env python3
"""
Deploy Number Guess Game to Google Cloud Compute Engine VM
Requires: gcloud CLI installed and authenticated
"""

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.constants.app_constants import (
    GCP_MACHINE_TYPE,
    GCP_PROJECT_ID,
    GCP_VM_NAME,
    GCP_ZONE,
    REPO_URL,
)


DEFAULT_PROJECT_ID = GCP_PROJECT_ID
DEFAULT_VM_NAME = GCP_VM_NAME
DEFAULT_ZONE = GCP_ZONE
DEFAULT_MACHINE_TYPE = GCP_MACHINE_TYPE
DEFAULT_REPO_URL = REPO_URL
LOG_FILE = Path(__file__).resolve().parent / "deploy_gcp.log"


def _log_line(message):
    timestamp = datetime.now(timezone.utc).isoformat()
    line = f"[{timestamp}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _reset_deploy_log() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")


def _instance_exists(project_id, zone, vm_name):
    """Return True if VM already exists."""
    cmd = (
        f"gcloud compute instances describe {vm_name} "
        f"--zone={zone} --project={project_id}"
    )
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return result.returncode == 0


def run_cmd(cmd, desc):
    """Run shell command"""
    _log_line(f"{desc}...")
    _log_line(f"CMD: {cmd.strip()}")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, text=True, capture_output=True
        )
        if result.stdout and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                _log_line(f"STDOUT: {line}")
        if result.stderr and result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                _log_line(f"STDERR: {line}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        _log_line(f"ERROR CODE: {e.returncode}")
        if e.stdout and e.stdout.strip():
            for line in e.stdout.strip().splitlines():
                _log_line(f"STDOUT: {line}")
        if e.stderr and e.stderr.strip():
            for line in e.stderr.strip().splitlines():
                _log_line(f"STDERR: {line}")
        _log_line(f"Deployment failed. Full logs: {LOG_FILE}")
        sys.exit(1)


def deploy(
    project_id,
    vm_name="guess-game-vm",
    zone="us-central1-a",
    machine_type="e2-medium",
    repo_url=None,
):
    """Deploy to GCP"""

    _reset_deploy_log()

    _log_line("Starting deployment to GCP")
    _log_line(f"Project: {project_id}")
    _log_line(f"VM: {vm_name} ({machine_type})")
    _log_line(f"Zone: {zone}")
    _log_line(f"Log file: {LOG_FILE}")

    # Build startup script first so it can be passed during create.
    repo = repo_url or "https://github.com/your-user/VCC.git"
    _log_line(f"Startup script will sync code from: {repo}")
    _log_line(
        "Startup script flow: apt update -> install tools -> clone/pull repo -> install requirements -> start uvicorn"
    )
    startup = f"""#!/bin/bash
apt-get update
apt-get install -y git python3-pip python3-venv
cd /opt
git clone {repo} app || (cd app && git pull)
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
nohup uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > /var/log/app.log 2>&1 &
echo "App deployed"
"""

    startup_file = Path("/tmp/startup.sh")
    startup_file.write_text(startup, encoding="utf-8")

    vm_exists = _instance_exists(project_id, zone, vm_name)
    if vm_exists:
        _log_line(
            f"VM '{vm_name}' already exists. Updating startup metadata and resetting VM."
        )
    else:
        create_cmd = f"""
        gcloud compute instances create {vm_name} \\
            --project={project_id} \\
            --zone={zone} \\
            --machine-type={machine_type} \\
            --image-family=ubuntu-2204-lts \\
            --image-project=ubuntu-os-cloud \\
            --boot-disk-size=20GB \\
            --scopes=cloud-platform \\
            --tags=http-server \\
            --metadata-from-file startup-script={startup_file}
        """
        run_cmd(create_cmd, f"Creating VM '{vm_name}'")
        time.sleep(10)

    # Open firewall
    run_cmd(
        f"gcloud compute firewall-rules create allow-8000 --allow=tcp:8000 --source-ranges=0.0.0.0/0 --project={project_id} 2>/dev/null || true",
        "Configuring firewall",
    )

    run_cmd(
        f"gcloud compute instances add-metadata {vm_name} --zone={zone} --project={project_id} --metadata-from-file startup-script={startup_file}",
        "Uploading startup script",
    )

    if vm_exists:
        run_cmd(
            f"gcloud compute instances reset {vm_name} --zone={zone} --project={project_id}",
            "Resetting existing VM so startup script runs",
        )
        time.sleep(10)

    # Get IP
    ip_cmd = f"gcloud compute instances describe {vm_name} --zone={zone} --project={project_id} --format='value(networkInterfaces[0].accessConfigs[0].natIP)'"
    ip = run_cmd(ip_cmd, "Getting external IP").strip()

    _log_line("Deployment started")
    _log_line(f"Game URL: http://{ip}:8000")
    _log_line(f"Health: http://{ip}:8000/api/health")
    _log_line("Wait 1-2 minutes for setup to complete")
    _log_line(
        f"Remote app logs: gcloud compute ssh {vm_name} --zone={zone} --project={project_id} -- tail -f /var/log/app.log"
    )
    _log_line(f"Local deploy logs: {LOG_FILE}")


if __name__ == "__main__":
    # Optional CLI args: project_id, vm_name, zone, machine_type, repo_url
    # If not provided, values come from backend constants.
    project_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT_ID
    vm_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_VM_NAME
    zone = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_ZONE
    machine_type = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_MACHINE_TYPE
    repo_url = sys.argv[5] if len(sys.argv) > 5 else DEFAULT_REPO_URL

    deploy(project_id, vm_name, zone, machine_type, repo_url)
