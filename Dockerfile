# Stage 1: Build stage to install dependencies
FROM python:3.9-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency file first to leverage Docker cache
COPY pyproject.toml .

# Install python dependencies
# Using a similar method as in the agent's manual installation process
# This is a simplified way to install from pyproject.toml without poetry
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir "fastapi" "uvicorn[standard]" "ollama" "playwright" "tomli" "websockets" "pytest" "anyio"

# Install Playwright browsers
RUN playwright install --with-deps

# Stage 2: Final application stage
FROM python:3.9-slim

WORKDIR /app

# Copy installed dependencies and browsers from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages/ /usr/local/lib/python3.9/site-packages/
COPY --from=builder /root/.cache/ms-playwright/ /root/.cache/ms-playwright/

# Copy the application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY config.toml .
COPY tests/ ./tests/

# Expose the port the app runs on
EXPOSE 8000

# The command to run the application
CMD ["python", "backend/main.py"]
