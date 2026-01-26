"use client";

import { useCallback, useRef, useEffect, useState } from "react";
import { useTimelineContext } from "./TimelineContext";

interface PlayheadProps {
  height: number;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export default function Playhead({ height, containerRef }: PlayheadProps) {
  const { playheadTime, scrollX, duration, zoom, setPlayheadTime, timeToPixels } = useTimelineContext();
  const [isDragging, setIsDragging] = useState(false);

  // Calculate playhead position
  const position = timeToPixels(playheadTime) - scrollX;

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
      const time = (x + scrollX) / zoom;
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

  // Don't render if playhead is outside visible area
  if (position < -10 || position > 2000) {
    return null;
  }

  return (
    <div
      className="absolute top-0 pointer-events-none z-20"
      style={{
        left: position,
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
