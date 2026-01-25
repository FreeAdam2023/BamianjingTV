"use client";

import { useRef, useEffect } from "react";
import type { EditableSegment, SegmentState } from "@/lib/types";
import { formatDuration } from "@/lib/api";

interface SegmentListProps {
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onSegmentClick: (segmentId: number) => void;
  onStateChange: (segmentId: number, state: SegmentState) => void;
}

export default function SegmentList({
  segments,
  currentSegmentId,
  onSegmentClick,
  onStateChange,
}: SegmentListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to current segment
  useEffect(() => {
    if (currentSegmentId === null || !listRef.current) return;

    const element = listRef.current.querySelector(
      `[data-segment-id="${currentSegmentId}"]`
    );
    if (element) {
      element.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [currentSegmentId]);

  const getStateClass = (state: SegmentState): string => {
    switch (state) {
      case "keep":
        return "segment-keep";
      case "drop":
        return "segment-drop";
      case "undecided":
      default:
        return "segment-undecided";
    }
  };

  return (
    <div ref={listRef} className="h-full overflow-y-auto space-y-2 p-2">
      {segments.map((segment) => (
        <div
          key={segment.id}
          data-segment-id={segment.id}
          className={`
            p-3 rounded-lg cursor-pointer transition
            ${getStateClass(segment.state)}
            ${segment.id === currentSegmentId ? "segment-active" : ""}
          `}
          onClick={() => onSegmentClick(segment.id)}
        >
          {/* Time and speaker */}
          <div className="flex justify-between items-center text-xs text-gray-400 mb-1">
            <span>
              {formatDuration(segment.start)} - {formatDuration(segment.end)}
            </span>
            {segment.speaker && (
              <span className="bg-gray-700 px-2 py-0.5 rounded">
                {segment.speaker}
              </span>
            )}
          </div>

          {/* English text */}
          <div className="text-white text-sm mb-1">{segment.en}</div>

          {/* Chinese text */}
          <div className="text-yellow-400 text-sm mb-2">{segment.zh}</div>

          {/* State buttons */}
          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            <button
              className={`
                flex-1 py-1 px-2 text-xs rounded transition
                ${
                  segment.state === "keep"
                    ? "bg-green-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-green-600"
                }
              `}
              onClick={() => onStateChange(segment.id, "keep")}
              title="Shift+K"
            >
              Keep
            </button>
            <button
              className={`
                flex-1 py-1 px-2 text-xs rounded transition
                ${
                  segment.state === "drop"
                    ? "bg-red-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-red-600"
                }
              `}
              onClick={() => onStateChange(segment.id, "drop")}
              title="D"
            >
              Drop
            </button>
            <button
              className={`
                flex-1 py-1 px-2 text-xs rounded transition
                ${
                  segment.state === "undecided"
                    ? "bg-gray-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-500"
                }
              `}
              onClick={() => onStateChange(segment.id, "undecided")}
              title="U"
            >
              ?
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
