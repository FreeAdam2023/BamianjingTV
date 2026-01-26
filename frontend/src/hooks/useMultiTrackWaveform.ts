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
 * Waveforms are NOT auto-loaded on mount to avoid 404 errors.
 * Call generateTrack() to generate and load waveform data when needed.
 *
 * @param timelineId - The timeline ID
 * @param enabledTracks - Which tracks are enabled (defaults to all)
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

  // Try to load from cache only (no API call)
  const loadFromCache = useCallback(async (trackType: TrackType): Promise<boolean> => {
    try {
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
        return true;
      }
    } catch {
      // Ignore cache errors
    }
    return false;
  }, [timelineId]);

  // Load cached waveforms on mount (no API calls)
  useEffect(() => {
    enabledTracks.forEach((trackType) => {
      loadFromCache(trackType);
    });
  }, [timelineId, enabledTracks.join(","), loadFromCache]);

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
