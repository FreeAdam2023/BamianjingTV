"use client";

/**
 * ObservationCapture - Capture observations (screenshots with notes) in Review page
 * For WATCHING mode timelines
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { addObservation, getObservationFrameUrl, OBSERVATION_TAGS, getObservationTagLabel, getObservationTagColor } from "@/lib/api";
import type { ObservationType, CropRegion, Observation } from "@/lib/types";

interface ObservationCaptureProps {
  timelineId: string;
  timecode: number;
  onSave: (observation: Observation) => void;
  onCancel: () => void;
}

export default function ObservationCapture({
  timelineId,
  timecode,
  onSave,
  onCancel,
}: ObservationCaptureProps) {
  const [note, setNote] = useState("");
  const [selectedTag, setSelectedTag] = useState<ObservationType>("general");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const noteInputRef = useRef<HTMLTextAreaElement>(null);

  // Focus input when panel opens
  useEffect(() => {
    if (noteInputRef.current) {
      noteInputRef.current.focus();
    }
  }, []);

  // Format timecode
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleSave = useCallback(async () => {
    if (!note.trim()) return;

    setSaving(true);
    setError(null);

    try {
      const observation = await addObservation(timelineId, {
        timecode,
        note: note.trim(),
        tag: selectedTag,
      });
      onSave(observation);
    } catch (err) {
      console.error("Failed to save observation:", err);
      setError(err instanceof Error ? err.message : "Failed to save");
      setSaving(false);
    }
  }, [timelineId, timecode, note, selectedTag, onSave]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLTextAreaElement) {
        if (e.key === "Escape") {
          onCancel();
        } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          handleSave();
        }
        return;
      }

      if (e.key === "Escape") {
        onCancel();
      } else if (e.key === "Enter" && note.trim()) {
        handleSave();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [note, handleSave, onCancel]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow-xl max-w-lg w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Add Observation</h3>
          <span className="text-gray-400 text-sm font-mono">
            @ {formatTime(timecode)}
          </span>
        </div>

        {/* Info */}
        <p className="text-gray-400 text-sm mb-4">
          A screenshot will be captured at the current video time.
        </p>

        {/* Tag Selection */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Tag</label>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(OBSERVATION_TAGS) as ObservationType[]).map((tag) => (
              <button
                key={tag}
                onClick={() => setSelectedTag(tag)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                  selectedTag === tag
                    ? `${getObservationTagColor(tag)} text-white`
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                {getObservationTagLabel(tag)}
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
            className="textarea"
            rows={3}
          />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
            disabled={saving}
          >
            Cancel
            <span className="ml-2 text-xs text-gray-500">Esc</span>
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!note.trim() || saving}
          >
            {saving ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
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
    </div>
  );
}
