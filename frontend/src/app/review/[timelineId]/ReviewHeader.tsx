"use client";

/**
 * ReviewHeader - Header with title, stats, and export button
 */

import Link from "next/link";
import type { ExportStatus, ExportStatusResponse } from "@/lib/types";
import ExportStatusIndicator from "./ExportStatusIndicator";

interface ReviewStats {
  keep: number;
  drop: number;
  undecided: number;
  total: number;
  progress: number;
}

type OutputMode = "learning" | "watching" | "dubbing";

interface ReviewHeaderProps {
  title: string;
  saving: boolean;
  stats: ReviewStats | null;
  timelineId: string;
  jobId: string;
  mode?: string;
  exportStatus?: ExportStatus;
  onExportClick: () => void;
  onDelete: () => void;
  onShowPreview?: (status: ExportStatusResponse) => void;
  /** Force polling to start (e.g., after starting a new export) */
  forcePolling?: boolean;
  /** Called when export status changes */
  onExportStatusChange?: (status: ExportStatusResponse) => void;
  /** Creative mode toggle */
  isCreativeMode?: boolean;
  onModeChange?: (isCreative: boolean) => void;
  /** Output mode (learning / watching / dubbing) */
  outputMode?: OutputMode;
  onOutputModeChange?: (mode: OutputMode) => void;
}

export default function ReviewHeader({
  title,
  saving,
  stats,
  timelineId,
  jobId,
  exportStatus = "idle",
  mode,
  onExportClick,
  onDelete,
  onShowPreview,
  forcePolling = false,
  onExportStatusChange,
  isCreativeMode = false,
  onModeChange,
  outputMode = "learning",
  onOutputModeChange,
}: ReviewHeaderProps) {
  return (
    <header className="bg-gray-800 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-gray-400 hover:text-white">
          &larr; 返回
        </Link>
        <h1 className="text-lg font-medium truncate max-w-md">{title}</h1>
        {saving && <span className="text-yellow-400 text-sm">保存中...</span>}

        {/* Creative mode toggle */}
        {onModeChange && (
          <div className="flex items-center gap-1 ml-2">
            <button
              onClick={() => onModeChange(false)}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                !isCreativeMode
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              审阅
            </button>
            <button
              onClick={() => onModeChange(true)}
              className={`px-3 py-1 text-sm rounded-lg transition-colors flex items-center gap-1.5 ${
                isCreativeMode
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
              </svg>
              动效字幕
            </button>
          </div>
        )}

        {/* Output mode toggle (learning / watching / dubbing) */}
        {onOutputModeChange && (
          <div className="flex items-center gap-1 ml-2 border-l border-gray-600 pl-3">
            <span className="text-xs text-gray-500 mr-1">模式</span>
            <button
              onClick={() => onOutputModeChange("learning")}
              className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                outputMode === "learning"
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-400 hover:bg-gray-600"
              }`}
              title="学习模式：半屏字幕 + 卡片面板"
            >
              学习
            </button>
            <button
              onClick={() => onOutputModeChange("watching")}
              className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                outputMode === "watching"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-400 hover:bg-gray-600"
              }`}
              title="观影模式：浮动字幕，全宽画面"
            >
              观影
            </button>
            <button
              onClick={() => onOutputModeChange("dubbing")}
              className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                outputMode === "dubbing"
                  ? "bg-orange-600 text-white"
                  : "bg-gray-700 text-gray-400 hover:bg-gray-600"
              }`}
              title="配音模式：无字幕"
            >
              配音
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Export Status Indicator */}
        {(exportStatus !== "idle" || forcePolling) && (
          <ExportStatusIndicator
            timelineId={timelineId}
            jobId={jobId}
            initialStatus={exportStatus}
            onShowPreview={onShowPreview}
            forcePolling={forcePolling}
            onStatusChange={onExportStatusChange}
          />
        )}

        {/* Stats */}
        {stats && (
          <div className="text-sm">
            <span className="text-green-400">{stats.keep} 保留</span>
            {" / "}
            <span className="text-red-400">{stats.drop} 丢弃</span>
            {" / "}
            <span className="text-gray-400">{stats.undecided} 待定</span>
            {" | "}
            <span className="text-blue-400">{Math.round(stats.progress)}%</span>
          </div>
        )}

        {/* Dubbing entry button */}
        {outputMode === "dubbing" && (
          <Link
            href={`/dub/${timelineId}`}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            进入配音
          </Link>
        )}

        {/* Export button */}
        <button
          onClick={onExportClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
        >
          导出
        </button>

        {/* Delete button */}
        <button
          onClick={onDelete}
          className="px-3 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm"
          title="删除此任务"
          aria-label="删除任务"
        >
          🗑️
        </button>
      </div>
    </header>
  );
}
