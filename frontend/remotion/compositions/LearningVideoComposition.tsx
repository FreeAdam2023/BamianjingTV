/**
 * LearningVideoComposition — Remotion composition for WYSIWYG video export.
 *
 * Layout (1920x1080):
 * +---- Left 65% (1248px) ------+--- Right 35% (672px) --+
 * |  <OffthreadVideo>            |  Actual React card      |
 * |  blurred bg fill + sharp     |  components from        |
 * |  video centered, any ratio   |  CardSidePanel.tsx      |
 * |  Height: 756px               |  Height: 756px          |
 * +------------------------------+-------------------------+
 * | Subtitle Area (1920px full width, bg: #1a2744)         |
 * | Bilingual: English (white) + Chinese (yellow)          |
 * | Height: 324px                                          |
 * +--------------------------------------------------------+
 */

import React from "react";
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SidePanelWordCard, SidePanelEntityCard, SidePanelIdiomCard } from "../../src/components/Cards/CardSidePanel";
import { ExportWordCard, ExportEntityCard, ExportIdiomCard } from "./ExportCard";
import type { WordCard, EntityCard, IdiomCard } from "../../src/lib/types";
import type { LearningVideoProps, PinnedCardInput, SubtitleInput, SubtitleStillProps } from "../types";
import { secondsToFrames } from "../types";
import "../style.css";

// ---- AnimatedCard: wraps a card component with slide-in animation ----

function AnimatedCard({ card }: { card: PinnedCardInput }) {
  const frame = useCurrentFrame();
  // 300ms at 30fps = 9 frames
  const opacity = interpolate(frame, [0, 9], [0, 1], { extrapolateRight: "clamp" });
  const translateX = interpolate(frame, [0, 9], [24, 0], { extrapolateRight: "clamp" });

  const noop = () => {};
  const cardData = card.card_data;

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `translateX(${translateX}px)`,
      }}
    >
      <div className="h-full bg-black/80">
        {card.card_type === "word" && (
          <SidePanelWordCard card={cardData as unknown as WordCard} onClose={noop} canPin={false} />
        )}
        {card.card_type === "entity" && (
          <SidePanelEntityCard card={cardData as unknown as EntityCard} onClose={noop} canPin={false} />
        )}
        {card.card_type === "idiom" && (
          <SidePanelIdiomCard card={cardData as unknown as IdiomCard} onClose={noop} canPin={false} />
        )}
      </div>
    </AbsoluteFill>
  );
}

// ---- BilingualSubtitle: renders en/zh text pair ----

function BilingualSubtitle({
  en,
  zh,
  style,
}: {
  en: string;
  zh: string;
  style: LearningVideoProps["subtitleStyle"];
}) {
  const frame = useCurrentFrame();
  // Fade-in over 6 frames (~200ms)
  const opacity = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        padding: "0 40px",
        textAlign: "center",
      }}
    >
      {en && (
        <div
          style={{
            color: style.enColor,
            fontSize: style.enFontSize,
            fontFamily: "Inter, Arial, sans-serif",
            fontWeight: 600,
            textShadow: "0 2px 4px rgba(0,0,0,0.8)",
            lineHeight: 1.3,
          }}
        >
          {en}
        </div>
      )}
      {zh && (
        <div
          style={{
            color: style.zhColor,
            fontSize: style.zhFontSize,
            fontFamily: "'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif",
            fontWeight: 700,
            textShadow: "0 2px 4px rgba(0,0,0,0.8)",
            lineHeight: 1.3,
          }}
        >
          {zh}
        </div>
      )}
    </div>
  );
}

// ---- CardStillComposition: static card for renderStill (no animation) ----

export const CardStillComposition: React.FC<{ card: PinnedCardInput }> = ({ card }) => {
  const cardData = card.card_data;

  return (
    <AbsoluteFill>
      <div style={{ height: "100%", background: "rgba(0,0,0,0.8)" }}>
        {card.card_type === "word" && (
          <ExportWordCard card={cardData as unknown as WordCard} />
        )}
        {card.card_type === "entity" && (
          <ExportEntityCard card={cardData as unknown as EntityCard} />
        )}
        {card.card_type === "idiom" && (
          <ExportIdiomCard card={cardData as unknown as IdiomCard} />
        )}
      </div>
    </AbsoluteFill>
  );
};

// ---- SubtitleStillComposition: static subtitle for renderStill (WYSIWYG match) ----

