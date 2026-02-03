"use client";

import { useState, useEffect, useRef } from "react";
import type { CropRegion, ObservationType } from "@/lib/scenemind-api";
import { getTagColor, getTagLabel } from "@/lib/scenemind-api";

interface ObservationPanelProps {
  frameUrl: string | null;
  cropUrl: string | null;
  timecode: number;
  cropRegion: CropRegion | null;
  onSave: (note: string, tag: ObservationType) => void;
  onCancel: () => void;
  saving: boolean;
}

const OBSERVATION_TAGS: ObservationType[] = [
  "slang",
  "prop",
  "character",
  "music",
  "visual",
  "general",
];

export default function ObservationPanel({
  frameUrl,
  cropUrl,
  timecode,
  cropRegion,
  onSave,
  onCancel,
  saving,
}: ObservationPanelProps) {
  const [note, setNote] = useState("");
  const [selectedTag, setSelectedTag] = useState<ObservationType>("general");
  const noteInputRef = useRef<HTMLTextAreaElement>(null);

  // Focus input when panel opens
  useEffect(() => {
    if (noteInputRef.current) {
      noteInputRef.current.focus();
    }
  }, []);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLTextAreaElement) {
        // Allow normal editing in textarea
        if (e.key === "Escape") {
          onCancel();
        } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          if (note.trim()) {
            onSave(note.trim(), selectedTag);
          }
        }
        return;
      }

      if (e.key === "Escape") {
        onCancel();
      } else if (e.key === "Enter" && note.trim()) {
        onSave(note.trim(), selectedTag);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [note, selectedTag, onSave, onCancel]);

  // Format timecode
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Add Observation</h3>
        <span className="text-gray-400 text-sm font-mono">
          @ {formatTime(timecode)}
        </span>
      </div>

      {/* Frame Preview */}
      <div className="mb-4 grid grid-cols-2 gap-2">
        {/* Full frame */}
        {frameUrl && (
          <div className="space-y-1">
            <span className="text-xs text-gray-500">Full Frame</span>
            <img
              src={frameUrl}
              alt="Captured frame"
              className="w-full rounded border border-[var(--border)]"
            />
          </div>
        )}

        {/* Cropped region */}
        {cropUrl && cropRegion && (
          <div className="space-y-1">
            <span className="text-xs text-gray-500">
              Selection ({cropRegion.width}x{cropRegion.height})
            </span>
            <img
              src={cropUrl}
              alt="Cropped region"
              className="w-full rounded border border-[var(--border)]"
            />
          </div>
        )}

        {/* Placeholder if no crop */}
        {frameUrl && !cropUrl && (
          <div className="space-y-1">
            <span className="text-xs text-gray-500">No Selection</span>
            <div className="w-full aspect-video rounded border border-dashed border-[var(--border)] flex items-center justify-center text-gray-500 text-sm">
              No crop region
            </div>
          </div>
        )}
      </div>

      {/* Tag Selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Tag</label>
        <div className="flex flex-wrap gap-2">
          {OBSERVATION_TAGS.map((tag) => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                selectedTag === tag
                  ? `${getTagColor(tag)} text-white`
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              {getTagLabel(tag)}
            </button>
          ))}
        </div>
      </div>

      {/* Note Input */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Note</label>
        <textarea
          ref={noteInputRef}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="What did you notice? (e.g., 'Groovy' means cool in 70s slang)"
          className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="btn btn-secondary"
          disabled={saving}
        >
          Cancel
          <span className="ml-2 text-xs text-gray-500">Esc</span>
        </button>
        <button
          onClick={() => note.trim() && onSave(note.trim(), selectedTag)}
          className="btn btn-primary"
          disabled={!note.trim() || saving}
        >
          {saving ? (
            <>
              <span className="spinner w-4 h-4 mr-2" />
              Saving...
            </>
          ) : (
            <>
              Save
              <span className="ml-2 text-xs opacity-70">Cmd+Enter</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
