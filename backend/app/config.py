from dataclasses import dataclass
from .constants.app_constants import (
    GCP_MACHINE_TYPE,
    GCP_PROJECT_ID,
    GCP_VM_NAME,
    GCP_ZONE,
    REPO_URL,
    SCALE_POLL_SECONDS,
    SCALE_UP_CPU_THRESHOLD,
    SCALE_UP_SECONDS,
    SERVICE_NAME,
)


@dataclass(frozen=True)
class Settings:
    service_name: str = SERVICE_NAME
    gcp_project_id: str = GCP_PROJECT_ID
    gcp_vm_name: str = GCP_VM_NAME
    gcp_zone: str = GCP_ZONE
    gcp_machine_type: str = GCP_MACHINE_TYPE
    repo_url: str = REPO_URL
    scale_up_cpu_threshold: float = SCALE_UP_CPU_THRESHOLD
    scale_up_seconds: int = SCALE_UP_SECONDS
    scale_poll_seconds: int = SCALE_POLL_SECONDS


settings = Settings()
