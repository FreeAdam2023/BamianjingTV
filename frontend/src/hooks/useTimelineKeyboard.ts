"use client";

import { useEffect, useCallback } from "react";

interface UseTimelineKeyboardProps {
  fps: number;
  duration: number;
  currentTime: number;
  isPlaying: boolean;
  onSeek: (time: number) => void;
  onPlayToggle: () => void;
  onPlayRateChange?: (rate: number) => void;
  segments?: { start: number; end: number }[];
}

/**
 * Hook for timeline-specific keyboard shortcuts.
 *
 * Standard editing shortcuts:
 * - , (comma): Step back one frame
 * - . (period): Step forward one frame
 * - Shift + , : Step back 10 frames
 * - Shift + . : Step forward 10 frames
 * - Home: Jump to start
 * - End: Jump to end
 * - [ (bracket): Jump to previous segment boundary
 * - ] (bracket): Jump to next segment boundary
 * - Alt + Left: Move playhead left 1 second
 * - Alt + Right: Move playhead right 1 second
 */
export function useTimelineKeyboard({
  fps,
  duration,
  currentTime,
  isPlaying,
  onSeek,
  onPlayToggle,
  onPlayRateChange,
  segments,
}: UseTimelineKeyboardProps) {
  const frameTime = 1 / fps;

  // Frame stepping
  const stepFrames = useCallback(
    (frames: number) => {
      const newTime = Math.max(0, Math.min(duration, currentTime + frames * frameTime));
      onSeek(newTime);
    },
    [currentTime, duration, frameTime, onSeek]
  );

  // Jump to start/end
  const jumpToStart = useCallback(() => {
    onSeek(0);
  }, [onSeek]);

  const jumpToEnd = useCallback(() => {
    onSeek(duration);
  }, [duration, onSeek]);

  // Jump to segment boundaries
  const jumpToPrevBoundary = useCallback(() => {
    if (!segments || segments.length === 0) return;

    // Find the nearest segment boundary before current time
    const boundaries = segments
      .flatMap((seg) => [seg.start, seg.end])
      .sort((a, b) => a - b);

    // Find the first boundary that's before current time (with small epsilon for floating point)
    const epsilon = 0.01;
    for (let i = boundaries.length - 1; i >= 0; i--) {
      if (boundaries[i] < currentTime - epsilon) {
        onSeek(boundaries[i]);
        return;
      }
    }
    // If no boundary found, go to start
    onSeek(0);
  }, [segments, currentTime, onSeek]);

  const jumpToNextBoundary = useCallback(() => {
    if (!segments || segments.length === 0) return;

    // Find the nearest segment boundary after current time
    const boundaries = segments
      .flatMap((seg) => [seg.start, seg.end])
      .sort((a, b) => a - b);

    // Find the first boundary that's after current time (with small epsilon)
    const epsilon = 0.01;
    for (const boundary of boundaries) {
      if (boundary > currentTime + epsilon) {
        onSeek(boundary);
        return;
      }
    }
    // If no boundary found, go to end
    onSeek(duration);
  }, [segments, currentTime, duration, onSeek]);

  // Move playhead by seconds
  const moveSeconds = useCallback(
    (seconds: number) => {
      const newTime = Math.max(0, Math.min(duration, currentTime + seconds));
      onSeek(newTime);
    },
    [currentTime, duration, onSeek]
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if in input field
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.key) {
        case ",":
          e.preventDefault();
          if (e.shiftKey) {
            stepFrames(-10);
          } else {
            stepFrames(-1);
          }
          break;

        case ".":
          e.preventDefault();
          if (e.shiftKey) {
            stepFrames(10);
          } else {
            stepFrames(1);
          }
          break;

        case "Home":
          e.preventDefault();
          jumpToStart();
          break;

        case "End":
          e.preventDefault();
          jumpToEnd();
          break;

        case "[":
          e.preventDefault();
          jumpToPrevBoundary();
          break;

        case "]":
          e.preventDefault();
          jumpToNextBoundary();
          break;

        case "ArrowLeft":
          if (e.altKey) {
            e.preventDefault();
            moveSeconds(-1);
          }
          break;

        case "ArrowRight":
          if (e.altKey) {
            e.preventDefault();
            moveSeconds(1);
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    stepFrames,
    jumpToStart,
    jumpToEnd,
    jumpToPrevBoundary,
    jumpToNextBoundary,
    moveSeconds,
  ]);

  return {
    stepFrames,
    jumpToStart,
    jumpToEnd,
    jumpToPrevBoundary,
    jumpToNextBoundary,
    moveSeconds,
  };
}
