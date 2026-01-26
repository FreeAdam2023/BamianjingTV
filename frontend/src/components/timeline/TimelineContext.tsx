"use client";

import { createContext, useContext, useState, useCallback, useRef, useEffect, useMemo, ReactNode } from "react";
import type { TimelineState, EditableSegment, SegmentState } from "@/lib/types";

type TrackType = "original" | "dubbing" | "bgm";

interface TrackAudioState {
  muted: boolean;
  solo: boolean;
  volume: number;
}

type TrackAudioStates = Record<TrackType, TrackAudioState>;

interface TimelineContextValue {
  // State
  playheadTime: number;
  zoom: number;
  scrollX: number;
  selectedSegmentId: number | null;
  duration: number;
  isPlaying: boolean;
  snapEnabled: boolean;
  fps: number;

  // Constants
  minZoom: number;
  maxZoom: number;
  trackHeight: number;

  // Actions
  setPlayheadTime: (time: number) => void;
  setZoom: (zoom: number) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  setScrollX: (x: number) => void;
  setSelectedSegmentId: (id: number | null) => void;
  setIsPlaying: (playing: boolean) => void;
  setSnapEnabled: (enabled: boolean) => void;

  // Utility functions
  timeToPixels: (time: number) => number;
  pixelsToTime: (pixels: number) => number;
  getVisibleTimeRange: () => { start: number; end: number };
  snapToFrame: (time: number) => number;

  // Segment helpers
  getSegmentColor: (state: SegmentState) => string;
  getSegmentBorderColor: (state: SegmentState) => string;

  // Track audio state
  trackAudioStates: TrackAudioStates;
  setTrackMuted: (track: TrackType, muted: boolean) => void;
  setTrackSolo: (track: TrackType, solo: boolean) => void;
  setTrackVolume: (track: TrackType, volume: number) => void;
  getEffectiveTrackMuted: (track: TrackType) => boolean;
}

const TimelineContext = createContext<TimelineContextValue | null>(null);

interface TimelineProviderProps {
  children: ReactNode;
  duration: number;
  initialPlayheadTime?: number;
  onPlayheadChange?: (time: number) => void;
  onSegmentSelect?: (segmentId: number | null) => void;
}

