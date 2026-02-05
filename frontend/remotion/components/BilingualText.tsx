import React from "react";
import type { SubtitleStyleConfig } from "../types";

interface BilingualTextProps {
  en: string;
  zh: string;
  style: SubtitleStyleConfig;
  opacity?: number;
  scale?: number;
  translateY?: number;
}

export const BilingualText: React.FC<BilingualTextProps> = ({
  en,
  zh,
  style,
  opacity = 1,
  scale = 1,
  translateY = 0,
}) => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: style.lineSpacing,
        opacity,
        transform: `scale(${scale}) translateY(${translateY}px)`,
        transition: "transform 0.1s ease-out",
      }}
    >
      {/* English text */}
      <div
        style={{
          color: style.enColor,
          fontSize: style.enFontSize,
          fontWeight: style.fontWeight,
          fontFamily: style.fontFamily,
          textAlign: "center",
          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
          lineHeight: 1.3,
        }}
      >
        {en}
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
          lineHeight: 1.3,
        }}
      >
        {zh}
      </div>
    </div>
  );
};
