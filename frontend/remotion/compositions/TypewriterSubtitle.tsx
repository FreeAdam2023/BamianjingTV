import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";

interface TypewriterSubtitleProps {
  segment: SubtitleSegment;
  style: SubtitleStyleConfig;
}

export const TypewriterSubtitle: React.FC<TypewriterSubtitleProps> = ({
  segment,
  style,
}) => {
  const frame = useCurrentFrame();

  if (frame < segment.startFrame || frame >= segment.endFrame) {
    return null;
  }

  const typingDuration = 20; // frames for full text to appear
  const exitDuration = 8;
  const exitStart = segment.endFrame - exitDuration;

  // Calculate how many characters to show for English
  const enProgress = interpolate(
    frame,
    [segment.startFrame, segment.startFrame + typingDuration],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const enCharsToShow = Math.floor(segment.en.length * enProgress);

  // Chinese appears slightly after English starts
  const zhDelay = 5;
  const zhProgress = interpolate(
    frame,
    [segment.startFrame + zhDelay, segment.startFrame + zhDelay + typingDuration],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const zhCharsToShow = Math.floor(segment.zh.length * zhProgress);

  // Fade out for exit
  const opacity = interpolate(
    frame,
    [exitStart, segment.endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Blinking cursor
  const cursorVisible = Math.floor(frame / 8) % 2 === 0;
  const showEnCursor = enProgress < 1;
  const showZhCursor = zhProgress < 1 && enProgress >= 1;

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
      {/* English with typewriter effect */}
      <div
        style={{
          color: style.enColor,
          fontSize: style.enFontSize,
          fontWeight: style.fontWeight,
          fontFamily: style.fontFamily,
          textAlign: "center",
          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
          maxWidth: "80%",
        }}
      >
        {segment.en.slice(0, enCharsToShow)}
        {showEnCursor && cursorVisible && (
          <span style={{ opacity: 0.8 }}>|</span>
        )}
      </div>
      {/* Chinese with typewriter effect */}
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
        {segment.zh.slice(0, zhCharsToShow)}
        {showZhCursor && cursorVisible && (
          <span style={{ opacity: 0.8 }}>|</span>
        )}
      </div>
    </div>
  );
};
