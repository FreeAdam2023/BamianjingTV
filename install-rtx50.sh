#!/bin/bash
# MirrorFlow RTX 50 Series Installation Script
# For Python 3.12 + CUDA 12.8 + PyTorch Nightly

set -e

echo "=== MirrorFlow RTX 50 Installation ==="

# 1. Core numerical
echo "[1/7] Installing core numerical packages..."
pip install numpy==1.26.4 scipy==1.12.0 numba==0.59.1

# 2. PyTorch (should already be installed)
echo "[2/7] Verifying PyTorch..."
python -c "import torch; print(f'PyTorch {torch.__version__} CUDA {torch.version.cuda}')"

# 3. FastAPI stack
echo "[3/7] Installing FastAPI stack..."
pip install fastapi==0.115.0 "uvicorn[standard]==0.30.0" python-multipart==0.0.9 \
    pydantic>=2.5.0 pydantic-settings>=2.1.0 python-dotenv>=1.0.0 aiofiles>=23.2.0 loguru>=0.7.2

# 4. ML/AI packages
echo "[4/7] Installing ML packages..."
pip install transformers==4.39.3 tokenizers==0.15.2 accelerate>=0.26.0 diffusers>=0.25.0

# 5. Audio/Video
echo "[5/7] Installing audio/video packages..."
pip install ffmpeg-python>=0.2.0 pydub>=0.25.1 soundfile>=0.12.1 Pillow>=10.2.0

# 6. ASR + TTS + Diarization
echo "[6/7] Installing ASR, TTS, Diarization..."
pip install openai-whisper>=20231117 faster-whisper>=0.10.0
pip install coqui-tts>=0.22.0
pip install git+https://github.com/pyannote/pyannote-audio.git

# 7. APIs and utilities
echo "[7/7] Installing APIs and utilities..."
pip install yt-dlp>=2024.1.0 openai>=1.10.0 httpx>=0.26.0 \
    google-api-python-client>=2.115.0 google-auth-oauthlib>=1.2.0 \
    pytest>=7.4.0 pytest-asyncio>=0.23.0

echo ""
echo "=== Installation Complete ==="
echo "Verifying..."
python -c "import torch; print(f'✓ PyTorch {torch.__version__}')"
python -c "from TTS.api import TTS; print('✓ XTTS')"
python -c "from pyannote.audio import Pipeline; print('✓ pyannote')"
python -c "from fastapi import FastAPI; print('✓ FastAPI')"
echo "Done!"
