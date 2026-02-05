import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";
import { BilingualText } from "../components/BilingualText";

interface SlideSubtitleProps {
  segment: SubtitleSegment;
  style: SubtitleStyleConfig;
}

export const SlideSubtitle: React.FC<SlideSubtitleProps> = ({
  segment,
  style,
}) => {
  const frame = useCurrentFrame();

  if (frame < segment.startFrame || frame >= segment.endFrame) {
    return null;
  }

  const entranceDuration = 12;
  const exitDuration = 12;
  const entranceEnd = segment.startFrame + entranceDuration;
  const exitStart = segment.endFrame - exitDuration;

  // Slide in from left
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

  // Slide out to right
  const exitProgress = interpolate(
    frame,
    [exitStart, segment.endFrame],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    }
  );

  const translateX = interpolate(
    frame,
    [segment.startFrame, entranceEnd, exitStart, segment.endFrame],
    [-100, 0, 0, 100],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = interpolate(
    frame,
    [segment.startFrame, entranceEnd, exitStart, segment.endFrame],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "20px",
        transform: `translateX(${translateX}px)`,
        opacity,
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
