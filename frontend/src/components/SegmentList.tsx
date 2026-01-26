"use client";

import { useRef, useEffect, useState } from "react";
import type { EditableSegment, SegmentState } from "@/lib/types";
import { formatDuration } from "@/lib/api";

interface SegmentListProps {
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onSegmentClick: (segmentId: number) => void;
  onStateChange: (segmentId: number, state: SegmentState) => void | Promise<void>;
  onTextChange?: (segmentId: number, en: string, zh: string) => void | Promise<void>;
}

export default function SegmentList({
  segments,
  currentSegmentId,
  onSegmentClick,
  onStateChange,
  onTextChange,
}: SegmentListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editEn, setEditEn] = useState("");
  const [editZh, setEditZh] = useState("");
  const [saving, setSaving] = useState(false);

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

  const startEditing = (segment: EditableSegment) => {
    setEditingId(segment.id);
    setEditEn(segment.en);
    setEditZh(segment.zh);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditEn("");
    setEditZh("");
  };

  const saveEditing = async (segmentId: number) => {
    if (onTextChange) {
      setSaving(true);
      try {
        await onTextChange(segmentId, editEn, editZh);
        setEditingId(null);
      } catch (err) {
        console.error("Failed to save:", err);
      } finally {
        setSaving(false);
      }
    }
  };

  // Handle double-click to edit
  const handleDoubleClick = (segment: EditableSegment, e: React.MouseEvent) => {
    e.stopPropagation();
    if (onTextChange && editingId !== segment.id) {
      startEditing(segment);
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
            <div className="flex items-center gap-2">
              {segment.speaker && (
                <span className="bg-gray-700 px-2 py-0.5 rounded">
                  {segment.speaker}
                </span>
              )}
              {/* Edit button */}
              {editingId !== segment.id && onTextChange && (
                <button
                  className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded hover:bg-blue-600 hover:text-white transition"
                  onClick={(e) => {
                    e.stopPropagation();
                    startEditing(segment);
                  }}
                  title="Edit subtitles (or double-click text)"
                >
                  Edit
                </button>
              )}
            </div>
          </div>

          {/* Text content - either editing or display mode */}
          {editingId === segment.id ? (
            <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
              {/* English input */}
              <div>
                <label className="text-xs text-gray-500 block mb-1">English:</label>
                <textarea
                  value={editEn}
                  onChange={(e) => setEditEn(e.target.value)}
                  className="w-full bg-gray-800 text-white text-sm p-2 rounded border border-gray-600 focus:border-blue-500 outline-none resize-none"
                  rows={2}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Escape") cancelEditing();
                  }}
                />
              </div>
              {/* Chinese input */}
              <div>
                <label className="text-xs text-gray-500 block mb-1">Chinese:</label>
                <textarea
                  value={editZh}
                  onChange={(e) => setEditZh(e.target.value)}
                  className="w-full bg-gray-800 text-yellow-400 text-sm p-2 rounded border border-gray-600 focus:border-blue-500 outline-none resize-none"
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") cancelEditing();
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      saveEditing(segment.id);
                    }
                  }}
                />
              </div>
              {/* Save/Cancel buttons */}
              <div className="flex gap-2 justify-end items-center">
                <span className="text-xs text-gray-500">Ctrl+Enter to save, Esc to cancel</span>
                <button
                  className="px-3 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-500 transition"
                  onClick={cancelEditing}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-400 transition disabled:bg-blue-400"
                  onClick={() => saveEditing(segment.id)}
                  disabled={saving}
                >
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
            </div>
          ) : (
            <div
              className="group cursor-text"
              onDoubleClick={(e) => handleDoubleClick(segment, e)}
              title="Double-click to edit"
            >
              {/* English text */}
              <div className="text-white text-sm mb-1 group-hover:bg-gray-700/50 rounded px-1 -mx-1 transition">
                {segment.en}
              </div>
              {/* Chinese text */}
              <div className="text-yellow-400 text-sm mb-2 group-hover:bg-gray-700/50 rounded px-1 -mx-1 transition">
                {segment.zh}
              </div>
            </div>
          )}

          {/* State buttons - hide when editing */}
          {editingId !== segment.id && (
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
          )}
        </div>
      ))}
    </div>
  );
}
