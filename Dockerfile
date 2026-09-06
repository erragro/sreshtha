FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tesseract OCR engine + Indic language data (used by app/contracts/ocr.py
# for photos/scans). libpq5 for psycopg. No torch/CUDA: the OCR engine is
# the C++ tesseract binary, so the image stays small and behaves the same
# on x86 and ARM.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-hin tesseract-ocr-ben tesseract-ocr-tam \
    tesseract-ocr-tel tesseract-ocr-kan tesseract-ocr-mar \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY pyproject.toml ./
RUN pip install --no-compile .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
