FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY alembic ./alembic
COPY alembic.ini .
COPY app ./app

# Create secrets directory (populated by Docker volume mount)
RUN mkdir -p .secrets

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
