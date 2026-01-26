"use client";

/**
 * BulkActions - Buttons for keep all / drop all / reset all
 */

import { keepAllSegments, dropAllSegments, resetAllSegments } from "@/lib/api";
import { useToast, useConfirm } from "@/components/ui";

interface BulkActionsProps {
  timelineId: string;
}

export default function BulkActions({ timelineId }: BulkActionsProps) {
  const toast = useToast();
  const confirm = useConfirm();

  const handleKeepAll = async () => {
    const confirmed = await confirm({
      title: "全部保留",
      message: "确定要将所有片段标记为保留吗？",
      type: "info",
      confirmText: "全部保留",
    });
    if (confirmed) {
      try {
        const result = await keepAllSegments(timelineId);
        toast.success(`已将 ${result.updated} 个片段标记为保留`);
        window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
    }
  };

  const handleDropAll = async () => {
    const confirmed = await confirm({
      title: "全部丢弃",
      message: "确定要将所有片段标记为丢弃吗？",
      type: "danger",
      confirmText: "全部丢弃",
    });
    if (confirmed) {
      try {
        const result = await dropAllSegments(timelineId);
        toast.success(`已将 ${result.updated} 个片段标记为丢弃`);
        window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
    }
  };

  const handleResetAll = async () => {
    const confirmed = await confirm({
      title: "全部重置",
      message: "确定要将所有片段重置为未决定状态吗？",
      type: "warning",
      confirmText: "重置",
    });
    if (confirmed) {
      try {
        const result = await resetAllSegments(timelineId);
        toast.success(`已重置 ${result.updated} 个片段`);
        window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
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
