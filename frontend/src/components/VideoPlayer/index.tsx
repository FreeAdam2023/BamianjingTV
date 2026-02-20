"use client";

/**
 * VideoPlayer - Main component for video playback with bilingual subtitles
 */

import { useRef, useEffect, useCallback, useState, forwardRef, useImperativeHandle } from "react";
import type { EditableSegment, PinnedCard } from "@/lib/types";
import type { CardPopupState } from "@/hooks/useCardPopup";
import { useVideoState } from "./useVideoState";
import SubtitleOverlay from "./SubtitleOverlay";
import VideoControls from "./VideoControls";
import PinnedCardOverlay from "./PinnedCardOverlay";
import { CardSidePanel } from "@/components/Cards";

interface VideoPlayerProps {
  jobId: string;
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: number) => void;
  coverFrameTime?: number | null;
  onSetCover?: (timestamp: number) => void;
  // Video trim (WYSIWYG)
  trimStart?: number;
  trimEnd?: number | null;
  sourceDuration?: number;
  // Chinese conversion
  useTraditional?: boolean;
  converting?: boolean;
  onConvertChinese?: (toTraditional: boolean) => void;
  // Regenerate translation
  regenerating?: boolean;
  regenerateProgress?: { current: number; total: number; phase?: string } | null;
  onRegenerateTranslation?: (model?: string) => void;
  onRetranscribe?: (source: "whisper", model?: string) => void;
  // Export preview
  hasExportFull?: boolean;
  hasExportEssence?: boolean;
  onPreviewExport?: (type: "full" | "essence") => void;
  // Subtitle language mode (synced with backend)
  subtitleLanguageMode?: "both" | "en" | "zh" | "none";
  onSubtitleLanguageModeChange?: (mode: "both" | "en" | "zh" | "none") => void;
  // Card side panel
  cardState?: CardPopupState;
  onCardClose?: () => void;
  // Pinned cards support
  timelineId?: string;
  pinnedCards?: PinnedCard[];
  onCardPinChange?: () => void;
  // Card refresh
  onCardRefresh?: () => void;
  cardRefreshing?: boolean;
  // Entity edit callback
  onEditEntity?: (entityId: string) => void;
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
  trimStart = 0,
  trimEnd = null,
  sourceDuration = 0,
  useTraditional,
  converting,
  onConvertChinese,
  regenerating,
  regenerateProgress,
  onRegenerateTranslation,
  onRetranscribe,
  hasExportFull = false,
  hasExportEssence = false,
  onPreviewExport,
  subtitleLanguageMode,
  onSubtitleLanguageModeChange,
  cardState,
  onCardClose,
  timelineId,
  pinnedCards = [],
  onCardPinChange,
  onCardRefresh,
  cardRefreshing = false,
  onEditEntity,
}, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // Grace period: after an explicit segment click/seek, ignore timeupdate-driven
  // segment changes briefly so short segments don't get overridden.
  const segmentLockUntilRef = useRef<number>(0);

  // Keep a ref to segments so skip logic always reads the latest state
  const segmentsRef = useRef(segments);
  segmentsRef.current = segments;

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
    watermarkUrl,
    handleWatermarkUpload,
    removeWatermark,
    subtitleStyle,
    updateSubtitleStyle,
    resetSubtitleStyle,
    cardPosition,
    toggleCardPosition,
  } = useVideoState();

  // Fullscreen state
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }, []);

  // Listen for fullscreen change events
  useEffect(() => {
    const handleChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleChange);
    return () => document.removeEventListener("fullscreenchange", handleChange);
  }, []);

  // Sync subtitle language mode with prop (from backend)
  useEffect(() => {
    if (subtitleLanguageMode !== undefined && subtitleLanguageMode !== subtitleStyle.languageMode) {
      updateSubtitleStyle({ languageMode: subtitleLanguageMode });
    }
  }, [subtitleLanguageMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Notify backend when language mode changes locally
  const handleStyleChange = (updates: Partial<typeof subtitleStyle>) => {
    updateSubtitleStyle(updates);
    // If language mode changed, notify parent
    if (updates.languageMode && onSubtitleLanguageModeChange) {
      onSubtitleLanguageModeChange(updates.languageMode);
    }
  };

  // Calculate effective duration (for WYSIWYG trim)
  const effectiveDuration = (trimEnd ?? sourceDuration) - trimStart;
  const actualTrimEnd = trimEnd ?? sourceDuration;

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    getVideoElement: () => videoRef.current,
    play: () => videoRef.current?.play(),
    pause: () => videoRef.current?.pause(),
    seekTo: (time: number) => {
      if (videoRef.current) {
        // Lock segment selection briefly so timeupdate doesn't override
        segmentLockUntilRef.current = Date.now() + 300;
        // Constrain seek to trimmed range
        const constrainedTime = Math.max(trimStart, Math.min(actualTrimEnd, time));
        videoRef.current.currentTime = constrainedTime;
      }
    },
    getCurrentTime: () => videoRef.current?.currentTime || 0,
  }), [trimStart, actualTrimEnd]);

  // Find current segment based on time
  const findSegmentAtTime = useCallback(
    (time: number): EditableSegment | null => {
      return segments.find((seg) => time >= seg.start && time < seg.end) || null;
    },
    [segments]
  );

  // Seek to trimStart when video loads (if trimmed)
  useEffect(() => {
    const video = videoRef.current;
    if (!video || trimStart <= 0) return;

    const handleLoadedMetadata = () => {
      // Only seek if current time is before trim start
      if (video.currentTime < trimStart) {
        video.currentTime = trimStart;
      }
    };

    // If already loaded, seek immediately
    if (video.readyState >= 1 && video.currentTime < trimStart) {
      video.currentTime = trimStart;
    }

    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    return () => video.removeEventListener("loadedmetadata", handleLoadedMetadata);
  }, [trimStart]);

  // Helper: skip to next non-dropped segment (reads from ref for freshest state)
  const skipDroppedSegment = useCallback((video: HTMLVideoElement, time: number): boolean => {
    const segs = segmentsRef.current;
    const segAtTime = segs.find((seg) => time >= seg.start && time < seg.end);
    if (!segAtTime || segAtTime.state !== "drop") return false;

    // Find the next non-dropped segment after this one
    const nextKeep = segs
      .filter((seg) => seg.start >= segAtTime.end && seg.state !== "drop")
      .sort((a, b) => a.start - b.start)[0];
    if (nextKeep) {
      if (trimEnd !== null && nextKeep.start >= trimEnd) {
        video.currentTime = trimEnd;
        if (!isLooping) video.pause();
        else video.currentTime = trimStart;
      } else {
        video.currentTime = nextKeep.start;
      }
    } else {
      // No more kept segments
      if (trimEnd !== null) {
        video.currentTime = trimEnd;
        if (!isLooping) video.pause();
        else video.currentTime = trimStart;
      } else {
        video.pause();
      }
    }
    return true;
  }, [trimStart, trimEnd, isLooping]);

  // RAF-based drop skip: runs at ~60fps while playing for instant response
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let rafId: number;

    const checkDrop = () => {
      if (!video.paused && !video.seeking) {
        skipDroppedSegment(video, video.currentTime);
      }
      rafId = requestAnimationFrame(checkDrop);
    };

    const startRaf = () => { rafId = requestAnimationFrame(checkDrop); };
    const stopRaf = () => cancelAnimationFrame(rafId);

    video.addEventListener("play", startRaf);
    video.addEventListener("pause", stopRaf);
    // Start immediately if already playing
    if (!video.paused) startRaf();

    return () => {
      cancelAnimationFrame(rafId);
      video.removeEventListener("play", startRaf);
      video.removeEventListener("pause", stopRaf);
    };
  }, [skipDroppedSegment]);

  // Video event handlers
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const time = video.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);

      // Update current segment (skip if within grace period from explicit click)
      if (Date.now() > segmentLockUntilRef.current) {
        const segment = findSegmentAtTime(time);
        if (segment && segment.id !== currentSegmentId) {
          onSegmentChange?.(segment.id);
        }
      }

      // Handle trim end boundary
      if (trimEnd !== null && time >= trimEnd) {
        if (isLooping) {
          video.currentTime = trimStart;
        } else {
          video.pause();
          video.currentTime = trimEnd;
        }
        return;
      }

      // Handle segment looping (only if within trim range)
      if (isLooping && currentSegmentId !== null) {
        const currentSeg = segmentsRef.current.find((s) => s.id === currentSegmentId);
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
    findSegmentAtTime,
    onTimeUpdate,
    onSegmentChange,
    setCurrentTime,
    setDuration,
    setIsPlaying,
    trimStart,
    trimEnd,
  ]);

  // Playback controls
  const play = useCallback(() => videoRef.current?.play(), []);
  const pause = useCallback(() => videoRef.current?.pause(), []);
  const toggle = useCallback(() => {
    if (isPlaying) pause();
    else play();
  }, [isPlaying, play, pause]);

  const seekTo = useCallback((time: number) => {
    if (videoRef.current) {
      // Lock segment selection briefly so timeupdate doesn't override
      segmentLockUntilRef.current = Date.now() + 300;
      // Constrain seek to trimmed range
      const constrainedTime = Math.max(trimStart, Math.min(actualTrimEnd, time));
      videoRef.current.currentTime = constrainedTime;
    }
  }, [trimStart, actualTrimEnd]);

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

  // Segment navigation: previous / next (skip dropped segments)
  const goToPrevSegment = useCallback(() => {
    const sorted = [...segments].sort((a, b) => a.start - b.start);
    const curIdx = currentSegmentId !== null
      ? sorted.findIndex((s) => s.id === currentSegmentId)
      : sorted.findIndex((s) => currentTime >= s.start && currentTime < s.end);

    // Search backward for a non-dropped segment
    for (let i = (curIdx > 0 ? curIdx - 1 : sorted.length - 1); i >= 0; i--) {
      const seg = sorted[i];
      if (seg.state !== "drop") {
        seekTo(seg.start);
        onSegmentChange?.(seg.id);
        return;
      }
    }
  }, [segments, currentSegmentId, currentTime, seekTo, onSegmentChange]);

  const goToNextSegment = useCallback(() => {
    const sorted = [...segments].sort((a, b) => a.start - b.start);
    const curIdx = currentSegmentId !== null
      ? sorted.findIndex((s) => s.id === currentSegmentId)
      : sorted.findIndex((s) => currentTime >= s.start && currentTime < s.end);

    // Search forward for a non-dropped segment
    for (let i = (curIdx >= 0 ? curIdx + 1 : 0); i < sorted.length; i++) {
      const seg = sorted[i];
      if (seg.state !== "drop") {
        seekTo(seg.start);
        onSegmentChange?.(seg.id);
        return;
      }
    }
  }, [segments, currentSegmentId, currentTime, seekTo, onSegmentChange]);

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
          // Shift+← = 10s, ← = 5s (constrained to trim range)
          seekTo(Math.max(trimStart, currentTime - (e.shiftKey ? 10 : 5)));
          break;
        case "ArrowRight":
          e.preventDefault();
          // Shift+→ = 10s, → = 5s (constrained to trim range)
          seekTo(Math.min(actualTrimEnd, currentTime + (e.shiftKey ? 10 : 5)));
          break;
        case "j":
        case "J":
          e.preventDefault();
          // J = rewind 10s (YouTube style, constrained to trim range)
          seekTo(Math.max(trimStart, currentTime - 10));
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
  }, [toggle, toggleLoop, playSegment, currentSegmentId, seekTo, currentTime, duration, trimStart, actualTrimEnd]);

  // Get current segment for subtitle display (skip dropped segments)
  const currentSegmentRaw = currentSegmentId !== null
    ? segments.find((s) => s.id === currentSegmentId)
    : findSegmentAtTime(currentTime);
  const currentSegment = (currentSegmentRaw?.state === "drop" || currentSegmentRaw?.subtitle_hidden) ? null : currentSegmentRaw;

  // Video source URL (always source video, export preview in modal)
  const videoUrl = typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8001/jobs/${jobId}/video`
    : `/api/jobs/${jobId}/video`;

  // Dark blue color matching subtitle area and export
  const containerBgColor = "#1a2744";
  const isHiddenMode = subtitleStyle.displayMode === "hidden";
  const hasCardOpen = cardState?.isOpen === true;
  const hasActivePinnedCardNow = pinnedCards.some(
    (c) => currentTime >= c.display_start && currentTime <= c.display_end
  );
  const showCardPanel = true;
  // Card drawer is visible when a card detail or pinned card is active
  const isCardDrawerOpen = showCardPanel && (hasCardOpen || hasActivePinnedCardNow);

  const subtitleHeightPercent = subtitleHeightRatio * 100;
  const isOnLeft = cardPosition === "left";

  return (
    <div
      ref={containerRef}
      className="flex flex-col rounded-lg overflow-hidden h-full"
      style={{ backgroundColor: containerBgColor }}
    >
      {/* Video area — always full width, full height */}
      <div className="relative flex-1 min-h-0" style={{ minHeight: "200px" }}>
        {/* Video with blurred background fill */}
        <div className="w-full h-full relative overflow-hidden">
          {/* Blurred background: covers area, zoomed in */}
          <video
            src={videoUrl}
            key={`${videoUrl}-bg`}
            className="absolute inset-0 w-full h-full pointer-events-none"
            style={{
              objectFit: "cover",
              filter: "blur(25px) brightness(0.6)",
            }}
            muted
            playsInline
            ref={(el) => {
              // Sync background video time with main video
              if (el && videoRef.current) {
                el.currentTime = videoRef.current.currentTime;
              }
            }}
          />
          {/* Sharp foreground: fits area, centered */}
          <video
            ref={videoRef}
            src={videoUrl}
            key={videoUrl}
            className="relative w-full h-full cursor-pointer"
            style={{
              backgroundColor: "transparent",
              objectFit: "contain",
            }}
            preload="auto"
            onClick={toggle}
            playsInline
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

          {/* Floating subtitle overlay (bottom 25%, transparent gradient) */}
          {!isHiddenMode && (
            <div className="absolute bottom-0 left-0 right-0 z-10" style={{ height: `${subtitleHeightPercent}%` }}>
              <SubtitleOverlay
                segment={currentSegment || null}
                style={subtitleStyle}
              />
            </div>
          )}
        </div>

        {/* Card drawer — slides in from left or right, ABOVE subtitle zone, opaque */}
        {showCardPanel && (
          <div
            className={`absolute top-0 w-[30%] z-20 overflow-hidden transition-transform duration-300 ease-out ${
              isOnLeft
                ? `left-0 border-r border-white/20 ${isCardDrawerOpen ? "translate-x-0" : "-translate-x-full"}`
                : `right-0 border-l border-white/20 ${isCardDrawerOpen ? "translate-x-0" : "translate-x-full"}`
            }`}
            style={{
              backgroundColor: containerBgColor,
              height: `${100 - subtitleHeightPercent}%`,
            }}
          >
            {/* Position toggle button */}
            <button
              onClick={toggleCardPosition}
              className="absolute top-2 z-30 p-1 rounded bg-black/40 text-white/70 hover:bg-black/60 hover:text-white transition-colors"
              style={isOnLeft ? { right: 8 } : { left: 8 }}
              title={isOnLeft ? "移到右侧" : "移到左侧"}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {isOnLeft ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 17l-5-5m0 0l5-5m-5 5h12" />
                )}
              </svg>
            </button>

            {/* Pinned card preview (visible when pinned cards active and no detail open) */}
            <div
              className={`absolute inset-0 transition-opacity duration-300 ${
                !hasCardOpen && hasActivePinnedCardNow ? "opacity-100" : "opacity-0 pointer-events-none"
              }`}
            >
              <PinnedCardOverlay
                pinnedCards={pinnedCards}
                currentTime={currentTime}
                timelineId={timelineId}
                onPinChange={onCardPinChange}
              />
            </div>

            {/* Card detail panel (highest priority) */}
            <div
              className={`h-full transition-opacity duration-200 ${
                hasCardOpen ? "opacity-100" : "opacity-0 pointer-events-none"
              }`}
            >
              {cardState && onCardClose && (
                <CardSidePanel
                  state={cardState}
                  onClose={onCardClose}
                  position={cardPosition}
                  inline={true}
                  sourceTimelineId={timelineId}
                  sourceSegmentId={currentSegmentId ?? undefined}
                  sourceTimecode={currentTime}
                  pinnedCards={pinnedCards}
                  onPinChange={onCardPinChange ? () => onCardPinChange() : undefined}
                  onRefresh={onCardRefresh}
                  refreshing={cardRefreshing}
                  onEditEntity={onEditEntity}
                />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Controls bar (full width) */}
      <VideoControls
        isPlaying={isPlaying}
        currentTime={currentTime}
        duration={duration}
        volume={volume}
        isMuted={isMuted}
        isLooping={isLooping}
        watermarkUrl={watermarkUrl}
        coverFrameTime={coverFrameTime ?? null}
        trimStart={trimStart}
        trimEnd={trimEnd}
        sourceDuration={sourceDuration || duration}
        useTraditional={useTraditional}
        converting={converting}
        segmentCount={segments.length}
        onConvertChinese={onConvertChinese}
        regenerating={regenerating}
        regenerateProgress={regenerateProgress}
        onRegenerateTranslation={onRegenerateTranslation}
        onRetranscribe={onRetranscribe}
        hasExportFull={hasExportFull}
        hasExportEssence={hasExportEssence}
        onPreviewExport={onPreviewExport}
        onPrevSegment={segments.length > 0 ? goToPrevSegment : undefined}
        onNextSegment={segments.length > 0 ? goToNextSegment : undefined}
        onTogglePlay={toggle}
        onSeek={seekTo}
        onVolumeChange={handleVolumeChange}
        onToggleMute={handleToggleMute}
        onToggleLoop={toggleLoop}
        onWatermarkUpload={handleWatermarkUpload}
        onWatermarkRemove={removeWatermark}
        onSetCover={onSetCover ? () => onSetCover(currentTime) : undefined}
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
        subtitleStyle={subtitleStyle}
        onSubtitleStyleChange={handleStyleChange}
        onSubtitleStyleReset={resetSubtitleStyle}
      />
    </div>
  );
});

export default VideoPlayer;
