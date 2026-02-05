"use client";

import React, { useState } from "react";
import type { RemotionConfig, SubtitlePosition } from "@/lib/creative-types";

interface CreativeConfigPanelProps {
  config: RemotionConfig;
  onConfigChange: (config: RemotionConfig) => void;
  disabled?: boolean;
}

export default function CreativeConfigPanel({
  config,
  onConfigChange,
  disabled = false,
}: CreativeConfigPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const updateGlobal = (key: keyof RemotionConfig["global"], value: any) => {
    onConfigChange({
      ...config,
      global: {
        ...config.global,
        [key]: value,
      },
    });
  };

  const updateAnimation = (
    section: "entrance" | "exit" | "wordHighlight",
    key: string,
    value: any
  ) => {
    if (section === "wordHighlight") {
      onConfigChange({
        ...config,
        animation: {
          ...config.animation,
          wordHighlight: {
            ...config.animation.wordHighlight,
            enabled: config.animation.wordHighlight?.enabled ?? false,
            color: config.animation.wordHighlight?.color ?? "#facc15",
            scale: config.animation.wordHighlight?.scale ?? 1.1,
            duration: config.animation.wordHighlight?.duration ?? 15,
            [key]: value,
          },
        },
      });
    } else {
      onConfigChange({
        ...config,
        animation: {
          ...config.animation,
          [section]: {
            ...config.animation[section],
            [key]: value,
          },
        },
      });
    }
  };

  return (
    <div className="border-b border-gray-700">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
        disabled={disabled}
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
          <span className="text-sm font-medium text-gray-200">Advanced Settings</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="p-3 pt-0 space-y-4">
          {/* Position */}
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Subtitle Position</label>
            <div className="flex gap-2">
              {(["top", "center", "bottom"] as SubtitlePosition[]).map((pos) => (
                <button
                  key={pos}
                  onClick={() => updateGlobal("subtitlePosition", pos)}
                  disabled={disabled}
                  className={`flex-1 py-1 px-2 text-xs rounded border transition-colors ${
                    config.global.subtitlePosition === pos
                      ? "border-blue-500 bg-blue-500/20 text-blue-300"
                      : "border-gray-600 text-gray-400 hover:border-gray-500"
                  }`}
                >
                  {pos.charAt(0).toUpperCase() + pos.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Colors */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">English Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={config.global.enColor}
                  onChange={(e) => updateGlobal("enColor", e.target.value)}
                  disabled={disabled}
                  className="w-8 h-8 rounded cursor-pointer bg-transparent border border-gray-600"
                />
                <span className="text-xs text-gray-400">{config.global.enColor}</span>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Chinese Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={config.global.zhColor}
                  onChange={(e) => updateGlobal("zhColor", e.target.value)}
                  disabled={disabled}
                  className="w-8 h-8 rounded cursor-pointer bg-transparent border border-gray-600"
                />
                <span className="text-xs text-gray-400">{config.global.zhColor}</span>
              </div>
            </div>
          </div>

          {/* Font Sizes */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                English Size: {config.global.enFontSize}px
              </label>
              <input
                type="range"
                min="16"
                max="64"
                value={config.global.enFontSize}
                onChange={(e) => updateGlobal("enFontSize", parseInt(e.target.value))}
                disabled={disabled}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                Chinese Size: {config.global.zhFontSize}px
              </label>
              <input
                type="range"
                min="16"
                max="64"
                value={config.global.zhFontSize}
                onChange={(e) => updateGlobal("zhFontSize", parseInt(e.target.value))}
                disabled={disabled}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
          </div>

          {/* Animation Durations */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                Entrance: {config.animation.entrance.duration}f
              </label>
              <input
                type="range"
                min="5"
                max="30"
                value={config.animation.entrance.duration}
                onChange={(e) => updateAnimation("entrance", "duration", parseInt(e.target.value))}
                disabled={disabled}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                Exit: {config.animation.exit.duration}f
              </label>
              <input
                type="range"
                min="5"
                max="30"
                value={config.animation.exit.duration}
                onChange={(e) => updateAnimation("exit", "duration", parseInt(e.target.value))}
                disabled={disabled}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
          </div>

          {/* Word Highlight (for karaoke/highlight styles) */}
          {(config.style === "karaoke" || config.style === "highlight") && (
            <div className="pt-2 border-t border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-400">Word Highlight</label>
                <input
                  type="checkbox"
                  checked={config.animation.wordHighlight?.enabled ?? false}
                  onChange={(e) => updateAnimation("wordHighlight", "enabled", e.target.checked)}
                  disabled={disabled}
                  className="rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
                />
              </div>
              {config.animation.wordHighlight?.enabled && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Highlight Color</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={config.animation.wordHighlight?.color ?? "#facc15"}
                        onChange={(e) => updateAnimation("wordHighlight", "color", e.target.value)}
                        disabled={disabled}
                        className="w-8 h-8 rounded cursor-pointer bg-transparent border border-gray-600"
                      />
                      <span className="text-xs text-gray-400">
                        {config.animation.wordHighlight?.color}
                      </span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">
                      Scale: {(config.animation.wordHighlight?.scale ?? 1.1).toFixed(2)}x
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="1.5"
                      step="0.05"
                      value={config.animation.wordHighlight?.scale ?? 1.1}
                      onChange={(e) => updateAnimation("wordHighlight", "scale", parseFloat(e.target.value))}
                      disabled={disabled}
                      className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Background Color */}
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Background Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={config.global.backgroundColor}
                onChange={(e) => updateGlobal("backgroundColor", e.target.value)}
                disabled={disabled}
                className="w-8 h-8 rounded cursor-pointer bg-transparent border border-gray-600"
              />
              <span className="text-xs text-gray-400">{config.global.backgroundColor}</span>
              <button
                onClick={() => updateGlobal("backgroundColor", "transparent")}
                disabled={disabled}
                className="ml-auto text-xs text-blue-400 hover:text-blue-300"
              >
                Transparent
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
