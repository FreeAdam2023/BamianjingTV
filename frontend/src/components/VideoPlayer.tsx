"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { EditableSegment } from "@/lib/types";
import { formatDuration } from "@/lib/api";

interface VideoPlayerProps {
  jobId: string;
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: number) => void;
}

export default function VideoPlayer({
  jobId,
  segments,
  currentSegmentId,
  onTimeUpdate,
  onSegmentChange,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const watermarkInputRef = useRef<HTMLInputElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLooping, setIsLooping] = useState(false);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Subtitle area height ratio (0.3 to 0.7, default 0.5 = 50%)
  const [subtitleHeightRatio, setSubtitleHeightRatio] = useState(0.5);
  const [isDragging, setIsDragging] = useState(false);

  // Watermark
  const [watermarkUrl, setWatermarkUrl] = useState<string | null>(null);

  // Load watermark from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("videoWatermark");
    if (saved) {
      setWatermarkUrl(saved);
    }
  }, []);

  // Handle watermark upload
  const handleWatermarkUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      setWatermarkUrl(dataUrl);
      localStorage.setItem("videoWatermark", dataUrl);
    };
    reader.readAsDataURL(file);
  }, []);

  // Remove watermark
  const handleRemoveWatermark = useCallback(() => {
    setWatermarkUrl(null);
    localStorage.removeItem("videoWatermark");
    if (watermarkInputRef.current) {
      watermarkInputRef.current.value = "";
    }
  }, []);

  // Find current segment based on time
  const findSegmentAtTime = useCallback(
    (time: number): EditableSegment | null => {
      return (
        segments.find(
          (seg) => time >= seg.start && time < seg.end
        ) || null
      );
    },
    [segments]
  );

  // Handle time update from video
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const time = video.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);

      // Update current segment
      const segment = findSegmentAtTime(time);
      if (segment && segment.id !== currentSegmentId) {
        onSegmentChange?.(segment.id);
      }

      // Handle looping
      if (isLooping && currentSegmentId !== null) {
        const currentSeg = segments.find((s) => s.id === currentSegmentId);
        if (currentSeg && time >= currentSeg.end) {
          video.currentTime = currentSeg.start;
        }
      }
    };

    const handleDurationChange = () => {
      setDuration(video.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("durationchange", handleDurationChange);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);

    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("durationchange", handleDurationChange);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
    };
  }, [
    currentSegmentId,
    isLooping,
    segments,
    findSegmentAtTime,
    onTimeUpdate,
    onSegmentChange,
  ]);

  // Handle drag to resize subtitle area
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalHeight = rect.height;
      const mouseY = e.clientY - rect.top;
      // Calculate ratio: video height / total height
      // Subtract controls bar height (~60px)
      const controlsHeight = 60;
      const availableHeight = totalHeight - controlsHeight;
      const videoHeight = mouseY;
      const newSubtitleRatio = 1 - (videoHeight / availableHeight);
      // Clamp between 0.2 and 0.7
      setSubtitleHeightRatio(Math.max(0.2, Math.min(0.7, newSubtitleRatio)));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  // Public methods via ref
  const play = useCallback(() => videoRef.current?.play(), []);
  const pause = useCallback(() => videoRef.current?.pause(), []);
  const toggle = useCallback(() => {
    if (isPlaying) pause();
    else play();
  }, [isPlaying, play, pause]);

  const seekTo = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
  }, []);

  const seekToSegment = useCallback(
    (segmentId: number) => {
      const segment = segments.find((s) => s.id === segmentId);
      if (segment) {
        seekTo(segment.start);
        onSegmentChange?.(segmentId);
      }
    },
    [segments, seekTo, onSegmentChange]
  );

  const playSegment = useCallback(
    (segmentId: number) => {
      seekToSegment(segmentId);
      play();
    },
    [seekToSegment, play]
  );

  const toggleLoop = useCallback(() => {
    setIsLooping((prev) => !prev);
  }, []);

  // Volume controls
  const handleVolumeChange = useCallback((newVolume: number) => {
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
      if (newVolume > 0 && isMuted) {
        setIsMuted(false);
        videoRef.current.muted = false;
      }
    }
  }, [isMuted]);

  const toggleMute = useCallback(() => {
    if (videoRef.current) {
      const newMuted = !isMuted;
      setIsMuted(newMuted);
      videoRef.current.muted = newMuted;
    }
  }, [isMuted]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if in input field
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.key) {
        case " ":
          e.preventDefault();
          toggle();
          break;
        case "l":
        case "L":
          e.preventDefault();
          toggleLoop();
          break;
        case "Enter":
          e.preventDefault();
          if (currentSegmentId !== null) {
            playSegment(currentSegmentId);
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggle, toggleLoop, playSegment, currentSegmentId]);

  // Get current segment for subtitle display
  const currentSegment = currentSegmentId !== null
    ? segments.find((s) => s.id === currentSegmentId)
    : findSegmentAtTime(currentTime);

  // Video source URL (proxied through Next.js rewrite)
  const videoUrl = `/api/jobs/${jobId}/video`;

  // Calculate font sizes based on subtitle height ratio
  // Base sizes at 50% ratio: English 24px, Chinese 28px
  const fontScale = subtitleHeightRatio / 0.5;
  const englishFontSize = Math.max(16, Math.min(36, 24 * fontScale));
  const chineseFontSize = Math.max(18, Math.min(42, 28 * fontScale));

  return (
    <div
      ref={containerRef}
      className="flex flex-col bg-black rounded-lg overflow-hidden"
      style={{ height: "100%" }}
    >
      {/* Video area */}
      <div
        className="relative flex-shrink-0"
        style={{ height: `${(1 - subtitleHeightRatio) * 100}%` }}
      >
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full h-full object-contain cursor-pointer bg-black"
          preload="metadata"
          onClick={toggle}
        />
        {/* Watermark overlay */}
        {watermarkUrl && (
          <div className="absolute top-3 left-3 pointer-events-none">
            <img
              src={watermarkUrl}
              alt="Watermark"
              className="max-h-16 max-w-32 object-contain opacity-90"
            />
          </div>
        )}
      </div>

      {/* Drag handle to resize */}
      <div
        className="h-1 bg-gray-600 hover:bg-blue-500 cursor-ns-resize flex-shrink-0 relative group"
        onMouseDown={() => setIsDragging(true)}
      >
        <div className="absolute inset-x-0 -top-2 -bottom-2" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-12 h-1 bg-gray-400 rounded group-hover:bg-blue-400" />
      </div>

      {/* Subtitle area */}
      <div
        className="flex-1 bg-[#1a2744] flex flex-col items-center justify-center px-8 py-4 min-h-0"
      >
        {currentSegment ? (
          <>
            {/* English text */}
            <div
              className="text-white text-center font-medium leading-relaxed mb-4"
              style={{ fontSize: `${englishFontSize}px` }}
            >
              {currentSegment.en}
            </div>
            {/* Chinese text */}
            <div
              className="text-yellow-400 text-center font-medium leading-relaxed"
              style={{ fontSize: `${chineseFontSize}px` }}
            >
              {currentSegment.zh}
            </div>
          </>
        ) : (
          <div className="text-gray-500 text-center">
            No subtitle
          </div>
        )}
      </div>

      {/* Controls bar */}
      <div className="bg-gray-900 p-3 flex-shrink-0">
        {/* Progress bar */}
        <div
          className="h-1 bg-gray-600 rounded-full mb-3 cursor-pointer"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const ratio = (e.clientX - rect.left) / rect.width;
            seekTo(ratio * duration);
          }}
        >
          <div
            className="h-1 bg-blue-500 rounded-full"
            style={{ width: `${(currentTime / duration) * 100}%` }}
          />
        </div>

        {/* Control buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Play/Pause */}
            <button
              onClick={toggle}
              className="text-white hover:text-blue-400"
              title="Space to toggle"
            >
              {isPlaying ? (
                <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
              ) : (
                <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>

            {/* Time display */}
            <span className="text-white text-sm">
              {formatDuration(currentTime)} / {formatDuration(duration)}
            </span>

            {/* Volume control */}
            <div className="flex items-center gap-2">
              <button
                onClick={toggleMute}
                className="text-white hover:text-blue-400"
                title={isMuted ? "Unmute" : "Mute"}
              >
                {isMuted || volume === 0 ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
                  </svg>
                ) : volume < 0.5 ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                  </svg>
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={isMuted ? 0 : volume}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                className="w-20 h-1 bg-gray-600 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Watermark upload */}
            <input
              ref={watermarkInputRef}
              type="file"
              accept="image/*"
              onChange={handleWatermarkUpload}
              className="hidden"
              id="watermark-upload"
            />
            {watermarkUrl ? (
              <div className="flex items-center gap-1">
                <img src={watermarkUrl} alt="Logo" className="h-6 w-6 object-contain rounded" />
                <button
                  onClick={handleRemoveWatermark}
                  className="text-xs text-red-400 hover:text-red-300"
                  title="Remove watermark"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => watermarkInputRef.current?.click()}
                className="text-sm px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center gap-1"
                title="Upload watermark logo"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Logo
              </button>
            )}

            {/* Loop toggle */}
            <button
              onClick={toggleLoop}
              className={`text-sm px-2 py-1 rounded ${
                isLooping
                  ? "bg-blue-500 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
              title="L to toggle loop"
            >
              Loop
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
