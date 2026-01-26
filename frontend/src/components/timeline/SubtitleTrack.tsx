"use client";

import { useMemo, useCallback, useRef, useEffect, useState } from "react";
import { useTimelineContext } from "./TimelineContext";
import TrimHandle from "./TrimHandle";
import type { EditableSegment, SegmentState } from "@/lib/types";

interface SubtitleTrackProps {
  segments: EditableSegment[];
  width: number;
  onSegmentClick?: (segmentId: number) => void;
  onStateChange?: (segmentId: number, state: SegmentState) => void;
  onTrimChange?: (segmentId: number, trimStart: number, trimEnd: number) => void;
}

export default function SubtitleTrack({
  segments,
  width,
  onSegmentClick,
  onStateChange,
  onTrimChange,
}: SubtitleTrackProps) {
  const {
    zoom,
    scrollX,
    duration,
    trackHeight,
    selectedSegmentId,
    setSelectedSegmentId,
    setPlayheadTime,
    timeToPixels,
    pixelsToTime,
    snapToFrame,
    getSegmentColor,
    getSegmentBorderColor,
  } = useTimelineContext();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Local trim state for dragging (commit to parent on drag end)
  const [localTrimState, setLocalTrimState] = useState<{
    segmentId: number;
    trimStart: number;
    trimEnd: number;
  } | null>(null);

  // Calculate visible segments for performance
  const visibleSegments = useMemo(() => {
    const startTime = Math.max(0, scrollX / zoom);
    const endTime = Math.min(duration, (scrollX + width) / zoom);

    return segments.filter(
      (seg) => seg.end >= startTime && seg.start <= endTime
    );
  }, [segments, scrollX, zoom, width, duration]);

  // Get selected segment
  const selectedSegment = useMemo(() => {
    if (selectedSegmentId === null) return null;
    return segments.find((seg) => seg.id === selectedSegmentId) || null;
  }, [segments, selectedSegmentId]);

  // Get effective trim values (local state if dragging, otherwise from segment)
  const getEffectiveTrim = useCallback((segment: EditableSegment) => {
    if (localTrimState && localTrimState.segmentId === segment.id) {
      return {
        trimStart: localTrimState.trimStart,
        trimEnd: localTrimState.trimEnd,
      };
    }
    return {
      trimStart: segment.trim_start,
      trimEnd: segment.trim_end,
    };
  }, [localTrimState]);

  // Draw segments on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Measure actual canvas container width
    const container = canvas.parentElement;
    const canvasWidth = container ? container.clientWidth : Math.max(100, width - 96);

    // Guard against invalid dimensions
    if (canvasWidth <= 0 || trackHeight <= 0) return;

    // Set up high DPI canvas
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasWidth * dpr;
    canvas.height = trackHeight * dpr;
    ctx.scale(dpr, dpr);

    // Clear canvas
    ctx.clearRect(0, 0, canvasWidth, trackHeight);

    // Draw track background
    ctx.fillStyle = "#111827"; // gray-900
    ctx.fillRect(0, 0, canvasWidth, trackHeight);

    // Draw grid lines (subtle vertical lines)
    ctx.strokeStyle = "rgba(75, 85, 99, 0.3)";
    ctx.lineWidth = 1;
    const gridInterval = zoom >= 100 ? 1 : zoom >= 50 ? 5 : 10;
    const startTime = Math.floor(scrollX / zoom / gridInterval) * gridInterval;

    for (let time = startTime; time <= duration; time += gridInterval) {
      const x = timeToPixels(time) - scrollX;
      if (x < 0 || x > canvasWidth) continue;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, trackHeight);
      ctx.stroke();
    }

    // Draw segments
    visibleSegments.forEach((segment) => {
      const effectiveTrim = getEffectiveTrim(segment);
      const segStart = segment.start + effectiveTrim.trimStart;
      const segEnd = segment.end - effectiveTrim.trimEnd;

      const x = timeToPixels(segStart) - scrollX;
      const segWidth = timeToPixels(segEnd - segStart);
      const isSelected = segment.id === selectedSegmentId;

      // Draw trimmed areas (dimmed)
      if (effectiveTrim.trimStart > 0 || effectiveTrim.trimEnd > 0) {
        ctx.fillStyle = "rgba(75, 85, 99, 0.2)"; // dimmed

        // Left trimmed area
        if (effectiveTrim.trimStart > 0) {
          const trimStartX = timeToPixels(segment.start) - scrollX;
          const trimWidth = timeToPixels(effectiveTrim.trimStart);
          ctx.fillRect(trimStartX, 4, trimWidth, trackHeight - 8);

          // Diagonal stripes pattern for trimmed area
          ctx.strokeStyle = "rgba(75, 85, 99, 0.3)";
          ctx.lineWidth = 1;
          for (let i = 0; i < trimWidth; i += 6) {
            ctx.beginPath();
            ctx.moveTo(trimStartX + i, 4);
            ctx.lineTo(trimStartX + i + (trackHeight - 8), trackHeight - 4);
            ctx.stroke();
          }
        }

        // Right trimmed area
        if (effectiveTrim.trimEnd > 0) {
          const trimEndX = timeToPixels(segEnd) - scrollX;
          const trimWidth = timeToPixels(effectiveTrim.trimEnd);
          ctx.fillRect(trimEndX, 4, trimWidth, trackHeight - 8);

          // Diagonal stripes pattern
          ctx.strokeStyle = "rgba(75, 85, 99, 0.3)";
          ctx.lineWidth = 1;
          for (let i = 0; i < trimWidth; i += 6) {
            ctx.beginPath();
            ctx.moveTo(trimEndX + i, 4);
            ctx.lineTo(trimEndX + i + (trackHeight - 8), trackHeight - 4);
            ctx.stroke();
          }
        }
      }

      // Segment background (active area)
      ctx.fillStyle = getSegmentColor(segment.state);
      ctx.fillRect(x, 4, segWidth, trackHeight - 8);

      // Segment border
      ctx.strokeStyle = getSegmentBorderColor(segment.state);
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.strokeRect(x, 4, segWidth, trackHeight - 8);

      // Selection highlight
      if (isSelected) {
        ctx.strokeStyle = "#fbbf24"; // yellow-400
        ctx.lineWidth = 2;
        ctx.strokeRect(x - 1, 3, segWidth + 2, trackHeight - 6);
      }

      // Text label (truncated to fit)
      if (segWidth > 30) {
        ctx.fillStyle = "#e5e7eb"; // gray-200
        ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
        ctx.textBaseline = "middle";

        // Calculate max text width
        const maxTextWidth = segWidth - 8;
        let text = segment.en || `#${segment.id}`;

        // Truncate text if necessary
        if (ctx.measureText(text).width > maxTextWidth) {
          while (text.length > 3 && ctx.measureText(text + "...").width > maxTextWidth) {
            text = text.slice(0, -1);
          }
          text += "...";
        }

        ctx.fillText(text, x + 4, trackHeight / 2);
      }
    });

    // Draw track border
    ctx.strokeStyle = "#374151"; // gray-700
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, trackHeight - 0.5);
    ctx.lineTo(canvasWidth, trackHeight - 0.5);
    ctx.stroke();
  }, [
    width,
    trackHeight,
    zoom,
    scrollX,
    duration,
    visibleSegments,
    selectedSegmentId,
    timeToPixels,
    getSegmentColor,
    getSegmentBorderColor,
    getEffectiveTrim,
  ]);

  // Handle trim drag start
  const handleTrimDragStart = useCallback((segment: EditableSegment) => {
    setLocalTrimState({
      segmentId: segment.id,
      trimStart: segment.trim_start,
      trimEnd: segment.trim_end,
    });
  }, []);

  // Handle left trim drag
  const handleLeftTrimDrag = useCallback((segment: EditableSegment, deltaX: number) => {
    const deltaTime = pixelsToTime(deltaX);
    const effectiveTrim = getEffectiveTrim(segment);
    const segmentDuration = segment.end - segment.start;

    // Calculate new trim start (clamp to valid range)
    let newTrimStart = effectiveTrim.trimStart + deltaTime;
    newTrimStart = Math.max(0, newTrimStart);
    newTrimStart = Math.min(segmentDuration - effectiveTrim.trimEnd - 0.1, newTrimStart);
    // Apply snap-to-frame
    newTrimStart = snapToFrame(newTrimStart);

    setLocalTrimState({
      segmentId: segment.id,
      trimStart: newTrimStart,
      trimEnd: effectiveTrim.trimEnd,
    });
  }, [pixelsToTime, getEffectiveTrim, snapToFrame]);

  // Handle right trim drag
  const handleRightTrimDrag = useCallback((segment: EditableSegment, deltaX: number) => {
    const deltaTime = pixelsToTime(deltaX);
    const effectiveTrim = getEffectiveTrim(segment);
    const segmentDuration = segment.end - segment.start;

    // Calculate new trim end (clamp to valid range)
    let newTrimEnd = effectiveTrim.trimEnd - deltaTime;
    newTrimEnd = Math.max(0, newTrimEnd);
    newTrimEnd = Math.min(segmentDuration - effectiveTrim.trimStart - 0.1, newTrimEnd);
    // Apply snap-to-frame
    newTrimEnd = snapToFrame(newTrimEnd);

    setLocalTrimState({
      segmentId: segment.id,
      trimStart: effectiveTrim.trimStart,
      trimEnd: newTrimEnd,
    });
  }, [pixelsToTime, getEffectiveTrim, snapToFrame]);

  // Handle trim drag end
  const handleTrimDragEnd = useCallback(() => {
    if (localTrimState && onTrimChange) {
      onTrimChange(
        localTrimState.segmentId,
        localTrimState.trimStart,
        localTrimState.trimEnd
      );
    }
    setLocalTrimState(null);
  }, [localTrimState, onTrimChange]);

  // Handle click on segment
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - 96; // Account for label width
      const clickTime = (x + scrollX) / zoom;

      // Find clicked segment (considering trim)
      const clickedSegment = segments.find((seg) => {
        const trim = getEffectiveTrim(seg);
        const segStart = seg.start + trim.trimStart;
        const segEnd = seg.end - trim.trimEnd;
        return clickTime >= segStart && clickTime <= segEnd;
      });

      if (clickedSegment) {
        setSelectedSegmentId(clickedSegment.id);
        setPlayheadTime(clickedSegment.start + getEffectiveTrim(clickedSegment).trimStart);
        onSegmentClick?.(clickedSegment.id);
      } else {
        // Click on empty area - just move playhead
        setPlayheadTime(clickTime);
        setSelectedSegmentId(null);
      }
    },
    [scrollX, zoom, segments, setSelectedSegmentId, setPlayheadTime, onSegmentClick, getEffectiveTrim]
  );

  // Handle double-click to toggle state
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!containerRef.current || !onStateChange) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - 96; // Account for label width
      const clickTime = (x + scrollX) / zoom;

      const clickedSegment = segments.find((seg) => {
        const trim = getEffectiveTrim(seg);
        const segStart = seg.start + trim.trimStart;
        const segEnd = seg.end - trim.trimEnd;
        return clickTime >= segStart && clickTime <= segEnd;
      });

      if (clickedSegment) {
        // Cycle through states: undecided -> keep -> drop -> undecided
        const nextState: SegmentState =
          clickedSegment.state === "undecided"
            ? "keep"
            : clickedSegment.state === "keep"
            ? "drop"
            : "undecided";

        onStateChange(clickedSegment.id, nextState);
      }
    },
    [scrollX, zoom, segments, onStateChange, getEffectiveTrim]
  );

  // Calculate trim handle positions for selected segment
  const trimHandlePositions = useMemo(() => {
    if (!selectedSegment) return null;

    const effectiveTrim = getEffectiveTrim(selectedSegment);
    const segStart = selectedSegment.start + effectiveTrim.trimStart;
    const segEnd = selectedSegment.end - effectiveTrim.trimEnd;

    return {
      left: timeToPixels(segStart) - scrollX,
      right: timeToPixels(segEnd) - scrollX,
    };
  }, [selectedSegment, getEffectiveTrim, timeToPixels, scrollX]);

  return (
    <div ref={containerRef} className="relative" style={{ height: trackHeight }}>
      {/* Track label */}
      <div className="absolute left-0 top-0 bottom-0 w-24 bg-gray-800 border-r border-gray-700 flex items-center px-2 z-10">
        <span className="text-xs text-gray-300 font-medium truncate">Subtitle</span>
      </div>

      {/* Track content */}
      <div className="ml-24 relative bg-gray-900" style={{ height: trackHeight }}>
        <canvas
          ref={canvasRef}
          className="cursor-pointer w-full h-full"
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
        />
        {/* Fallback when no segments */}
        {(!segments || segments.length === 0) && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span className="text-xs text-gray-500">No segments</span>
          </div>
        )}

        {/* Trim handles for selected segment */}
        {selectedSegment && trimHandlePositions && onTrimChange && (
          <>
            <TrimHandle
              position="left"
              x={trimHandlePositions.left}
              height={trackHeight}
              color={getSegmentBorderColor(selectedSegment.state)}
              containerRef={containerRef}
              onDragStart={() => handleTrimDragStart(selectedSegment)}
              onDrag={(deltaX) => handleLeftTrimDrag(selectedSegment, deltaX)}
              onDragEnd={handleTrimDragEnd}
            />
            <TrimHandle
              position="right"
              x={trimHandlePositions.right}
              height={trackHeight}
              color={getSegmentBorderColor(selectedSegment.state)}
              containerRef={containerRef}
              onDragStart={() => handleTrimDragStart(selectedSegment)}
              onDrag={(deltaX) => handleRightTrimDrag(selectedSegment, deltaX)}
              onDragEnd={handleTrimDragEnd}
            />
          </>
        )}
      </div>
    </div>
  );
}
