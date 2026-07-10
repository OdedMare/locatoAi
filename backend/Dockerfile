# Exact target runtime: Python 3.8.10 (see runtime.txt / .python-version).
# Build with: docker build --platform linux/amd64 ...
# (the geo stack ships no linux-arm64 wheels for Python 3.8; on Apple
# Silicon the amd64 image runs via Rosetta emulation)
FROM python:3.8.10-slim

WORKDIR /srv/backend

RUN pip install --no-cache-dir --upgrade "pip<25"

COPY pyproject.toml ./
COPY app ./app
COPY data ./data
COPY tests ./tests
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[dev]"

# The layer catalog lives in Postgres on the host machine.
ENV AILOCATOR_DATABASE_URL=postgresql://host.docker.internal:5432/gis

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
