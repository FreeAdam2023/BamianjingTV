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
  jobId: string;
  exportStatus?: ExportStatus;
  onExportClick: () => void;
  onDelete: () => void;
  onRegenerateTranslation: () => void;
  regenerating?: boolean;
}

export default function ReviewHeader({
  title,
  saving,
  stats,
  timelineId,
  jobId,
  exportStatus = "idle",
  onExportClick,
  onDelete,
  onRegenerateTranslation,
  regenerating = false,
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

        {/* Regenerate Translation button */}
        <button
          onClick={onRegenerateTranslation}
          disabled={regenerating}
          className="px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded-lg text-sm flex items-center gap-1"
          title="重新生成翻译字幕"
        >
          {regenerating ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              翻译中...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              重新翻译
            </>
          )}
        </button>

        {/* Export button */}
        <button
          onClick={onExportClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
        >
          Export
        </button>

        {/* Delete button */}
        <button
          onClick={onDelete}
          className="px-3 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm"
          title="删除此 Job"
        >
          🗑️
        </button>
      </div>
    </header>
  );
}
