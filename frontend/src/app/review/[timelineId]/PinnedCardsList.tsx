"use client";

/**
 * PinnedCardsList - Collapsible panel showing pinned cards with timestamps
 */

import { useState, useCallback } from "react";
import type { PinnedCard, PinnedCardType } from "@/lib/types";
import { unpinCard, getPinnedCardsDescription } from "@/lib/api";

interface PinnedCardsListProps {
  timelineId: string;
  pinnedCards: PinnedCard[];
  onCardClick: (card: PinnedCard) => void;
  onRefresh: () => void;
}

// Format timestamp to MM:SS
function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// Card type colors and labels
const CARD_TYPE_CONFIG: Record<PinnedCardType, { color: string; bgColor: string; label: string }> = {
  word: { color: "text-purple-400", bgColor: "bg-purple-500/20", label: "Word" },
  entity: { color: "text-cyan-400", bgColor: "bg-cyan-500/20", label: "Entity" },
  idiom: { color: "text-amber-400", bgColor: "bg-amber-500/20", label: "Idiom" },
  insight: { color: "text-yellow-400", bgColor: "bg-yellow-500/20", label: "Insight" },
};

export default function PinnedCardsList({
  timelineId,
  pinnedCards,
  onCardClick,
  onRefresh,
}: PinnedCardsListProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copying, setCopying] = useState(false);
  const [unpinning, setUnpinning] = useState<string | null>(null);

  // Handle unpin card
  const handleUnpin = useCallback(async (cardId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setUnpinning(cardId);
    try {
      await unpinCard(timelineId, cardId);
      onRefresh();
    } catch (err) {
      console.error("Failed to unpin card:", err);
    } finally {
      setUnpinning(null);
    }
  }, [timelineId, onRefresh]);

  // Copy description to clipboard
  const handleCopyDescription = useCallback(async () => {
    setCopying(true);
    try {
      const result = await getPinnedCardsDescription(timelineId, true);
      await navigator.clipboard.writeText(result.description);
      // Could add a toast here
    } catch (err) {
      console.error("Failed to copy description:", err);
    } finally {
      setCopying(false);
    }
  }, [timelineId]);

  // Sort cards by timestamp
  const sortedCards = [...pinnedCards].sort((a, b) => a.timestamp - b.timestamp);

  // Count by type
  const wordCount = pinnedCards.filter(c => c.card_type === "word").length;
  const entityCount = pinnedCards.filter(c => c.card_type === "entity").length;

  if (pinnedCards.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-gray-700">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2 bg-gray-800/50 hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-4 h-4 text-purple-400 transition-transform ${isExpanded ? "rotate-90" : ""}`}
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
          </svg>
          <span className="text-sm font-medium text-gray-200">Pinned Cards</span>
          <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">
            {pinnedCards.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {wordCount > 0 && (
            <span className="text-xs text-purple-400">{wordCount} words</span>
          )}
          {entityCount > 0 && (
            <span className="text-xs text-cyan-400">{entityCount} entities</span>
          )}
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="max-h-48 overflow-y-auto">
          {/* Card list */}
          {sortedCards.map((card) => {
            const config = CARD_TYPE_CONFIG[card.card_type];
            const label = card.card_data
              ? card.card_type === "word"
                ? (card.card_data as { word?: string }).word
                : (card.card_data as { name?: string }).name
              : "Unknown";

            return (
              <div
                key={card.id}
                onClick={() => onCardClick(card)}
                className="flex items-center gap-2 px-4 py-2 hover:bg-gray-800/50 cursor-pointer group"
              >
                {/* Timestamp */}
                <span className="text-xs text-gray-500 font-mono w-12 flex-shrink-0">
                  {formatTimestamp(card.timestamp)}
                </span>

                {/* Type badge */}
                <span className={`px-1.5 py-0.5 text-xs ${config.bgColor} ${config.color} rounded`}>
                  {config.label}
                </span>

                {/* Card label */}
                <span className="text-sm text-gray-300 truncate flex-1">
                  {label}
                </span>

                {/* Display duration */}
                <span className="text-xs text-gray-600">
                  {Math.round(card.display_end - card.display_start)}s
                </span>

                {/* Unpin button */}
                <button
                  onClick={(e) => handleUnpin(card.id, e)}
                  disabled={unpinning === card.id}
                  className="p-1 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Unpin"
                >
                  {unpinning === card.id ? (
                    <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                </button>
              </div>
            );
          })}

          {/* Copy description button */}
          <div className="px-4 py-2 border-t border-gray-700/50">
            <button
              onClick={handleCopyDescription}
              disabled={copying}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors disabled:opacity-50"
            >
              {copying ? (
                <>
                  <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
                  Copying...
                </>
              ) : (
                <>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy for YouTube Description
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
