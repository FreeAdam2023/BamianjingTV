/**
 * SubtitleStylePanel - Modal dialog for subtitle appearance settings
 *
 * Renders as a centered modal via React portal so it's never clipped
 * by parent overflow:hidden containers.
 */

import { useEffect } from "react";
import { createPortal } from "react-dom";
import {
  SubtitleStyle,
  FONT_FAMILIES,
  FONT_WEIGHTS,
  PRESET_COLORS,
  DISPLAY_MODES,
  LANGUAGE_MODES,
} from "./constants";

interface SubtitleStylePanelProps {
  style: SubtitleStyle;
  onStyleChange: (updates: Partial<SubtitleStyle>) => void;
  onReset: () => void;
  onClose: () => void;
}

export default function SubtitleStylePanel({
  style,
  onStyleChange,
  onReset,
  onClose,
}: SubtitleStylePanelProps) {
  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const panel = (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      {/* Modal content */}
      <div className="relative w-80 bg-gray-800 rounded-xl shadow-2xl p-5 text-sm border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-medium text-base">字幕样式</h3>
          <div className="flex items-center gap-3">
            <button
              onClick={onReset}
              className="text-xs text-gray-400 hover:text-white"
            >
              重置
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white p-0.5"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Display mode */}
        <div className="mb-3">
          <label className="block text-gray-400 text-xs mb-1">显示模式</label>
          <div className="flex gap-1">
            {DISPLAY_MODES.map((mode) => (
              <button
                key={mode.value}
                onClick={() => onStyleChange({ displayMode: mode.value })}
                className={`flex-1 py-1.5 text-xs rounded ${
                  style.displayMode === mode.value
                    ? "bg-blue-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
                title={mode.description}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        {/* Language mode */}
        <div className="mb-3">
          <label className="block text-gray-400 text-xs mb-1">字幕语言</label>
          <div className="flex gap-1">
            {LANGUAGE_MODES.map((mode) => (
              <button
                key={mode.value}
                onClick={() => onStyleChange({ languageMode: mode.value })}
                className={`flex-1 py-1.5 text-xs rounded ${
                  style.languageMode === mode.value
                    ? "bg-blue-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
                title={mode.label}
              >
                {mode.icon}
              </button>
            ))}
          </div>
        </div>

        {/* Font family */}
        <div className="mb-3">
          <label className="block text-gray-400 text-xs mb-1">字体</label>
          <select
            value={style.fontFamily}
            onChange={(e) => onStyleChange({ fontFamily: e.target.value })}
            className="w-full bg-gray-700 text-white rounded px-2 py-1.5 text-sm"
          >
            {FONT_FAMILIES.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>

        {/* Font sizes */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-gray-400 text-xs mb-1">EN 字号: {style.enFontSize}px</label>
            <input
              type="range"
              min="14"
              max="48"
              value={style.enFontSize}
              onChange={(e) => onStyleChange({ enFontSize: parseInt(e.target.value) })}
              className="w-full h-1 bg-gray-600 rounded-full appearance-none cursor-pointer"
            />
          </div>
          <div>
            <label className="block text-gray-400 text-xs mb-1">ZH 字号: {style.zhFontSize}px</label>
            <input
              type="range"
              min="16"
              max="56"
              value={style.zhFontSize}
              onChange={(e) => onStyleChange({ zhFontSize: parseInt(e.target.value) })}
              className="w-full h-1 bg-gray-600 rounded-full appearance-none cursor-pointer"
            />
          </div>
        </div>

        {/* Font weight */}
        <div className="mb-3">
          <label className="block text-gray-400 text-xs mb-1">字重</label>
          <div className="flex gap-1">
            {FONT_WEIGHTS.map((w) => (
              <button
                key={w.value}
                onClick={() => onStyleChange({ fontWeight: w.value })}
                className={`flex-1 py-1 text-xs rounded ${
                  style.fontWeight === w.value
                    ? "bg-blue-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>

        {/* Colors */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-gray-400 text-xs mb-1">EN 颜色</label>
            <div className="flex flex-wrap gap-1">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  onClick={() => onStyleChange({ enColor: color })}
                  className={`w-5 h-5 rounded border-2 ${
                    style.enColor === color ? "border-white" : "border-transparent"
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
          <div>
            <label className="block text-gray-400 text-xs mb-1">ZH 颜色</label>
            <div className="flex flex-wrap gap-1">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  onClick={() => onStyleChange({ zhColor: color })}
                  className={`w-5 h-5 rounded border-2 ${
                    style.zhColor === color ? "border-white" : "border-transparent"
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Text shadow toggle */}
        <div className="flex items-center justify-between mb-3">
          <label className="text-gray-400 text-xs">文字阴影</label>
          <button
            onClick={() => onStyleChange({ textShadow: !style.textShadow })}
            className={`w-10 h-5 rounded-full transition-colors ${
              style.textShadow ? "bg-blue-500" : "bg-gray-600"
            }`}
          >
            <div
              className={`w-4 h-4 bg-white rounded-full transition-transform ${
                style.textShadow ? "translate-x-5" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>

      </div>
    </div>
  );

  // Portal to document.body so it's never clipped
  if (typeof window === "undefined") return null;
  return createPortal(panel, document.body);
}
