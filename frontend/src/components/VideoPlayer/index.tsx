"use client";

/**
 * VideoPlayer - Main component for video playback with bilingual subtitles
 */

import { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
import type { EditableSegment } from "@/lib/types";
import { useVideoState } from "./useVideoState";
import SubtitleOverlay from "./SubtitleOverlay";
import VideoControls from "./VideoControls";

export type VideoMode = "source" | "export_full" | "export_essence";

interface VideoPlayerProps {
  jobId: string;
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: number) => void;
  coverFrameTime?: number | null;
  onSetCover?: (timestamp: number) => void;
  // Chinese conversion
  useTraditional?: boolean;
  converting?: boolean;
  onConvertChinese?: (toTraditional: boolean) => void;
  // Regenerate translation
  regenerating?: boolean;
  regenerateProgress?: { current: number; total: number } | null;
  onRegenerateTranslation?: () => void;
  // Video mode for preview
  videoMode?: VideoMode;
  onVideoModeChange?: (mode: VideoMode) => void;
  hasExportFull?: boolean;
  hasExportEssence?: boolean;
}

export interface VideoPlayerRef {
  getVideoElement: () => HTMLVideoElement | null;
  play: () => void;
  pause: () => void;
  seekTo: (time: number) => void;
  getCurrentTime: () => number;
}