export function TimelineProvider({
  children,
  duration,
  initialPlayheadTime = 0,
  onPlayheadChange,
  onSegmentSelect,
}: TimelineProviderProps) {
  // Zoom: pixels per second. 100 means 100px = 1 second
  const minZoom = 10;   // 10px per second (zoomed out)
  const maxZoom = 500;  // 500px per second (zoomed in)
  const trackHeight = 48;

  const [playheadTime, setPlayheadTimeInternal] = useState(initialPlayheadTime);
  const [zoom, setZoomInternal] = useState(50); // Default: 50px per second
  const [scrollX, setScrollX] = useState(0);
  const [selectedSegmentId, setSelectedSegmentIdInternal] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const fps = 30; // Frames per second for snap-to-frame

  // Track audio states
  const [trackAudioStates, setTrackAudioStates] = useState<TrackAudioStates>({
    original: { muted: false, solo: false, volume: 1.0 },
    dubbing: { muted: false, solo: false, volume: 1.0 },
    bgm: { muted: false, solo: false, volume: 0.5 },
  });

  // Sync playhead with external changes
  useEffect(() => {
    setPlayheadTimeInternal(initialPlayheadTime);
  }, [initialPlayheadTime]);

  const setPlayheadTime = useCallback((time: number) => {
    const clampedTime = Math.max(0, Math.min(duration, time));
    setPlayheadTimeInternal(clampedTime);
    onPlayheadChange?.(clampedTime);
  }, [duration, onPlayheadChange]);

  const setZoom = useCallback((newZoom: number) => {
    setZoomInternal(Math.max(minZoom, Math.min(maxZoom, newZoom)));
  }, [minZoom, maxZoom]);

  const zoomIn = useCallback(() => {
    setZoom(zoom * 1.5);
  }, [zoom, setZoom]);

  const zoomOut = useCallback(() => {
    setZoom(zoom / 1.5);
  }, [zoom, setZoom]);

  const setSelectedSegmentId = useCallback((id: number | null) => {
    setSelectedSegmentIdInternal(id);
    onSegmentSelect?.(id);
  }, [onSegmentSelect]);

  // Track audio control functions
  const setTrackMuted = useCallback((track: TrackType, muted: boolean) => {
    setTrackAudioStates((prev) => ({
      ...prev,
      [track]: { ...prev[track], muted },
    }));
  }, []);

  const setTrackSolo = useCallback((track: TrackType, solo: boolean) => {
    setTrackAudioStates((prev) => ({
      ...prev,
      [track]: { ...prev[track], solo },
    }));
  }, []);

  const setTrackVolume = useCallback((track: TrackType, volume: number) => {
    setTrackAudioStates((prev) => ({
      ...prev,
      [track]: { ...prev[track], volume: Math.max(0, Math.min(1, volume)) },
    }));
  }, []);

  // Calculate effective muted state considering solo
  const getEffectiveTrackMuted = useCallback((track: TrackType): boolean => {
    const state = trackAudioStates[track];

    // If track is explicitly muted, it's muted
    if (state.muted) return true;

    // Check if any track has solo enabled
    const anySoloed = Object.values(trackAudioStates).some((s) => s.solo);

    // If any track is soloed and this track is not, it's effectively muted
    if (anySoloed && !state.solo) return true;

    return false;
  }, [trackAudioStates]);

  // Convert time (seconds) to pixel position
  const timeToPixels = useCallback((time: number): number => {
    return time * zoom;
  }, [zoom]);

  // Convert pixel position to time (seconds)
  const pixelsToTime = useCallback((pixels: number): number => {
    return pixels / zoom;
  }, [zoom]);

  // Get the visible time range based on scroll and container width
  const getVisibleTimeRange = useCallback(() => {
    // Approximate visible width (will be refined when we have container ref)
    const visibleWidth = 1200; // Default fallback
    const startTime = scrollX / zoom;
    const endTime = (scrollX + visibleWidth) / zoom;
    return { start: Math.max(0, startTime), end: Math.min(duration, endTime) };
  }, [scrollX, zoom, duration]);

  // Snap time to nearest frame boundary
  const snapToFrame = useCallback((time: number): number => {
    if (!snapEnabled) return time;
    // Round to nearest frame: fps=30 means 1 frame = 1/30 second ≈ 33.33ms
    return Math.round(time * fps) / fps;
  }, [snapEnabled, fps]);

  // Segment state color helpers
  const getSegmentColor = useCallback((state: SegmentState): string => {
    switch (state) {
      case "keep":
        return "rgba(34, 197, 94, 0.3)"; // green-500 with opacity
      case "drop":
        return "rgba(239, 68, 68, 0.3)"; // red-500 with opacity
      case "undecided":
      default:
        return "rgba(107, 114, 128, 0.3)"; // gray-500 with opacity
    }
  }, []);

  const getSegmentBorderColor = useCallback((state: SegmentState): string => {
    switch (state) {
      case "keep":
        return "#22c55e"; // green-500
      case "drop":
        return "#ef4444"; // red-500
      case "undecided":
      default:
        return "#6b7280"; // gray-500
    }
  }, []);

  const value: TimelineContextValue = {
    playheadTime,
    zoom,
    scrollX,
    selectedSegmentId,
    duration,
    isPlaying,
    snapEnabled,
    fps,
    minZoom,
    maxZoom,
    trackHeight,
    setPlayheadTime,
    setZoom,
    zoomIn,
    zoomOut,
    setScrollX,
    setSelectedSegmentId,
    setIsPlaying,
    setSnapEnabled,
    timeToPixels,
    pixelsToTime,
    getVisibleTimeRange,
    snapToFrame,
    getSegmentColor,
    getSegmentBorderColor,
    trackAudioStates,
    setTrackMuted,
    setTrackSolo,
    setTrackVolume,
    getEffectiveTrackMuted,
  };

  return (
    <TimelineContext.Provider value={value}>
      {children}
    </TimelineContext.Provider>
  );
}

export function useTimelineContext() {
  const context = useContext(TimelineContext);
  if (!context) {
    throw new Error("useTimelineContext must be used within a TimelineProvider");
  }
  return context;
}
