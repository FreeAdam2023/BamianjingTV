"use client";

/**
 * ObservationList - Display list of observations for a timeline
 */

import { useState } from "react";
import type { Observation } from "@/lib/types";
import { getObservationTagColor, getObservationTagLabel, deleteObservation, getObservationFrameUrl } from "@/lib/api";

interface ObservationListProps {
  timelineId: string;
  observations: Observation[];
  onObservationClick?: (observation: Observation) => void;
  onDelete?: (observationId: string) => void;
}

export default function ObservationList({
  timelineId,
  observations,
  onObservationClick,
  onDelete,
}: ObservationListProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleDelete = async (observationId: string) => {
    if (!confirm("Delete this observation?")) return;
    setDeletingId(observationId);
    try {
      await deleteObservation(timelineId, observationId);
      onDelete?.(observationId);
    } catch (err) {
      console.error("Failed to delete observation:", err);
    } finally {
      setDeletingId(null);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  if (observations.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 text-sm">
        No observations yet. Press <kbd className="px-1.5 py-0.5 bg-gray-700 rounded text-xs">S</kbd> to capture.
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-700">
      {observations.map((obs) => (
        <div
          key={obs.id}
          className="p-3 hover:bg-gray-800/50 transition-colors"
        >
          <div className="flex items-start justify-between gap-2">
            {/* Main content - clickable */}
            <div
              className="flex-1 cursor-pointer"
              onClick={() => onObservationClick?.(obs)}
            >
              {/* Header */}
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${getObservationTagColor(obs.tag)}`}
                >
                  {getObservationTagLabel(obs.tag)}
                </span>
                <span className="text-xs text-gray-500 font-mono">
                  {formatTime(obs.timecode)}
                </span>
              </div>

              {/* Note */}
              <p className="text-sm text-gray-300 line-clamp-2">{obs.note}</p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1">
              {/* Expand/View button */}
              <button
                onClick={() => setExpandedId(expandedId === obs.id ? null : obs.id)}
                className="p-1.5 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-colors"
                title="View frame"
                aria-label="View frame"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>

              {/* Delete button */}
              <button
                onClick={() => handleDelete(obs.id)}
                disabled={deletingId === obs.id}
                className="p-1.5 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors disabled:opacity-50"
                title="Delete"
                aria-label="Delete observation"
              >
                {deletingId === obs.id ? (
                  <span className="inline-block w-4 h-4 border-2 border-gray-500/30 border-t-gray-500 rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Expanded view with frame preview */}
          {expandedId === obs.id && (
            <div className="mt-3 rounded-lg overflow-hidden border border-gray-700">
              <img
                src={getObservationFrameUrl(timelineId, obs.id)}
                alt={obs.note}
                className="w-full"
                loading="lazy"
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
