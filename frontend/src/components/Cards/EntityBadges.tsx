"use client";

/**
 * EntityBadges - Displays detected entities as clickable badges
 * Clicking a badge opens the entity card popup
 */

import type { EntityAnnotation } from "@/lib/types";

interface EntityBadgesProps {
  entities: EntityAnnotation[];
  onEntityClick: (entity: EntityAnnotation, position: { x: number; y: number }) => void;
  className?: string;
}

// Get badge color based on entity type
function getEntityTypeColor(entityType: string): string {
  const colors: Record<string, string> = {
    person: "bg-blue-500/20 text-blue-300 border-blue-500/40 hover:bg-blue-500/30",
    place: "bg-green-500/20 text-green-300 border-green-500/40 hover:bg-green-500/30",
    organization: "bg-purple-500/20 text-purple-300 border-purple-500/40 hover:bg-purple-500/30",
    event: "bg-orange-500/20 text-orange-300 border-orange-500/40 hover:bg-orange-500/30",
    work: "bg-pink-500/20 text-pink-300 border-pink-500/40 hover:bg-pink-500/30",
    product: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 hover:bg-cyan-500/30",
    concept: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40 hover:bg-yellow-500/30",
    other: "bg-gray-500/20 text-gray-300 border-gray-500/40 hover:bg-gray-500/30",
  };
  return colors[entityType.toLowerCase()] || colors.other;
}

// Get icon for entity type
function getEntityTypeIcon(entityType: string): string {
  const icons: Record<string, string> = {
    person: "👤",
    place: "📍",
    organization: "🏢",
    event: "📅",
    work: "🎬",
    product: "📦",
    concept: "💡",
    other: "🏷️",
  };
  return icons[entityType.toLowerCase()] || "🏷️";
}

export default function EntityBadges({
  entities,
  onEntityClick,
  className = "",
}: EntityBadgesProps) {
  if (!entities || entities.length === 0) {
    return null;
  }

  const handleClick = (
    e: React.MouseEvent<HTMLButtonElement>,
    entity: EntityAnnotation
  ) => {
    e.stopPropagation();
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.bottom + 4,
    };
    onEntityClick(entity, position);
  };

  return (
    <div className={`flex flex-wrap gap-1 ${className}`}>
      {entities.map((entity, idx) => (
        <button
          key={`${entity.text}-${idx}`}
          onClick={(e) => handleClick(e, entity)}
          className={`
            inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full
            border transition-colors cursor-pointer
            ${getEntityTypeColor(entity.entity_type)}
          `}
          title={`${entity.entity_type}: ${entity.text}${entity.entity_id ? ` (${entity.entity_id})` : ""}`}
        >
          <span>{getEntityTypeIcon(entity.entity_type)}</span>
          <span className="max-w-[120px] truncate">{entity.text}</span>
        </button>
      ))}
    </div>
  );
}

// Named export for the loading state
export function EntityBadgesSkeleton() {
  return (
    <div className="flex flex-wrap gap-1 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-5 w-16 bg-gray-700 rounded-full"
        />
      ))}
    </div>
  );
}
