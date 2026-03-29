from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class ClassifyResponse(BaseModel):
    text: str
    toxic: bool
    confidence: float
    reason: str
    source: str


class LoadRequest(BaseModel):
    total_requests: int = Field(default=120, ge=1, le=5000)
    concurrency: int = Field(default=20, ge=1, le=200)
    toxic_ratio: float = Field(default=0.5, ge=0.0, le=1.0)


class LoadResponse(BaseModel):
    total_requests: int
    completed: int
    failures: int
    local_routed: int
    cloud_routed: int
