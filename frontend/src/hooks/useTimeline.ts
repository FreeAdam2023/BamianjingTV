"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getTimeline,
  updateSegment,
  markTimelineReviewed,
  triggerExport,
} from "@/lib/api";
import type { Timeline, SegmentState, ExportRequest } from "@/lib/types";

export function useTimeline(timelineId: string) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Load timeline
  const loadTimeline = useCallback(async () => {
    try {
      const data = await getTimeline(timelineId);
      setTimeline(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timeline");
      throw err;
    }
  }, [timelineId]);

  useEffect(() => {
    loadTimeline().finally(() => setLoading(false));
  }, [loadTimeline]);

  // Refresh timeline data
  const refresh = useCallback(async () => {
    return loadTimeline();
  }, [loadTimeline]);

  // Update segment state
  const setSegmentState = useCallback(
    async (segmentId: number, state: SegmentState) => {
      if (!timeline) return;

      // Optimistic update
      setTimeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          segments: prev.segments.map((seg) =>
            seg.id === segmentId ? { ...seg, state } : seg
          ),
        };
      });

      // Persist to backend
      setSaving(true);
      try {
        await updateSegment(timelineId, segmentId, { state });
      } catch (err) {
        // Revert on error
        console.error("Failed to update segment:", err);
        setTimeline((prev) => {
          if (!prev) return prev;
          // Reload timeline to get correct state
          getTimeline(timelineId).then(setTimeline);
          return prev;
        });
      } finally {
        setSaving(false);
      }
    },
    [timeline, timelineId]
  );

  // Toggle subtitle_hidden on a segment
  const toggleSubtitleHidden = useCallback(
    async (segmentId: number) => {
      if (!timeline) return;
      const seg = timeline.segments.find((s) => s.id === segmentId);
      if (!seg) return;
      const newVal = !seg.subtitle_hidden;

      setTimeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          segments: prev.segments.map((s) =>
            s.id === segmentId ? { ...s, subtitle_hidden: newVal } : s
          ),
        };
      });

      setSaving(true);
      try {
        await updateSegment(timelineId, segmentId, { subtitle_hidden: newVal });
      } catch (err) {
        console.error("Failed to toggle subtitle_hidden:", err);
        getTimeline(timelineId).then(setTimeline);
      } finally {
        setSaving(false);
      }
    },
    [timeline, timelineId]
  );

  // Toggle bookmark on a segment
  const toggleBookmark = useCallback(
    async (segmentId: number) => {
      if (!timeline) return;

      const segment = timeline.segments.find((s) => s.id === segmentId);
      if (!segment) return;

      const newBookmarked = !segment.bookmarked;

      // Optimistic update
      setTimeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          segments: prev.segments.map((seg) =>
            seg.id === segmentId ? { ...seg, bookmarked: newBookmarked } : seg
          ),
        };
      });

      // Persist to backend
      setSaving(true);
      try {
        await updateSegment(timelineId, segmentId, { bookmarked: newBookmarked });
      } catch (err) {
        // Revert on error
        console.error("Failed to toggle bookmark:", err);
        getTimeline(timelineId).then(setTimeline);
      } finally {
        setSaving(false);
      }
    },
    [timeline, timelineId]
  );

  // Mark as reviewed
  const markReviewed = useCallback(async () => {
    if (!timeline) return;

    try {
      await markTimelineReviewed(timelineId);
      setTimeline((prev) => (prev ? { ...prev, is_reviewed: true } : prev));
    } catch (err) {
      console.error("Failed to mark reviewed:", err);
      throw err;
    }
  }, [timeline, timelineId]);

  // Update segment text (English and Chinese)
  const setSegmentText = useCallback(
    async (segmentId: number, en: string, zh: string) => {
      if (!timeline) return;

      // Optimistic update
      setTimeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          segments: prev.segments.map((seg) =>
            seg.id === segmentId ? { ...seg, en, zh } : seg
          ),
        };
      });

      // Persist to backend
      setSaving(true);
      try {
        await updateSegment(timelineId, segmentId, { en, zh });
      } catch (err) {
        // Revert on error
        console.error("Failed to update segment text:", err);
        // Reload timeline to get correct state
        getTimeline(timelineId).then(setTimeline);
      } finally {
        setSaving(false);
      }
    },
    [timeline, timelineId]
  );

  // Update segment timestamps (start/end)
  const setSegmentTime = useCallback(
    async (segmentId: number, start: number, end: number) => {
      if (!timeline) return;

      // Optimistic update
      setTimeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          segments: prev.segments.map((seg) =>
            seg.id === segmentId ? { ...seg, start, end } : seg
          ),
        };
      });

      // Persist to backend
      setSaving(true);
      try {
        await updateSegment(timelineId, segmentId, { start, end });
      } catch (err) {
        console.error("Failed to update segment time:", err);
        getTimeline(timelineId).then(setTimeline);
      } finally {
        setSaving(false);
      }
    },
    [timeline, timelineId]
  );

  // Update segment trim values
  const setSegmentTrim = useCallback(
    async (segmentId: number, trimStart: number, trimEnd: number) => {
      if (!timeline) return;

      // Optimistic update
      setTimeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          segments: prev.segments.map((seg) =>
            seg.id === segmentId
              ? { ...seg, trim_start: trimStart, trim_end: trimEnd }
              : seg
          ),
        };
      });

      // Persist to backend
      setSaving(true);
      try {
        await updateSegment(timelineId, segmentId, {
          trim_start: trimStart,
          trim_end: trimEnd,
        });
      } catch (err) {
        // Revert on error
        console.error("Failed to update segment trim:", err);
        // Reload timeline to get correct state
        getTimeline(timelineId).then(setTimeline);
      } finally {
        setSaving(false);
      }
    },
    [timeline, timelineId]
  );

  // Trigger export
  const startExport = useCallback(
    async (request: ExportRequest) => {
      try {
        const result = await triggerExport(timelineId, request);
        return result;
      } catch (err) {
        console.error("Failed to trigger export:", err);
        throw err;
      }
    },
    [timelineId]
  );

  // Computed stats
  const stats = timeline
    ? {
        total: timeline.segments.length,
        keep: timeline.segments.filter((s) => s.state === "keep").length,
        drop: timeline.segments.filter((s) => s.state === "drop").length,
        undecided: timeline.segments.filter((s) => s.state === "undecided")
          .length,
        progress:
          timeline.segments.length > 0
            ? ((timeline.segments.filter((s) => s.state !== "undecided").length /
                timeline.segments.length) *
                100)
            : 100,
      }
    : null;

  return {
    timeline,
    loading,
    error,
    saving,
    stats,
    setSegmentState,
    setSegmentText,
    setSegmentTime,
    setSegmentTrim,
    toggleSubtitleHidden,
    toggleBookmark,
    markReviewed,
    startExport,
    refresh,
  };
}
