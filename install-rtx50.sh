#!/bin/bash
# MirrorFlow RTX 50 Series Installation Script
# Python 3.12 + CUDA 12.8 + PyTorch Nightly
#
# Solution:
# - pyannote.audio from GitHub (fixes torchaudio.set_audio_backend removal)
# - pyannote.core==5.0.0 (numpy 1.x compatible)
# - Install with --no-deps to prevent dependency upgrades

set -e

echo "=== MirrorFlow RTX 50 Installation ==="
echo ""

# Accept Coqui TOS automatically
export COQUI_TOS_AGREED=1

# 0. Clean slate
echo "[0/9] Cleaning all conflicting packages..."
pip uninstall -y pyannote-audio pyannote-core pyannote-pipeline pyannote-database pyannote-metrics \
    torch torchvision torchaudio numpy 2>/dev/null || true

# 1. PyTorch Nightly
echo "[1/9] Installing PyTorch Nightly (CUDA 12.8)..."
pip install --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cu128

# 2. Lock numpy to 1.x
echo "[2/9] Installing numpy 1.x..."
pip install "numpy>=1.26.0,<2.0"

# 3. Verify
echo "[3/9] Verifying PyTorch + numpy..."
python -c "import torch; print(f'PyTorch {torch.__version__} CUDA {torch.version.cuda}')"
python -c "import numpy; print(f'NumPy {numpy.__version__}')"

# 4. Install pyannote dependencies with locked versions
echo "[4/9] Installing pyannote dependencies (locked versions)..."
pip install "pyannote.core==5.0.0"
pip install "pyannote.database>=5.0.1,<6.0"
pip install "pyannote.metrics>=3.2,<4.0"
pip install "pyannote.pipeline>=3.0.1,<4.0"
pip install pytorch-lightning speechbrain asteroid-filterbanks \
    torch-audiomentations pytorch-metric-learning einops optuna \
    tensorboardX rich semver omegaconf hyperpyyaml

# 5. Install pyannote.audio from GitHub with --no-deps
echo "[5/9] Installing pyannote.audio from GitHub (no deps)..."
pip install git+https://github.com/pyannote/pyannote-audio.git --no-deps

# 6. Verify numpy still 1.x
echo "[6/9] Verifying numpy is still 1.x..."
python -c "import numpy; v=numpy.__version__; assert v.startswith('1.'), f'FAIL: numpy {v}'; print(f'NumPy {v} ✓')"

# 7. FastAPI + TTS + ML
echo "[7/9] Installing FastAPI, TTS, ML packages..."
pip install fastapi uvicorn[standard] python-multipart \
    pydantic pydantic-settings python-dotenv aiofiles loguru
pip install transformers==4.39.3 tokenizers==0.15.2 accelerate diffusers Pillow
pip install coqui-tts

# Patch coqpit for Python 3.12 compatibility (union types like float | list[float])
echo "Patching coqpit for Python 3.12..."
python -c "f='$(python -c \"import coqpit;print(coqpit.__file__.replace('__init__.py','coqpit.py'))\")';c=open(f).read();c=c.replace('import typing','import typing\nimport types');c=c.replace('if issubclass(field_type, Serializable):','if isinstance(field_type, type) and issubclass(field_type, Serializable):');c=c.replace('if field_type is Any:','if hasattr(__import__(\"types\"),\"UnionType\") and isinstance(field_type,__import__(\"types\").UnionType): return x\n    if field_type is Any:');open(f,'w').write(c);print('coqpit patched')"

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
