import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";
import { AnimatedWord } from "../components/AnimatedWord";

interface KaraokeSubtitleProps {
  segment: SubtitleSegment;
  style: SubtitleStyleConfig;
  highlightColor: string;
  highlightScale: number;
}

export const KaraokeSubtitle: React.FC<KaraokeSubtitleProps> = ({
  segment,
  style,
  highlightColor,
  highlightScale,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance and exit animations
  const entranceEnd = segment.startFrame + 10;
  const exitStart = segment.endFrame - 10;

  const entranceProgress = interpolate(
    frame,
    [segment.startFrame, entranceEnd],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const exitProgress = interpolate(
    frame,
    [exitStart, segment.endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = Math.min(entranceProgress, exitProgress);

  // Split English text into words for karaoke effect
  const words = segment.en.split(" ");
  const segmentDuration = segment.endFrame - segment.startFrame;
  const wordDuration = Math.floor(segmentDuration / words.length);

  // If we have word-level timing, use it; otherwise distribute evenly
  const wordTimings = segment.words || words.map((word, i) => ({
    word,
    startFrame: segment.startFrame + i * wordDuration,
    endFrame: segment.startFrame + (i + 1) * wordDuration,
  }));

  if (frame < segment.startFrame || frame >= segment.endFrame) {
    return null;
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: style.lineSpacing,
        opacity,
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
        {wordTimings.map((wordTiming, i) => (
          <AnimatedWord
            key={i}
            word={wordTiming.word}
            startFrame={wordTiming.startFrame}
            endFrame={wordTiming.endFrame}
            highlightColor={highlightColor}
            highlightScale={highlightScale}
            baseColor={style.enColor}
            fontSize={style.enFontSize}
            fontWeight={style.fontWeight}
            fontFamily={style.fontFamily}
          />
        ))}
      </div>
      {/* Chinese text (no word highlighting) */}
      <div
        style={{
          color: style.zhColor,
          fontSize: style.zhFontSize,
          fontWeight: style.fontWeight,
          fontFamily: style.fontFamily,
          textAlign: "center",
          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
          maxWidth: "80%",
        }}
      >
        {segment.zh}
      </div>
    </div>
  );
};
