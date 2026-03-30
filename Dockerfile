# Kokoro / misaki: Python 3.12, espeak-ng (G2P fallback), libsndfile (soundfile)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Install CPU-only PyTorch first. Default PyPI torch on Linux pulls CUDA stacks (~GB of nvidia-* wheels) and makes the build very slow.
RUN pip install --upgrade pip && \
    pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p audio && \
    addgroup --system app && \
    adduser --system --ingroup app appuser && \
    chown -R appuser:app /app

EXPOSE 8000

# Models download to HF cache on first request (needs network unless cache is baked in).
USER appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
