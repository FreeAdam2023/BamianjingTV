"use client";

/**
 * PinnedCardOverlay - Renders compact mini-cards over the video area
 * during playback when currentTime falls within a card's display window.
 *
 * Caps at MAX_VISIBLE simultaneous cards, always showing the newest.
 * Bumped or expired cards exit with a smooth slide-out animation.
 */

import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import type {
  PinnedCard,
  WordCard,
  EntityCard,
  IdiomCard,
  InsightCard,
} from "@/lib/types";

interface PinnedCardOverlayProps {
  pinnedCards: PinnedCard[];
  currentTime: number;
}

/** Max cards visible at once — one card displays cleanly without clutter */
const MAX_VISIBLE = 1;

// Color config per card type
const CARD_COLORS: Record<string, { border: string; badge: string }> = {
  word: { border: "border-l-blue-400", badge: "bg-blue-500/20 text-blue-300" },
  entity: { border: "border-l-cyan-400", badge: "bg-cyan-500/20 text-cyan-300" },
  idiom: { border: "border-l-amber-400", badge: "bg-amber-500/20 text-amber-300" },
  insight: { border: "border-l-purple-400", badge: "bg-purple-500/20 text-purple-300" },
};

function WordMiniCard({ card }: { card: WordCard }) {
  const ipa = card.pronunciations?.[0]?.ipa;
  const firstSense = card.senses?.[0];
  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline gap-2">
        <span className="font-bold text-white text-sm">{card.word}</span>
        {ipa && <span className="text-blue-300 text-xs">/{ipa}/</span>}
        {card.cefr_level && (
          <span className="text-[10px] px-1 py-0.5 rounded bg-blue-500/20 text-blue-300 leading-none">
            {card.cefr_level}
          </span>
        )}
      </div>
      {firstSense && (
        <p className="text-gray-300 text-xs leading-snug line-clamp-2">
          <span className="text-blue-300/70 text-[10px] mr-1">{firstSense.part_of_speech}</span>
          {firstSense.definition_zh || firstSense.definition}
        </p>
      )}
    </div>
  );
}

function EntityMiniCard({ card }: { card: EntityCard }) {
  const zhName = card.localizations?.zh?.name;
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 leading-none capitalize">
          {card.entity_type}
        </span>
        <span className="font-bold text-white text-sm truncate">{card.name}</span>
      </div>
      {zhName && zhName !== card.name && (
        <p className="text-cyan-200/60 text-xs">{zhName}</p>
      )}
      <p className="text-gray-300 text-xs leading-snug line-clamp-2">
        {card.localizations?.zh?.description || card.description}
      </p>
    </div>
  );
}

function IdiomMiniCard({ card }: { card: IdiomCard }) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 leading-none capitalize">
          {card.category}
        </span>
        <span className="font-bold text-amber-200 text-sm truncate">{card.text}</span>
      </div>
      <p className="text-gray-300 text-xs leading-snug line-clamp-2">
        {card.meaning_localized || card.meaning_original}
      </p>
    </div>
  );
}

function InsightMiniCard({ card }: { card: InsightCard }) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 leading-none capitalize">
          {card.category}
        </span>
        <span className="font-bold text-purple-200 text-sm truncate">{card.title}</span>
      </div>
      <p className="text-gray-300 text-xs leading-snug line-clamp-2">{card.content}</p>
    </div>
  );
}

