# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MirrorFlow** - Automated video language conversion pipeline that transforms English video content (interviews, talks, podcasts) into Chinese dubbed videos. The system runs on local GPU (RTX 5080) and produces upload-ready content for YouTube.

## Architecture

```
┌─────────┐
│  n8n    │  ← Workflow orchestration / state control
└────┬────┘
     ↓
┌────────────────────────┐
│ Python Worker API       │
│ (FastAPI)               │
├────────────────────────┤
│ • Whisper Worker (GPU)  │  ← ASR with Whisper large-v3
│ • Diarization Worker    │  ← Speaker separation with pyannote.audio
│ • Translation Worker    │  ← API-based translation (口语化中文)
│ • XTTS Worker (GPU)     │  ← Multi-voice Chinese TTS with XTTS v2
│ • Video Mux Worker      │  ← ffmpeg with NVENC
│ • Thumbnail Worker      │  ← SDXL/Flux image generation
└────────────────────────┘
     ↓
 YouTube Upload / Local Output
```

**Design Principles:**
- n8n handles orchestration only, no heavy computation
- GPU resources concentrated in Python workers
- Each module independently replaceable/upgradable

## Job Data Structure

```
job/
 ├── source/
 │   ├── video.mp4
 │   └── audio.wav
 ├── transcript/
 │   ├── raw.json          # Whisper output with timestamps
 │   └── diarized.json     # With speaker labels
 ├── translation/
 │   └── zh.json
 ├── tts/
 │   ├── speaker_1.wav
 │   └── speaker_2.wav
 ├── output/
 │   └── final_video.mp4
 └── meta.json
```

## Tech Stack

- **Python 3.10+** with FastAPI
- **yt-dlp** for video download
- **Whisper large-v3** for speech recognition (CUDA)
- **pyannote.audio** for speaker diarization
- **XTTS v2** for Chinese TTS with speaker-specific voices
- **ffmpeg** with NVENC for GPU-accelerated video encoding
- **n8n** for workflow orchestration
- **YouTube Data API v3** for automated upload

## Expected Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the FastAPI worker server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Download a video (standalone)
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" <URL>

# Process video with ffmpeg (NVENC)
ffmpeg -i input.mp4 -c:v h264_nvenc -c:a aac output.mp4
```

## Environment Requirements

- OS: Ubuntu 22.04
- GPU: RTX 5080 with CUDA/cuDNN
- RAM: 32GB+
- Storage: NVMe SSD

## Content Guidelines

- Only process interview/talk/podcast content (no movies, music, or live streams)
- Use "similar style" voices, not precise voice cloning
- Generate distinct thumbnails and titles (not copies of original)
- Prioritize voice stability over similarity to original speaker
