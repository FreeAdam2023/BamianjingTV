import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";
import { BilingualText } from "../components/BilingualText";

interface PopupSubtitleProps {
  segment: SubtitleSegment;
  style: SubtitleStyleConfig;
}

export const PopupSubtitle: React.FC<PopupSubtitleProps> = ({
  segment,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < segment.startFrame || frame >= segment.endFrame) {
    return null;
  }

  // Spring animation for entrance (bounce effect)
  const entranceSpring = spring({
    frame: frame - segment.startFrame,
    fps,
    config: {
      damping: 12,
      stiffness: 200,
      mass: 0.5,
    },
  });

  // Fade out for exit
  const exitStart = segment.endFrame - 10;
  const exitProgress = interpolate(
    frame,
    [exitStart, segment.endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scale = entranceSpring;
  const opacity = exitProgress;
  const translateY = interpolate(entranceSpring, [0, 1], [30, 0]);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "20px",
      }}
    >
      <BilingualText
        en={segment.en}
        zh={segment.zh}
        style={style}
        opacity={opacity}
        scale={scale}
        translateY={translateY}
      />
    </div>
  );
};
