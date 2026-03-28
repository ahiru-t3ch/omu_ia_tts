from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from kokoro import KPipeline
from models.TTSRequest import TTSRequest
from utils.tts_utils import validate_text, generate_audio
from pathlib import Path
import logging


MAX_CHARS = 5000
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


pipelines = {
    "a": KPipeline(lang_code="a"), # American English
    "e": KPipeline(lang_code="e"), # Spanish es
    "f": KPipeline(lang_code="f"), # French fr-fr
}


# Position: 0 => female, 1 => male
voices = {
    "a": ["af_heart","am_adam"],
    "e": ["ef_dora","em_alex"],
    "f": ["ff_siwis", None], # no male voice for french
}

@app.get("/audio/{filename}")
def get_audio(filename: str):
    file_path = (AUDIO_DIR / filename).resolve()
    if not file_path.exists():
        logger.error(f"File not found: {file_path}") 
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")   
    return FileResponse(path=file_path, filename=filename, media_type="audio/wav")


@app.post("/tts")
def tts(request: TTSRequest, http_request: Request, download: bool = Query(default=False)):
    error_messages = validate_text(request.text, MAX_CHARS)
    if len(error_messages) > 0:
        logger.error(f"Validation errors: {error_messages}")
        raise HTTPException(status_code=400, detail=error_messages)

    pipeline = pipelines.get(request.lang_code)
    if pipeline is None:
        logger.error(f"Invalid language code: {request.lang_code}")
        raise HTTPException(status_code=400, detail=f"Invalid language code: {request.lang_code}")

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