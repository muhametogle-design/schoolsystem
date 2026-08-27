# Layer caching: dependencies install in a cached layer because requirements.txt
# is copied and installed before the application source.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
COPY sql ./sql
COPY scripts ./scripts
COPY .env.example .env.example

# Local SQLite store used in demo mode.
RUN mkdir -p /app/data

EXPOSE 5000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
