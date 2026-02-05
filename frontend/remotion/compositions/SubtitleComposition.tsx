import React from "react";
import { AbsoluteFill, OffthreadVideo, useCurrentFrame, useVideoConfig } from "remotion";
import type { SubtitleSegment, SubtitleStyleConfig } from "../types";
import type { RemotionConfig, CreativeStyle } from "@/lib/creative-types";
import { KaraokeSubtitle } from "./KaraokeSubtitle";
import { PopupSubtitle } from "./PopupSubtitle";
import { SlideSubtitle } from "./SlideSubtitle";
import { TypewriterSubtitle } from "./TypewriterSubtitle";
import { HighlightSubtitle } from "./HighlightSubtitle";
import { FadeSubtitle } from "./FadeSubtitle";

export interface SubtitleCompositionProps {
  segments: SubtitleSegment[];
  config: RemotionConfig;
  videoSrc?: string;
}

export const SubtitleComposition: React.FC<SubtitleCompositionProps> = ({
  segments,
  config,
  videoSrc,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  // Convert config to style config
  const styleConfig: SubtitleStyleConfig = {
    fontFamily: config.global.fontFamily,
    backgroundColor: config.global.backgroundColor,
    position: config.global.subtitlePosition,
    enFontSize: config.global.enFontSize,
    zhFontSize: config.global.zhFontSize,
    enColor: config.global.enColor,
    zhColor: config.global.zhColor,
    fontWeight: config.global.fontWeight,
    lineSpacing: config.global.lineSpacing,
  };

  // Find current segment
  const currentSegment = segments.find(
    (seg) => frame >= seg.startFrame && frame < seg.endFrame
  );

  // Determine position styles
  const getPositionStyle = (): React.CSSProperties => {
    switch (config.global.subtitlePosition) {
      case "top":
        return { top: "10%", left: 0, right: 0 };
      case "center":
        return { top: "50%", left: 0, right: 0, transform: "translateY(-50%)" };
      case "bottom":
      default:
        return { bottom: "10%", left: 0, right: 0 };
    }
  };

  // Render subtitle based on style
  const renderSubtitle = () => {
    if (!currentSegment) return null;

    switch (config.style) {
      case "karaoke":
        return (
          <KaraokeSubtitle
            segment={currentSegment}
            style={styleConfig}
            highlightColor={config.animation.wordHighlight?.color || "#facc15"}
            highlightScale={config.animation.wordHighlight?.scale || 1.1}
          />
        );
      case "popup":
        return <PopupSubtitle segment={currentSegment} style={styleConfig} />;
      case "slide":
        return <SlideSubtitle segment={currentSegment} style={styleConfig} />;
      case "typewriter":
        return <TypewriterSubtitle segment={currentSegment} style={styleConfig} />;
      case "highlight":
        return (
          <HighlightSubtitle
            segment={currentSegment}
            style={styleConfig}
            highlightColor={config.animation.wordHighlight?.color || "#facc15"}
          />
        );
      case "fade":
        return <FadeSubtitle segment={currentSegment} style={styleConfig} />;
      case "custom":
      default:
        // Default to popup for custom (can be enhanced later)
        return <PopupSubtitle segment={currentSegment} style={styleConfig} />;
    }
  };

  return (
    <AbsoluteFill style={{ backgroundColor: config.global.backgroundColor }}>
      {/* Video layer (optional) */}
      {videoSrc && (
        <AbsoluteFill>
          <OffthreadVideo
            src={videoSrc}
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
        </AbsoluteFill>
      )}

      {/* Subtitle layer */}
      <div
        style={{
          position: "absolute",
          ...getPositionStyle(),
          display: "flex",
          justifyContent: "center",
          zIndex: 10,
        }}
      >
        {renderSubtitle()}
      </div>
    </AbsoluteFill>
  );
};
