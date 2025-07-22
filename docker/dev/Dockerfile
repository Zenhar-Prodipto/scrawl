# Development Dockerfile - optimized for dev environment
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies + dev tools
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    curl \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy dev entrypoint script and make it executable
COPY docker/dev/entrypoint.sh /app/docker/dev/
RUN chmod +x /app/docker/dev/entrypoint.sh

# Copy project (no volumes in dev, code baked in)
COPY . /app/

# Expose port
EXPOSE 8000

# Set entrypoint to dev-specific script
ENTRYPOINT ["/app/docker/dev/entrypoint.sh"]