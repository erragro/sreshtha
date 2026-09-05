FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-hin tesseract-ocr-ben tesseract-ocr-tam \
    tesseract-ocr-tel tesseract-ocr-kan tesseract-ocr-mar \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

# Install torch (~200MB CPU wheel) in its own layer. Doing this before the
# main pip resolve keeps the peak-memory spike per RUN below Docker Desktop's
# 8GB default; a single monolithic pip install of easyocr + scikit-image +
# scipy + torch has OOM'd historically (SIGKILL / exit 137).
RUN pip install --upgrade pip \
 && pip install --no-compile torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml ./
RUN pip install --no-compile .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
