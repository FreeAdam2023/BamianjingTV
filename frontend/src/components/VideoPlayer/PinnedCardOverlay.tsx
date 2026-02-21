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
  NoteCard,
} from "@/lib/types";
import {
  SidePanelWordCard,
  SidePanelEntityCard,
  SidePanelIdiomCard,
} from "@/components/Cards/CardSidePanel";
import { unpinCard } from "@/lib/api";

interface PinnedCardOverlayProps {
  pinnedCards: PinnedCard[];
  currentTime: number;
  timelineId?: string;
  onPinChange?: () => void;
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
function FullCard({ pinnedCard, onUnpin, onDismiss, pinLoading }: {
  pinnedCard: PinnedCard;
  onUnpin?: (pinId: string) => void;
  onDismiss?: (pinId: string) => void;
  pinLoading?: boolean;
}) {
  const data = pinnedCard.card_data;
  const note = pinnedCard.note;
  const canPin = !!onUnpin;
  const handleClose = onDismiss ? () => onDismiss(pinnedCard.id) : () => {};
  const handleTogglePin = onUnpin ? () => onUnpin(pinnedCard.id) : undefined;

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
          onClose={handleClose}
          canPin={canPin}
          isPinned={true}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
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
          onClose={handleClose}
          canPin={canPin}
          isPinned={true}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
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
          onClose={handleClose}
          canPin={canPin}
          isPinned={true}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
        />
        {note && <NoteDisplay note={note} />}
      </>
    );
  }

  if (pinnedCard.card_type === "note") {
    const noteData = data as NoteCard;
    return (
      <div className="h-full flex flex-col">
        <div className="relative flex-shrink-0">
          <div className="h-16 bg-gradient-to-r from-green-900/30 to-green-800/20" />
          <span className="absolute top-2 left-2 px-2 py-0.5 bg-green-500/50 text-white text-xs font-medium rounded backdrop-blur-sm">
            笔记
          </span>
          <div className="absolute top-2 right-2 flex items-center gap-1">
            {onUnpin && (
              <button
                onClick={() => onUnpin(pinnedCard.id)}
                disabled={pinLoading}
                className="p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition"
                title="取消钉住"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
                </svg>
              </button>
            )}
            {onDismiss && (
              <button
                onClick={() => onDismiss(pinnedCard.id)}
                className="p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <h2 className="text-xl font-bold text-white">{noteData.title}</h2>
          <p className="text-sm text-white/60 whitespace-pre-wrap">{noteData.content}</p>
        </div>
        {note && <NoteDisplay note={note} />}
      </div>
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
function EnteringCard({ pinnedCard, onUnpin, onDismiss, pinLoading }: {
  pinnedCard: PinnedCard;
  onUnpin?: (pinId: string) => void;
  onDismiss?: (pinId: string) => void;
  pinLoading?: boolean;
}) {
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
      <FullCard pinnedCard={pinnedCard} onUnpin={onUnpin} onDismiss={onDismiss} pinLoading={pinLoading} />
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

export default function PinnedCardOverlay({ pinnedCards, currentTime, timelineId, onPinChange }: PinnedCardOverlayProps) {
  const [pinLoading, setPinLoading] = useState(false);
  // Temporarily dismissed cards (hidden until they leave the time window)
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  // All time-active cards, sorted by display_start ascending (oldest first = top)
  const allActive = useMemo(
    () => pinnedCards
      .filter((c) => currentTime >= c.display_start && currentTime <= c.display_end)
      .sort((a, b) => a.display_start - b.display_start),
    [pinnedCards, currentTime]
  );

  // Clear dismissed IDs when cards leave the time window
  useEffect(() => {
    const activeIds = new Set(allActive.map((c) => c.id));
    setDismissedIds((prev) => {
      const next = new Set<string>();
      prev.forEach((id) => { if (activeIds.has(id)) next.add(id); });
      return next.size !== prev.size ? next : prev;
    });
  }, [allActive]);

  // Filter out dismissed cards
  const activeNotDismissed = useMemo(
    () => allActive.filter((c) => !dismissedIds.has(c.id)),
    [allActive, dismissedIds]
  );

  // Cap: keep only the newest MAX_VISIBLE (tail of the sorted array)
  const visibleCards = useMemo(
    () => activeNotDismissed.length > MAX_VISIBLE
      ? activeNotDismissed.slice(activeNotDismissed.length - MAX_VISIBLE)
      : activeNotDismissed,
    [activeNotDismissed]
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

  // Unpin a card
  const handleUnpin = useCallback(async (pinId: string) => {
    if (!timelineId || pinLoading) return;
    setPinLoading(true);
    try {
      await unpinCard(timelineId, pinId);
      onPinChange?.();
    } catch (err) {
      console.error("Failed to unpin card:", err);
    } finally {
      setPinLoading(false);
    }
  }, [timelineId, pinLoading, onPinChange]);

  // Dismiss a card temporarily (until it leaves the time window)
  const handleDismiss = useCallback((pinId: string) => {
    setDismissedIds((prev) => new Set(prev).add(pinId));
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
            <EnteringCard
              key={card.id}
              pinnedCard={card}
              onUnpin={timelineId ? handleUnpin : undefined}
              onDismiss={handleDismiss}
              pinLoading={pinLoading}
            />
          ))}
        </>
      ) : null}
    </div>
  );
}