function MiniCard({ pinnedCard }: { pinnedCard: PinnedCard }) {
  const colors = CARD_COLORS[pinnedCard.card_type] || CARD_COLORS.word;
  const data = pinnedCard.card_data;

  return (
    <div
      className={`rounded-lg border-l-2 ${colors.border} backdrop-blur-sm px-3 py-2 w-[260px] shadow-lg`}
      style={{ backgroundColor: "rgba(26, 39, 68, 0.92)" }}
    >
      {pinnedCard.card_type === "word" && data && (
        <WordMiniCard card={data as WordCard} />
      )}
      {pinnedCard.card_type === "entity" && data && (
        <EntityMiniCard card={data as EntityCard} />
      )}
      {pinnedCard.card_type === "idiom" && data && (
        <IdiomMiniCard card={data as IdiomCard} />
      )}
      {pinnedCard.card_type === "insight" && data && (
        <InsightMiniCard card={data as InsightCard} />
      )}
      {!data && (
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${colors.badge} leading-none`}>
            {pinnedCard.card_type}
          </span>
          <span className="text-white/50 text-xs">{pinnedCard.card_id}</span>
        </div>
      )}
    </div>
  );
}

/** Slides in from right on mount */
function EnteringCard({ pinnedCard }: { pinnedCard: PinnedCard }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      className="transition-all duration-300 ease-out"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateX(0)" : "translateX(24px)",
      }}
    >
      <MiniCard pinnedCard={pinnedCard} />
    </div>
  );
}

/** Starts visible, then slides out to right and fades. Calls onDone after transition. */
function ExitingCard({ pinnedCard, onDone }: { pinnedCard: PinnedCard; onDone: (id: string) => void }) {
  const [gone, setGone] = useState(false);

  useEffect(() => {
    // Kick off exit on next frame so the browser paints at opacity 1 first
    const raf = requestAnimationFrame(() => setGone(true));
    const timer = setTimeout(() => onDone(pinnedCard.id), 280);
    return () => { cancelAnimationFrame(raf); clearTimeout(timer); };
  }, [pinnedCard.id, onDone]);

  return (
    <div
      className="transition-all duration-250 ease-in"
      style={{
        opacity: gone ? 0 : 1,
        transform: gone ? "translateX(24px)" : "translateX(0)",
        // Collapse height smoothly so cards below slide up
        maxHeight: gone ? 0 : 200,
        marginBottom: gone ? 0 : undefined,
        overflow: "hidden",
      }}
    >
      <MiniCard pinnedCard={pinnedCard} />
    </div>
  );
}

export default function PinnedCardOverlay({ pinnedCards, currentTime }: PinnedCardOverlayProps) {
  // All time-active cards, sorted by display_start ascending (oldest first = top)
  const allActive = useMemo(
    () => pinnedCards
      .filter((c) => currentTime >= c.display_start && currentTime <= c.display_end)
      .sort((a, b) => a.display_start - b.display_start),
    [pinnedCards, currentTime]
  );

  // Cap: keep only the newest MAX_VISIBLE (tail of the sorted array)
  const visibleCards = useMemo(
    () => allActive.length > MAX_VISIBLE
      ? allActive.slice(allActive.length - MAX_VISIBLE)
      : allActive,
    [allActive]
  );

  // Detect cards leaving the visible set (expired naturally OR bumped by newer cards)
  const prevVisibleIdsRef = useRef<Set<string>>(new Set());
  const [exitingCards, setExitingCards] = useState<PinnedCard[]>([]);

  useEffect(() => {
    const currentIds = new Set(visibleCards.map((c) => c.id));
    const prev = prevVisibleIdsRef.current;

    // Cards that were visible last frame but aren't now
    const departedIds = new Set<string>();
    prev.forEach((id) => { if (!currentIds.has(id)) departedIds.add(id); });

    if (departedIds.size > 0) {
      // Resolve full card objects from either allActive or pinnedCards
      const departedCards = pinnedCards.filter((c) => departedIds.has(c.id));
      setExitingCards((ex) => {
        const existingIds = new Set(ex.map((c) => c.id));
        const fresh = departedCards.filter((c) => !existingIds.has(c.id));
        return fresh.length > 0 ? [...ex, ...fresh] : ex;
      });
    }

    prevVisibleIdsRef.current = currentIds;
  }, [visibleCards, pinnedCards, allActive]);

  const handleExitDone = useCallback((id: string) => {
    setExitingCards((prev) => prev.filter((c) => c.id !== id));
  }, []);

  if (visibleCards.length === 0 && exitingCards.length === 0) return null;

  return (
    <div className="absolute right-2 top-2 flex flex-col items-end gap-2 pointer-events-none z-10">
      {exitingCards.map((card) => (
        <ExitingCard key={`exit-${card.id}`} pinnedCard={card} onDone={handleExitDone} />
      ))}
      {visibleCards.map((card) => (
        <EnteringCard key={card.id} pinnedCard={card} />
      ))}
    </div>
  );
}
