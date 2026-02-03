"use client";

import { useCallback, useRef } from "react";

interface ClickableSubtitleProps {
  text: string;
  onWordClick: (word: string, position: { x: number; y: number }) => void;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * ClickableSubtitle - Makes individual words in English text clickable
 * Clicking a word triggers a callback with the word and click position
 */
export default function ClickableSubtitle({
  text,
  onWordClick,
  className = "",
  style,
}: ClickableSubtitleProps) {
  const containerRef = useRef<HTMLSpanElement>(null);

  // Extract clean word from token (remove punctuation)
  const extractWord = (token: string): string => {
    return token.replace(/^[^\w]+|[^\w]+$/g, "").toLowerCase();
  };

  // Check if token contains a word (not just punctuation)
  const hasWord = (token: string): boolean => {
    return /[a-zA-Z]/.test(token);
  };

  const handleWordClick = useCallback(
    (e: React.MouseEvent<HTMLSpanElement>, token: string) => {
      e.stopPropagation();
      const word = extractWord(token);
      if (!word) return;

      // Get click position for popup
      const rect = (e.target as HTMLElement).getBoundingClientRect();
      const position = {
        x: rect.left + rect.width / 2,
        y: rect.bottom + 4,
      };

      onWordClick(word, position);
    },
    [onWordClick]
  );

  // Split text into tokens (words + punctuation)
  const tokens = text.split(/(\s+)/);

  return (
    <span ref={containerRef} className={className} style={style}>
      {tokens.map((token, idx) => {
        // Whitespace - render as-is
        if (/^\s+$/.test(token)) {
          return <span key={idx}>{token}</span>;
        }

        // Token with word - make clickable
        if (hasWord(token)) {
          return (
            <span
              key={idx}
              onClick={(e) => handleWordClick(e, token)}
              className="cursor-pointer hover:bg-blue-500/30 hover:text-blue-300 rounded px-0.5 -mx-0.5 transition-colors"
              title={`Click to look up "${extractWord(token)}"`}
            >
              {token}
            </span>
          );
        }

        // Pure punctuation - not clickable
        return <span key={idx}>{token}</span>;
      })}
    </span>
  );
}
