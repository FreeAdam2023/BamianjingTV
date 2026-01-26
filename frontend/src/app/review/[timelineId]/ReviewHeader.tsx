"use client";

/**
 * ReviewHeader - Header with title, stats, and export button
 */

import Link from "next/link";
import type { ExportStatus } from "@/lib/types";
import ExportStatusIndicator from "./ExportStatusIndicator";

interface ReviewStats {
  keep: number;
  drop: number;
  undecided: number;
  total: number;
  progress: number;
}

interface ReviewHeaderProps {
  title: string;
  saving: boolean;
  stats: ReviewStats | null;
  timelineId: string;
  exportStatus?: ExportStatus;
  onExportClick: () => void;
}

export default function ReviewHeader({
  title,
  saving,
  stats,
  timelineId,
  exportStatus = "idle",
  onExportClick,
}: ReviewHeaderProps) {
  return (
    <header className="bg-gray-800 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-gray-400 hover:text-white">
          &larr; Back
        </Link>
        <h1 className="text-lg font-medium truncate max-w-md">{title}</h1>
        {saving && <span className="text-yellow-400 text-sm">Saving...</span>}
      </div>

      <div className="flex items-center gap-4">
        {/* Export Status Indicator */}
        {exportStatus !== "idle" && (
          <ExportStatusIndicator
            timelineId={timelineId}
            initialStatus={exportStatus}
          />
        )}

        {/* Stats */}
        {stats && (
          <div className="text-sm">
            <span className="text-green-400">{stats.keep} keep</span>
            {" / "}
            <span className="text-red-400">{stats.drop} drop</span>
            {" / "}
            <span className="text-gray-400">{stats.undecided} pending</span>
            {" | "}
            <span className="text-blue-400">{Math.round(stats.progress)}%</span>
          </div>
        )}

        {/* Export button */}
        <button
          onClick={onExportClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
        >
          Export
        </button>
      </div>
    </header>
  );
}
