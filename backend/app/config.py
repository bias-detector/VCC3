import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "Number Guess Game")
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
    gcp_vm_name: str = os.getenv("GCP_VM_NAME", "guess-game-vm")
    gcp_zone: str = os.getenv("GCP_ZONE", "us-central1-a")
    gcp_machine_type: str = os.getenv("GCP_MACHINE_TYPE", "e2-medium")
    repo_url: str = os.getenv("REPO_URL", "")
    scale_up_cpu_threshold: float = float(os.getenv("SCALE_UP_CPU_THRESHOLD", "75"))
    scale_up_seconds: int = int(os.getenv("SCALE_UP_SECONDS", "10"))
    scale_poll_seconds: int = int(os.getenv("SCALE_POLL_SECONDS", "1"))


settings = Settings()
