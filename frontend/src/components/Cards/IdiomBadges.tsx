"use client";

/**
 * IdiomBadges - Displays detected idioms as clickable amber badges
 * Clicking a badge opens the idiom card in the side panel
 */

import type { IdiomAnnotation } from "@/lib/types";

interface IdiomBadgesProps {
  idioms: IdiomAnnotation[];
  onIdiomClick: (idiom: IdiomAnnotation, position: { x: number; y: number }) => void;
  className?: string;
}

// Get badge color based on idiom category
function getIdiomCategoryColor(category: string): string {
  const colors: Record<string, string> = {
    idiom: "bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30",
    phrasal_verb: "bg-amber-600/20 text-amber-200 border-amber-600/40 hover:bg-amber-600/30",
    slang: "bg-orange-500/20 text-orange-300 border-orange-500/40 hover:bg-orange-500/30",
  };
  return colors[category.toLowerCase()] || colors.idiom;
}

// Get icon for idiom category
function getIdiomCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    idiom: "\u{1F4AC}",       // 💬
    phrasal_verb: "\u{1F517}", // 🔗
    slang: "\u{1F5E3}",       // 🗣️
  };
  return icons[category.toLowerCase()] || "\u{1F4AC}";
}

export default function IdiomBadges({
  idioms,
  onIdiomClick,
  className = "",
}: IdiomBadgesProps) {
  if (!idioms || idioms.length === 0) {
    return null;
  }

  const handleClick = (
    e: React.MouseEvent<HTMLButtonElement>,
    idiom: IdiomAnnotation
  ) => {
    e.stopPropagation();
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.bottom + 4,
    };
    onIdiomClick(idiom, position);
  };

  return (
    <div className={`flex flex-wrap gap-1 ${className}`}>
      {idioms.map((idiom, idx) => (
        <button
          key={`${idiom.text}-${idx}`}
          onClick={(e) => handleClick(e, idiom)}
          className={`
            inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full
            border transition-colors cursor-pointer
            ${getIdiomCategoryColor(idiom.category)}
          `}
          title={`${idiom.category}: ${idiom.text}`}
        >
          <span>{getIdiomCategoryIcon(idiom.category)}</span>
          <span className="max-w-[140px] truncate">{idiom.text}</span>
        </button>
      ))}
    </div>
  );
}

// Named export for the loading state
export function IdiomBadgesSkeleton() {
  return (
    <div className="flex flex-wrap gap-1 animate-pulse">
      {[1, 2].map((i) => (
        <div
          key={i}
          className="h-5 w-20 bg-amber-900/30 rounded-full"
        />
      ))}
    </div>
  );
}
