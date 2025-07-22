# Multi-stage production Dockerfile
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Production stage
FROM base as production

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# Copy entrypoint
COPY docker/base/entrypoint.sh /app/docker/base/
RUN chmod +x /app/docker/base/entrypoint.sh

# Copy project
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput || echo "Static files collection failed, continuing..."

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker/base/entrypoint.sh"]