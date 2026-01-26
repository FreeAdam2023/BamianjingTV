"use client";

import { useCallback, useState, useEffect } from "react";

interface TrimHandleProps {
  position: "left" | "right";
  x: number;
  height: number;
  color: string;
  onDrag: (deltaX: number) => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  containerRef: React.RefObject<HTMLElement | null>;
}

export default function TrimHandle({
  position,
  x,
  height,
  color,
  onDrag,
  onDragStart,
  onDragEnd,
  containerRef,
}: TrimHandleProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);

  // Handle drag start
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);
      setStartX(e.clientX);
      onDragStart?.();
    },
    [onDragStart]
  );

  // Handle drag
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - startX;
      setStartX(e.clientX);
      onDrag(deltaX);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      onDragEnd?.();
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, startX, onDrag, onDragEnd]);

  const handleWidth = 6;
  const handleOffset = position === "left" ? -handleWidth / 2 : -handleWidth / 2;

  return (
    <div
      className="absolute top-0 z-10 cursor-ew-resize group"
      style={{
        left: x + handleOffset,
        width: handleWidth,
        height,
      }}
      onMouseDown={handleMouseDown}
    >
      {/* Handle visual */}
      <div
        className={`w-full h-full transition-colors ${
          isDragging ? "bg-white" : "bg-transparent group-hover:bg-white/50"
        }`}
        style={{
          borderLeft: position === "left" ? `2px solid ${color}` : "none",
          borderRight: position === "right" ? `2px solid ${color}` : "none",
        }}
      />

      {/* Grip dots */}
      <div
        className={`absolute top-1/2 -translate-y-1/2 flex flex-col gap-0.5 transition-opacity ${
          isDragging ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
        style={{
          left: position === "left" ? 1 : undefined,
          right: position === "right" ? 1 : undefined,
        }}
      >
        <div className="w-0.5 h-0.5 rounded-full bg-white" />
        <div className="w-0.5 h-0.5 rounded-full bg-white" />
        <div className="w-0.5 h-0.5 rounded-full bg-white" />
      </div>
    </div>
  );
}
