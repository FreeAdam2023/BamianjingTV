"use client";

import { useState, useEffect, useCallback } from "react";
import { getWaveform, generateWaveform } from "@/lib/api";
import { getCachedWaveform, setCachedWaveform } from "@/lib/waveformCache";
import type { WaveformData } from "@/lib/types";

interface UseWaveformResult {
  waveform: WaveformData | null;
  loading: boolean;
  error: string | null;
  fromCache: boolean;
  generate: () => Promise<void>;
}

/**
 * Hook to fetch and manage waveform data for a timeline.
 *
 * Attempts to load from IndexedDB cache first, then falls back to API.
 * If not available, provides a generate function to create it on-demand.
 *
 * @param timelineId - The timeline ID
 * @param trackType - Audio track type (original, dubbing, bgm)
 */
export function useWaveform(
  timelineId: string,
  trackType: "original" | "dubbing" | "bgm" = "original"
): UseWaveformResult {
  const [waveform, setWaveform] = useState<WaveformData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);

  // Try to load existing waveform (cache first, then API)
  useEffect(() => {
    let cancelled = false;

    const loadWaveform = async () => {
      setLoading(true);
      setError(null);
      setFromCache(false);

      try {
        // Try IndexedDB cache first
        const cached = await getCachedWaveform(timelineId, trackType);
        if (cached && !cancelled) {
          setWaveform(cached);
          setFromCache(true);
          setLoading(false);
          return;
        }

        // Fall back to API
        const data = await getWaveform(timelineId, trackType);
        if (!cancelled) {
          setWaveform(data);
          // Cache the result
          await setCachedWaveform(timelineId, trackType, data);
        }
      } catch (err) {
        if (!cancelled) {
          // 404 is expected if waveform hasn't been generated yet
          if (err instanceof Error && err.message.includes("not found")) {
            setError(null); // Not an error, just not generated yet
          } else {
            setError(err instanceof Error ? err.message : "Failed to load waveform");
          }
          setWaveform(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadWaveform();

    return () => {
      cancelled = true;
    };
  }, [timelineId, trackType]);

  // Generate waveform on demand
  const generate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFromCache(false);

    try {
      // Trigger generation
      await generateWaveform(timelineId, trackType);

      // Fetch the newly generated waveform
      const data = await getWaveform(timelineId, trackType);
      setWaveform(data);

      // Cache the result
      await setCachedWaveform(timelineId, trackType, data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate waveform");
    } finally {
      setLoading(false);
    }
  }, [timelineId, trackType]);

  return { waveform, loading, error, fromCache, generate };
}
