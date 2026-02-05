import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";

interface HighlightWord {
  word: string;
  isHighlighted: boolean;
  highlightColor?: string;
  highlightType?: "vocabulary" | "entity" | "emphasis";
}

interface HighlightSubtitleProps {
  segment: SubtitleSegment;
  style: SubtitleStyleConfig;
  highlightColor?: string;
  highlightScale?: number;
  // Words to highlight (from NER or vocabulary analysis)
  highlightedWords?: string[];
  entityWords?: string[];
}

// Parse text into words with highlight info
function parseHighlightedText(
  text: string,
  highlightedWords: string[] = [],
  entityWords: string[] = [],
  highlightColor: string = "#facc15"
): HighlightWord[] {
  const words = text.split(/(\s+)/);
  return words.map((word) => {
    const cleanWord = word.toLowerCase().replace(/[^a-z]/g, "");
    const isVocab = highlightedWords.some(
      (hw) => hw.toLowerCase() === cleanWord
    );
    const isEntity = entityWords.some(
      (ew) => ew.toLowerCase() === cleanWord
    );

    return {
      word,
      isHighlighted: isVocab || isEntity,
      highlightColor: isEntity ? "#60a5fa" : highlightColor, // Blue for entities, yellow for vocab
      highlightType: isEntity ? "entity" : isVocab ? "vocabulary" : undefined,
    };
  });
}

export const HighlightSubtitle: React.FC<HighlightSubtitleProps> = ({
  segment,
  style,
  highlightColor = "#facc15",
  highlightScale = 1.05,
  highlightedWords = [],
  entityWords = [],
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < segment.startFrame || frame >= segment.endFrame) {
    return null;
  }

  // Entrance animation
  const entranceProgress = spring({
    frame: frame - segment.startFrame,
    fps,
    config: {
      damping: 20,
      stiffness: 150,
      mass: 0.8,
    },
  });

  // Exit animation
  const exitStart = segment.endFrame - 12;
  const exitProgress = interpolate(
    frame,
    [exitStart, segment.endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = Math.min(entranceProgress, exitProgress);
  const translateY = interpolate(entranceProgress, [0, 1], [20, 0]);

  // Parse English text for highlighting
  const enWords = parseHighlightedText(
    segment.en,
    highlightedWords,
    entityWords,
    highlightColor
  );

  // Staggered word animation
  const wordCount = enWords.filter((w) => w.word.trim()).length;
  const staggerDelay = 2; // frames between each word

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: style.lineSpacing,
        opacity,
        transform: `translateY(${translateY}px)`,
        padding: "20px",
      }}
    >
      {/* English with word highlighting */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          maxWidth: "80%",
          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
        }}
      >
        {enWords.map((wordInfo, i) => {
          // Calculate stagger for this word
          const wordIndex = enWords.slice(0, i).filter((w) => w.word.trim()).length;
          const wordEntrance = interpolate(
            frame - segment.startFrame,
            [wordIndex * staggerDelay, wordIndex * staggerDelay + 8],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          // Highlight pulse animation for highlighted words
          const highlightPulse = wordInfo.isHighlighted
            ? interpolate(
                Math.sin((frame - segment.startFrame) * 0.15),
                [-1, 1],
                [1, highlightScale]
              )
            : 1;

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                color: wordInfo.isHighlighted
                  ? wordInfo.highlightColor
                  : style.enColor,
                fontSize: style.enFontSize,
                fontWeight: wordInfo.isHighlighted ? "700" : style.fontWeight,
                fontFamily: style.fontFamily,
                transform: `scale(${wordEntrance * highlightPulse})`,
                opacity: wordEntrance,
                textDecoration: wordInfo.highlightType === "entity"
                  ? "underline"
                  : "none",
                textDecorationColor: wordInfo.highlightColor,
                textUnderlineOffset: "4px",
              }}
            >
              {wordInfo.word}
            </span>
          );
        })}
      </div>

      {/* Chinese text */}
      <div
        style={{
          color: style.zhColor,
          fontSize: style.zhFontSize,
          fontWeight: style.fontWeight,
          fontFamily: style.fontFamily,
          textAlign: "center",
          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
          maxWidth: "80%",
          opacity: interpolate(
            frame - segment.startFrame,
            [5, 15],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          ),
        }}
      >
        {segment.zh}
      </div>
    </div>
  );
};
