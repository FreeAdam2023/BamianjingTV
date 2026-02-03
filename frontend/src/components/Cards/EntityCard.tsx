"use client";

import type { EntityCard as EntityCardType } from "@/lib/types";
import { CollectButton } from "@/components/MemoryBook";

interface EntityCardProps {
  card: EntityCardType;
  onClose: () => void;
  onAddToMemory?: (entityId: string) => void;
  sourceTimelineId?: string;
  sourceTimecode?: number;
  sourceSegmentText?: string;
}

const entityTypeLabels: Record<string, { label: string; color: string }> = {
  person: { label: "Person", color: "bg-blue-600" },
  place: { label: "Place", color: "bg-green-600" },
  organization: { label: "Organization", color: "bg-purple-600" },
  event: { label: "Event", color: "bg-orange-600" },
  work: { label: "Work", color: "bg-pink-600" },
  concept: { label: "Concept", color: "bg-cyan-600" },
  product: { label: "Product", color: "bg-yellow-600" },
  other: { label: "Other", color: "bg-gray-600" },
};

export default function EntityCard({
  card,
  onClose,
  onAddToMemory,
  sourceTimelineId,
  sourceTimecode,
  sourceSegmentText,
}: EntityCardProps) {
  const typeInfo = entityTypeLabels[card.entity_type] || entityTypeLabels.other;

  // Get Chinese localization if available
  const zhLocalization = card.localizations?.zh;

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl w-96 max-h-[500px] overflow-hidden flex flex-col">
      {/* Header with optional image */}
      <div className="relative">
        {/* Entity image */}
        {card.image_url ? (
          <div className="h-40 overflow-hidden">
            <img
              src={card.image_url}
              alt={card.name}
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-transparent to-transparent" />
          </div>
        ) : (
          <div className="h-16 bg-gradient-to-r from-gray-800 to-gray-700" />
        )}

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-2 right-2 p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Entity type badge */}
        <span
          className={`absolute top-2 left-2 px-2 py-0.5 ${typeInfo.color} text-white text-xs font-medium rounded`}
        >
          {typeInfo.label}
        </span>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 overflow-y-auto">
        {/* Name */}
        <h2 className="text-xl font-bold text-white mb-1">{card.name}</h2>

        {/* Chinese name */}
        {zhLocalization?.name && zhLocalization.name !== card.name && (
          <p className="text-gray-400 text-sm mb-2">{zhLocalization.name}</p>
        )}

        {/* Description */}
        <p className="text-gray-300 text-sm mb-4">
          {card.description}
        </p>

        {/* Chinese description */}
        {zhLocalization?.description && (
          <p className="text-gray-400 text-sm mb-4">
            {zhLocalization.description}
          </p>
        )}

        {/* Type-specific info */}
        <div className="space-y-2 text-sm">
          {/* Person info */}
          {card.entity_type === "person" && (
            <>
              {card.birth_date && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Born:</span>
                  <span className="text-gray-300">{card.birth_date}</span>
                </div>
              )}
              {card.death_date && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Died:</span>
                  <span className="text-gray-300">{card.death_date}</span>
                </div>
              )}
              {card.nationality && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Nationality:</span>
                  <span className="text-gray-300">{card.nationality}</span>
                </div>
              )}
            </>
          )}

          {/* Place info */}
          {card.entity_type === "place" && card.location && (
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Location:</span>
              <span className="text-gray-300">{card.location}</span>
            </div>
          )}

          {/* Organization info */}
          {card.entity_type === "organization" && card.founded_date && (
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Founded:</span>
              <span className="text-gray-300">{card.founded_date}</span>
            </div>
          )}
        </div>

        {/* Links */}
        <div className="mt-4 flex flex-wrap gap-2">
          {card.wikipedia_url && (
            <a
              href={card.wikipedia_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.09 13.119c-.936 1.932-2.217 4.548-2.853 5.728-.616 1.074-1.127.931-1.532.029-1.406-3.321-4.293-9.144-5.651-12.409-.251-.601-.441-.987-.619-1.139-.181-.15-.554-.24-1.122-.271C.103 5.033 0 4.982 0 4.898v-.455l.052-.045c.924-.005 5.401 0 5.401 0l.051.045v.434c0 .119-.075.176-.225.176l-.564.031c-.485.029-.727.164-.727.436 0 .135.053.33.166.601 1.082 2.646 4.818 10.521 4.818 10.521l.136.046 2.411-4.81-.482-1.067-1.658-3.264s-.318-.654-.428-.872c-.728-1.443-.712-1.518-1.447-1.617-.207-.023-.313-.05-.313-.149v-.468l.06-.045h4.292l.113.037v.451c0 .105-.076.15-.227.15l-.308.047c-.792.061-.661.381-.136 1.422l1.582 3.252 1.758-3.504c.293-.64.233-.801-.378-.801h-.283c-.104 0-.166-.045-.166-.134v-.485l.06-.045c1.538 0 4.044 0 4.044 0l.06.045v.48c0 .104-.061.157-.166.157-.503.013-.728.042-.894.111-.166.075-.406.32-.639.787l-2.713 5.478.136.046 2.932 6.029c.063.134.224.206.389.286.34.146.626.131.781.131.166 0 .271.05.271.135v.485c0 .095-.045.149-.135.149h-4.478l-.075-.045v-.451c0-.088.06-.15.166-.15h.166c.652 0 .871-.166.559-.706l-3.173-6.363-3.049 6.065c-.429.924-.35 1.004.67 1.004h.105c.105 0 .166.052.166.15v.469l-.051.044h-4.098l-.075-.045v-.468c0-.098.045-.149.166-.149.926 0 1.443-.136 1.909-.971 1.073-1.894 2.723-5.328 3.814-7.53.016-.044.016-.089 0-.133l-2.081-4.258z"/>
              </svg>
              Wikipedia
            </a>
          )}
          {card.wikidata_url && (
            <a
              href={card.wikidata_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2 3h1v18H2V3zm2 0h1v18H4V3zm14 0h1v18h-1V3zm2 0h1v18h-1V3zm2 0h1v18h-1V3zM6 3h1v3H6V3zm0 5h1v3H6V8zm0 5h1v3H6v-3zm0 5h1v3H6v-3zm2-15h1v3H8V3zm0 5h1v3H8V8zm0 5h1v3H8v-3zm0 5h1v3H8v-3zm2-12h1v6h-1V6zm0 8h1v6h-1v-6zm2-8h1v6h-1V6zm0 8h1v6h-1v-6z"/>
              </svg>
              Wikidata
            </a>
          )}
          {card.official_website && (
            <a
              href={card.official_website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Website
            </a>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-[var(--border)] flex items-center justify-between bg-[var(--card)]">
        <span className="text-xs text-gray-500">
          {card.entity_id} | {card.source}
        </span>

        <div className="flex items-center gap-2">
          <CollectButton
            targetType="entity"
            targetId={card.entity_id}
            cardData={card}
            sourceTimelineId={sourceTimelineId}
            sourceTimecode={sourceTimecode}
            sourceSegmentText={sourceSegmentText}
            size="md"
          />
          {onAddToMemory && (
            <button
              onClick={() => onAddToMemory(card.entity_id)}
              className="btn btn-sm btn-primary flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add to Memory
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
