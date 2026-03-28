from pydantic import BaseModel, Field, field_validator
import logging


logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    lang_code: str = "a"
    voice: str = "af_heart"
    speed: float = 1.0
    split_pattern: str = r'\n+'

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value:
            logger.error("Text is required")
            raise ValueError("Text is required")
        return value