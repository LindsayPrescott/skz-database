FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy dependency files first (better layer caching — only re-installs if these change)
COPY pyproject.toml poetry.lock* ./

# Install dependencies without creating a virtualenv inside the container
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy the rest of the application code
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
