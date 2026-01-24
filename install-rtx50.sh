#!/bin/bash
# MirrorFlow RTX 50 Series Installation Script
# Python 3.12 + CUDA 12.8 + PyTorch Nightly
#
# Compatible versions found:
# - pyannote-audio 3.1.1: requires torch>=2.0.0 (flexible), pyannote-core>=5.0.0
# - pyannote-core 5.0.0: requires numpy>=1.10.4 (compatible with coqui-tts)
# - coqui-tts: requires numpy<2.0

set -e

echo "=== MirrorFlow RTX 50 Installation ==="
echo "Compatible stack: pyannote 3.1.1 + numpy 1.x + PyTorch nightly"
echo ""

# 0. Clean slate
echo "[0/8] Cleaning conflicting packages..."
pip uninstall -y pyannote-audio pyannote-core pyannote-pipeline pyannote-database pyannote-metrics torch torchvision torchaudio 2>/dev/null || true

# 1. PyTorch Nightly (CUDA 12.8)
echo "[1/8] Installing PyTorch Nightly..."
pip install --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cu128

# 2. Verify PyTorch
echo "[2/8] Verifying PyTorch..."
python -c "import torch; print(f'PyTorch {torch.__version__} CUDA {torch.version.cuda}')"

# 3. Pin pyannote-core to 5.x (numpy 1.x compatible)
echo "[3/8] Installing pyannote stack (3.1.1 + core 5.x)..."
pip install "pyannote.core>=5.0.0,<6.0"
pip install "pyannote.audio==3.1.1"

# 4. Verify numpy is still 1.x
echo "[4/8] Checking numpy version..."
python -c "import numpy; v=numpy.__version__; assert v.startswith('1.'), f'numpy {v} not 1.x!'; print(f'NumPy {v} ✓')"

# 5. FastAPI stack
echo "[5/8] Installing FastAPI stack..."
pip install fastapi uvicorn[standard] python-multipart \
    pydantic pydantic-settings python-dotenv aiofiles loguru

# 6. coqui-tts + ML packages
echo "[6/8] Installing TTS and ML packages..."
pip install transformers==4.39.3 tokenizers==0.15.2 accelerate diffusers Pillow
pip install coqui-tts

# 7. ASR + Audio/Video
echo "[7/8] Installing ASR and media packages..."
pip install openai-whisper faster-whisper
pip install ffmpeg-python pydub soundfile yt-dlp

# 8. APIs and testing
echo "[8/8] Installing APIs and utilities..."
pip install openai httpx google-api-python-client google-auth-oauthlib \
    pytest pytest-asyncio

echo ""
echo "=== Verifying Installation ==="
python -c "import torch; print(f'✓ PyTorch {torch.__version__} (CUDA {torch.version.cuda})')"
python -c "import numpy; print(f'✓ NumPy {numpy.__version__}')"
python -c "from pyannote.audio import Pipeline; print('✓ pyannote.audio 3.1.1')"
python -c "from TTS.api import TTS; print('✓ coqui-tts (XTTS)')"
python -c "from fastapi import FastAPI; print('✓ FastAPI')"
echo ""
echo "=== All components verified! ==="
