import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";
import { BilingualText } from "../components/BilingualText";

interface FadeSubtitleProps {
  segment: SubtitleSegment;
  style: SubtitleStyleConfig;
  fadeInDuration?: number;
  fadeOutDuration?: number;
}

export const FadeSubtitle: React.FC<FadeSubtitleProps> = ({
  segment,
  style,
  fadeInDuration = 12,
  fadeOutDuration = 12,
}) => {
  const frame = useCurrentFrame();

  if (frame < segment.startFrame || frame >= segment.endFrame) {
    return null;
  }

  const entranceEnd = segment.startFrame + fadeInDuration;
  const exitStart = segment.endFrame - fadeOutDuration;

  // Smooth fade in with slight scale
  const entranceProgress = interpolate(
    frame,
    [segment.startFrame, entranceEnd],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    }
  );

  // Smooth fade out
  const exitProgress = interpolate(
    frame,
    [exitStart, segment.endFrame],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    }
  );

  const opacity = Math.min(entranceProgress, exitProgress);
  const scale = interpolate(entranceProgress, [0, 1], [0.95, 1]);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "20px",
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <BilingualText
        en={segment.en}
        zh={segment.zh}
        style={style}
      />
    </div>
  );
};
