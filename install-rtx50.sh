#!/bin/bash
# MirrorFlow RTX 50 Series Installation Script
# Python 3.12 + CUDA 12.8 + PyTorch Nightly
#
# Key version locks:
# - pyannote.core==5.0.0 (numpy>=1.10.4, NOT 6.x which needs numpy>=2.0)
# - pyannote.audio==3.1.1 with --no-deps to prevent core upgrade

set -e

echo "=== MirrorFlow RTX 50 Installation ==="
echo ""

# 0. Clean slate
echo "[0/9] Cleaning all conflicting packages..."
pip uninstall -y pyannote-audio pyannote-core pyannote-pipeline pyannote-database pyannote-metrics \
    torch torchvision torchaudio numpy 2>/dev/null || true

# 1. PyTorch Nightly
echo "[1/9] Installing PyTorch Nightly (CUDA 12.8)..."
pip install --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cu128

# 2. Lock numpy to 1.x FIRST
echo "[2/9] Installing numpy 1.x..."
pip install "numpy>=1.26.0,<2.0"

# 3. Verify
echo "[3/9] Verifying PyTorch + numpy..."
python -c "import torch; print(f'PyTorch {torch.__version__} CUDA {torch.version.cuda}')"
python -c "import numpy; print(f'NumPy {numpy.__version__}')"

# 4. Install pyannote.core 5.x FIRST (locked)
echo "[4/9] Installing pyannote.core 5.0.0 (locked)..."
pip install "pyannote.core==5.0.0"
pip install "pyannote.database>=5.0.1,<6.0"
pip install "pyannote.metrics>=3.2,<4.0"
pip install "pyannote.pipeline>=3.0.1,<4.0"

# 5. Install pyannote.audio with --no-deps (prevent core upgrade)
echo "[5/9] Installing pyannote.audio 3.1.1 (no deps)..."
pip install "pyannote.audio==3.1.1" --no-deps
# Install remaining pyannote.audio deps manually
pip install pytorch-lightning speechbrain asteroid-filterbanks \
    torch-audiomentations pytorch-metric-learning einops optuna \
    tensorboardX rich semver omegaconf hyperpyyaml

# 6. Verify numpy still 1.x
echo "[6/9] Verifying numpy is still 1.x..."
python -c "import numpy; v=numpy.__version__; assert v.startswith('1.'), f'FAIL: numpy {v}'; print(f'NumPy {v} ✓')"

# 7. FastAPI + TTS + ML
echo "[7/9] Installing FastAPI, TTS, ML packages..."
pip install fastapi uvicorn[standard] python-multipart \
    pydantic pydantic-settings python-dotenv aiofiles loguru
pip install transformers==4.39.3 tokenizers==0.15.2 accelerate diffusers Pillow
pip install coqui-tts

# 8. ASR + Media
echo "[8/9] Installing ASR and media packages..."
pip install openai-whisper faster-whisper
pip install ffmpeg-python pydub soundfile yt-dlp

# 9. APIs and testing
echo "[9/9] Installing APIs and utilities..."
pip install openai httpx google-api-python-client google-auth-oauthlib \
    pytest pytest-asyncio

echo ""
echo "=== Final Verification ==="
python -c "import torch; print(f'✓ PyTorch {torch.__version__}')"
python -c "import numpy; print(f'✓ NumPy {numpy.__version__}')"
python -c "from pyannote.audio import Pipeline; print('✓ pyannote.audio')"
python -c "from TTS.api import TTS; print('✓ coqui-tts')"
python -c "from fastapi import FastAPI; print('✓ FastAPI')"
echo ""
echo "=== SUCCESS ==="
