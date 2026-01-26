"use client";

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { useTimelineContext } from "./TimelineContext";
import type { WaveformData } from "@/lib/types";

interface AudioTrackProps {
  name: string;
  width: number;
  jobId: string;
  trackType: "original" | "dubbing" | "bgm";
  waveformData?: WaveformData | null;
  muted?: boolean;
  solo?: boolean;
  onMuteChange?: (muted: boolean) => void;
  onSoloChange?: (solo: boolean) => void;
  onGenerateWaveform?: () => void;
}

export default function AudioTrack({
  name,
  width,
  jobId,
  trackType,
  waveformData,
  muted: externalMuted,
  solo: externalSolo,
  onMuteChange,
  onSoloChange,
  onGenerateWaveform,
}: AudioTrackProps) {
  const {
    zoom,
    scrollX,
    duration,
    trackHeight,
    playheadTime,
    setPlayheadTime,
    timeToPixels,
    pixelsToTime,
    trackAudioStates,
    setTrackMuted,
    setTrackSolo,
    getEffectiveTrackMuted,
  } = useTimelineContext();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [internalMuted, setInternalMuted] = useState(false);
  const [internalSolo, setInternalSolo] = useState(false);

  // Use context state if available, then external state, then internal state
  const contextState = trackAudioStates[trackType];
  const isMuted = contextState?.muted ?? (externalMuted !== undefined ? externalMuted : internalMuted);
  const isSolo = contextState?.solo ?? (externalSolo !== undefined ? externalSolo : internalSolo);

  // Check if track is effectively muted (muted or not soloed when another is soloed)
  const isEffectivelyMuted = getEffectiveTrackMuted(trackType);

  const handleMuteToggle = useCallback(() => {
    // Use context function first, then callback, then internal state
    setTrackMuted(trackType, !isMuted);
    onMuteChange?.(!isMuted);
  }, [trackType, isMuted, setTrackMuted, onMuteChange]);

  const handleSoloToggle = useCallback(() => {
    // Use context function first, then callback, then internal state
    setTrackSolo(trackType, !isSolo);
    onSoloChange?.(!isSolo);
  }, [trackType, isSolo, setTrackSolo, onSoloChange]);

  // Track colors based on type
  const trackColors = useMemo(() => {
    switch (trackType) {
      case "original":
        return { waveform: "#3b82f6", background: "rgba(59, 130, 246, 0.1)" }; // blue
      case "dubbing":
        return { waveform: "#8b5cf6", background: "rgba(139, 92, 246, 0.1)" }; // purple
      case "bgm":
        return { waveform: "#10b981", background: "rgba(16, 185, 129, 0.1)" }; // green
      default:
        return { waveform: "#6b7280", background: "rgba(107, 114, 128, 0.1)" }; // gray
    }
  }, [trackType]);

  // Draw waveform on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Measure actual canvas container width
    const container = canvas.parentElement;
    const canvasWidth = container ? container.clientWidth : Math.max(100, width - 96);

    // Guard against invalid dimensions
    if (canvasWidth <= 0 || trackHeight <= 0) return;

    // Set up high DPI canvas
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasWidth * dpr;
    canvas.height = trackHeight * dpr;
    ctx.scale(dpr, dpr);

    // Clear canvas
    ctx.clearRect(0, 0, canvasWidth, trackHeight);

    // Draw track background
    ctx.fillStyle = "#111827"; // gray-900
    ctx.fillRect(0, 0, canvasWidth, trackHeight);

    // Draw background tint
    ctx.fillStyle = trackColors.background;
    ctx.fillRect(0, 0, canvasWidth, trackHeight);

    // Draw grid lines
    ctx.strokeStyle = "rgba(75, 85, 99, 0.3)";
    ctx.lineWidth = 1;
    const gridInterval = zoom >= 100 ? 1 : zoom >= 50 ? 5 : 10;
    const startTime = Math.floor(scrollX / zoom / gridInterval) * gridInterval;

    for (let time = startTime; time <= duration; time += gridInterval) {
      const x = timeToPixels(time) - scrollX;
      if (x < 0 || x > canvasWidth) continue;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, trackHeight);
      ctx.stroke();
    }

    // Draw waveform if data available
    if (waveformData && waveformData.peaks.length > 0) {
      const { peaks, sampleRate } = waveformData;
      const centerY = trackHeight / 2;
      const amplitude = (trackHeight - 8) / 2;

      // Use dimmed color if track is effectively muted
      ctx.strokeStyle = isEffectivelyMuted
        ? "rgba(107, 114, 128, 0.4)" // gray when muted
        : trackColors.waveform;
      ctx.lineWidth = 1;
      ctx.beginPath();

      // Calculate visible range
      const visibleStartTime = Math.max(0, scrollX / zoom);
      const visibleEndTime = Math.min(duration, (scrollX + canvasWidth) / zoom);
      const startSample = Math.floor(visibleStartTime * sampleRate);
      const endSample = Math.ceil(visibleEndTime * sampleRate);

      // Draw waveform as connected line
      let firstPoint = true;
      for (let i = startSample; i < Math.min(endSample, peaks.length); i++) {
        const time = i / sampleRate;
        const x = timeToPixels(time) - scrollX;

        if (x < -1 || x > canvasWidth + 1) continue;

        const peak = peaks[i];
        const y = centerY - peak * amplitude;

        if (firstPoint) {
          ctx.moveTo(x, y);
          firstPoint = false;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      // Draw mirrored waveform for visual balance
      ctx.beginPath();
      firstPoint = true;
      for (let i = startSample; i < Math.min(endSample, peaks.length); i++) {
        const time = i / sampleRate;
        const x = timeToPixels(time) - scrollX;

        if (x < -1 || x > canvasWidth + 1) continue;

        const peak = peaks[i];
        const y = centerY + peak * amplitude;

        if (firstPoint) {
          ctx.moveTo(x, y);
          firstPoint = false;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }
    // No else block needed - fallback div handles the "no data" message

    // Draw track border
    ctx.strokeStyle = "#374151"; // gray-700
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, trackHeight - 0.5);
    ctx.lineTo(canvasWidth, trackHeight - 0.5);
    ctx.stroke();
  }, [width, trackHeight, zoom, scrollX, duration, waveformData, trackColors, timeToPixels, isEffectivelyMuted, onGenerateWaveform]);

  // Handle click to seek or generate waveform
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      // If no waveform data and generator available, trigger generation
      if (!waveformData && onGenerateWaveform) {
        onGenerateWaveform();
        return;
      }

      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const time = (x + scrollX) / zoom;
      setPlayheadTime(Math.max(0, Math.min(duration, time)));
    },
    [scrollX, zoom, duration, setPlayheadTime, waveformData, onGenerateWaveform]
  );

  return (
    <div className="relative flex" style={{ height: trackHeight }}>
      {/* Track label and controls */}
      <div className="w-24 bg-gray-800 border-r border-gray-700 flex flex-col justify-center px-2 z-10 flex-shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-300 font-medium truncate flex-1">{name}</span>
          <div className="flex items-center gap-1">
            {/* Mute button */}
            <button
              onClick={handleMuteToggle}
              className={`w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold ${
                isMuted
                  ? "bg-red-500 text-white"
                  : "bg-gray-700 text-gray-400 hover:bg-gray-600"
              }`}
              title={isMuted ? "Unmute" : "Mute"}
            >
              M
            </button>
            {/* Solo button */}
            <button
              onClick={handleSoloToggle}
              className={`w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold ${
                isSolo
                  ? "bg-yellow-500 text-black"
                  : "bg-gray-700 text-gray-400 hover:bg-gray-600"
              }`}
              title={isSolo ? "Unsolo" : "Solo"}
            >
              S
            </button>
          </div>
        </div>
      </div>

      {/* Waveform area */}
      <div
        className="relative flex-1 bg-gray-900"
        style={{ height: trackHeight }}
      >
        {/* Canvas for waveform */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 cursor-pointer"
          style={{ width: "100%", height: "100%" }}
          onClick={handleClick}
        />
        {/* Fallback when no waveform data */}
        {!waveformData && (
          <div
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
            style={{ backgroundColor: trackColors.background }}
          >
            <span className="text-xs text-gray-500">
              {onGenerateWaveform ? "Click to generate waveform" : "No waveform"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
