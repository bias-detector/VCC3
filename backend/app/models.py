from pydantic import BaseModel, Field


class GuessRequest(BaseModel):
    guess: int = Field(..., ge=1, le=100)


class GuessResponse(BaseModel):
    result: str
    message: str
    game_over: bool
    attempts: int
