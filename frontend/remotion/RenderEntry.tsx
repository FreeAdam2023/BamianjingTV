/**
 * RenderEntry.tsx - Entry point for Remotion server-side rendering
 * This file registers the composition that will be bundled and rendered
 */

import React from "react";
import { Composition, registerRoot } from "remotion";
import { SubtitleComposition } from "./compositions/SubtitleComposition";
import { LearningVideoComposition } from "./compositions/LearningVideoComposition";
import type { SubtitleCompositionProps } from "./compositions/SubtitleComposition";
import type { RemotionConfig } from "../src/lib/creative-types";
import type { SubtitleSegment, LearningVideoProps } from "./types";

// Default props for the composition (will be overridden by inputProps)
const defaultConfig: RemotionConfig = {
  version: "1.0",
  style: "karaoke",
  global: {
    fontFamily: "Inter, system-ui, sans-serif",
    backgroundColor: "transparent",
    subtitlePosition: "bottom",
    enFontSize: 32,
    zhFontSize: 28,
    enColor: "#ffffff",
    zhColor: "#facc15",
    fontWeight: "600",
    lineSpacing: 8,
  },
  animation: {
    entrance: { type: "fadeIn", duration: 10, easing: "easeOut" },
    wordHighlight: { enabled: true, color: "#facc15", scale: 1.1, duration: 15 },
    exit: { type: "fadeOut", duration: 10, easing: "easeIn" },
  },
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SubtitleComposition"
        component={SubtitleComposition as unknown as React.ComponentType<Record<string, unknown>>}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          segments: [] as SubtitleSegment[],
          config: defaultConfig,
          videoSrc: undefined,
        }}
      />
      <Composition
        id="LearningVideo"
        component={LearningVideoComposition as unknown as React.ComponentType<Record<string, unknown>>}
        width={1920}
        height={1080}
        fps={30}
        durationInFrames={300}
        defaultProps={{
          videoSrc: "",
          durationInFrames: 300,
          fps: 30,
          pinnedCards: [],
          subtitles: [],
          layout: {
            videoRatio: 0.65,
            subtitleRatio: 0.3,
            bgColor: "#1a2744",
          },
          subtitleStyle: {
            enColor: "#ffffff",
            zhColor: "#facc15",
            enFontSize: 40,
            zhFontSize: 40,
          },
        } satisfies LearningVideoProps}
        calculateMetadata={({ props }) => {
          const p = props as unknown as LearningVideoProps;
          return {
            durationInFrames: p.durationInFrames,
            fps: p.fps,
          };
        }}
      />
    </>
  );
};

registerRoot(RemotionRoot);
