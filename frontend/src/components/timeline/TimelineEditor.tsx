"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { TimelineProvider, useTimelineContext } from "./TimelineContext";
import TimeRuler from "./TimeRuler";
import Playhead from "./Playhead";
import SubtitleTrack from "./SubtitleTrack";
import AudioTrack from "./AudioTrack";
import type { EditableSegment, SegmentState, WaveformData } from "@/lib/types";

type TrackType = "original" | "dubbing" | "bgm";

interface TrackConfig {
  type: TrackType;
  name: string;
  visible: boolean;
  muted: boolean;
  solo: boolean;
}

interface TrackWaveformData {
  original?: WaveformData | null;
  dubbing?: WaveformData | null;
  bgm?: WaveformData | null;
}

interface TimelineEditorInnerProps {
  segments: EditableSegment[];
  jobId: string;
  onSegmentClick?: (segmentId: number) => void;
  onStateChange?: (segmentId: number, state: SegmentState) => void;
  onTrimChange?: (segmentId: number, trimStart: number, trimEnd: number) => void;
  waveformData?: TrackWaveformData;
  onGenerateWaveform?: (trackType: TrackType) => Promise<void>;
  trackConfigs: TrackConfig[];
  onTrackConfigChange: (trackType: TrackType, config: Partial<TrackConfig>) => void;
  // Video-level trim (WYSIWYG)
  trimStart: number;
  trimEnd: number | null;
}

