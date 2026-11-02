FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY bankbridge ./bankbridge
RUN pip install --no-cache-dir ".[events]" && useradd -u 10001 -m bb
USER bb
EXPOSE 8000
CMD ["uvicorn", "bankbridge.api:app", "--host", "0.0.0.0", "--port", "8000"]
