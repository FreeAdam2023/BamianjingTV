/**
 * LearningVideoComposition — Remotion composition for WYSIWYG video export.
 *
 * Layout (1920x1080):
 * +---- Left 65% (1248px) ------+--- Right 35% (672px) --+
 * |  <OffthreadVideo>            |  Actual React card      |
 * |  source video, centered      |  components from        |
 * |  bg: #1a2744                 |  CardSidePanel.tsx      |
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
import type { WordCard, EntityCard, IdiomCard } from "../../src/lib/types";
import type { LearningVideoProps, PinnedCardInput, SubtitleInput } from "../types";
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
  const noop = () => {};
  const cardData = card.card_data;

  return (
    <AbsoluteFill>
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
        {/* Left: Video area */}
        <div
          style={{
            width: leftWidth,
            height: videoAreaHeight,
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          {videoSrc && (
            <OffthreadVideo
              src={videoSrc}
              style={{
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
            width: 1,
            height: videoAreaHeight,
            backgroundColor: "rgba(255,255,255,0.1)",
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
          height: 1,
          backgroundColor: "rgba(255,255,255,0.1)",
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
