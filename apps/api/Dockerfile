FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/api/pyproject.toml ./
COPY apps/api/app ./app

# The compose stack runs PostgreSQL; a SQLite DATABASE_URL still works, the
# driver is simply unused.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[postgres]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