function TimelineEditorInner({
  segments,
  jobId,
  onSegmentClick,
  onStateChange,
  onTrimChange,
  waveformData,
  onGenerateWaveform,
  trackConfigs,
  onTrackConfigChange,
  trimStart,
  trimEnd,
}: TimelineEditorInnerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(800);
  const {
    zoom,
    scrollX,
    duration,
    playheadTime,
    trackHeight,
    snapEnabled,
    fps,
    setScrollX,
    zoomIn,
    zoomOut,
    setZoom,
    setSnapEnabled,
    timeToPixels,
  } = useTimelineContext();

  // Calculate trim overlay positions
  const hasTrim = trimStart > 0 || trimEnd !== null;
  const trimStartPx = timeToPixels(trimStart);
  const trimEndPx = trimEnd !== null ? timeToPixels(trimEnd) : timeToPixels(duration);

  // Measure container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth);
      }
    };

    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // Handle horizontal scroll
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      setScrollX(e.currentTarget.scrollLeft);
    },
    [setScrollX]
  );

  // Handle wheel zoom
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        setZoom(zoom * delta);
      }
    },
    [zoom, setZoom]
  );

  // Calculate timeline total width
  const timelineWidth = Math.max(containerWidth, timeToPixels(duration) + 100);

  // Log timeline dimensions for debugging
  useEffect(() => {
    console.log("[TimelineEditor] Dimensions:", {
      containerWidth,
      duration,
      zoom,
      timelineWidth,
      pixelsFromDuration: timeToPixels(duration),
    });
  }, [containerWidth, duration, zoom, timelineWidth, timeToPixels]);

  // Format playhead time for display
  const formatPlayheadTime = (time: number): string => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    const frames = Math.floor((time % 1) * 30);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}:${frames.toString().padStart(2, "0")}`;
  };

  // Count visible tracks
  const visibleAudioTracks = trackConfigs.filter((t) => t.visible).length;

  // Calculate total height for tracks
  // Ruler (28px) + visible audio tracks + Subtitle track (48px) + padding
  const totalHeight = 28 + visibleAudioTracks * trackHeight + trackHeight + 8;

  // Check if any waveform needs to be generated
  const needsWaveformGeneration = trackConfigs.some(
    (t) => t.visible && !waveformData?.[t.type]
  );

  return (
    <div
      ref={containerRef}
      className="bg-gray-900 rounded-lg overflow-hidden border border-gray-700"
      onWheel={handleWheel}
    >
      {/* Toolbar */}
      <div className="bg-gray-800 px-3 py-2 flex items-center justify-between border-b border-gray-700">
        <div className="flex items-center gap-3">
          {/* Zoom controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={zoomOut}
              className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-700 text-gray-400 hover:text-white"
              title="Zoom Out"
              aria-label="Zoom out"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
            </button>
            <span className="text-xs text-gray-400 w-12 text-center">{Math.round(zoom)}px/s</span>
            <button
              onClick={zoomIn}
              className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-700 text-gray-400 hover:text-white"
              title="Zoom In"
              aria-label="Zoom in"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>

          <div className="w-px h-5 bg-gray-600" />

          {/* Track visibility toggles */}
          <div className="flex items-center gap-1">
            {trackConfigs.map((track) => (
              <button
                key={track.type}
                onClick={() => onTrackConfigChange(track.type, { visible: !track.visible })}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  track.visible
                    ? "bg-gray-600 text-white"
                    : "bg-gray-700 text-gray-500 hover:bg-gray-600"
                }`}
                title={`Toggle ${track.name} track`}
              >
                {track.name}
              </button>
            ))}
          </div>

          <div className="w-px h-5 bg-gray-600" />

          {/* Snap toggle */}
          <button
            onClick={() => setSnapEnabled(!snapEnabled)}
            className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1 ${
              snapEnabled
                ? "bg-orange-600 text-white"
                : "bg-gray-700 text-gray-400 hover:bg-gray-600"
            }`}
            title={`Snap to frame (${fps}fps) - ${snapEnabled ? "On" : "Off"}`}
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Snap
          </button>

          <div className="w-px h-5 bg-gray-600" />

          {/* Playhead time display */}
          <div className="text-xs font-mono text-gray-300">
            <span className="text-gray-500">Playhead:</span>{" "}
            <span className="text-blue-400">{formatPlayheadTime(playheadTime)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Generate waveform button */}
          {needsWaveformGeneration && onGenerateWaveform && (
            <button
              onClick={() => {
                // Generate waveform for the first visible track without data
                const trackNeedingWaveform = trackConfigs.find(
                  (t) => t.visible && !waveformData?.[t.type]
                );
                if (trackNeedingWaveform) {
                  onGenerateWaveform(trackNeedingWaveform.type);
                }
              }}
              className="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 rounded text-white flex items-center gap-1"
              title="Generate waveform visualization"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
              </svg>
              Generate Waveform
            </button>
          )}
          <span className="text-xs text-gray-500">Ctrl+Scroll to zoom</span>
        </div>
      </div>

      {/* Timeline area */}
      <div
        ref={scrollContainerRef}
        className="overflow-x-auto overflow-y-hidden"
        style={{ height: totalHeight }}
        onScroll={handleScroll}
      >
        <div
          className="relative"
          style={{ width: timelineWidth, height: totalHeight }}
        >
          {/* Time ruler - fixed position */}
          <div className="sticky top-0 z-30 ml-24" style={{ width: timelineWidth - 96 }}>
            <TimeRuler width={timelineWidth - 96} />
          </div>

          {/* Tracks container */}
          <div className="relative" style={{ paddingTop: 0 }}>
            {/* Audio Tracks */}
            {trackConfigs
              .filter((t) => t.visible)
              .map((track) => (
                <AudioTrack
                  key={track.type}
                  name={track.name}
                  width={timelineWidth}
                  jobId={jobId}
                  trackType={track.type}
                  waveformData={waveformData?.[track.type] || null}
                  muted={track.muted}
                  solo={track.solo}
                  onMuteChange={(muted) => onTrackConfigChange(track.type, { muted })}
                  onSoloChange={(solo) => onTrackConfigChange(track.type, { solo })}
                  onGenerateWaveform={
                    onGenerateWaveform
                      ? () => onGenerateWaveform(track.type)
                      : undefined
                  }
                />
              ))}

            {/* Subtitle Track */}
            <SubtitleTrack
              segments={segments}
              width={timelineWidth}
              onSegmentClick={onSegmentClick}
              onStateChange={onStateChange}
              onTrimChange={onTrimChange}
            />
          </div>

          {/* Trim zone overlays - grayed out areas */}
          {hasTrim && (
            <>
              {/* Start trim zone (before trimStart) */}
              {trimStart > 0 && (
                <div
                  className="absolute top-0 bg-black/50 pointer-events-none z-20"
                  style={{
                    left: 96, // Account for track label width
                    width: trimStartPx,
                    height: totalHeight,
                  }}
                >
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-purple-300 text-xs font-medium bg-black/50 px-2 py-1 rounded">
                      ✂️ Trimmed
                    </span>
                  </div>
                </div>
              )}
              {/* End trim zone (after trimEnd) */}
              {trimEnd !== null && (
                <div
                  className="absolute top-0 bg-black/50 pointer-events-none z-20"
                  style={{
                    left: 96 + trimEndPx, // Account for track label width
                    width: timeToPixels(duration) - trimEndPx,
                    height: totalHeight,
                  }}
                >
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-purple-300 text-xs font-medium bg-black/50 px-2 py-1 rounded">
                      ✂️ Trimmed
                    </span>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Playhead - spans full height */}
          <Playhead
            height={totalHeight}
            containerRef={scrollContainerRef}
          />
        </div>
      </div>
    </div>
  );
}

interface TimelineEditorProps {
  segments: EditableSegment[];
  duration: number;
  jobId: string;
  currentTime: number;
  onTimeChange?: (time: number) => void;
  onSegmentClick?: (segmentId: number) => void;
  onSegmentSelect?: (segmentId: number | null) => void;
  onStateChange?: (segmentId: number, state: SegmentState) => void;
  onTrimChange?: (segmentId: number, trimStart: number, trimEnd: number) => void;
  waveformData?: TrackWaveformData;
  onGenerateWaveform?: (trackType: TrackType) => Promise<void>;
  // Video-level trim (WYSIWYG)
  trimStart?: number;
  trimEnd?: number | null;
}

export default function TimelineEditor({
  segments,
  duration,
  jobId,
  currentTime,
  onTimeChange,
  onSegmentClick,
  onSegmentSelect,
  onStateChange,
  onTrimChange,
  waveformData,
  onGenerateWaveform,
  trimStart = 0,
  trimEnd = null,
}: TimelineEditorProps) {
  // Track configuration state - all audio tracks hidden by default, show on demand
  const [trackConfigs, setTrackConfigs] = useState<TrackConfig[]>([
    { type: "original", name: "Original", visible: false, muted: false, solo: false },
    { type: "dubbing", name: "Dubbing", visible: false, muted: false, solo: false },
    { type: "bgm", name: "BGM", visible: false, muted: false, solo: false },
  ]);

  const handleTrackConfigChange = useCallback(
    (trackType: TrackType, config: Partial<TrackConfig>) => {
      setTrackConfigs((prev) =>
        prev.map((t) => (t.type === trackType ? { ...t, ...config } : t))
      );
    },
    []
  );

  return (
    <TimelineProvider
      duration={duration}
      initialPlayheadTime={currentTime}
      onPlayheadChange={onTimeChange}
      onSegmentSelect={onSegmentSelect}
    >
      <TimelineEditorInner
        segments={segments}
        jobId={jobId}
        onSegmentClick={onSegmentClick}
        onStateChange={onStateChange}
        onTrimChange={onTrimChange}
        waveformData={waveformData}
        onGenerateWaveform={onGenerateWaveform}
        trackConfigs={trackConfigs}
        onTrackConfigChange={handleTrackConfigChange}
        trimStart={trimStart}
        trimEnd={trimEnd}
      />
    </TimelineProvider>
  );
}
