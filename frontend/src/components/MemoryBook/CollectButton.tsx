"use client";

/**
 * CollectButton - Add items to memory book
 */

import { useState, useEffect } from "react";
import type { MemoryItemType, MemoryItemCreate, WordCard, EntityCard } from "@/lib/types";
import {
  getDefaultMemoryBook,
  addMemoryItem,
  checkMemoryItemExists,
  deleteMemoryItem,
} from "@/lib/api";

interface CollectButtonProps {
  targetType: MemoryItemType;
  targetId: string;
  cardData?: WordCard | EntityCard | null;
  sourceTimelineId?: string;
  sourceTimecode?: number;
  sourceSegmentText?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export default function CollectButton({
  targetType,
  targetId,
  cardData,
  sourceTimelineId,
  sourceTimecode,
  sourceSegmentText,
  className = "",
  size = "md",
}: CollectButtonProps) {
  const [isCollected, setIsCollected] = useState(false);
  const [collectedItemId, setCollectedItemId] = useState<string | null>(null);
  const [bookId, setBookId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Check if already collected
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const book = await getDefaultMemoryBook();
        setBookId(book.book_id);
        const result = await checkMemoryItemExists(book.book_id, targetType, targetId);
        setIsCollected(result.exists);
        setCollectedItemId(result.item_id);
      } catch (err) {
        console.error("Failed to check collection status:", err);
      } finally {
        setLoading(false);
      }
    };
    checkStatus();
  }, [targetType, targetId]);

  const handleToggle = async () => {
    if (!bookId) return;
    setSaving(true);

    try {
      if (isCollected && collectedItemId) {
        // Remove from collection
        await deleteMemoryItem(bookId, collectedItemId);
        setIsCollected(false);
        setCollectedItemId(null);
      } else {
        // Add to collection
        const data: MemoryItemCreate = {
          target_type: targetType,
          target_id: targetId,
          source_timeline_id: sourceTimelineId,
          source_timecode: sourceTimecode,
          source_segment_text: sourceSegmentText,
          card_data: cardData ? (cardData as unknown as Record<string, unknown>) : undefined,
        };
        const item = await addMemoryItem(bookId, data);
        setIsCollected(true);
        setCollectedItemId(item.item_id);
      }
    } catch (err) {
      console.error("Failed to toggle collection:", err);
    } finally {
      setSaving(false);
    }
  };

  const sizeClasses = {
    sm: "p-1",
    md: "p-1.5",
    lg: "p-2",
  };

  const iconSizes = {
    sm: "w-3.5 h-3.5",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  };

  if (loading) {
    return (
      <button
        disabled
        className={`rounded ${sizeClasses[size]} text-gray-500 ${className}`}
      >
        <span className={`inline-block ${iconSizes[size]} border-2 border-gray-500/30 border-t-gray-500 rounded-full animate-spin`} />
      </button>
    );
  }

  return (
    <button
      onClick={handleToggle}
      disabled={saving}
      className={`
        rounded transition-colors
        ${sizeClasses[size]}
        ${isCollected
          ? "text-yellow-500 hover:text-yellow-400 bg-yellow-500/10 hover:bg-yellow-500/20"
          : "text-gray-500 hover:text-yellow-400 hover:bg-gray-700"
        }
        disabled:opacity-50
        ${className}
      `}
      title={isCollected ? "从收藏中移除" : "添加到收藏"}
    >
      {saving ? (
        <span className={`inline-block ${iconSizes[size]} border-2 border-current/30 border-t-current rounded-full animate-spin`} />
      ) : (
        <svg
          className={iconSizes[size]}
          fill={isCollected ? "currentColor" : "none"}
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
          />
        </svg>
      )}
    </button>
  );
}
