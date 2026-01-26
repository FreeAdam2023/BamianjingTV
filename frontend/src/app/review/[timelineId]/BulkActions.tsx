"use client";

/**
 * BulkActions - Buttons for keep all / drop all / reset all
 */

import { keepAllSegments, dropAllSegments, resetAllSegments } from "@/lib/api";

interface BulkActionsProps {
  timelineId: string;
}

export default function BulkActions({ timelineId }: BulkActionsProps) {
  const handleKeepAll = async () => {
    if (confirm("Mark all segments as KEEP?")) {
      await keepAllSegments(timelineId);
      window.location.reload();
    }
  };

  const handleDropAll = async () => {
    if (confirm("Mark all segments as DROP?")) {
      await dropAllSegments(timelineId);
      window.location.reload();
    }
  };

  const handleResetAll = async () => {
    if (confirm("Reset all segments to UNDECIDED?")) {
      await resetAllSegments(timelineId);
      window.location.reload();
    }
  };

  return (
    <div className="p-2 border-b border-gray-700 flex gap-2">
      <button
        onClick={handleKeepAll}
        className="flex-1 py-1 text-xs bg-green-600 hover:bg-green-700 rounded"
      >
        Keep All
      </button>
      <button
        onClick={handleDropAll}
        className="flex-1 py-1 text-xs bg-red-600 hover:bg-red-700 rounded"
      >
        Drop All
      </button>
      <button
        onClick={handleResetAll}
        className="flex-1 py-1 text-xs bg-gray-600 hover:bg-gray-700 rounded"
      >
        Reset
      </button>
    </div>
  );
}
