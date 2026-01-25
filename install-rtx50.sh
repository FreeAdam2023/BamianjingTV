#!/bin/bash
# Hardcore Player RTX 50 Series Installation Script
# Python 3.12 + CUDA 12.8 + PyTorch Nightly
#
# Usage:
#   git clone <repo>
#   cd BamianjingTV
#   ./install-rtx50.sh

set -e

echo "=== Hardcore Player RTX 50 Installation ==="
echo ""

# Accept Coqui TOS automatically
export COQUI_TOS_AGREED=1

# 0. Clean slate
echo "[0/10] Cleaning all conflicting packages..."
pip uninstall -y pyannote-audio pyannote-core pyannote-pipeline pyannote-database pyannote-metrics \
    torch torchvision torchaudio numpy 2>/dev/null || true

# 1. PyTorch Nightly
echo "[1/10] Installing PyTorch Nightly (CUDA 12.8)..."
pip install --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cu128

# 2. Lock numpy to 1.x
echo "[2/10] Installing numpy 1.x..."
pip install "numpy>=1.26.0,<2.0"

# 3. Verify
echo "[3/10] Verifying PyTorch + numpy..."
python -c "import torch; print(f'PyTorch {torch.__version__} CUDA {torch.version.cuda}')"
python -c "import numpy; print(f'NumPy {numpy.__version__}')"

# 4. Install pyannote dependencies with locked versions
echo "[4/10] Installing pyannote dependencies (locked versions)..."
pip install "pyannote.core==5.0.0"
pip install "pyannote.database>=5.0.1,<6.0"
pip install "pyannote.metrics>=3.2,<4.0"
pip install "pyannote.pipeline>=3.0.1,<4.0"
pip install pytorch-lightning speechbrain asteroid-filterbanks \
    torch-audiomentations pytorch-metric-learning einops optuna \
    tensorboardX rich semver omegaconf hyperpyyaml

# 5. Install pyannote.audio from GitHub with --no-deps
echo "[5/10] Installing pyannote.audio from GitHub (no deps)..."
pip install git+https://github.com/pyannote/pyannote-audio.git --no-deps

# 6. Verify numpy still 1.x
echo "[6/10] Verifying numpy is still 1.x..."
python -c "import numpy; v=numpy.__version__; assert v.startswith('1.'), f'FAIL: numpy {v}'; print(f'NumPy {v} ✓')"

# 7. FastAPI + TTS + ML
echo "[7/10] Installing FastAPI, TTS, ML packages..."
pip install fastapi uvicorn[standard] python-multipart \
    pydantic pydantic-settings python-dotenv aiofiles loguru
pip install transformers==4.39.3 tokenizers==0.15.2 accelerate diffusers Pillow
pip install coqui-tts

# 8. Patch coqpit for Python 3.12 compatibility
echo "[8/10] Patching coqpit for Python 3.12..."
COQPIT_PATH=$(python -c "import coqpit; import os; print(os.path.join(os.path.dirname(coqpit.__file__), 'coqpit.py'))")
python << PATCH_EOF
coqpit_file = "$COQPIT_PATH"
with open(coqpit_file, 'r') as f:
    content = f.read()

# Add types import
if 'import types' not in content:
    content = content.replace('import typing', 'import typing\nimport types')

# Fix issubclass check for generic types
content = content.replace(
    'if issubclass(field_type, Serializable):',
    'if isinstance(field_type, type) and issubclass(field_type, Serializable):'
)

# Fix union type handling (float | list[float])
content = content.replace(
    'if field_type is Any:',
    'if hasattr(types, "UnionType") and isinstance(field_type, types.UnionType): return x\n    if field_type is Any:'
)

with open(coqpit_file, 'w') as f:
    f.write(content)

print("coqpit patched for Python 3.12 ✓")
PATCH_EOF

# 9. ASR + Media
echo "[9/10] Installing ASR and media packages..."
pip install openai-whisper faster-whisper
pip install ffmpeg-python pydub soundfile yt-dlp

# 10. APIs and testing
echo "[10/10] Installing APIs and utilities..."
pip install openai httpx google-api-python-client google-auth-oauthlib \
    pytest pytest-asyncio opencc-python-reimplemented

echo ""
echo "=== Final Verification ==="
python -c "import torch; print(f'✓ PyTorch {torch.__version__}')"
python -c "import numpy; print(f'✓ NumPy {numpy.__version__}')"
python -c "from pyannote.audio import Pipeline; print('✓ pyannote.audio')"
python -c "from TTS.api import TTS; print('✓ coqui-tts')"
python -c "from fastapi import FastAPI; print('✓ FastAPI')"
echo ""
echo "=== SUCCESS ==="
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in API keys"
echo "  2. Run: make dev"
echo "  3. Visit: http://localhost:8000/docs"
