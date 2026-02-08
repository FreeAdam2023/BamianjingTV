"use client";

import { useCallback, useEffect, useState } from "react";
import { useTimelineContext } from "./TimelineContext";

const LABEL_WIDTH = 96; // Track label width in pixels

interface PlayheadProps {
  height: number;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export default function Playhead({ height, containerRef }: PlayheadProps) {
  const { playheadTime, scrollX, duration, zoom, setPlayheadTime, timeToPixels } = useTimelineContext();
  const [isDragging, setIsDragging] = useState(false);

  // Absolute position in the content div (aligned with track content after label)
  const absolutePosition = LABEL_WIDTH + timeToPixels(playheadTime);
  // Visual position relative to scroll container viewport (for visibility check)
  const visualPosition = absolutePosition - scrollX;

  // Handle drag start
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  // Handle drag
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      // Convert viewport-relative position to time, accounting for scroll and label width
      const time = (x + scrollX - LABEL_WIDTH) / zoom;
      setPlayheadTime(Math.max(0, Math.min(duration, time)));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, containerRef, scrollX, zoom, duration, setPlayheadTime]);

  // Don't render if playhead is far outside the visible area
  if (visualPosition < -20 || visualPosition > 5000) {
    return null;
  }

  return (
    <div
      className="absolute top-0 pointer-events-none z-20"
      style={{
        left: absolutePosition,
        height: height,
        transform: "translateX(-1px)",
      }}
    >
      {/* Playhead line */}
      <div className="w-0.5 h-full bg-red-500" />

      {/* Playhead handle (triangle at top) */}
      <div
        className="absolute -top-2 left-1/2 -translate-x-1/2 cursor-ew-resize pointer-events-auto"
        onMouseDown={handleMouseDown}
      >
        <svg width="12" height="14" viewBox="0 0 12 14" className="fill-red-500">
          <path d="M0 0 L12 0 L12 6 L6 14 L0 6 Z" />
        </svg>
      </div>
    </div>
  );
}
