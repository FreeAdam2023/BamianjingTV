"""
Lip Sync Worker - Wav2Lip integration for lip synchronization.

This module provides lip syncing capabilities using Wav2Lip to match
dubbed audio with video lip movements.

Requirements:
    pip install opencv-python mediapipe

Optional (for Wav2Lip):
    - Clone Wav2Lip repo
    - Download pretrained models (wav2lip.pth, wav2lip_gan.pth)
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LipSyncStatus(str, Enum):
    """Lip sync processing status."""
    PENDING = "pending"
    DETECTING_FACES = "detecting_faces"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # No faces detected


@dataclass
class FaceRegion:
    """Detected face bounding box."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    frame_index: int


@dataclass
class FaceTrack:
    """Tracked face across frames."""
    track_id: str
    speaker_id: Optional[str]
    regions: List[FaceRegion]
    start_frame: int
    end_frame: int


class LipSyncWorker:
    """
    Worker for lip synchronization using Wav2Lip.

    Pipeline:
    1. Face detection - detect faces in video frames
    2. Face tracking - track faces across frames
    3. Speaker assignment - match faces to audio speakers
    4. Lip sync - apply Wav2Lip to sync lips with audio
    5. Frame replacement - composite synced faces back into video
    """

    def __init__(
        self,
        wav2lip_path: Optional[Path] = None,
        model_path: Optional[Path] = None,
        use_gan: bool = True,
        device: str = "cuda"
    ):
        """
        Initialize lip sync worker.

        Args:
            wav2lip_path: Path to Wav2Lip repository
            model_path: Path to pretrained model (wav2lip.pth or wav2lip_gan.pth)
            use_gan: Use GAN model for better quality (slower)
            device: Device to run on ("cuda" or "cpu")
        """
        self.wav2lip_path = wav2lip_path
        self.model_path = model_path
        self.use_gan = use_gan
        self.device = device

        # Check dependencies
        self._face_detector = None
        self._wav2lip_available = False
        self._check_dependencies()

    def _check_dependencies(self):
        """Check and initialize dependencies."""
        # Check for mediapipe face detection
        try:
            import mediapipe as mp
            self._mp = mp
            self._face_detector = mp.solutions.face_detection.FaceDetection(
                model_selection=1,  # Full range model
                min_detection_confidence=0.5
            )
            logger.info("MediaPipe face detection initialized")
        except ImportError:
            logger.warning("MediaPipe not installed - face detection unavailable")
            self._mp = None

        # Check for OpenCV
        try:
            import cv2
            self._cv2 = cv2
            logger.info("OpenCV available")
        except ImportError:
            logger.warning("OpenCV not installed - video processing unavailable")
            self._cv2 = None

        # Check for Wav2Lip
        if self.wav2lip_path and self.wav2lip_path.exists():
            inference_script = self.wav2lip_path / "inference.py"
            if inference_script.exists():
                self._wav2lip_available = True
                logger.info(f"Wav2Lip found at {self.wav2lip_path}")
            else:
                logger.warning(f"Wav2Lip inference.py not found at {self.wav2lip_path}")
        else:
            logger.warning("Wav2Lip path not configured or not found")

    @property
    def is_available(self) -> bool:
        """Check if lip sync is available."""
        return self._cv2 is not None and self._face_detector is not None

    @property
    def wav2lip_available(self) -> bool:
        """Check if Wav2Lip is available."""
        return self._wav2lip_available and self.model_path and self.model_path.exists()

    async def detect_faces_in_frame(
        self,
        frame_path: Path
    ) -> List[FaceRegion]:
        """
        Detect faces in a single frame.

        Args:
            frame_path: Path to frame image

        Returns:
            List of detected face regions
        """
        if not self._face_detector:
            raise RuntimeError("Face detector not available")

        cv2 = self._cv2

        # Read frame
        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise ValueError(f"Failed to read frame: {frame_path}")

        height, width = frame.shape[:2]

        # Convert to RGB for mediapipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        results = self._face_detector.process(rgb_frame)

        faces = []
        if results.detections:
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box

                # Convert relative to absolute coordinates
                x = int(bbox.xmin * width)
                y = int(bbox.ymin * height)
                w = int(bbox.width * width)
                h = int(bbox.height * height)

                # Ensure coordinates are within bounds
                x = max(0, x)
                y = max(0, y)
                w = min(w, width - x)
                h = min(h, height - y)

                faces.append(FaceRegion(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    confidence=detection.score[0],
                    frame_index=0
                ))

        return faces

    async def detect_faces_in_video(
        self,
        video_path: Path,
        sample_interval: float = 0.5,
        progress_callback: Optional[callable] = None
    ) -> List[FaceRegion]:
        """
        Detect faces throughout a video by sampling frames.

        Args:
            video_path: Path to video file
            sample_interval: Sample every N seconds
            progress_callback: Called with (current, total) for progress

        Returns:
            List of face regions with frame indices
        """
        if not self._cv2:
            raise RuntimeError("OpenCV not available")

        cv2 = self._cv2

        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(fps * sample_interval)

        all_faces = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Sample at interval
            if frame_idx % frame_interval == 0:
                height, width = frame.shape[:2]
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                results = self._face_detector.process(rgb_frame)

                if results.detections:
                    for detection in results.detections:
                        bbox = detection.location_data.relative_bounding_box

                        x = int(bbox.xmin * width)
                        y = int(bbox.ymin * height)
                        w = int(bbox.width * width)
                        h = int(bbox.height * height)

                        x = max(0, x)
                        y = max(0, y)
                        w = min(w, width - x)
                        h = min(h, height - y)

                        all_faces.append(FaceRegion(
                            x=x,
                            y=y,
                            width=w,
                            height=h,
                            confidence=detection.score[0],
                            frame_index=frame_idx
                        ))

                if progress_callback:
                    progress_callback(frame_idx, total_frames)

            frame_idx += 1

        cap.release()

        return all_faces

    async def track_faces(
        self,
        faces: List[FaceRegion],
        iou_threshold: float = 0.3
    ) -> List[FaceTrack]:
        """
        Group face detections into tracks using simple IoU matching.

        Args:
            faces: List of face regions from detection
            iou_threshold: Minimum IoU to consider same face

        Returns:
            List of face tracks
        """
        if not faces:
            return []

        # Sort by frame index
        sorted_faces = sorted(faces, key=lambda f: f.frame_index)

        tracks: List[FaceTrack] = []

        def compute_iou(r1: FaceRegion, r2: FaceRegion) -> float:
            """Compute Intersection over Union."""
            x1 = max(r1.x, r2.x)
            y1 = max(r1.y, r2.y)
            x2 = min(r1.x + r1.width, r2.x + r2.width)
            y2 = min(r1.y + r1.height, r2.y + r2.height)

            if x2 <= x1 or y2 <= y1:
                return 0.0

            intersection = (x2 - x1) * (y2 - y1)
            area1 = r1.width * r1.height
            area2 = r2.width * r2.height
            union = area1 + area2 - intersection

            return intersection / union if union > 0 else 0.0

        for face in sorted_faces:
            # Try to match to existing track
            best_track = None
            best_iou = iou_threshold

            for track in tracks:
                if track.end_frame < face.frame_index:
                    # Track may continue
                    last_face = track.regions[-1]
                    iou = compute_iou(last_face, face)
                    if iou > best_iou:
                        best_iou = iou
                        best_track = track

            if best_track:
                # Add to existing track
                best_track.regions.append(face)
                best_track.end_frame = face.frame_index
            else:
                # Create new track
                tracks.append(FaceTrack(
                    track_id=f"track_{len(tracks)}",
                    speaker_id=None,
                    regions=[face],
                    start_frame=face.frame_index,
                    end_frame=face.frame_index
                ))

        return tracks

    async def lip_sync_segment(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        start_time: float = 0,
        end_time: Optional[float] = None,
        face_region: Optional[FaceRegion] = None
    ) -> Path:
        """
        Apply lip sync to a video segment using Wav2Lip.

        Args:
            video_path: Path to input video
            audio_path: Path to dubbed audio
            output_path: Path for output video
            start_time: Start time in seconds
            end_time: End time in seconds (None for full video)
            face_region: Optional face region to process (None for auto-detect)

        Returns:
            Path to lip-synced video
        """
        if not self.wav2lip_available:
            # Fallback: just replace audio without lip sync
            logger.warning("Wav2Lip not available, falling back to audio replacement only")
            return await self._replace_audio_only(video_path, audio_path, output_path)

        # Prepare temp files for segment
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Extract video segment if needed
            segment_video = temp_dir / "segment.mp4"
            segment_audio = temp_dir / "segment.wav"

            if start_time > 0 or end_time:
                await self._extract_segment(
                    video_path, segment_video,
                    start_time, end_time
                )
                await self._extract_audio_segment(
                    audio_path, segment_audio,
                    start_time, end_time
                )
            else:
                segment_video = video_path
                segment_audio = audio_path

            # Run Wav2Lip
            synced_output = temp_dir / "synced.mp4"
            await self._run_wav2lip(
                segment_video,
                segment_audio,
                synced_output,
                face_region
            )

            # Copy to output
            if synced_output.exists():
                import shutil
                shutil.copy(synced_output, output_path)
            else:
                # Fallback if Wav2Lip failed
                logger.warning("Wav2Lip failed, using audio replacement fallback")
                await self._replace_audio_only(segment_video, segment_audio, output_path)

        return output_path

    async def lip_sync_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        segments: Optional[List[Dict]] = None,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """
        Apply lip sync to full video.

        Args:
            video_path: Path to input video
            audio_path: Path to dubbed audio
            output_path: Path for output video
            segments: Optional list of segments with timing info
            progress_callback: Called with (current_step, total_steps, message)

        Returns:
            Path to lip-synced video
        """
        if not self.wav2lip_available:
            logger.warning("Wav2Lip not available, using audio replacement only")
            return await self._replace_audio_only(video_path, audio_path, output_path)

        if progress_callback:
            progress_callback(0, 3, "Detecting faces")

        # Detect faces in video
        faces = await self.detect_faces_in_video(video_path)

        if not faces:
            logger.info("No faces detected, skipping lip sync")
            return await self._replace_audio_only(video_path, audio_path, output_path)

        if progress_callback:
            progress_callback(1, 3, "Tracking faces")

        # Track faces
        tracks = await self.track_faces(faces)
        logger.info(f"Found {len(tracks)} face tracks")

        if progress_callback:
            progress_callback(2, 3, "Applying lip sync")

        # Apply Wav2Lip to full video
        await self._run_wav2lip(video_path, audio_path, output_path)

        if progress_callback:
            progress_callback(3, 3, "Complete")

        return output_path

    async def _run_wav2lip(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        face_region: Optional[FaceRegion] = None
    ):
        """Run Wav2Lip inference."""
        if not self.wav2lip_available:
            raise RuntimeError("Wav2Lip not available")

        # Build command
        model_name = "wav2lip_gan.pth" if self.use_gan else "wav2lip.pth"
        checkpoint_path = self.model_path / model_name if self.model_path.is_dir() else self.model_path

        cmd = [
            "python",
            str(self.wav2lip_path / "inference.py"),
            "--checkpoint_path", str(checkpoint_path),
            "--face", str(video_path),
            "--audio", str(audio_path),
            "--outfile", str(output_path),
        ]

        # Add face region if specified
        if face_region:
            # Wav2Lip can use a face bounding box
            cmd.extend([
                "--box", str(face_region.x), str(face_region.y),
                str(face_region.x + face_region.width),
                str(face_region.y + face_region.height)
            ])

        # Add device
        if self.device == "cpu":
            cmd.append("--cpu")

        logger.info(f"Running Wav2Lip: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.wav2lip_path)
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Wav2Lip failed: {error_msg}")
            raise RuntimeError(f"Wav2Lip inference failed: {error_msg}")

        logger.info("Wav2Lip completed successfully")

    async def _replace_audio_only(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path
    ) -> Path:
        """Replace video audio without lip sync (fallback)."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()

        return output_path

    async def _extract_segment(
        self,
        video_path: Path,
        output_path: Path,
        start_time: float,
        end_time: Optional[float]
    ):
        """Extract video segment."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", str(video_path),
        ]

        if end_time:
            cmd.extend(["-t", str(end_time - start_time)])

        cmd.extend([
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path)
        ])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()

    async def _extract_audio_segment(
        self,
        audio_path: Path,
        output_path: Path,
        start_time: float,
        end_time: Optional[float]
    ):
        """Extract audio segment."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", str(audio_path),
        ]

        if end_time:
            cmd.extend(["-t", str(end_time - start_time)])

        cmd.extend([
            "-c:a", "pcm_s16le",
            str(output_path)
        ])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()

    def get_status(self) -> Dict[str, Any]:
        """Get worker status."""
        return {
            "available": self.is_available,
            "wav2lip_available": self.wav2lip_available,
            "face_detection": self._face_detector is not None,
            "opencv": self._cv2 is not None,
            "device": self.device,
            "use_gan": self.use_gan
        }
