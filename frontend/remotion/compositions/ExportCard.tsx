/**
 * ExportCard — Inline-style card components for Remotion renderStill.
 *
 * Uses ONLY React inline styles (no Tailwind classes) to guarantee
 * text rendering in headless Chrome / Docker environments where
 * Tailwind CSS purging or font resolution may fail.
 *
 * Visually mirrors SidePanelWordCard / SidePanelEntityCard / SidePanelIdiomCard.
 *
 * Scale factor: The export card panel is 672px (35% of 1920) while the
 * review UI card panel is ~493px (35% of ~1408px). To achieve identical
 * visual perception at fullscreen, all sizes are multiplied by 1.36×.
 * UI text-xs (12) → 16, text-sm (14) → 19, text-base (16) → 22,
 * text-xl (20) → 27, text-2xl (24) → 33, p-4 (16) → 22.
 */

import React, { useState } from "react";
import type { WordCard, EntityCard, IdiomCard } from "../../src/lib/types";

const FONT = "'Noto Sans CJK SC', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif";
const FONT_IPA = "'Noto Sans', 'Noto Sans CJK SC', 'DejaVu Sans', Arial, sans-serif";
const FONT_MONO = "'Courier New', monospace";
const WHITE = "#ffffff";
const WHITE_80 = "rgba(255,255,255,0.8)";
const WHITE_70 = "rgba(255,255,255,0.7)";
const WHITE_60 = "rgba(255,255,255,0.6)";
const WHITE_50 = "rgba(255,255,255,0.5)";
const WHITE_40 = "rgba(255,255,255,0.4)";
const WHITE_10 = "rgba(255,255,255,0.1)";
const YELLOW_80 = "rgba(253,224,71,0.8)";
const YELLOW_70 = "rgba(253,224,71,0.7)";
const YELLOW_60 = "rgba(253,224,71,0.6)";
const AMBER_300 = "#fcd34d";
const BLUE_300 = "#93c5fd";
const PURPLE_300 = "rgba(196,181,253,1)";
const PURPLE_BG = "rgba(168,85,247,0.3)";
const GREEN_400 = "#4ade80";
const GREEN_300 = "#86efac";
const GREEN_BG = "rgba(20,83,45,0.4)";
const RED_400 = "#f87171";
const RED_300 = "#fca5a5";
const RED_BG = "rgba(127,29,29,0.4)";

// ---- Section header (e.g., "释义 ───────") ----
function SectionHeader({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 11 }}>
      <span style={{ fontSize: 16, fontWeight: 500, color: WHITE_40, textTransform: "uppercase", letterSpacing: "0.05em", fontFamily: FONT }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: WHITE_10 }} />
    </div>
  );
}

// ---- Tag chip (synonyms, antonyms) ----
function TagChip({ text, color, bg }: { text: string; color: string; bg: string }) {
  return (
    <span style={{
      display: "inline-block",
      fontSize: 16,
      padding: "3px 8px",
      background: bg,
      color,
      borderRadius: 4,
      fontFamily: FONT,
    }}>
      {text}
    </span>
  );
}

// ============ Word Card ============

