import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

interface AnimatedWordProps {
  word: string;
  startFrame: number;
  endFrame: number;
  highlightColor: string;
  highlightScale: number;
  baseColor: string;
  fontSize: number;
  fontWeight: string;
  fontFamily: string;
}

export const AnimatedWord: React.FC<AnimatedWordProps> = ({
  word,
  startFrame,
  endFrame,
  highlightColor,
  highlightScale,
  baseColor,
  fontSize,
  fontWeight,
  fontFamily,
}) => {
  const frame = useCurrentFrame();

  const isActive = frame >= startFrame && frame < endFrame;
  const progress = interpolate(
    frame,
    [startFrame, startFrame + 5, endFrame - 5, endFrame],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scale = isActive ? interpolate(progress, [0, 1], [1, highlightScale]) : 1;
  const color = isActive ? highlightColor : baseColor;

  return (
    <span
      style={{
        display: "inline-block",
        color,
        fontSize,
        fontWeight,
        fontFamily,
        transform: `scale(${scale})`,
        transition: "color 0.1s ease",
        marginRight: "0.25em",
      }}
    >
      {word}
    </span>
  );
};
