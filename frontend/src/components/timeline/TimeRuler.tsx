"use client";

import { useMemo, useRef, useEffect } from "react";
import { useTimelineContext } from "./TimelineContext";

interface TimeRulerProps {
  width: number;
}

export default function TimeRuler({ width }: TimeRulerProps) {
  const { zoom, scrollX, duration, setPlayheadTime, timeToPixels } = useTimelineContext();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Calculate appropriate interval based on zoom level
  const interval = useMemo(() => {
    // At zoom 10 (zoomed out), show markers every 30 seconds
    // At zoom 500 (zoomed in), show markers every 1 second
    const pixelsPerSecond = zoom;

    if (pixelsPerSecond < 20) return 30;      // 30 second intervals
    if (pixelsPerSecond < 50) return 10;      // 10 second intervals
    if (pixelsPerSecond < 100) return 5;      // 5 second intervals
    if (pixelsPerSecond < 200) return 2;      // 2 second intervals
    return 1;                                  // 1 second intervals
  }, [zoom]);

  // Calculate sub-tick interval (smaller ticks between major ticks)
  const subTickInterval = useMemo(() => {
    if (interval >= 30) return 10;
    if (interval >= 10) return 5;
    if (interval >= 5) return 1;
    if (interval >= 2) return 0.5;
    return 0.25;
  }, [interval]);

  // Format time for display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const frames = Math.floor((seconds % 1) * 30); // Assuming 30fps

    if (zoom >= 200) {
      // Show frames at high zoom
      return `${mins}:${secs.toString().padStart(2, "0")}:${frames.toString().padStart(2, "0")}`;
    }
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Draw ruler using canvas for performance
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set up high DPI canvas
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = 28 * dpr;
    ctx.scale(dpr, dpr);

    // Clear canvas
    ctx.clearRect(0, 0, width, 28);

    // Calculate visible time range
    const startTime = Math.max(0, scrollX / zoom);
    const endTime = Math.min(duration, (scrollX + width) / zoom);

    // Draw background
    ctx.fillStyle = "#1f2937"; // gray-800
    ctx.fillRect(0, 0, width, 28);

    // Draw major ticks and labels
    const firstMajorTick = Math.floor(startTime / interval) * interval;

    ctx.fillStyle = "#9ca3af"; // gray-400
    ctx.strokeStyle = "#4b5563"; // gray-600
    ctx.font = "11px ui-monospace, monospace";
    ctx.textAlign = "center";

    for (let time = firstMajorTick; time <= endTime + interval; time += interval) {
      const x = timeToPixels(time);

      if (x < -50 || x > width + 50) continue;

      // Major tick
      ctx.beginPath();
      ctx.moveTo(x, 18);
      ctx.lineTo(x, 28);
      ctx.stroke();

      // Time label
      ctx.fillText(formatTime(time), x, 14);
    }

    // Draw sub-ticks
    ctx.strokeStyle = "#374151"; // gray-700
    const firstSubTick = Math.floor(startTime / subTickInterval) * subTickInterval;

    for (let time = firstSubTick; time <= endTime + subTickInterval; time += subTickInterval) {
      // Skip major tick positions
      if (Math.abs(time % interval) < 0.001) continue;

      const x = timeToPixels(time);
      if (x < 0 || x > width) continue;

      ctx.beginPath();
      ctx.moveTo(x, 22);
      ctx.lineTo(x, 28);
      ctx.stroke();
    }

    // Draw bottom border
    ctx.strokeStyle = "#374151";
    ctx.beginPath();
    ctx.moveTo(0, 27.5);
    ctx.lineTo(width, 27.5);
    ctx.stroke();
  }, [width, zoom, scrollX, duration, interval, subTickInterval, timeToPixels]);

  // Handle click to seek
  const handleClick = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const time = x / zoom;
    setPlayheadTime(Math.max(0, Math.min(duration, time)));
  };

  return (
    <canvas
      ref={canvasRef}
      className="cursor-pointer"
      style={{ width, height: 28 }}
      onClick={handleClick}
    />
  );
}