const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(function VideoPlayer({
  jobId,
  segments,
  currentSegmentId,
  onTimeUpdate,
  onSegmentChange,
  coverFrameTime,
  onSetCover,
  useTraditional,
  converting,
  onConvertChinese,
  regenerating,
  regenerateProgress,
  onRegenerateTranslation,
  videoMode = "source",
  onVideoModeChange,
  hasExportFull = false,
  hasExportEssence = false,
}, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const {
    isPlaying,
    setIsPlaying,
    currentTime,
    setCurrentTime,
    duration,
    setDuration,
    isLooping,
    toggleLoop,
    volume,
    setVolume,
    isMuted,
    setIsMuted,
    toggleMute,
    subtitleHeightRatio,
    setSubtitleHeightRatio,
    isDragging,
    setIsDragging,
    watermarkUrl,
    handleWatermarkUpload,
    removeWatermark,
    subtitleStyle,
    updateSubtitleStyle,
    resetSubtitleStyle,
  } = useVideoState();

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    getVideoElement: () => videoRef.current,
    play: () => videoRef.current?.play(),
    pause: () => videoRef.current?.pause(),
    seekTo: (time: number) => {
      if (videoRef.current) {
        videoRef.current.currentTime = time;
      }
    },
    getCurrentTime: () => videoRef.current?.currentTime || 0,
  }), []);

  // Find current segment based on time
  const findSegmentAtTime = useCallback(
    (time: number): EditableSegment | null => {
      return segments.find((seg) => time >= seg.start && time < seg.end) || null;
    },
    [segments]
  );

  // Video event handlers
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

    const handleDurationChange = () => setDuration(video.duration);
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
    setCurrentTime,
    setDuration,
    setIsPlaying,
  ]);

  // Handle drag to resize subtitle area
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalHeight = rect.height;
      const mouseY = e.clientY - rect.top;
      const controlsHeight = 60;
      const availableHeight = totalHeight - controlsHeight;
      const videoHeight = mouseY;
      const newSubtitleRatio = 1 - (videoHeight / availableHeight);
      setSubtitleHeightRatio(Math.max(0.2, Math.min(0.7, newSubtitleRatio)));
    };

    const handleMouseUp = () => setIsDragging(false);

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, setSubtitleHeightRatio, setIsDragging]);

  // Playback controls
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

  const playSegment = useCallback(
    (segmentId: number) => {
      const segment = segments.find((s) => s.id === segmentId);
      if (segment) {
        seekTo(segment.start);
        onSegmentChange?.(segmentId);
        play();
      }
    },
    [segments, seekTo, onSegmentChange, play]
  );

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
  }, [isMuted, setVolume, setIsMuted]);

  const handleToggleMute = useCallback(() => {
    if (videoRef.current) {
      const newMuted = !isMuted;
      setIsMuted(newMuted);
      videoRef.current.muted = newMuted;
    }
  }, [isMuted, setIsMuted]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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
        case "ArrowLeft":
          e.preventDefault();
          // Shift+← = 10s, ← = 5s
          seekTo(Math.max(0, currentTime - (e.shiftKey ? 10 : 5)));
          break;
        case "ArrowRight":
          e.preventDefault();
          // Shift+→ = 10s, → = 5s
          seekTo(Math.min(duration, currentTime + (e.shiftKey ? 10 : 5)));
          break;
        case "j":
        case "J":
          e.preventDefault();
          // J = rewind 10s (YouTube style)
          seekTo(Math.max(0, currentTime - 10));
          break;
        case "k":
        case "K":
          e.preventDefault();
          // K = play/pause (YouTube style)
          toggle();
          break;
        // Note: We skip "l" here as it's already used for loop
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggle, toggleLoop, playSegment, currentSegmentId, seekTo, currentTime, duration]);

  // Get current segment for subtitle display
  const currentSegment = currentSegmentId !== null
    ? segments.find((s) => s.id === currentSegmentId)
    : findSegmentAtTime(currentTime);

  // Video source URL based on mode
  const getVideoUrl = () => {
    if (typeof window !== "undefined") {
      const { protocol, hostname } = window.location;
      const base = `${protocol}//${hostname}:8000`;
      switch (videoMode) {
        case "export_full":
          return `${base}/jobs/${jobId}/video/preview/full`;
        case "export_essence":
          return `${base}/jobs/${jobId}/video/preview/essence`;
        default:
          return `${base}/jobs/${jobId}/video`;
      }
    }
    return `/api/jobs/${jobId}/video`;
  };
  const videoUrl = getVideoUrl();

  // Check if we're in preview mode (showing exported video)
  const isPreviewMode = videoMode !== "source";

  // Dark blue color matching subtitle area and export
  const containerBgColor = "#1a2744";

  return (
    <div
      ref={containerRef}
      className="flex flex-col rounded-lg overflow-hidden h-full"
      style={{ backgroundColor: containerBgColor }}
    >
      {/* Video area */}
      <div
        className="relative flex-shrink-0"
        style={{
          height: `${(1 - subtitleHeightRatio) * 100}%`,
          minHeight: "200px",
        }}
      >
        <video
          ref={videoRef}
          src={videoUrl}
          key={videoUrl} // Force remount when URL changes
          className="w-full h-full object-contain cursor-pointer"
          style={{ backgroundColor: containerBgColor }}
          preload="auto"
          onClick={toggle}
          playsInline
        />
        {/* Preview mode indicator */}
        {isPreviewMode && (
          <div className={`absolute top-3 right-3 px-2 py-1 rounded text-xs font-medium ${
            videoMode === "export_full"
              ? "bg-green-600 text-white"
              : "bg-purple-600 text-white"
          }`}>
            {videoMode === "export_full" ? "Preview: Full Export" : "Preview: Essence"}
          </div>
        )}
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
        {/* Percentage indicator shown during drag */}
        {isDragging && (
          <div className="absolute left-1/2 -translate-x-1/2 -top-8 px-2 py-1 bg-blue-600 text-white text-xs font-medium rounded shadow-lg whitespace-nowrap">
            字幕区域: {Math.round(subtitleHeightRatio * 100)}%
          </div>
        )}
      </div>

      {/* Subtitle overlay */}
      <SubtitleOverlay
        segment={currentSegment || null}
        style={subtitleStyle}
        subtitleHeightRatio={subtitleHeightRatio}
        onStyleChange={updateSubtitleStyle}
        onStyleReset={resetSubtitleStyle}
      />

      {/* Controls bar */}
      <VideoControls
        isPlaying={isPlaying}
        currentTime={currentTime}
        duration={duration}
        volume={volume}
        isMuted={isMuted}
        isLooping={isLooping}
        watermarkUrl={watermarkUrl}
        coverFrameTime={coverFrameTime ?? null}
        useTraditional={useTraditional}
        converting={converting}
        segmentCount={segments.length}
        onConvertChinese={onConvertChinese}
        regenerating={regenerating}
        regenerateProgress={regenerateProgress}
        onRegenerateTranslation={onRegenerateTranslation}
        videoMode={videoMode}
        onVideoModeChange={onVideoModeChange}
        hasExportFull={hasExportFull}
        hasExportEssence={hasExportEssence}
        onTogglePlay={toggle}
        onSeek={seekTo}
        onVolumeChange={handleVolumeChange}
        onToggleMute={handleToggleMute}
        onToggleLoop={toggleLoop}
        onWatermarkUpload={handleWatermarkUpload}
        onWatermarkRemove={removeWatermark}
        onSetCover={onSetCover ? () => onSetCover(currentTime) : undefined}
      />
    </div>
  );
});

export default VideoPlayer;
