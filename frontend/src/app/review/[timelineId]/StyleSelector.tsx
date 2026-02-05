"use client";

import React, { useState } from "react";
import type { CreativeStyle } from "@/lib/creative-types";

interface StyleSelectorProps {
  currentStyle: CreativeStyle;
  onStyleChange: (style: CreativeStyle) => void;
  disabled?: boolean;
}

const STYLE_OPTIONS: { value: CreativeStyle; label: string; description: string }[] = [
  {
    value: "karaoke",
    label: "Karaoke",
    description: "Word-by-word highlighting",
  },
  {
    value: "popup",
    label: "Popup",
    description: "Bouncy entrance",
  },
  {
    value: "slide",
    label: "Slide",
    description: "Smooth slide in/out",
  },
  {
    value: "typewriter",
    label: "Typewriter",
    description: "Character-by-character",
  },
  {
    value: "highlight",
    label: "Highlight",
    description: "Entity & vocab highlighting",
  },
  {
    value: "fade",
    label: "Fade",
    description: "Clean fade in/out",
  },
];

// Mini animated preview for each style
function StylePreview({ style, isActive }: { style: CreativeStyle; isActive: boolean }) {
  const baseClass = "text-[8px] leading-tight font-medium whitespace-nowrap";

  switch (style) {
    case "karaoke":
      return (
        <div className={`${baseClass} overflow-hidden`}>
          <span className="inline-block">
            {"Hello".split("").map((char, i) => (
              <span
                key={i}
                className={isActive ? "animate-karaoke-char" : ""}
                style={{
                  animationDelay: `${i * 200}ms`,
                  color: isActive ? undefined : "#9ca3af"
                }}
              >
                {char}
              </span>
            ))}
          </span>
        </div>
      );

    case "popup":
      return (
        <div className={`${baseClass}`}>
          <span
            className={isActive ? "animate-popup-bounce inline-block" : ""}
            style={{ color: isActive ? undefined : "#9ca3af" }}
          >
            Hello
          </span>
        </div>
      );

    case "slide":
      return (
        <div className={`${baseClass} overflow-hidden`}>
          <span
            className={isActive ? "animate-slide-in inline-block" : ""}
            style={{ color: isActive ? undefined : "#9ca3af" }}
          >
            Hello
          </span>
        </div>
      );

    case "typewriter":
      return (
        <div className={`${baseClass} overflow-hidden`}>
          <span
            className={isActive ? "animate-typewriter inline-block" : ""}
            style={{
              color: isActive ? undefined : "#9ca3af",
              width: isActive ? undefined : "auto"
            }}
          >
            Hello
          </span>
        </div>
      );

    case "highlight":
      return (
        <div className={`${baseClass}`}>
          <span style={{ color: isActive ? undefined : "#9ca3af" }}>
            He
            <span
              className={isActive ? "animate-highlight-pulse" : ""}
              style={{ color: isActive ? "#facc15" : "#9ca3af" }}
            >
              llo
            </span>
          </span>
        </div>
      );

    case "fade":
      return (
        <div className={`${baseClass}`}>
          <span
            className={isActive ? "animate-fade-pulse" : ""}
            style={{ color: isActive ? undefined : "#9ca3af" }}
          >
            Hello
          </span>
        </div>
      );

    default:
      return <div className={baseClass}>Hello</div>;
  }
}

export default function StyleSelector({
  currentStyle,
  onStyleChange,
  disabled = false,
}: StyleSelectorProps) {
  const [hoveredStyle, setHoveredStyle] = useState<CreativeStyle | null>(null);

  return (
    <div className="p-3 border-b border-gray-700">
      <style jsx global>{`
        @keyframes karaoke-char {
          0%, 100% { color: #9ca3af; }
          50% { color: #facc15; transform: scale(1.1); }
        }
        .animate-karaoke-char {
          animation: karaoke-char 1s ease-in-out infinite;
          display: inline-block;
        }

        @keyframes popup-bounce {
          0%, 100% { transform: scale(1); }
          25% { transform: scale(0.8); }
          50% { transform: scale(1.15); }
          75% { transform: scale(0.95); }
        }
        .animate-popup-bounce {
          animation: popup-bounce 0.6s ease-out infinite;
        }

        @keyframes slide-in {
          0%, 100% { transform: translateX(0); opacity: 1; }
          50% { transform: translateX(-100%); opacity: 0; }
          51% { transform: translateX(100%); opacity: 0; }
        }
        .animate-slide-in {
          animation: slide-in 2s ease-in-out infinite;
        }

        @keyframes typewriter {
          0%, 100% { width: 100%; }
          50% { width: 0; }
        }
        .animate-typewriter {
          animation: typewriter 2s steps(5) infinite;
          overflow: hidden;
        }

        @keyframes highlight-pulse {
          0%, 100% { color: #facc15; transform: scale(1); }
          50% { color: #fef08a; transform: scale(1.1); }
        }
        .animate-highlight-pulse {
          animation: highlight-pulse 1s ease-in-out infinite;
          display: inline-block;
        }

        @keyframes fade-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        .animate-fade-pulse {
          animation: fade-pulse 2s ease-in-out infinite;
        }
      `}</style>

      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
        <span className="text-sm font-medium text-gray-200">Subtitle Style</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {STYLE_OPTIONS.map((option) => {
          const isSelected = currentStyle === option.value;
          const isHovered = hoveredStyle === option.value;

          return (
            <button
              key={option.value}
              onClick={() => onStyleChange(option.value)}
              onMouseEnter={() => setHoveredStyle(option.value)}
              onMouseLeave={() => setHoveredStyle(null)}
              disabled={disabled}
              className={`
                flex flex-col items-center p-2 rounded-lg border transition-all
                ${isSelected
                  ? "border-purple-500 bg-purple-500/20 text-purple-300"
                  : "border-gray-600 hover:border-gray-500 text-gray-400 hover:text-gray-300"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              `}
            >
              {/* Animated preview */}
              <div className="h-5 flex items-center justify-center mb-1 text-white">
                <StylePreview style={option.value} isActive={isSelected || isHovered} />
              </div>
              <span className="text-xs font-medium">{option.label}</span>
            </button>
          );
        })}
      </div>

      {/* Current style description */}
      <div className="mt-2 text-xs text-gray-500 text-center">
        {STYLE_OPTIONS.find((o) => o.value === currentStyle)?.description}
      </div>
    </div>
  );
}
