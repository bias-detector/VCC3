#!/usr/bin/env python3
"""
Deploy Number Guess Game to Google Cloud Compute Engine VM
Requires: gcloud CLI installed and authenticated
"""

import subprocess
import sys
import time


def run_cmd(cmd, desc):
    """Run shell command"""
    print(f"▶ {desc}...")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, text=True, capture_output=True
        )
        print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e.stderr}")
        sys.exit(1)


def deploy(
    project_id,
    vm_name="guess-game-vm",
    zone="us-central1-a",
    machine_type="e2-medium",
    repo_url=None,
):
    """Deploy to GCP"""

    print(f"\n🚀 Deploying to GCP")
    print(f"   Project: {project_id}")
    print(f"   VM: {vm_name} ({machine_type})")
    print(f"   Zone: {zone}\n")

    # Create VM
    create_cmd = f"""
    gcloud compute instances create {vm_name} \\
        --project={project_id} \\
        --zone={zone} \\
        --machine-type={machine_type} \\
        --image-family=ubuntu-2204-lts \\
        --image-project=ubuntu-os-cloud \\
        --boot-disk-size=20GB \\
        --scopes=cloud-platform \\
        --tags=http-server
    """

    run_cmd(create_cmd, f"Creating VM '{vm_name}'")
    time.sleep(10)

    # Open firewall
    run_cmd(
        f"gcloud compute firewall-rules create allow-8000 --allow=tcp:8000 --source-ranges=0.0.0.0/0 --project={project_id} 2>/dev/null || true",
        "Configuring firewall",
    )

    # Startup script
    repo = repo_url or "https://github.com/your-user/VCC.git"
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
echo "✓ App deployed!"
"""

    with open("/tmp/startup.sh", "w") as f:
        f.write(startup)

    run_cmd(
        f"gcloud compute instances add-metadata {vm_name} --zone={zone} --project={project_id} --metadata startup-script='$(cat /tmp/startup.sh)'",
        "Uploading startup script",
    )

    # Get IP
    ip_cmd = f"gcloud compute instances describe {vm_name} --zone={zone} --project={project_id} --format='value(networkInterfaces[0].accessConfigs[0].natIP)'"
    ip = run_cmd(ip_cmd, "Getting external IP").strip()

    print(f"\n✅ Deployment initiated!")
    print(f"\n   Game URL: http://{ip}:8000")
    print(f"   Health:   http://{ip}:8000/api/health")
    print(f"\n   ⏳ Wait 1-2 min for setup to complete")
    print(
        f"   View logs: gcloud compute ssh {vm_name} --zone={zone} --project={project_id} -- tail -f /var/log/app.log"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 deploy_gcp.py <project_id> [vm_name] [zone] [machine_type] [repo_url]"
        )
        print("\nExample:")
        print("  python3 deploy_gcp.py my-project")
        print(
            "  python3 deploy_gcp.py my-project guess-game us-central1-a e2-medium https://github.com/user/VCC.git"
        )
        sys.exit(1)

    project_id = sys.argv[1]
    vm_name = sys.argv[2] if len(sys.argv) > 2 else "guess-game-vm"
    zone = sys.argv[3] if len(sys.argv) > 3 else "us-central1-a"
    machine_type = sys.argv[4] if len(sys.argv) > 4 else "e2-medium"
    repo_url = sys.argv[5] if len(sys.argv) > 5 else None

    deploy(project_id, vm_name, zone, machine_type, repo_url)
