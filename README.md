# OMU IA TTS

API FastAPI which transform text in audi using the inference (already trained) and open-weight (weights and params are published) model **Kokoro**.  
Kokoro is an opensource TTS (Text To Speach) open-weight model.

## Table of content
- [About Kokoro](#about-kokoro)
- [Requirements](#requirements)
- [Install](#install)
- [Run fast api server in local and test API](#run-fast-api-server-in-local-and-test-api)
- [Endpoints](#endpoints)
- [Languages and Voicices](#languages-and-voices)
- [Project Structure](#project-structure)
- [API errors reference](#api-errors-reference)

<!--
 ![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
-->

## About Kokoro
- [deepwiki.com/hexgrad/kokoro](https://deepwiki.com/hexgrad/kokoro)
- [huggingface.co/hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
- [kokorottsai.com](https://kokorottsai.com/)
- [github.com/hexgrad/kokoro](https://github.com/hexgrad/kokoro)
- [huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)

## Requirements
- Python 3.10-3.12 is recommanded according to Kokoro doc.
- Avoid Python 3.14.
- Use a virtual environement.

## Install
Bellow command will install kokoro (the TTS model) and soundfile (to write audio files) with their required dependencies: 
```bash
# Force CPU instead of GPU (GPU download very long same logic in Dockerfile)
python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Run fast api server in local and test API

### Local machine
```bash
fastapi dev
```

### Docker
```bash
docker build -t omu-ia-tts .
docker run --rm -p 8000:8000 omu-ia-tts
```

## Endpoints
Test with Bruno or Postman.

### GET /health
Light **liveness** check for load balancers, Coolify, and monitoring. Does not run Kokoro inference.

**URL:**
```
http://127.0.0.1:8000/health
```

**Response:** `200` with JSON:
```json
{"status": "ok"}
```

Params: None · Body: None · Auth: None

### POST /tts
Post url (param downlad added by Bruno or Postman):
```
http://127.0.0.1:8000/tts?download=false
```

Params:
|Name    |Value|
|--------|-----|
|download|true |

If param "download" is "true" then audio file is in the API response.  
If "false" then a downlad url is shared to user.  

Body:
```json
{
  "text": "This is a test.\n Another line in the test ...",
  "lang_code": "a",
  "voice": "af_heart",
  "speed": 1.0,
  "split_pattern": "\\n+"
}
```

Headers:
|Name        |Value           |
|------------|----------------|
|Content-Type|application/json|

Auth: No Auth

### GET /audio/{filename}
Get audio file is in the API response.  

Get url:
```
http://127.0.0.1:8000/audio/{file_name}
```

Ex file_name: audio-20260328-113258-601da369.wav 

Params: None  

Body: None  

Headers:
|Name        |Value           |
|------------|----------------|
|Content-Type|application/json|

Auth: No Auth

## Languages and Voicices
|Language|Code|Female voice|Male voice|
|--------|----|------------|----------|
|US EN   |a   |af_heart    |am_adam   |
|ES      |e   |ef_dora     |em_alex   |
|FR      |f   |ff_siwis    |None      |

## Project Structure
| File / folder | Role |
|---------------|------|
| `main.py` | FastAPI app: `/health`, `/tts`, `/audio/{filename}` |
| `config/voices.py` | Supported `lang_code` entries and allowed `voice_name` list per language |
| `models/TTSRequest.py` | JSON body expected by `POST /tts` |
| `utils/tts_utils.py` | Text validation; WAV files written under `audio/` |
| `audio/` | Generated `.wav` files (gitignored) |

## API errors reference

Responses use FastAPI’s `{ "detail": ... }` shape unless noted. Some `detail` values are **dynamic** (paths, counts, upstream messages).

### `POST /tts`

| HTTP | When | Typical `detail` |
|------|------|-------------------|
| **422** | JSON body invalid before the route runs (Pydantic) | Object with `detail` (list of Pydantic errors) and `message`: `"Invalid request payload"` (see global handler below). |
| **422** | `text` fails `Field(..., min_length=1)` (e.g. `""`) | Pydantic error on field `text` (too short / string_too_short). |
| **422** | `text` empty in custom validator | `"Text is required"` (from `TTSRequest` validator). |
| **400** | `validate_text()` in `utils/tts_utils.py` | List of strings, e.g. `"Text is required"` and/or `"Text too long: {len} > 5000"` (`5000` = `MAX_CHARS` in `main.py`). |
| **400** | Unknown `lang_code` (not a key in `config/voices.py` / no pipeline for that language) | `"Invalid language code: {lang_code}"` |
| **400** | `voice` not listed for that `lang_code` in `config/voices.py` (`VOICE_NAMES_BY_LANG`) | `"Invalid voice '{voice}' for language '{lang_code}'"` (exact strings from the request appear in the message). |
| **500** | Any exception inside `generate_audio()` (Kokoro, Hugging Face download, I/O, etc.) | `str(exception)` — e.g. Hugging Face **404** if `voice` does not exist on the hub (typo, removed voice): message often mentions `https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/{voice}.pt`. |
| **404** | WAV not on disk after generation | `"File not found: {absolute_path}"` |

### `GET /audio/{filename}`

| HTTP | When | Typical `detail` |
|------|------|-------------------|
| **404** | File missing under `audio/` (or path does not exist) | `"File not found: {absolute_path}"` |

### Global: invalid JSON / wrong types (any route)

| HTTP | When | Body shape |
|------|------|------------|
| **422** | `RequestValidationError` (malformed JSON, wrong types, missing required fields) | `{ "detail": [ ... ], "message": "Invalid request payload" }` — `detail` is Pydantic’s error list (field, type, input, etc.). |

### Notes

- **`400` `detail`** for text validation can be a **list** of strings (several rules at once).
- **`500` `detail`** is **not fixed**: it mirrors libraries (Kokoro, `huggingface_hub`, etc.). Keep `config/voices.py` aligned with [VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) so allowed `(lang_code, voice)` pairs are caught as **400** before generation; typos or voices removed upstream can still surface as **500** if they slip past the catalog.
- Supported languages and voices are defined in **`config/voices.py`**; `main.py` builds one `KPipeline` per key and validates `voice` against that file.