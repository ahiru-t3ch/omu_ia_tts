from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from kokoro import KPipeline

from pathlib import Path
from dotenv import load_dotenv
import logging
import os
import secrets

# Load keys from .env file
# Keys need to be read befor project's imports
# If they use env var it's better to read it here
load_dotenv()
API_KEY = os.getenv("API_KEY")
MAX_CHARS = int(os.getenv("MAX_CHARS"))
KOKORO_REPO_ID = os.getenv("KOKORO_REPO_ID") or "hexgrad/Kokoro-82M"

from models.TTSRequest import TTSRequest
from utils.tts_utils import validate_text, generate_audio
from config.voices import voices


AUDIO_DIR = Path("audio")


app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "Validation error on %s %s | errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "Invalid request payload",
        },
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("omu_ia_tts")


# One pipeline per lang_code; voice is passed when calling pipeline(..., voice=...).
pipelines = {
    lang_code: KPipeline(lang_code=lang_code, repo_id=KOKORO_REPO_ID)
    for lang_code in voices
}

VOICE_NAMES_BY_LANG = {
    lang_code: frozenset(entry["voice_name"] for entry in voice_list)
    for lang_code, voice_list in voices.items()
}


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Server API key is not configured",
        )
    provided = x_api_key
    if provided is None and authorization:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip() or None
    if provided is None or len(provided) != len(API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not secrets.compare_digest(provided, API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health(_: None = Depends(require_api_key)):
    """Light liveness probe for reverse proxies, Coolify, load balancers (no Kokoro inference)."""
    return {"status": "ok"}


@app.get("/audio/{filename}")
def get_audio(filename: str, _: None = Depends(require_api_key)):
    file_path = (AUDIO_DIR / filename).resolve()
    if not file_path.exists():
        logger.error(f"File not found: {file_path}") 
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")   
    return FileResponse(path=file_path, filename=filename, media_type="audio/wav")


@app.post("/tts")
def tts(request: TTSRequest, http_request: Request, download: bool = Query(default=False), _: None = Depends(require_api_key)):
    error_messages = validate_text(request.text, MAX_CHARS)
    if len(error_messages) > 0:
        logger.error(f"Validation errors: {error_messages}")
        raise HTTPException(status_code=400, detail=error_messages)

    pipeline = pipelines.get(request.lang_code)

    if pipeline is None:
        logger.error(f"Invalid language code: {request.lang_code}")
        raise HTTPException(status_code=400, detail=f"Invalid language code: {request.lang_code}")

    allowed_voices = VOICE_NAMES_BY_LANG.get(request.lang_code, frozenset())
    if request.voice not in allowed_voices:
        logger.error(f"Invalid voice for lang {request.lang_code}: {request.voice}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice '{request.voice}' for language '{request.lang_code}'",
        )

    try:
        file_path, filename = generate_audio(
            request.text, 
            request.voice, 
            request.speed, 
            request.split_pattern, 
            pipeline,
            AUDIO_DIR
        )
    except Exception as e:
        logger.error(f"Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not file_path.exists() or filename == None:
        logger.error(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    if download:
        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename={file_path.name}"}
        )
    else:
        audio_url = str(http_request.url_for("get_audio", filename=filename))
        return {"filename": file_path.name, "audio_url": audio_url}