export function ExportWordCard({ card }: { card: WordCard }) {
  const [imageError, setImageError] = useState(false);
  const pronunciations = card.pronunciations || [];
  const senses = card.senses || [];
  const primaryPronunciation = pronunciations.find((p) => p.region === "us") || pronunciations[0];
  const primaryImage = card.images?.[0];
  const showImage = primaryImage && !imageError;

  const sensesByPos = senses.reduce((acc, sense) => {
    const pos = sense.part_of_speech;
    if (!acc[pos]) acc[pos] = [];
    acc[pos].push(sense);
    return acc;
  }, {} as Record<string, typeof senses>);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: FONT }}>
      {/* Image header */}
      {showImage && (
        <div style={{ position: "relative", height: 160, flexShrink: 0, overflow: "hidden", background: "rgba(0,0,0,0.3)" }}>
          <img src={primaryImage} alt={card.word} style={{ width: "100%", height: "100%", objectFit: "contain" }} onError={() => setImageError(true)} />
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0.2), transparent)" }} />
        </div>
      )}

      {/* Header */}
      <div style={{
        display: "flex", alignItems: "flex-start", justifyContent: "space-between",
        padding: 22, borderBottom: `1px solid ${WHITE_10}`,
        ...(showImage ? { marginTop: -56, position: "relative" as const, zIndex: 10 } : {}),
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <span style={{ fontSize: 33, fontWeight: 700, color: WHITE }}>{card.word}</span>
            {card.lemma && card.lemma !== card.word && (
              <span style={{ fontSize: 19, color: WHITE_50 }}>({card.lemma})</span>
            )}
          </div>
          {primaryPronunciation && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
              <span style={{ color: BLUE_300, fontFamily: FONT_IPA, fontSize: 19 }}>{primaryPronunciation.ipa}</span>
            </div>
          )}
          {card.cefr_level && (
            <span style={{ display: "inline-block", marginTop: 8, padding: "3px 11px", background: PURPLE_BG, color: PURPLE_300, fontSize: 16, borderRadius: 4 }}>
              {card.cefr_level}
            </span>
          )}
        </div>
      </div>

      {/* Senses */}
      <div style={{ flex: 1, overflow: "hidden", padding: 22, display: "flex", flexDirection: "column", gap: 22 }}>
        {Object.entries(sensesByPos).map(([pos, posSenses]) => (
          <div key={pos}>
            <SectionHeader label={pos} />
            <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            {posSenses.slice(0, 3).map((sense, idx) => (
              <div key={idx} style={{ display: "flex", flexDirection: "column", gap: 11 }}>
                {/* Chinese Definition - Primary */}
                {sense.definition_zh && (
                  <p style={{ fontSize: 22, color: WHITE, fontWeight: 500, margin: 0 }}>
                    {idx + 1}. {sense.definition_zh}
                  </p>
                )}

                {/* English Definition */}
                {sense.definition && sense.definition !== sense.definition_zh && (
                  <p style={{ fontSize: 19, color: WHITE_60, margin: 0, marginLeft: 22 }}>
                    {sense.definition}
                  </p>
                )}

                {/* Examples with translations */}
                {(sense.examples?.length ?? 0) > 0 && (
                  <div style={{ marginLeft: 22, display: "flex", flexDirection: "column", gap: 11 }}>
                    {sense.examples.slice(0, 2).map((example, exIdx) => (
                      <div key={exIdx} style={{ paddingLeft: 16, borderLeft: "3px solid rgba(255,255,255,0.2)" }}>
                        <p style={{ fontSize: 19, color: WHITE_70, fontStyle: "italic", margin: 0, lineHeight: 1.6 }}>
                          &quot;{example}&quot;
                        </p>
                        {sense.examples_zh?.[exIdx] && (
                          <p style={{ fontSize: 19, color: YELLOW_70, margin: "4px 0 0", lineHeight: 1.6 }}>
                            {sense.examples_zh[exIdx]}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Synonyms & Antonyms */}
                {((sense.synonyms?.length ?? 0) > 0 || (sense.antonyms?.length ?? 0) > 0) && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 11, marginLeft: 22 }}>
                    {(sense.synonyms?.length ?? 0) > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 5 }}>
                        <span style={{ fontSize: 16, color: GREEN_400 }}>&asymp;</span>
                        {sense.synonyms!.slice(0, 3).map((syn, synIdx) => (
                          <TagChip key={synIdx} text={syn} color={GREEN_300} bg={GREEN_BG} />
                        ))}
                      </div>
                    )}
                    {(sense.antonyms?.length ?? 0) > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 5 }}>
                        <span style={{ fontSize: 16, color: RED_400 }}>&ne;</span>
                        {sense.antonyms!.slice(0, 2).map((ant, antIdx) => (
                          <TagChip key={antIdx} text={ant} color={RED_300} bg={RED_BG} />
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============ Entity Card ============

const ENTITY_TYPE_COLORS: Record<string, string> = {
  person: "rgba(59,130,246,0.5)",
  place: "rgba(34,197,94,0.5)",
  organization: "rgba(168,85,247,0.5)",
  event: "rgba(249,115,22,0.5)",
  work: "rgba(236,72,153,0.5)",
  concept: "rgba(6,182,212,0.5)",
  product: "rgba(234,179,8,0.5)",
  other: "rgba(107,114,128,0.5)",
};

export function ExportEntityCard({ card }: { card: EntityCard }) {
  const [imageError, setImageError] = useState(false);
  const zhLocalization = card.localizations?.zh;
  const badgeColor = ENTITY_TYPE_COLORS[card.entity_type] || ENTITY_TYPE_COLORS.other;
  const showImage = card.image_url && !imageError;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: FONT }}>
      {/* Header */}
      <div style={{ position: "relative", flexShrink: 0 }}>
        {showImage ? (
          <div style={{ height: 160, overflow: "hidden", background: "rgba(0,0,0,0.3)" }}>
            <img src={card.image_url!} alt={card.name} style={{ width: "100%", height: "100%", objectFit: "contain" }} onError={() => setImageError(true)} />
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0.2), transparent)" }} />
          </div>
        ) : (
          <div style={{ height: 64, background: "linear-gradient(to right, rgba(255,255,255,0.05), rgba(255,255,255,0.1))" }} />
        )}
        <span style={{
          position: "absolute", top: 8, left: 8,
          padding: "3px 11px", background: badgeColor,
          color: WHITE, fontSize: 16, fontWeight: 500, borderRadius: 4,
        }}>
          {card.entity_type}
        </span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", padding: 22 }}>
        <p style={{ fontSize: 27, fontWeight: 700, color: WHITE, margin: "0 0 6px" }}>{card.name}</p>
        {zhLocalization?.name && zhLocalization.name !== card.name && (
          <p style={{ fontSize: 19, color: YELLOW_80, margin: "0 0 16px" }}>{zhLocalization.name}</p>
        )}
        <p style={{ fontSize: 19, color: WHITE_80, margin: "0 0 16px", lineHeight: 1.7 }}>{card.description}</p>
        {zhLocalization?.description && zhLocalization.description !== card.description && (
          <p style={{ fontSize: 19, color: WHITE_60, margin: "0 0 22px", lineHeight: 1.7 }}>{zhLocalization.description}</p>
        )}

        {/* Links */}
        {(card.wikipedia_url || card.wikidata_url) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 11, marginTop: 22 }}>
            {card.wikipedia_url && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                padding: "5px 14px", background: "rgba(255,255,255,0.1)",
                color: WHITE_80, fontSize: 16, borderRadius: 4,
              }}>
                Wikipedia
              </span>
            )}
            {card.wikidata_url && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                padding: "5px 14px", background: "rgba(255,255,255,0.1)",
                color: WHITE_80, fontSize: 16, borderRadius: 4,
              }}>
                Wikidata
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Idiom Card ============

export function ExportIdiomCard({ card }: { card: IdiomCard }) {
  const categoryLabels: Record<string, string> = {
    idiom: "Idiom",
    phrasal_verb: "Phrasal Verb",
    slang: "Slang",
  };
  const categoryColors: Record<string, string> = {
    idiom: "rgba(245,158,11,0.5)",
    phrasal_verb: "rgba(217,119,6,0.5)",
    slang: "rgba(249,115,22,0.5)",
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: FONT }}>
      {/* Header gradient */}
      <div style={{ position: "relative", flexShrink: 0 }}>
        <div style={{ height: 64, background: "linear-gradient(to right, rgba(120,53,15,0.3), rgba(146,64,14,0.2))" }} />
        <span style={{
          position: "absolute", top: 8, left: 8,
          padding: "3px 11px", background: categoryColors[card.category] || categoryColors.idiom,
          color: WHITE, fontSize: 16, fontWeight: 500, borderRadius: 4,
        }}>
          {categoryLabels[card.category] || card.category}
        </span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", padding: 22, display: "flex", flexDirection: "column", gap: 22 }}>
        <p style={{ fontSize: 27, fontWeight: 700, color: AMBER_300, margin: 0 }}>{card.text}</p>

        {card.meaning_localized && (
          <div>
            <SectionHeader label="释义" />
            <p style={{ fontSize: 19, color: YELLOW_70, margin: 0, lineHeight: 1.7 }}>{card.meaning_localized}</p>
          </div>
        )}

        {card.example_localized && (
          <div>
            <SectionHeader label="例句" />
            <div style={{ paddingLeft: 16, borderLeft: "3px solid rgba(245,158,11,0.3)" }}>
              <p style={{ fontSize: 19, color: YELLOW_70, margin: 0, lineHeight: 1.7 }}>{card.example_localized}</p>
            </div>
          </div>
        )}

        {card.origin_localized && (
          <div>
            <SectionHeader label="来源" />
            <p style={{ fontSize: 19, color: YELLOW_60, margin: 0, lineHeight: 1.7 }}>{card.origin_localized}</p>
          </div>
        )}

        {card.usage_note_localized && (
          <div>
            <SectionHeader label="用法" />
            <p style={{ fontSize: 19, color: YELLOW_60, margin: 0, lineHeight: 1.7 }}>{card.usage_note_localized}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Card Placeholder (empty state) ============

function PlaceholderBadge({ text, color, bg }: { text: string; color: string; bg: string }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "5px 11px",
      background: bg,
      color,
      fontSize: 16,
      borderRadius: 9999,
      fontFamily: FONT,
    }}>
      {text}
    </span>
  );
}

export function ExportCardPlaceholder() {
  return (
    <div style={{
      height: "100%",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: 33,
      fontFamily: FONT,
    }}>
      {/* Icon */}
      <div style={{
        width: 87,
        height: 87,
        borderRadius: 22,
        background: "linear-gradient(135deg, rgba(168,85,247,0.2), rgba(59,130,246,0.2))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 22,
      }}>
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="rgba(168,85,247,0.6)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>

      {/* Title */}
      <p style={{ fontSize: 24, fontWeight: 500, color: WHITE_70, margin: "0 0 11px", textAlign: "center" }}>
        学习卡片
      </p>

      {/* Description */}
      <p style={{ fontSize: 19, color: WHITE_40, margin: "0 0 22px", textAlign: "center", maxWidth: 272, lineHeight: 1.6 }}>
        点击字幕中高亮的单词或实体查看详细卡片
      </p>

      {/* Badges */}
      <div style={{ display: "flex", gap: 11 }}>
        <PlaceholderBadge text="单词" color="rgba(96,165,250,0.6)" bg="rgba(59,130,246,0.1)" />
        <PlaceholderBadge text="实体" color="rgba(192,132,252,0.6)" bg="rgba(168,85,247,0.1)" />
        <PlaceholderBadge text="习语" color="rgba(251,191,36,0.6)" bg="rgba(245,158,11,0.1)" />
      </div>
    </div>
  );
}
