from kokoro import KPipeline
import soundfile as sf
import numpy as np
from datetime import datetime
import uuid
from pathlib import Path
import logging


logger = logging.getLogger(__name__) # defined into main.py called omu_ia_tts


def validate_text(text: str, max_chars: int) -> list[str]:
    error_message = []

    if not text:
        error_message.append("Text is required")
        logger.error("Text is required")
    
    if len(text) > max_chars:
        error_message.append(f"Text too long: {len(text)} > {max_chars}")
        logger.error(f"Text too long: {len(text)} > {max_chars}")
    
    return error_message


def generate_audio(
    text: str,
    voice: str,
    speed: float,
    split_pattern: str,
    pipeline: KPipeline,
    audio_dir: Path,
) -> tuple[Path, str]:
    generator = pipeline(text=text, voice=voice, speed=speed, split_pattern=split_pattern)
    chunks_sounds = []
    for i, (gs, ps, audio) in enumerate(generator):
        logger.info(f"Chunk {i}: {gs} - {ps}")
        chunks_sounds.append(audio)

    final_audio = np.concatenate(chunks_sounds, axis=0)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    uid = uuid.uuid4().hex[:8]
    filename = f"audio-{ts}-{uid}.wav"
    audio_dir.mkdir(parents=True, exist_ok=True)
    file_path = (audio_dir / filename).resolve()
    
    sf.write(file_path, final_audio, 24000)

    return file_path, filename
