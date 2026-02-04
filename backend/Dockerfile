# SceneMind - Backend API
# Learning video factory with bilingual subtitles

FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    ffmpeg \
    git \
    curl \
    unzip \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

# Install deno (required by yt-dlp for YouTube extraction)
RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -s /root/.deno/bin/deno /usr/local/bin/deno

# Install pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Create app user
RUN useradd -m -u 1000 app
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
COPY requirements-tts.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Optional: Install TTS dependencies (comment out if not needed)
RUN python3 -m pip install --no-cache-dir -r requirements-tts.txt || echo "TTS installation skipped"

# Copy application code
COPY app/ ./app/
COPY pyproject.toml .

# Create directories
RUN mkdir -p jobs data data/timelines data/items .cache/models credentials \
    && chown -R app:app /app

# Switch to non-root user
USER app

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV JOBS_DIR=/app/jobs
ENV DATA_DIR=/app/data
ENV MODELS_CACHE_DIR=/app/.cache/models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
