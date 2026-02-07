"use client";

/**
 * PinnedCardsTrack - Timeline track showing pinned cards
 * Displays card markers with type-specific colors and timestamps
 */

import { useTimelineContext } from "./TimelineContext";
import type { PinnedCard, PinnedCardType } from "@/lib/types";

interface PinnedCardsTrackProps {
  pinnedCards: PinnedCard[];
  width: number;
  onCardClick?: (card: PinnedCard) => void;
  onCardUnpin?: (cardId: string) => void;
}

// Color scheme for card types
const CARD_TYPE_COLORS: Record<PinnedCardType, { bg: string; border: string; text: string }> = {
  word: {
    bg: "bg-purple-500/30",
    border: "border-purple-400",
    text: "text-purple-300",
  },
  entity: {
    bg: "bg-cyan-500/30",
    border: "border-cyan-400",
    text: "text-cyan-300",
  },
  insight: {
    bg: "bg-yellow-500/30",
    border: "border-yellow-400",
    text: "text-yellow-300",
  },
};

// Format timestamp to MM:SS
function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default function PinnedCardsTrack({
  pinnedCards,
  width,
  onCardClick,
  onCardUnpin,
}: PinnedCardsTrackProps) {
  const { timeToPixels, trackHeight } = useTimelineContext();

  // Sort cards by timestamp
  const sortedCards = [...pinnedCards].sort((a, b) => a.timestamp - b.timestamp);

  return (
    <div
      className="relative flex"
      style={{ width, height: trackHeight }}
    >
      {/* Track label */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-2 bg-gray-800 border-r border-gray-700"
        style={{ width: 96 }}
      >
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 text-purple-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
          </svg>
          <span className="text-xs text-gray-300 font-medium">Cards</span>
        </div>
        <span className="text-xs text-gray-500">{pinnedCards.length}</span>
      </div>

      {/* Track content */}
      <div
        className="relative flex-1 bg-gray-850"
        style={{ backgroundColor: "#1a1d24" }}
      >
        {/* Grid lines background */}
        <div className="absolute inset-0 opacity-20">
          <div
            className="h-full"
            style={{
              backgroundImage: "repeating-linear-gradient(90deg, #374151 0, #374151 1px, transparent 1px, transparent 50px)",
              backgroundSize: "50px 100%",
            }}
          />
        </div>

        {/* Card markers */}
        {sortedCards.map((card) => {
          const startX = timeToPixels(card.display_start);
          const endX = timeToPixels(card.display_end);
          const cardWidth = Math.max(endX - startX, 40); // Minimum width
          const colors = CARD_TYPE_COLORS[card.card_type] || CARD_TYPE_COLORS.word;

          // Get card label
          let label = "";
          if (card.card_data) {
            if (card.card_type === "word") {
              label = (card.card_data as { word?: string }).word || "";
            } else {
              label = (card.card_data as { name?: string }).name || "";
            }
          }

          return (
            <div
              key={card.id}
              className={`absolute top-1 bottom-1 ${colors.bg} ${colors.border} border rounded cursor-pointer
                hover:brightness-125 transition-all group`}
              style={{
                left: startX,
                width: cardWidth,
              }}
              onClick={() => onCardClick?.(card)}
              title={`${card.card_type === "word" ? "Word" : "Entity"}: ${label}\nTime: ${formatTimestamp(card.timestamp)}\nDisplay: ${formatTimestamp(card.display_start)} - ${formatTimestamp(card.display_end)}`}
            >
              {/* Card type icon and label */}
              <div className="absolute inset-0 flex items-center px-1.5 overflow-hidden">
                {card.card_type === "word" ? (
                  <span className={`text-xs font-medium ${colors.text} truncate`}>
                    {label || "Word"}
                  </span>
                ) : (
                  <span className={`text-xs font-medium ${colors.text} truncate`}>
                    {label || "Entity"}
                  </span>
                )}
              </div>

              {/* Unpin button (visible on hover) */}
              {onCardUnpin && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onCardUnpin(card.id);
                  }}
                  className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 hover:bg-red-600 rounded-full
                    flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
                  title="Unpin card"
                >
                  <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}

              {/* Timestamp marker line at pin point */}
              <div
                className={`absolute top-0 bottom-0 w-0.5 ${colors.border.replace("border-", "bg-")}`}
                style={{ left: timeToPixels(card.timestamp) - startX }}
              />
            </div>
          );
        })}

        {/* Empty state */}
        {pinnedCards.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs text-gray-600">No pinned cards - click a word or entity to pin</span>
          </div>
        )}
      </div>
    </div>
  );
}
