# syntax=docker/dockerfile:1
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
    build-essential \
    pkg-config \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    git \
    curl \
    unzip \
    fonts-noto-cjk \
    fonts-noto-core \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

# Install Node.js 20 LTS (required by Remotion for WYSIWYG export)
# Use direct apt repo setup instead of setup_20.x script which can fail
# when unrelated repos (e.g. CUDA) have transient mirror sync issues.
# Also install Chromium dependencies needed by Remotion's headless Chrome.
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && node --version && npm --version \
    && npm install -g pnpm@9 \
    && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install deno (required by yt-dlp for YouTube extraction)
RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -s /root/.deno/bin/deno /usr/local/bin/deno

# Install pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Create app user
RUN useradd -m -u 1000 app
WORKDIR /app

# Install Python dependencies (BuildKit cache keeps pip downloads across rebuilds)
COPY requirements.txt .
COPY requirements-tts.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r requirements.txt

# Optional: Install TTS dependencies (comment out if not needed)
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r requirements-tts.txt || echo "TTS installation skipped"

# Install Music generation dependencies (audiocraft/MusicGen)
COPY requirements-music.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r requirements-music.txt

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
