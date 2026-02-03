"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getSession,
  getObservations,
  addObservation,
  deleteObservation,
  updateSessionTime,
  completeSession,
} from "@/lib/scenemind-api";
import type {
  Session,
  Observation,
  ObservationCreate,
  CropRegion,
  ObservationType,
} from "@/lib/scenemind-api";

export function useSceneMindSession(sessionId: string) {
  const [session, setSession] = useState<Session | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Load session and observations
  const loadSession = useCallback(async () => {
    try {
      const [sessionData, observationsData] = await Promise.all([
        getSession(sessionId),
        getObservations(sessionId),
      ]);
      setSession(sessionData);
      setObservations(observationsData);
      setError(null);
      return sessionData;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session");
      throw err;
    }
  }, [sessionId]);

  useEffect(() => {
    loadSession().finally(() => setLoading(false));
  }, [loadSession]);

  // Refresh session data
  const refresh = useCallback(async () => {
    return loadSession();
  }, [loadSession]);

  // Add observation with frame capture
  const createObservation = useCallback(
    async (
      timecode: number,
      note: string,
      tag: ObservationType = "general",
      cropRegion?: CropRegion
    ) => {
      if (!session) return null;

      setSaving(true);
      try {
        const create: ObservationCreate = {
          timecode,
          note,
          tag,
          crop_region: cropRegion,
        };

        const observation = await addObservation(sessionId, create);

        // Update local state
        setObservations((prev) => [...prev, observation]);
        setSession((prev) =>
          prev
            ? { ...prev, observation_count: prev.observation_count + 1 }
            : prev
        );

        return observation;
      } catch (err) {
        console.error("Failed to add observation:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [session, sessionId]
  );

  // Delete observation
  const removeObservation = useCallback(
    async (observationId: string) => {
      if (!session) return;

      // Optimistic update
      setObservations((prev) => prev.filter((obs) => obs.id !== observationId));
      setSession((prev) =>
        prev
          ? { ...prev, observation_count: Math.max(0, prev.observation_count - 1) }
          : prev
      );

      try {
        await deleteObservation(sessionId, observationId);
      } catch (err) {
        // Revert on error
        console.error("Failed to delete observation:", err);
        loadSession();
      }
    },
    [session, sessionId, loadSession]
  );

  // Update current playback time
  const saveCurrentTime = useCallback(
    async (currentTime: number) => {
      if (!session) return;

      try {
        await updateSessionTime(sessionId, currentTime);
        setSession((prev) =>
          prev ? { ...prev, current_time: currentTime } : prev
        );
      } catch (err) {
        console.error("Failed to update session time:", err);
      }
    },
    [session, sessionId]
  );

  // Mark session as completed
  const markCompleted = useCallback(async () => {
    if (!session) return;

    try {
      const updated = await completeSession(sessionId);
      setSession(updated);
      return updated;
    } catch (err) {
      console.error("Failed to complete session:", err);
      throw err;
    }
  }, [session, sessionId]);

  // Computed stats
  const stats = observations
    ? {
        total: observations.length,
        byTag: observations.reduce(
          (acc, obs) => {
            acc[obs.tag] = (acc[obs.tag] || 0) + 1;
            return acc;
          },
          {} as Record<ObservationType, number>
        ),
      }
    : null;

  return {
    session,
    observations,
    loading,
    error,
    saving,
    stats,
    createObservation,
    removeObservation,
    saveCurrentTime,
    markCompleted,
    refresh,
  };
}
