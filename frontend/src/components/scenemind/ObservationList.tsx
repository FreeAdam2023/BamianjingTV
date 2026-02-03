"use client";

import type { Observation } from "@/lib/scenemind-api";
import {
  formatTimecode,
  getTagColor,
  getTagLabel,
  getFrameUrlFromPath,
} from "@/lib/scenemind-api";

interface ObservationListProps {
  sessionId: string;
  observations: Observation[];
  onDelete: (observationId: string) => void;
  onSeek: (timecode: number) => void;
}

export default function ObservationList({
  sessionId,
  observations,
  onDelete,
  onSeek,
}: ObservationListProps) {
  if (observations.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <svg
          className="w-12 h-12 mx-auto mb-3 opacity-50"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        <p>No observations yet</p>
        <p className="text-sm mt-1">
          Press <kbd className="px-1.5 py-0.5 bg-gray-700 rounded">S</kbd> to
          capture
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {observations.map((obs) => (
        <div
          key={obs.id}
          className="card card-hover p-3 cursor-pointer"
          onClick={() => onSeek(obs.timecode)}
        >
          <div className="flex gap-3">
            {/* Thumbnail */}
            <div className="w-24 h-16 flex-shrink-0 rounded overflow-hidden bg-gray-800">
              <img
                src={getFrameUrlFromPath(sessionId, obs.crop_path || obs.frame_path)}
                alt="Observation"
                className="w-full h-full object-cover"
              />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-mono text-gray-400">
                  {formatTimecode(obs.timecode)}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${getTagColor(
                    obs.tag
                  )} text-white`}
                >
                  {getTagLabel(obs.tag)}
                </span>
              </div>
              <p className="text-sm text-gray-300 line-clamp-2">{obs.note}</p>
            </div>

            {/* Delete button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(obs.id);
              }}
              className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors flex-shrink-0"
              title="Delete observation"
              aria-label="Delete observation"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
