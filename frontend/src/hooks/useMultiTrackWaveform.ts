"use client";

import { useState, useEffect, useCallback } from "react";
import { getWaveform, generateWaveform } from "@/lib/api";
import { getCachedWaveform, setCachedWaveform } from "@/lib/waveformCache";
import type { WaveformData } from "@/lib/types";

export type TrackType = "original" | "dubbing" | "bgm";

export interface TrackWaveform {
  trackType: TrackType;
  waveform: WaveformData | null;
  loading: boolean;
  error: string | null;
  exists: boolean; // Whether the audio file exists on server
}

interface UseMultiTrackWaveformResult {
  tracks: Record<TrackType, TrackWaveform>;
  generateTrack: (trackType: TrackType) => Promise<void>;
  generateAllTracks: () => Promise<void>;
  isAnyLoading: boolean;
}

/**
 * Hook to fetch and manage waveform data for multiple audio tracks.
 *
 * @param timelineId - The timeline ID
 * @param enabledTracks - Which tracks to load (defaults to all)
 */
export function useMultiTrackWaveform(
  timelineId: string,
  enabledTracks: TrackType[] = ["original", "dubbing", "bgm"]
): UseMultiTrackWaveformResult {
  const [tracks, setTracks] = useState<Record<TrackType, TrackWaveform>>({
    original: { trackType: "original", waveform: null, loading: false, error: null, exists: false },
    dubbing: { trackType: "dubbing", waveform: null, loading: false, error: null, exists: false },
    bgm: { trackType: "bgm", waveform: null, loading: false, error: null, exists: false },
  });

  // Load waveform for a single track
  const loadTrack = useCallback(async (trackType: TrackType): Promise<void> => {
    setTracks((prev) => ({
      ...prev,
      [trackType]: { ...prev[trackType], loading: true, error: null },
    }));

    try {
      // Try IndexedDB cache first
      const cached = await getCachedWaveform(timelineId, trackType);
      if (cached) {
        setTracks((prev) => ({
          ...prev,
          [trackType]: {
            ...prev[trackType],
            waveform: cached,
            loading: false,
            exists: true,
          },
        }));
        return;
      }

      // Fall back to API
      const data = await getWaveform(timelineId, trackType);
      await setCachedWaveform(timelineId, trackType, data);

      setTracks((prev) => ({
        ...prev,
        [trackType]: {
          ...prev[trackType],
          waveform: data,
          loading: false,
          exists: true,
        },
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load waveform";
      const notFound = errorMessage.includes("not found");

      setTracks((prev) => ({
        ...prev,
        [trackType]: {
          ...prev[trackType],
          waveform: null,
          loading: false,
          error: notFound ? null : errorMessage,
          exists: !notFound,
        },
      }));
    }
  }, [timelineId]);

  // Load all enabled tracks on mount
  useEffect(() => {
    enabledTracks.forEach((trackType) => {
      loadTrack(trackType);
    });
  }, [timelineId, enabledTracks.join(","), loadTrack]);

  // Generate waveform for a single track
  const generateTrack = useCallback(async (trackType: TrackType): Promise<void> => {
    setTracks((prev) => ({
      ...prev,
      [trackType]: { ...prev[trackType], loading: true, error: null },
    }));

    try {
      await generateWaveform(timelineId, trackType);
      const data = await getWaveform(timelineId, trackType);
      await setCachedWaveform(timelineId, trackType, data);

      setTracks((prev) => ({
        ...prev,
        [trackType]: {
          ...prev[trackType],
          waveform: data,
          loading: false,
          exists: true,
        },
      }));
    } catch (err) {
      setTracks((prev) => ({
        ...prev,
        [trackType]: {
          ...prev[trackType],
          loading: false,
          error: err instanceof Error ? err.message : "Failed to generate waveform",
        },
      }));
    }
  }, [timelineId]);

  // Generate all tracks
  const generateAllTracks = useCallback(async (): Promise<void> => {
    await Promise.all(enabledTracks.map((trackType) => generateTrack(trackType)));
  }, [enabledTracks, generateTrack]);

  const isAnyLoading = Object.values(tracks).some((t) => t.loading);

  return { tracks, generateTrack, generateAllTracks, isAnyLoading };
}