// Replicates SubtitleOverlay.tsx split-mode styling exactly:
// - SUBTITLE_HEIGHT_RATIO = 0.33, fontScale = 0.33 / 0.5 = 0.66
// - Adaptive text-length scaling (sqrt-based)
// - leading-relaxed (line-height: 1.625)
// - fontWeight: 500
// - textShadow for readability
// - Solid bgColor container, flexbox centering

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

// ---- Main Composition ----

export const LearningVideoComposition: React.FC<LearningVideoProps> = ({
  videoSrc,
  durationInFrames,
  fps,
  pinnedCards,
  subtitles,
  layout,
  subtitleStyle,
}) => {
  const { width, height } = useVideoConfig();

  const videoAreaHeight = Math.round(height * (1 - layout.subtitleRatio));
  const leftWidth = Math.round(width * layout.videoRatio);
  const rightWidth = width - leftWidth;
  const subtitleAreaHeight = height - videoAreaHeight;

  return (
    <AbsoluteFill style={{ backgroundColor: layout.bgColor }}>
      {/* Row: Video + Card Panel */}
      <div
        style={{
          display: "flex",
          height: videoAreaHeight,
          width: "100%",
          position: "relative",
        }}
      >
        {/* Left: Video area with blurred background fill */}
        <div
          style={{
            width: leftWidth,
            height: videoAreaHeight,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Blurred background: covers panel, zoomed in */}
          {videoSrc && (
            <OffthreadVideo
              src={videoSrc}
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                minWidth: "100%",
                minHeight: "100%",
                objectFit: "cover",
                filter: "blur(25px) brightness(0.6)",
              }}
            />
          )}
          {/* Sharp foreground: fits panel, centered */}
          {videoSrc && (
            <OffthreadVideo
              src={videoSrc}
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                maxWidth: "100%",
                maxHeight: "100%",
                objectFit: "contain",
              }}
            />
          )}
        </div>

        {/* Vertical divider */}
        <div
          style={{
            width: 2,
            height: videoAreaHeight,
            background: "linear-gradient(to bottom, rgba(255,255,255,0.05), rgba(255,255,255,0.2), rgba(255,255,255,0.05))",
            flexShrink: 0,
          }}
        />

        {/* Right: Card Panel */}
        <div
          style={{
            flex: 1,
            position: "relative",
            overflow: "hidden",
            height: videoAreaHeight,
          }}
        >
          {/* Empty-state placeholder (behind card Sequences) */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(0,0,0,0.85)",
              gap: 16,
            }}
          >
            {/* Decorative bracket icon */}
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect x="8" y="6" width="32" height="36" rx="3" stroke="rgba(255,255,255,0.12)" strokeWidth="1.5" />
              <line x1="14" y1="16" x2="34" y2="16" stroke="rgba(255,255,255,0.10)" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="14" y1="22" x2="30" y2="22" stroke="rgba(255,255,255,0.10)" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="14" y1="28" x2="26" y2="28" stroke="rgba(255,255,255,0.10)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 500,
                  color: "rgba(255,255,255,0.18)",
                  fontFamily: "'Noto Sans CJK SC', 'PingFang SC', sans-serif",
                  letterSpacing: "0.08em",
                }}
              >
                Learning Notes
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: "rgba(255,255,255,0.10)",
                  fontFamily: "Inter, Arial, sans-serif",
                  marginTop: 6,
                }}
              >
                SceneMind
              </div>
            </div>
          </div>

          {pinnedCards.map((card) => {
            const fromFrame = secondsToFrames(card.display_start, fps);
            const durationFrames = secondsToFrames(
              card.display_end - card.display_start,
              fps
            );
            if (durationFrames <= 0) return null;
            return (
              <Sequence
                key={card.id}
                from={fromFrame}
                durationInFrames={durationFrames}
                layout="none"
              >
                <AnimatedCard card={card} />
              </Sequence>
            );
          })}
        </div>
      </div>

      {/* Horizontal divider */}
      <div
        style={{
          width: "100%",
          height: 2,
          background: "linear-gradient(to right, rgba(255,255,255,0.05), rgba(255,255,255,0.2), rgba(255,255,255,0.05))",
        }}
      />

      {/* Bottom: Subtitle Area */}
      <div
        style={{
          height: subtitleAreaHeight - 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {subtitles.map((sub) => {
          const fromFrame = secondsToFrames(sub.start, fps);
          const durationFrames = secondsToFrames(sub.end - sub.start, fps);
          if (durationFrames <= 0) return null;
          return (
            <Sequence
              key={sub.id}
              from={fromFrame}
              durationInFrames={durationFrames}
              layout="none"
            >
              <BilingualSubtitle en={sub.en} zh={sub.zh} style={subtitleStyle} />
            </Sequence>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
