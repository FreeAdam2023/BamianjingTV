"use client";

import React, { useState, useEffect, useCallback } from "react";
import type { RemotionConfig } from "@/lib/creative-types";
import {
  startCreativeRender,
  getCreativeRenderStatus,
  saveCreativeConfig,
  getCreativeExportUrl,
  type CreativeRenderStatusResponse,
} from "@/lib/api";

interface RemotionExportPanelProps {
  timelineId: string;
  jobId: string;
  config: RemotionConfig;
  onClose?: () => void;
}

export default function RemotionExportPanel({
  timelineId,
  jobId,
  config,
  onClose,
}: RemotionExportPanelProps) {
  const [status, setStatus] = useState<CreativeRenderStatusResponse | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll for status while rendering
  useEffect(() => {
    if (!status || status.status === "idle") return;
    if (status.status === "completed" || status.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const newStatus = await getCreativeRenderStatus(timelineId);
        setStatus(newStatus);
      } catch (err) {
        console.error("Failed to get render status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [timelineId, status?.status]);

  // Load initial status
  useEffect(() => {
    getCreativeRenderStatus(timelineId)
      .then(setStatus)
      .catch(() => {
        // No existing job, that's fine
        setStatus({ timeline_id: timelineId, status: "idle", progress: 0 });
      });
  }, [timelineId]);

  const handleStartRender = useCallback(async () => {
    setIsStarting(true);
    setError(null);

    try {
      // Save config first
      await saveCreativeConfig(timelineId, config);

      // Start render
      const response = await startCreativeRender(timelineId, {
        config,
        options: {
          fps: 30,
          quality: "high",
        },
      });

      setStatus({
        timeline_id: timelineId,
        status: "queued",
        progress: 0,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start render");
    } finally {
      setIsStarting(false);
    }
  }, [timelineId, config]);

  const handleDownload = useCallback(() => {
    const url = getCreativeExportUrl(jobId);
    window.open(url, "_blank");
  }, [jobId]);

  const isRendering = status?.status === "queued" || status?.status === "rendering";
  const isComplete = status?.status === "completed";
  const isFailed = status?.status === "failed";

  return (
    <div className="border-t border-gray-700 p-3">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span className="text-sm font-medium text-gray-200">Creative Export</span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Status display */}
      {status && status.status !== "idle" && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-400">
              {status.status === "queued" && "Queued..."}
              {status.status === "rendering" && "Rendering..."}
              {status.status === "completed" && "Complete!"}
              {status.status === "failed" && "Failed"}
            </span>
            <span className="text-gray-400">{status.progress}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                isComplete ? "bg-green-500" : isFailed ? "bg-red-500" : "bg-purple-500"
              }`}
              style={{ width: `${status.progress}%` }}
            />
          </div>
          {status.error && (
            <p className="text-xs text-red-400 mt-1">{status.error}</p>
          )}
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="mb-3 p-2 bg-red-500/20 border border-red-500/50 rounded text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {!isRendering && !isComplete && (
          <button
            onClick={handleStartRender}
            disabled={isStarting}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-600/50 text-white text-sm rounded-lg transition-colors"
          >
            {isStarting ? (
              <>
                <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                Starting...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Render Video
              </>
            )}
          </button>
        )}

        {isRendering && (
          <button
            disabled
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-gray-600 text-gray-300 text-sm rounded-lg cursor-not-allowed"
          >
            <span className="animate-spin w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full" />
            Rendering... {status?.progress}%
          </button>
        )}

        {isComplete && (
          <>
            <button
              onClick={handleDownload}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download
            </button>
            <button
              onClick={handleStartRender}
              disabled={isStarting}
              className="px-3 py-2 bg-gray-600 hover:bg-gray-500 text-white text-sm rounded-lg transition-colors"
              title="Re-render with current settings"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </>
        )}

        {isFailed && (
          <button
            onClick={handleStartRender}
            disabled={isStarting}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-orange-600 hover:bg-orange-500 text-white text-sm rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Retry
          </button>
        )}
      </div>

      {/* Info text */}
      <p className="mt-2 text-xs text-gray-500">
        {isRendering
          ? "Rendering may take several minutes depending on video length."
          : isComplete
          ? "Video rendered with Remotion dynamic subtitles."
          : "Export video with animated subtitles powered by Remotion."}
      </p>
    </div>
  );
}
