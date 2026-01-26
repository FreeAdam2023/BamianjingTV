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
  initialStatus?: ExportStatus;
  onStatusChange?: (status: ExportStatusResponse) => void;
}

export default function ExportStatusIndicator({
  timelineId,
  initialStatus = "idle",
  onStatusChange,
}: ExportStatusIndicatorProps) {
  const [status, setStatus] = useState<ExportStatusResponse | null>(null);
  const [polling, setPolling] = useState(false);

  const fetchStatus = useCallback(async () => {
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
    }
  }, [timelineId, onStatusChange]);

  // Start polling when status is active
  useEffect(() => {
    // Start polling if we have an active export
    const shouldPoll = initialStatus === "exporting" || initialStatus === "uploading";

    if (shouldPoll && !polling) {
      console.log("[ExportStatusIndicator] Starting polling, initialStatus:", initialStatus);
      setPolling(true);
      fetchStatus();
    }
  }, [initialStatus, polling, fetchStatus]);

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

  // Don't show anything if idle and no active status
  if (!status && initialStatus === "idle") {
    return null;
  }

  // Use initial status if no status fetched yet
  const currentStatus = status?.status || initialStatus;
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
        return "Exporting";
      case "uploading":
        return "Uploading";
      case "completed":
        return "Complete";
      case "failed":
        return "Failed";
      default:
        return "";
    }
  };

  return (
    <div className="flex items-center gap-2">
      {/* Status indicator */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 rounded-lg">
        {getStatusIcon()}
        <span className="text-sm font-medium">{getStatusLabel()}</span>
        {(currentStatus === "exporting" || currentStatus === "uploading") && (
          <span className="text-sm text-gray-400">{Math.round(progress)}%</span>
        )}
      </div>

      {/* Progress bar */}
      {(currentStatus === "exporting" || currentStatus === "uploading") && (
        <div className="w-24 h-2 bg-gray-600 rounded-full overflow-hidden">
          <div
            className={`h-full ${getStatusColor()} transition-all duration-300`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Message tooltip on hover */}
      {message && (
        <span className="text-xs text-gray-400 max-w-[200px] truncate" title={message}>
          {message}
        </span>
      )}

      {/* YouTube link when completed with YouTube upload */}
      {currentStatus === "completed" && status?.youtube_url && (
        <a
          href={status.youtube_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
            <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
          </svg>
          YouTube
        </a>
      )}

      {/* Error message */}
      {currentStatus === "failed" && status?.error && (
        <span className="text-xs text-red-400 max-w-[200px] truncate" title={status.error}>
          {status.error}
        </span>
      )}
    </div>
  );
}
