#!/bin/bash
# MirrorFlow RTX 50 Series Installation Script
# For Python 3.12 + CUDA 12.8 + PyTorch Nightly
#
# Key insight: pyannote requires numpy>=2.0, gruut requires numpy<2.0
# Solution: Use numpy>=2.0 and install coqui-tts without gruut

set -e

echo "=== MirrorFlow RTX 50 Installation ==="

# 1. Core numerical (numpy 2.x for pyannote)
echo "[1/8] Installing core numerical packages..."
pip install "numpy>=2.0,<2.4" scipy numba>=0.59.0

# 2. PyTorch (should already be installed)
echo "[2/8] Verifying PyTorch..."
python -c "import torch; print(f'PyTorch {torch.__version__} CUDA {torch.version.cuda}')"

# 3. pyannote from GitHub (first, to establish numpy>=2.0)
echo "[3/8] Installing pyannote.audio from GitHub..."
pip install git+https://github.com/pyannote/pyannote-audio.git

# 4. FastAPI stack
echo "[4/8] Installing FastAPI stack..."
pip install fastapi uvicorn[standard] python-multipart \
    pydantic pydantic-settings python-dotenv aiofiles loguru

# 5. ML/AI packages (pinned for XTTS)
echo "[5/8] Installing ML packages..."
pip install transformers==4.39.3 tokenizers==0.15.2 accelerate diffusers

# 6. Audio/Video
echo "[6/8] Installing audio/video packages..."
pip install ffmpeg-python pydub soundfile Pillow yt-dlp

# 7. TTS - install without deps first, then fill in
echo "[7/8] Installing coqui-tts..."
pip install coqui-tts --no-deps
# Install coqui-tts dependencies except gruut (which conflicts with numpy>=2.0)
pip install coqpit trainer encodec inflect pypinyin jieba unidecode num2words \
    bangla bnnumerizer bnunicodenormalizer gruut-ipa g2pkk jamo nltk umap-learn

# 8. APIs and testing
echo "[8/8] Installing APIs and testing..."
pip install openai httpx google-api-python-client google-auth-oauthlib \
    pytest pytest-asyncio openai-whisper faster-whisper

echo ""
echo "=== Installation Complete ==="
echo "Verifying..."
python -c "import torch; print(f'✓ PyTorch {torch.__version__}')"
python -c "import numpy; print(f'✓ NumPy {numpy.__version__}')"
python -c "from pyannote.audio import Pipeline; print('✓ pyannote.audio')"
python -c "from TTS.api import TTS; print('✓ coqui-tts')"
python -c "from fastapi import FastAPI; print('✓ FastAPI')"
echo ""
echo "Note: gruut (text normalization) skipped due to numpy conflict."
echo "XTTS Chinese TTS should work without gruut."
echo "Done!"
