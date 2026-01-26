"use client";

/**
 * ReviewHeader - Header with title, stats, and export button
 */

import Link from "next/link";

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
  useTraditional: boolean;
  converting: boolean;
  onExportClick: () => void;
  onConvertChinese: (toTraditional: boolean) => void;
}

export default function ReviewHeader({
  title,
  saving,
  stats,
  useTraditional,
  converting,
  onExportClick,
  onConvertChinese,
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

        {/* Chinese Toggle */}
        <div className="flex items-center gap-1 bg-gray-700 rounded-lg p-1">
          <button
            onClick={() => onConvertChinese(false)}
            disabled={converting || !useTraditional}
            className={`px-3 py-1 text-sm rounded transition-colors ${
              !useTraditional
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-600"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
            title="Convert to Simplified Chinese"
          >
            {converting && !useTraditional ? (
              <span className="flex items-center gap-1">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                简
              </span>
            ) : (
              "简"
            )}
          </button>
          <button
            onClick={() => onConvertChinese(true)}
            disabled={converting || useTraditional}
            className={`px-3 py-1 text-sm rounded transition-colors ${
              useTraditional
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-600"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
            title="Convert to Traditional Chinese"
          >
            {converting && useTraditional ? (
              <span className="flex items-center gap-1">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                繁
              </span>
            ) : (
              "繁"
            )}
          </button>
        </div>

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
