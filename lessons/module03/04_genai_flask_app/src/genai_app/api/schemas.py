from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from genai_app.services.assistant import InquiryAnalysis

MAX_MESSAGE_CHARS = 4000


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]


class GenerateResponse(BaseModel):
    analysis: InquiryAnalysis
    model: str
    duration: float
