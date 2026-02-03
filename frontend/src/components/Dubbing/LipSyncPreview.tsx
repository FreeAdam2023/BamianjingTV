"use client";

/**
 * LipSyncPreview - Preview and control lip sync processing
 */

import { useState, useEffect, useRef } from "react";
import type { LipSyncStatus, DubbingStatus } from "@/lib/types";
import {
  getLipSyncStatus,
  triggerLipSync,
  getLipSyncedVideoUrl,
  getDubbedVideoUrl,
} from "@/lib/api";

interface LipSyncPreviewProps {
  timelineId: string;
  dubbingStatus: DubbingStatus;
}

export default function LipSyncPreview({
  timelineId,
  dubbingStatus,
}: LipSyncPreviewProps) {
  const [lipSyncStatus, setLipSyncStatus] = useState<LipSyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Load initial status
  useEffect(() => {
    const loadStatus = async () => {
      try {
        setLoading(true);
        const status = await getLipSyncStatus(timelineId);
        setLipSyncStatus(status);
      } catch (err) {
        console.error("Failed to load lip sync status:", err);
      } finally {
        setLoading(false);
      }
    };

    loadStatus();
  }, [timelineId]);

  // Poll for status updates when processing
  useEffect(() => {
    if (!lipSyncStatus) return;

    const isProcessing = ["detecting_faces", "processing"].includes(lipSyncStatus.status);
    if (!isProcessing) return;

    const interval = setInterval(async () => {
      try {
        const status = await getLipSyncStatus(timelineId);
        setLipSyncStatus(status);
      } catch (err) {
        console.error("Failed to poll lip sync status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [timelineId, lipSyncStatus?.status]);

  const handleStartLipSync = async () => {
    try {
      setError(null);
      await triggerLipSync(timelineId);
      setLipSyncStatus({ ...lipSyncStatus!, status: "detecting_faces" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start lip sync");
    }
  };

  // Check if dubbing is complete
  const isDubbingComplete = dubbingStatus.status === "completed";

  // Get video URL based on status
  const getVideoUrl = () => {
    if (lipSyncStatus?.status === "completed") {
      return getLipSyncedVideoUrl(timelineId);
    }
    if (isDubbingComplete) {
      return getDubbedVideoUrl(timelineId);
    }
    return null;
  };

  const videoUrl = getVideoUrl();

  if (loading) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500" />
        </div>
      </div>
    );
  }

  const isProcessing = lipSyncStatus?.status === "detecting_faces" || lipSyncStatus?.status === "processing";

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <h3 className="text-sm font-medium text-gray-200">Lip Sync (Wav2Lip)</h3>
        </div>
        <div className="flex items-center gap-2">
          {lipSyncStatus?.status === "completed" && (
            <span className="text-xs text-green-500 flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Lip synced
            </span>
          )}
          {lipSyncStatus?.status === "skipped" && (
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
              No faces detected
            </span>
          )}
        </div>
      </div>

      {/* Video Preview */}
      <div className="aspect-video bg-black relative">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            className="w-full h-full"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500">
            {isDubbingComplete ? (
              <p>Ready for lip sync</p>
            ) : (
              <p>Complete dubbing first</p>
            )}
          </div>
        )}
      </div>

      {/* Status and Controls */}
      <div className="p-4 space-y-4">
        {/* Progress */}
        {isProcessing && lipSyncStatus && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-300">
                {lipSyncStatus.current_step || "Processing..."}
              </span>
              <span className="text-sm text-gray-500">{lipSyncStatus.progress}%</span>
            </div>
            <div className="progress-bar">
              <div
                className="progress-fill progress-fill-accent"
                style={{ width: `${lipSyncStatus.progress}%` }}
              />
            </div>
            {lipSyncStatus.faces_detected > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                {lipSyncStatus.faces_detected} face(s) detected
              </p>
            )}
          </div>
        )}

        {/* Error */}
        {(lipSyncStatus?.error || error) && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
            {lipSyncStatus?.error || error}
          </div>
        )}

        {/* Action Button */}
        {isDubbingComplete && lipSyncStatus?.status !== "completed" && (
          <button
            onClick={handleStartLipSync}
            disabled={isProcessing}
            className="w-full px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-600/50 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {isProcessing ? (
              <>
                <span className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white" />
                Processing Lip Sync...
              </>
            ) : lipSyncStatus?.status === "skipped" ? (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Retry Lip Sync
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Apply Lip Sync
              </>
            )}
          </button>
        )}

        {/* Download Button */}
        {lipSyncStatus?.status === "completed" && videoUrl && (
          <a
            href={videoUrl}
            download={`lip_synced_${timelineId}.mp4`}
            className="w-full px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download Lip-Synced Video
          </a>
        )}

        {/* Info */}
        <p className="text-xs text-gray-500">
          Lip sync uses Wav2Lip to match mouth movements with the dubbed audio.
          This is optional and works best with close-up face shots.
        </p>
      </div>
    </div>
  );
}
