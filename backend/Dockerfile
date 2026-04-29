# Build stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js (needed for npx-based MCP servers)
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-client \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and src so the editable install can find the package root
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies (including the package itself in editable mode)
RUN pip install --no-cache-dir -e ".[snowflake]"

# Copy remaining files (mcp_servers, alembic, etc.)
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

