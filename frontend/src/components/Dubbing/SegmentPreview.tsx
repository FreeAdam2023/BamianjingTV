"use client";

/**
 * SegmentPreview - Preview dubbed audio for individual segments
 */

import { useState, useRef } from "react";
import type { EditableSegment, SpeakerVoiceConfig, PreviewResponse } from "@/lib/types";
import { previewDubbedSegment, getDubbingPreviewUrl } from "@/lib/api";

interface SegmentPreviewProps {
  timelineId: string;
  segments: EditableSegment[];
  speakers: SpeakerVoiceConfig[];
}

function formatDuration(seconds: number): string {
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, "0")}`;
}

export default function SegmentPreview({
  timelineId,
  segments,
  speakers,
}: SegmentPreviewProps) {
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const hasSamples = speakers.some((s) => s.voice_sample_path && s.is_enabled);
  const activeSegments = segments.filter((s) => s.state !== "drop");

  const handlePreview = async (segment: EditableSegment) => {
    setError(null);

    // Stop current playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      if (playingId === segment.id) {
        setPlayingId(null);
        return;
      }
    }

    setLoadingId(segment.id);

    try {
      const response: PreviewResponse = await previewDubbedSegment(timelineId, {
        segment_id: segment.id,
      });

      // Play audio
      const audio = new Audio(getDubbingPreviewUrl(timelineId, segment.id));
      audioRef.current = audio;

      audio.onplay = () => {
        setPlayingId(segment.id);
        setLoadingId(null);
      };
      audio.onended = () => {
        setPlayingId(null);
        audioRef.current = null;
      };
      audio.onerror = () => {
        setError("Failed to play audio");
        setPlayingId(null);
        setLoadingId(null);
        audioRef.current = null;
      };

      await audio.play();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
      setLoadingId(null);
    }
  };

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">Segment Preview</h3>

      {!hasSamples && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4">
          <p className="text-sm text-yellow-400">
            Speaker samples not yet extracted. Run &quot;Generate Dubbed Video&quot; first to extract voice samples, then you can preview individual segments.
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <div className="space-y-1 max-h-96 overflow-y-auto">
        {activeSegments.map((segment) => {
          const duration = segment.end - segment.start;
          const text = segment.zh || segment.en || "(empty)";
          const isLoading = loadingId === segment.id;
          const isPlaying = playingId === segment.id;

          return (
            <div
              key={segment.id}
              className="flex items-center gap-3 p-2 rounded-lg hover:bg-[var(--background)] transition-colors"
            >
              {/* Segment number */}
              <span className="text-xs text-gray-500 w-8 text-right shrink-0">
                #{segment.id}
              </span>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-300 truncate">{text}</p>
                <p className="text-xs text-gray-600">
                  {formatDuration(duration)}
                  {segment.speaker && ` · ${segment.speaker}`}
                </p>
              </div>

              {/* Preview button */}
              <button
                onClick={() => handlePreview(segment)}
                disabled={!hasSamples || isLoading}
                className="shrink-0 px-3 py-1.5 text-xs rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: isPlaying ? "rgba(239, 68, 68, 0.2)" : "rgba(59, 130, 246, 0.2)",
                  color: isPlaying ? "#ef4444" : "#3b82f6",
                }}
              >
                {isLoading ? (
                  <span className="flex items-center gap-1">
                    <span className="animate-spin rounded-full h-3 w-3 border-t border-b border-blue-500" />
                    Synth...
                  </span>
                ) : isPlaying ? (
                  "Stop"
                ) : (
                  "Preview"
                )}
              </button>
            </div>
          );
        })}

        {activeSegments.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">No active segments.</p>
        )}
      </div>
    </div>
  );
}
