"use client";

/**
 * PinnedCardOverlay - Renders full card detail in the right panel
 * during playback when currentTime falls within a card's display window.
 *
 * Shows the same CardSidePanel-style content the user sees when clicking a word.
 * Caps at MAX_VISIBLE=1, with smooth enter/exit animations.
 */

import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import type {
  PinnedCard,
  WordCard,
  EntityCard,
  IdiomCard,
  InsightCard,
} from "@/lib/types";
import {
  SidePanelWordCard,
  SidePanelEntityCard,
  SidePanelIdiomCard,
} from "@/components/Cards/CardSidePanel";

interface PinnedCardOverlayProps {
  pinnedCards: PinnedCard[];
  currentTime: number;
}

/** Max cards visible at once */
const MAX_VISIBLE = 1;

/** Read-only note display for overlay */
function NoteDisplay({ note }: { note: string }) {
  return (
    <div className="px-4 pb-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-medium text-white/40 uppercase tracking-wider">备注</span>
        <div className="flex-1 h-px bg-white/10" />
      </div>
      <p className="text-sm text-purple-300/80 italic">{note}</p>
    </div>
  );
}

/** Renders a full card based on type — same style as CardSidePanel */
function FullCard({ pinnedCard }: { pinnedCard: PinnedCard }) {
  const data = pinnedCard.card_data;
  const note = pinnedCard.note;
  const noop = () => {};

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-white/30 text-sm">
        {pinnedCard.card_type}: {pinnedCard.card_id}
      </div>
    );
  }

  if (pinnedCard.card_type === "word") {
    return (
      <>
        <SidePanelWordCard
          card={data as WordCard}
          onClose={noop}
          canPin={false}
        />
        {note && <NoteDisplay note={note} />}
      </>
    );
  }

  if (pinnedCard.card_type === "entity") {
    return (
      <>
        <SidePanelEntityCard
          card={data as EntityCard}
          onClose={noop}
          canPin={false}
        />
        {note && <NoteDisplay note={note} />}
      </>
    );
  }

  if (pinnedCard.card_type === "idiom") {
    return (
      <>
        <SidePanelIdiomCard
          card={data as IdiomCard}
          onClose={noop}
          canPin={false}
        />
        {note && <NoteDisplay note={note} />}
      </>
    );
  }

  // insight or unknown — fallback
  const insight = data as InsightCard;
  return (
    <div className="h-full flex flex-col p-4">
      <div className="relative flex-shrink-0">
        <div className="h-16 bg-gradient-to-r from-purple-900/30 to-purple-800/20" />
        <span className="absolute top-2 left-2 px-2 py-0.5 bg-purple-500/50 text-white text-xs font-medium rounded backdrop-blur-sm">
          {insight.category || "insight"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        <h2 className="text-xl font-bold text-white">{insight.title}</h2>
        <p className="text-sm text-white/60">{insight.content}</p>
      </div>
      {note && <NoteDisplay note={note} />}
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
      className="h-full transition-all duration-300 ease-out"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateX(0)" : "translateX(24px)",
      }}
    >
      <FullCard pinnedCard={pinnedCard} />
    </div>
  );
}

/** Starts visible, then slides out to right and fades. Calls onDone after transition. */
function ExitingCard({ pinnedCard, onDone }: { pinnedCard: PinnedCard; onDone: (id: string) => void }) {
  const [gone, setGone] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setGone(true));
    const timer = setTimeout(() => onDone(pinnedCard.id), 280);
    return () => { cancelAnimationFrame(raf); clearTimeout(timer); };
  }, [pinnedCard.id, onDone]);

  return (
    <div
      className="h-full transition-all duration-250 ease-in absolute inset-0"
      style={{
        opacity: gone ? 0 : 1,
        transform: gone ? "translateX(24px)" : "translateX(0)",
      }}
    >
      <FullCard pinnedCard={pinnedCard} />
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

  const hasContent = visibleCards.length > 0 || exitingCards.length > 0;

  return (
    <div className="h-full relative">
      {hasContent ? (
        <>
          {exitingCards.map((card) => (
            <ExitingCard key={`exit-${card.id}`} pinnedCard={card} onDone={handleExitDone} />
          ))}
          {visibleCards.map((card) => (
            <EnteringCard key={card.id} pinnedCard={card} />
          ))}
        </>
      ) : null}
    </div>
  );
}
