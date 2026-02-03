"use client";

/**
 * ObservationMarkers - Display observation markers on the timeline
 */

import { useMemo } from "react";
import type { Observation } from "@/lib/types";
import { getObservationTagColor, getObservationTagLabel } from "@/lib/api";

interface ObservationMarkersProps {
  observations: Observation[];
  duration: number;
  zoom: number; // pixels per second
  scrollX: number; // scroll offset in pixels
  onMarkerClick?: (observation: Observation) => void;
}

export default function ObservationMarkers({
  observations,
  duration,
  zoom,
  scrollX,
  onMarkerClick,
}: ObservationMarkersProps) {
  const markers = useMemo(() => {
    return observations.map((obs) => ({
      ...obs,
      position: obs.timecode * zoom - scrollX,
    }));
  }, [observations, zoom, scrollX]);

  if (!observations.length) return null;

  return (
    <div className="absolute inset-0 pointer-events-none">
      {markers.map((obs) => {
        // Skip markers outside visible area
        if (obs.position < -20 || obs.position > window.innerWidth + 20) {
          return null;
        }

        return (
          <div
            key={obs.id}
            className="absolute top-0 bottom-0 pointer-events-auto cursor-pointer group"
            style={{ left: `${obs.position}px` }}
            onClick={() => onMarkerClick?.(obs)}
            title={`${getObservationTagLabel(obs.tag)}: ${obs.note}`}
          >
            {/* Marker line */}
            <div className="w-0.5 h-full bg-yellow-500/50 group-hover:bg-yellow-400" />

            {/* Marker icon */}
            <div
              className={`absolute -top-1 -left-2 w-4 h-4 rounded-full ${getObservationTagColor(obs.tag)} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform`}
            >
              <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4 5a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V7a2 2 0 00-2-2h-1.586a1 1 0 01-.707-.293l-1.121-1.121A2 2 0 0011.172 3H8.828a2 2 0 00-1.414.586L6.293 4.707A1 1 0 015.586 5H4zm6 9a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
              </svg>
            </div>

            {/* Tooltip on hover */}
            <div className="absolute top-5 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
              <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl whitespace-nowrap max-w-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-xs ${getObservationTagColor(obs.tag)}`}>
                    {getObservationTagLabel(obs.tag)}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatTime(obs.timecode)}
                  </span>
                </div>
                <p className="text-sm text-gray-300 truncate max-w-[200px]">
                  {obs.note}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
