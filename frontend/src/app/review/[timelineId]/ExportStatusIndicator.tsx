"use client";

/**
 * ExportStatusIndicator - Shows export/upload progress status
 * Can be used in header to show progress even after closing export panel
 */

import { useEffect, useState, useCallback } from "react";
import type { ExportStatus, ExportStatusResponse } from "@/lib/types";
import { getExportStatus } from "@/lib/api";

interface ExportStatusIndicatorProps {
  timelineId: string;
  jobId: string;
  initialStatus?: ExportStatus;
  onStatusChange?: (status: ExportStatusResponse) => void;
  onShowPreview?: (status: ExportStatusResponse) => void;
  /** Force start polling (e.g., after starting a new export) */
  forcePolling?: boolean;
}

export default function ExportStatusIndicator({
  timelineId,
  jobId,
  initialStatus = "idle",
  onStatusChange,
  onShowPreview,
  forcePolling = false,
}: ExportStatusIndicatorProps) {
  const [status, setStatus] = useState<ExportStatusResponse | null>(null);
  const [polling, setPolling] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getExportStatus(timelineId);
      console.log("[ExportStatusIndicator] Status update:", {
        status: result.status,
        progress: result.progress,
        message: result.message,
      });
      setStatus(result);
      onStatusChange?.(result);
      return result;
    } catch (err) {
      console.error("[ExportStatusIndicator] Failed to fetch status:", err);
      return null;
    } finally {
      setLoading(false);
    }
  }, [timelineId, onStatusChange]);

  // Fetch status on mount if we have a completed/failed status (to get full details)
  useEffect(() => {
    if ((initialStatus === "completed" || initialStatus === "failed") && !status) {
      console.log("[ExportStatusIndicator] Fetching status for completed/failed state");
      fetchStatus();
    }
  }, [initialStatus, status, fetchStatus]);

  // Start polling when status is active or forcePolling is true
  useEffect(() => {
    // Start polling if we have an active export or force polling
    const shouldPoll = forcePolling || initialStatus === "exporting" || initialStatus === "uploading";

    if (shouldPoll && !polling) {
      console.log("[ExportStatusIndicator] Starting polling, initialStatus:", initialStatus, "forcePolling:", forcePolling);
      setPolling(true);
      fetchStatus();
    }
  }, [initialStatus, polling, fetchStatus, forcePolling]);

  // Polling loop
  useEffect(() => {
    if (!polling) return;

    console.log("[ExportStatusIndicator] Polling started");
    const interval = setInterval(async () => {
      const result = await fetchStatus();

      // Stop polling when completed or failed
      if (result && (result.status === "completed" || result.status === "failed" || result.status === "idle")) {
        console.log("[ExportStatusIndicator] Polling stopped, final status:", result.status);
        setPolling(false);
      }
    }, 2000); // Poll every 2 seconds

    return () => {
      console.log("[ExportStatusIndicator] Polling cleanup");
      clearInterval(interval);
    };
  }, [polling, fetchStatus]);

  // Don't show anything if idle and no active status (unless force polling)
  if (!status && initialStatus === "idle" && !forcePolling) {
    return null;
  }

  // Use initial status if no status fetched yet
  // When forcePolling is true and no status yet, show "exporting" to indicate we're starting
  const currentStatus = status?.status || (forcePolling && !status ? "exporting" : initialStatus);
  const progress = status?.progress || 0;
  const message = status?.message || "";

  // Don't show for idle status
  if (currentStatus === "idle") {
    return null;
  }

  const getStatusColor = () => {
    switch (currentStatus) {
      case "exporting":
        return "bg-blue-500";
      case "uploading":
        return "bg-purple-500";
      case "completed":
        return "bg-green-500";
      case "failed":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  const getStatusIcon = () => {
    switch (currentStatus) {
      case "exporting":
      case "uploading":
        return (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        );
      case "completed":
        return (
          <svg className="h-4 w-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case "failed":
        return (
          <svg className="h-4 w-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      default:
        return null;
    }
  };

  const getStatusLabel = () => {
    switch (currentStatus) {
      case "exporting":
        return "导出中";
      case "uploading":
        return "上传中";
      case "completed":
        return "完成";
      case "failed":
        return "失败";
      default:
        return "";
    }
  };

  const isActive = currentStatus === "exporting" || currentStatus === "uploading";

  return (
    <div className={`flex items-center gap-3 px-4 py-2 rounded-lg ${
      isActive ? "bg-blue-500/15 border border-blue-500/30" :
      currentStatus === "completed" ? "bg-green-500/15 border border-green-500/30" :
      currentStatus === "failed" ? "bg-red-500/15 border border-red-500/30" :
      "bg-gray-700"
    }`}>
      {/* Icon */}
      {getStatusIcon()}

      {/* Label + progress */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{getStatusLabel()}</span>
          {isActive && (
            <span className="text-sm font-bold text-blue-300">{Math.round(progress)}%</span>
          )}
          {message && (
            <span className="text-xs text-gray-400 max-w-[200px] truncate" title={message}>
              {message}
            </span>
          )}
        </div>

        {/* Progress bar — wider and taller */}
        {isActive && (
          <div className="w-48 h-2.5 bg-gray-600 rounded-full overflow-hidden">
            <div
              className={`h-full ${getStatusColor()} transition-all duration-300 rounded-full`}
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Actions when completed */}
      {currentStatus === "completed" && (
        <>
          {loading && !status && (
            <span className="text-xs text-gray-400">加载中...</span>
          )}
          {!status?.youtube_url && onShowPreview && status && (
            <button
              onClick={() => onShowPreview(status)}
              className="px-4 py-1.5 text-sm font-medium bg-green-600 hover:bg-green-700 rounded-lg flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              预览 & 上传
            </button>
          )}
          {status?.youtube_url && (
            <a
              href={status.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-1.5 text-sm font-medium bg-red-600 hover:bg-red-700 rounded-lg flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
              </svg>
              查看 YouTube
            </a>
          )}
        </>
      )}

      {/* Actions when failed */}
      {currentStatus === "failed" && (
        <>
          {status?.error && (
            <span className="text-xs text-red-400 max-w-[200px] truncate" title={status.error}>
              {status.error.slice(0, 50)}...
            </span>
          )}
          {status?.full_video_path && onShowPreview && (
            <button
              onClick={() => onShowPreview(status)}
              className="px-4 py-1.5 text-sm font-medium bg-yellow-600 hover:bg-yellow-700 rounded-lg flex items-center gap-1.5"
              title="视频已导出，点击重试上传"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              重试上传
            </button>
          )}
        </>
      )}
    </div>
  );
}
