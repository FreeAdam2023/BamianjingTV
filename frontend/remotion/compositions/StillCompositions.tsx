/**
 * StillCompositions.tsx — Isolated compositions for renderStill (PNG export).
 *
 * These components are used ONLY by renderStills.mjs for headless Chrome rendering.
 * They use ONLY React inline styles — NO Tailwind CSS, NO external stylesheets.
 *
 * This file must NOT import any CSS files (especially style.css with @tailwind).
 * Tailwind's Preflight CSS reset causes blank renders in headless Chrome Docker.
 */

import React from "react";
import { AbsoluteFill } from "remotion";
import { ExportWordCard, ExportEntityCard, ExportIdiomCard } from "./ExportCard";
import type { WordCard, EntityCard, IdiomCard } from "../../src/lib/types";
import type { PinnedCardInput, SubtitleStillProps } from "../types";

// ---- Error Boundary ----

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class CardErrorBoundary extends React.Component<
  { children: React.ReactNode; cardId?: string; cardType?: string },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode; cardId?: string; cardType?: string }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to stderr (captured by Remotion)
    console.error(
      `[CardStill] React error in ${this.props.cardType}/${this.props.cardId}: ${error.message}`,
      errorInfo.componentStack
    );
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(180,0,0,0.9)",
            padding: 24,
            fontFamily: "Arial, sans-serif",
          }}
        >
          <div style={{ fontSize: 20, fontWeight: 700, color: "#ffffff", marginBottom: 12 }}>
            Card Render Error
          </div>
          <div style={{ fontSize: 14, color: "rgba(255,255,255,0.8)", textAlign: "center", wordBreak: "break-all" }}>
            {this.props.cardType}/{this.props.cardId}: {this.state.error?.message || "Unknown error"}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---- CardStillComposition ----

export const CardStillComposition: React.FC<{ card: PinnedCardInput }> = ({ card }) => {
  const cardData = card.card_data;

  // Validate card_data has content
  const dataKeys = cardData ? Object.keys(cardData) : [];
  const hasData = dataKeys.length > 0;

  if (!hasData) {
    // Render visible diagnostic when card_data is empty
    return (
      <AbsoluteFill>
        <div
          style={{
            height: "100%",
            background: "rgba(120,60,0,0.9)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            fontFamily: "Arial, sans-serif",
          }}
        >
          <div style={{ fontSize: 18, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>
            Empty card_data
          </div>
          <div style={{ fontSize: 14, color: "rgba(255,255,255,0.7)" }}>
            id: {card.id} | type: {card.card_type}
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginTop: 8 }}>
            card_data keys: {JSON.stringify(dataKeys)}
          </div>
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      <div style={{ height: "100%", background: "#1a2744" }}>
        <CardErrorBoundary cardId={card.id} cardType={card.card_type}>
          {card.card_type === "word" && (
            <ExportWordCard card={cardData as unknown as WordCard} />
          )}
          {card.card_type === "entity" && (
            <ExportEntityCard card={cardData as unknown as EntityCard} />
          )}
          {card.card_type === "idiom" && (
            <ExportIdiomCard card={cardData as unknown as IdiomCard} />
          )}
        </CardErrorBoundary>
      </div>
    </AbsoluteFill>
  );
};

// ---- SubtitleStillComposition ----

const SUB_MIN_EN_FONT_SIZE = 18;
const SUB_MIN_ZH_FONT_SIZE = 20;
const SUB_EN_CHARS_PER_LINE = 60;
const SUB_ZH_CHARS_PER_LINE = 30;
const SUB_MAX_LINES = 4;
const SUB_FONT_SCALE = 0.33 / 0.5; // 0.66 — matches split-mode fontScale

function computeAdaptiveFontSize(
  baseSize: number,
  minSize: number,
  textLength: number,
  charsPerLine: number,
): number {
  let size = Math.max(minSize, Math.min(48, baseSize * SUB_FONT_SCALE));
  const maxChars = charsPerLine * SUB_MAX_LINES;

  if (textLength > maxChars) {
    const scale = Math.sqrt(maxChars / textLength);
    size = Math.max(minSize, size * scale);
  } else if (textLength > charsPerLine * 2) {
    const scale = Math.sqrt((charsPerLine * 2) / textLength);
    size = Math.max(minSize, size * Math.max(0.8, scale));
  }

  return Math.round(size);
}

export const SubtitleStillComposition: React.FC<SubtitleStillProps> = ({
  en,
  zh,
  style,
  bgColor,
  width,
  height,
  languageMode,
}) => {
  const enFontSize = computeAdaptiveFontSize(
    style.enFontSize, SUB_MIN_EN_FONT_SIZE, (en || "").length, SUB_EN_CHARS_PER_LINE,
  );
  const zhFontSize = computeAdaptiveFontSize(
    style.zhFontSize, SUB_MIN_ZH_FONT_SIZE, (zh || "").length, SUB_ZH_CHARS_PER_LINE,
  );

  const textShadow = "2px 2px 4px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.5)";

  return (
    <AbsoluteFill
      style={{
        width,
        height,
        backgroundColor: bgColor,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px 32px",
      }}
    >
      {/* English text */}
      {(languageMode === "both" || languageMode === "en") && en && (
        <div
          style={{
            textAlign: "center",
            lineHeight: 1.625,
            fontSize: enFontSize,
            fontFamily: "system-ui, -apple-system, sans-serif",
            fontWeight: 500,
            color: style.enColor,
            textShadow,
            marginBottom: languageMode === "both" ? 16 : 0,
          }}
        >
          {en}
        </div>
      )}
      {/* Chinese text */}
      {(languageMode === "both" || languageMode === "zh") && zh && (
        <div
          style={{
            textAlign: "center",
            lineHeight: 1.625,
            fontSize: zhFontSize,
            fontFamily: "system-ui, -apple-system, sans-serif",
            fontWeight: 500,
            color: style.zhColor,
            textShadow,
          }}
        >
          {zh}
        </div>
      )}
    </AbsoluteFill>
  );
};
