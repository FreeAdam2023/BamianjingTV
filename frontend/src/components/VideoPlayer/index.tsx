"use client";

/**
 * VideoPlayer - Main component for video playback with bilingual subtitles
 */

import { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
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
  onRegenerateTranslation?: () => void;
  // Export preview
  hasExportFull?: boolean;
  hasExportEssence?: boolean;
  onPreviewExport?: (type: "full" | "essence") => void;
  // Subtitle area ratio (synced with backend)
  subtitleAreaRatio?: number;
  onSubtitleAreaRatioChange?: (ratio: number) => void;
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
  hasExportFull = false,
  hasExportEssence = false,
  onPreviewExport,
  subtitleAreaRatio,
  onSubtitleAreaRatioChange,
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

  // Sync subtitle ratio with prop (from backend)
  useEffect(() => {
    if (subtitleAreaRatio !== undefined) {
      setSubtitleHeightRatio(subtitleAreaRatio);
    }
  }, [subtitleAreaRatio, setSubtitleHeightRatio]);

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

  // Handle drag to resize subtitle area
  useEffect(() => {
    if (!isDragging) return;

    let latestRatio = subtitleHeightRatio;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalHeight = rect.height;
      const mouseY = e.clientY - rect.top;
      const controlsHeight = 60;
      const availableHeight = totalHeight - controlsHeight;
      const videoHeight = mouseY;
      const newSubtitleRatio = Math.max(0.2, Math.min(0.7, 1 - (videoHeight / availableHeight)));
      latestRatio = newSubtitleRatio;
      setSubtitleHeightRatio(newSubtitleRatio);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      // Save to backend when drag ends
      onSubtitleAreaRatioChange?.(latestRatio);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, subtitleHeightRatio, setSubtitleHeightRatio, setIsDragging, onSubtitleAreaRatioChange]);

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
  const currentSegment = currentSegmentRaw?.state === "drop" ? null : currentSegmentRaw;

  // Video source URL (always source video, export preview in modal)
  const videoUrl = typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8001/jobs/${jobId}/video`
    : `/api/jobs/${jobId}/video`;

  // Dark blue color matching subtitle area and export
  const containerBgColor = "#1a2744";
  const isOverlayMode = subtitleStyle.displayMode === "overlay";
  const hasCardOpen = cardState?.isOpen === true;

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
        {/* Video area */}
        <div className="w-[65%] relative">
          <video
            ref={videoRef}
            src={videoUrl}
            key={videoUrl}
            className="w-full h-full cursor-pointer"
            style={{
              backgroundColor: containerBgColor,
              objectFit: "contain",
              objectPosition: "left center",
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
              subtitleHeightRatio={subtitleHeightRatio}
              onStyleChange={handleStyleChange}
              onStyleReset={resetSubtitleStyle}
              overlayMode={true}
            />
          )}

          {/* Pinned card live preview */}
          {pinnedCards.length > 0 && (
            <PinnedCardOverlay
              pinnedCards={pinnedCards}
              currentTime={currentTime}
            />
          )}
        </div>

        {/* Card panel (next to video only) */}
        <div className="w-[35%] flex-shrink-0 border-l border-white/10 bg-gradient-to-b from-slate-900/80 to-slate-800/60 backdrop-blur-sm relative overflow-hidden">
          {/* Placeholder when no card is open */}
          <div
            className={`absolute inset-0 flex flex-col items-center justify-center p-6 transition-opacity duration-300 ${
              hasCardOpen ? "opacity-0 pointer-events-none" : "opacity-100"
            }`}
          >
            <div className="text-center space-y-4">
              {/* Icon */}
              <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-purple-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>

              {/* Title */}
              <h3 className="text-white/70 font-medium text-lg">学习卡片</h3>

              {/* Description */}
              <p className="text-white/40 text-sm leading-relaxed max-w-[200px]">
                点击字幕中高亮的单词或实体查看详细卡片
              </p>

              {/* Hint badges */}
              <div className="flex flex-wrap justify-center gap-2 pt-2">
                <span className="px-2 py-1 bg-blue-500/10 text-blue-400/60 text-xs rounded-full">
                  单词
                </span>
                <span className="px-2 py-1 bg-purple-500/10 text-purple-400/60 text-xs rounded-full">
                  实体
                </span>
                <span className="px-2 py-1 bg-amber-500/10 text-amber-400/60 text-xs rounded-full">
                  习语
                </span>
              </div>
            </div>
          </div>

          {/* Card content with slide-in animation */}
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

      {/* Drag handle to resize (only in split mode) */}
      {!isOverlayMode && (
        <div
          className="h-1.5 bg-gray-600 hover:bg-blue-500 cursor-ns-resize flex-shrink-0 relative group"
          onMouseDown={() => setIsDragging(true)}
        >
          <div className="absolute inset-x-0 -top-2 -bottom-2" />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-1 bg-gray-400 rounded group-hover:bg-blue-400" />
          {isDragging && (
            <div className="absolute left-1/2 -translate-x-1/2 -top-8 px-2 py-1 bg-blue-600 text-white text-xs font-medium rounded shadow-lg whitespace-nowrap z-10">
              字幕: {Math.round(subtitleHeightRatio * 100)}%
            </div>
          )}
        </div>
      )}

      {/* Split mode: subtitles below video (full width) */}
      {!isOverlayMode && (
        <div
          className="flex-1 min-h-0"
          style={{ height: `${subtitleHeightPercent}%` }}
        >
          <SubtitleOverlay
            segment={currentSegment || null}
            style={subtitleStyle}
            subtitleHeightRatio={subtitleHeightRatio}
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
      />
    </div>
  );
});

export default VideoPlayer;
