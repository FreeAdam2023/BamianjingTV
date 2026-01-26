"use client";

/**
 * KeyboardHelp - Collapsible keyboard shortcuts panel
 */

import { useState } from "react";

export default function KeyboardHelp() {
  const [showHelp, setShowHelp] = useState(false);

  return (
    <div className="mt-2 flex-shrink-0">
      <button
        onClick={() => setShowHelp(!showHelp)}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        title="Keyboard shortcuts"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        <span>Shortcuts</span>
        <svg className={`w-3 h-3 transition-transform ${showHelp ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {showHelp && (
        <div className="mt-2 text-xs text-gray-500 flex flex-wrap gap-4 bg-gray-800/50 rounded-lg p-3">
          <span><kbd className="kbd">Space</kbd> Play/Pause</span>
          <span><kbd className="kbd">j</kbd>/<kbd className="kbd">k</kbd> Next/Prev</span>
          <span><kbd className="kbd">Shift+K</kbd> Keep</span>
          <span><kbd className="kbd">D</kbd> Drop</span>
          <span><kbd className="kbd">U</kbd> Undecided</span>
          <span><kbd className="kbd">L</kbd> Loop</span>
          <span><kbd className="kbd">,</kbd>/<kbd className="kbd">.</kbd> Frame ±1</span>
          <span><kbd className="kbd">[</kbd>/<kbd className="kbd">]</kbd> Prev/Next boundary</span>
        </div>
      )}
    </div>
  );
}
