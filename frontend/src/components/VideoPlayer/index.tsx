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
  regenerateProgress?: { current: number; total: number } | null;
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

  // Video event handlers
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const time = video.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);

      // Skip dropped segments instantly during playback
      if (!video.paused) {
        const segAtTime = segments.find((seg) => time >= seg.start && time < seg.end);
        if (segAtTime && segAtTime.state === "drop") {
          // Find the next non-dropped segment after this one
          const nextKeep = segments
            .filter((seg) => seg.start >= segAtTime.end && seg.state !== "drop")
            .sort((a, b) => a.start - b.start)[0];
          if (nextKeep) {
            // Respect trim end
            if (trimEnd !== null && nextKeep.start >= trimEnd) {
              video.currentTime = trimEnd;
              if (!isLooping) video.pause();
              else video.currentTime = trimStart;
            } else {
              video.currentTime = nextKeep.start;
            }
          } else {
            // No more kept segments, go to end
            if (trimEnd !== null) {
              video.currentTime = trimEnd;
              if (!isLooping) video.pause();
              else video.currentTime = trimStart;
            }
          }
          return;
        }
      }

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
          // Loop back to trim start
          video.currentTime = trimStart;
        } else {
          // Pause at trim end
          video.pause();
          video.currentTime = trimEnd;
        }
        return;
      }

      // Handle segment looping (only if within trim range)
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
  const isOverlayMode = subtitleStyle.displayMode === "overlay";
  const hasCardOpen = cardState?.isOpen === true;
  const hasActivePinnedCards = pinnedCards.length > 0;
  const hasActivePinnedCardNow = pinnedCards.some(
    (c) => currentTime >= c.display_start && currentTime <= c.display_end
  );

  // Calculate heights for split mode
  const videoHeightPercent = isOverlayMode ? 100 : (1 - subtitleHeightRatio) * 100;
  const subtitleHeightPercent = isOverlayMode ? 0 : subtitleHeightRatio * 100;

  return (
    <div
      ref={containerRef}
      className="flex flex-col rounded-lg overflow-hidden h-full"
      style={{ backgroundColor: containerBgColor }}
    >
      {/* Top section: Video + Card Panel side by side */}
      <div
        className="flex flex-shrink-0"
        style={{
          height: isOverlayMode ? "calc(100% - 60px)" : `${videoHeightPercent}%`,
          minHeight: "200px",
        }}
      >
        {/* Video area with blurred background fill */}
        <div className="w-[65%] relative overflow-hidden">
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

          {/* Overlay mode: subtitles on video */}
          {isOverlayMode && (
            <SubtitleOverlay
              segment={currentSegment || null}
              style={subtitleStyle}
              onStyleChange={handleStyleChange}
              onStyleReset={resetSubtitleStyle}
              overlayMode={true}
            />
          )}

        </div>

        {/* Card panel (next to video only) — matches export card area */}
        <div
          className="w-[35%] flex-shrink-0 border-l border-white/20 relative overflow-hidden"
          style={{ backgroundColor: containerBgColor }}
        >
          {/* Layer 1: Placeholder (visible when nothing else is showing) */}
          <div
            className={`absolute inset-0 flex flex-col items-center justify-center p-6 transition-opacity duration-300 ${
              hasCardOpen || hasActivePinnedCardNow ? "opacity-0 pointer-events-none" : "opacity-100"
            }`}
          >
            <div className="text-center space-y-4">
              <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-purple-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="text-white/70 font-medium text-lg">学习卡片</h3>
              <p className="text-white/40 text-sm leading-relaxed max-w-[200px]">
                点击字幕中高亮的单词或实体查看详细卡片
              </p>
              <div className="flex flex-wrap justify-center gap-2 pt-2">
                <span className="px-2 py-1 bg-blue-500/10 text-blue-400/60 text-xs rounded-full">单词</span>
                <span className="px-2 py-1 bg-purple-500/10 text-purple-400/60 text-xs rounded-full">实体</span>
                <span className="px-2 py-1 bg-amber-500/10 text-amber-400/60 text-xs rounded-full">习语</span>
              </div>
            </div>
          </div>

          {/* Layer 2: Pinned card live preview (visible when pinned cards exist and no card detail open) */}
          <div
            className={`absolute inset-0 transition-opacity duration-300 ${
              !hasCardOpen && hasActivePinnedCards ? "opacity-100" : "opacity-0 pointer-events-none"
            }`}
          >
            <PinnedCardOverlay
              pinnedCards={pinnedCards}
              currentTime={currentTime}
            />
          </div>

          {/* Layer 3: Card detail panel (highest priority, shown when user clicks a word) */}
          <div
            className={`h-full transition-all duration-300 ease-out ${
              hasCardOpen
                ? "opacity-100 translate-x-0"
                : "opacity-0 translate-x-4 pointer-events-none"
            }`}
          >
            {cardState && onCardClose && (
              <CardSidePanel
                state={cardState}
                onClose={onCardClose}
                position="right"
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
      </div>

      {/* Split mode: subtitles below video (full width) */}
      {!isOverlayMode && (
        <div
          className="flex-1 min-h-0 border-t border-white/20"
          style={{ height: `${subtitleHeightPercent}%` }}
        >
          <SubtitleOverlay
            segment={currentSegment || null}
            style={subtitleStyle}
            onStyleChange={handleStyleChange}
            onStyleReset={resetSubtitleStyle}
            overlayMode={false}
          />
        </div>
      )}

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
      />
    </div>
  );
});

export default VideoPlayer;
