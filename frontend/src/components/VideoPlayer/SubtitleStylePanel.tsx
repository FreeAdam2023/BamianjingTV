/**
 * SubtitleStylePanel - Settings panel for subtitle appearance
 */

import {
  SubtitleStyle,
  FONT_FAMILIES,
  FONT_WEIGHTS,
  PRESET_COLORS,
  BACKGROUND_COLORS,
  DISPLAY_MODES,
  LANGUAGE_MODES,
} from "./constants";

interface SubtitleStylePanelProps {
  style: SubtitleStyle;
  onStyleChange: (updates: Partial<SubtitleStyle>) => void;
  onReset: () => void;
  openUpward?: boolean;
}

export default function SubtitleStylePanel({
  style,
  onStyleChange,
  onReset,
  openUpward = false,
}: SubtitleStylePanelProps) {
  return (
    <div className={`absolute ${openUpward ? "bottom-full mb-2" : "top-10"} right-2 w-72 bg-gray-800 rounded-lg shadow-xl p-4 z-20 text-sm`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-medium">Subtitle Style</h3>
        <button
          onClick={onReset}
          className="text-xs text-gray-400 hover:text-white"
        >
          Reset
        </button>
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
        <label className="block text-gray-400 text-xs mb-1">Font Family</label>
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
          <label className="block text-gray-400 text-xs mb-1">EN Size: {style.enFontSize}px</label>
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
          <label className="block text-gray-400 text-xs mb-1">ZH Size: {style.zhFontSize}px</label>
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
        <label className="block text-gray-400 text-xs mb-1">Font Weight</label>
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
          <label className="block text-gray-400 text-xs mb-1">EN Color</label>
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
          <label className="block text-gray-400 text-xs mb-1">ZH Color</label>
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
        <label className="text-gray-400 text-xs">Text Shadow</label>
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

      {/* Background color */}
      <div>
        <label className="block text-gray-400 text-xs mb-1">Background</label>
        <div className="flex gap-1">
          {BACKGROUND_COLORS.map((color) => (
            <button
              key={color}
              onClick={() => onStyleChange({ backgroundColor: color })}
              className={`w-8 h-5 rounded border-2 ${
                style.backgroundColor === color ? "border-white" : "border-gray-500"
              }`}
              style={{ backgroundColor: color }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
