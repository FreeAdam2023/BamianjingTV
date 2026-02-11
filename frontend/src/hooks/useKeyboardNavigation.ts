"use client";

import { useEffect, useCallback } from "react";
import type { SegmentState } from "@/lib/types";

interface UseKeyboardNavigationProps {
  segmentCount: number;
  currentSegmentId: number | null;
  onSegmentChange: (segmentId: number) => void;
  onStateChange: (segmentId: number, state: SegmentState) => void;
  onPlayToggle: () => void;
  onLoopToggle: () => void;
  onPlaySegment: (segmentId: number) => void;
  onTimeNudge?: (segmentId: number, delta: number) => void;
}

/**
 * Hook for keyboard shortcuts in the review page.
 *
 * Keyboard shortcuts:
 * - Space: Play/Pause
 * - j/Down: Next segment
 * - k/Up: Previous segment
 * - Shift+K: Mark current segment as KEEP
 * - d/D: Mark current segment as DROP
 * - u/U: Mark current segment as UNDECIDED
 * - l/L: Toggle loop current segment
 * - Enter: Play current segment from start
 * - - (minus): Nudge current segment 0.05s earlier
 * - = (plus): Nudge current segment 0.05s later
 */
export function useKeyboardNavigation({
  segmentCount,
  currentSegmentId,
  onSegmentChange,
  onStateChange,
  onPlayToggle,
  onLoopToggle,
  onPlaySegment,
  onTimeNudge,
}: UseKeyboardNavigationProps) {
  const goToPreviousSegment = useCallback(() => {
    if (currentSegmentId === null) {
      if (segmentCount > 0) onSegmentChange(0);
      return;
    }
    const prevId = Math.max(0, currentSegmentId - 1);
    onSegmentChange(prevId);
  }, [currentSegmentId, segmentCount, onSegmentChange]);

  const goToNextSegment = useCallback(() => {
    if (currentSegmentId === null) {
      if (segmentCount > 0) onSegmentChange(0);
      return;
    }
    const nextId = Math.min(segmentCount - 1, currentSegmentId + 1);
    onSegmentChange(nextId);
  }, [currentSegmentId, segmentCount, onSegmentChange]);

  const markKeep = useCallback(() => {
    if (currentSegmentId !== null) {
      onStateChange(currentSegmentId, "keep");
    }
  }, [currentSegmentId, onStateChange]);

  const markDrop = useCallback(() => {
    if (currentSegmentId !== null) {
      onStateChange(currentSegmentId, "drop");
    }
  }, [currentSegmentId, onStateChange]);

  const markUndecided = useCallback(() => {
    if (currentSegmentId !== null) {
      onStateChange(currentSegmentId, "undecided");
    }
  }, [currentSegmentId, onStateChange]);

  const playCurrentSegment = useCallback(() => {
    if (currentSegmentId !== null) {
      onPlaySegment(currentSegmentId);
    }
  }, [currentSegmentId, onPlaySegment]);

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
        case " ":
          e.preventDefault();
          onPlayToggle();
          break;

        case "ArrowUp":
        case "k":
          if (!e.shiftKey) {
            e.preventDefault();
            goToPreviousSegment();
          }
          break;

        case "ArrowDown":
        case "j":
          e.preventDefault();
          goToNextSegment();
          break;

        case "K":
          // Shift+K for KEEP
          if (e.shiftKey) {
            e.preventDefault();
            markKeep();
          }
          break;

        case "d":
        case "D":
          e.preventDefault();
          markDrop();
          break;

        case "u":
        case "U":
          e.preventDefault();
          markUndecided();
          break;

        case "l":
        case "L":
          e.preventDefault();
          onLoopToggle();
          break;

        case "Enter":
          e.preventDefault();
          playCurrentSegment();
          break;

        case "-":
          if (onTimeNudge && currentSegmentId !== null) {
            e.preventDefault();
            onTimeNudge(currentSegmentId, -0.05);
          }
          break;

        case "=":
          if (onTimeNudge && currentSegmentId !== null) {
            e.preventDefault();
            onTimeNudge(currentSegmentId, 0.05);
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    onPlayToggle,
    onLoopToggle,
    goToPreviousSegment,
    goToNextSegment,
    markKeep,
    markDrop,
    markUndecided,
    playCurrentSegment,
    onTimeNudge,
    currentSegmentId,
  ]);

  return {
    goToPreviousSegment,
    goToNextSegment,
    markKeep,
    markDrop,
    markUndecided,
    playCurrentSegment,
  };
}
