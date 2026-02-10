/**
 * ExportCard — Inline-style card components for Remotion renderStill.
 *
 * Uses ONLY React inline styles (no Tailwind classes) to guarantee
 * text rendering in headless Chrome / Docker environments where
 * Tailwind CSS purging or font resolution may fail.
 *
 * Visually mirrors SidePanelWordCard / SidePanelEntityCard / SidePanelIdiomCard.
 */

import React from "react";
import type { WordCard, EntityCard, IdiomCard } from "../../src/lib/types";

const FONT = "'Noto Sans CJK SC', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif";
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
const GREEN_300 = "#86efac";
const GREEN_BG = "rgba(20,83,45,0.4)";
const RED_300 = "#fca5a5";
const RED_BG = "rgba(127,29,29,0.4)";

// ---- Section header (e.g., "释义 ───────") ----
function SectionHeader({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
      <span style={{ fontSize: 12, fontWeight: 500, color: WHITE_40, textTransform: "uppercase", letterSpacing: "0.05em", fontFamily: FONT }}>
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
      fontSize: 12,
      padding: "2px 7px",
      background: bg,
      color,
      borderRadius: 4,
      marginRight: 4,
      marginBottom: 4,
      fontFamily: FONT,
    }}>
      {text}
    </span>
  );
}

// ============ Word Card ============

export function ExportWordCard({ card }: { card: WordCard }) {
  const pronunciations = card.pronunciations || [];
  const senses = card.senses || [];
  const primaryPronunciation = pronunciations.find((p) => p.region === "us") || pronunciations[0];
  const primaryImage = card.images?.[0];

  const sensesByPos = senses.reduce((acc, sense) => {
    const pos = sense.part_of_speech;
    if (!acc[pos]) acc[pos] = [];
    acc[pos].push(sense);
    return acc;
  }, {} as Record<string, typeof senses>);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: FONT }}>
      {/* Image header */}
      {primaryImage && (
        <div style={{ position: "relative", height: 160, flexShrink: 0, overflow: "hidden", background: "rgba(0,0,0,0.3)" }}>
          <img src={primaryImage} alt={card.word} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0.2), transparent)" }} />
        </div>
      )}

      {/* Header */}
      <div style={{
        display: "flex", alignItems: "flex-start", justifyContent: "space-between",
        padding: 16, borderBottom: `1px solid ${WHITE_10}`,
        ...(primaryImage ? { marginTop: -56, position: "relative" as const, zIndex: 10 } : {}),
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 24, fontWeight: 700, color: WHITE }}>{card.word}</span>
            {card.lemma && card.lemma !== card.word && (
              <span style={{ fontSize: 14, color: WHITE_50 }}>({card.lemma})</span>
            )}
          </div>
          {primaryPronunciation && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
              <span style={{ color: BLUE_300, fontFamily: FONT_MONO, fontSize: 14 }}>{primaryPronunciation.ipa}</span>
            </div>
          )}
          {card.cefr_level && (
            <span style={{ display: "inline-block", marginTop: 8, padding: "2px 8px", background: PURPLE_BG, color: PURPLE_300, fontSize: 12, borderRadius: 4 }}>
              {card.cefr_level}
            </span>
          )}
        </div>
      </div>

      {/* Senses */}
      <div style={{ flex: 1, overflow: "hidden", padding: 16 }}>
        {Object.entries(sensesByPos).map(([pos, posSenses]) => (
          <div key={pos} style={{ marginBottom: 20 }}>
            <SectionHeader label={pos} />
            {posSenses.slice(0, 3).map((sense, idx) => (
              <div key={idx} style={{ marginBottom: 16 }}>
                {/* Chinese Definition - Primary */}
                {sense.definition_zh && (
                  <p style={{ fontSize: 15, color: WHITE, fontWeight: 500, margin: 0, marginBottom: 6 }}>
                    {idx + 1}. {sense.definition_zh}
                  </p>
                )}

                {/* English Definition */}
                {sense.definition && sense.definition !== sense.definition_zh && (
                  <p style={{ fontSize: 13, color: WHITE_60, margin: 0, marginLeft: 16, marginBottom: 6 }}>
                    {sense.definition}
                  </p>
                )}

                {/* Examples with translations */}
                {(sense.examples?.length ?? 0) > 0 && (
                  <div style={{ marginLeft: 16, marginBottom: 8 }}>
                    {sense.examples.slice(0, 2).map((example, exIdx) => (
                      <div key={exIdx} style={{ paddingLeft: 12, borderLeft: "2px solid rgba(255,255,255,0.2)", marginBottom: 8 }}>
                        <p style={{ fontSize: 13, color: WHITE_70, fontStyle: "italic", margin: 0 }}>
                          &quot;{example}&quot;
                        </p>
                        {sense.examples_zh?.[exIdx] && (
                          <p style={{ fontSize: 13, color: YELLOW_70, margin: "3px 0 0" }}>
                            {sense.examples_zh[exIdx]}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Synonyms & Antonyms */}
                {((sense.synonyms?.length ?? 0) > 0 || (sense.antonyms?.length ?? 0) > 0) && (
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 4, marginLeft: 16, marginTop: 6 }}>
                    {(sense.synonyms?.length ?? 0) > 0 && (
                      <>
                        <span style={{ fontSize: 12, color: GREEN_300, marginRight: 2 }}>&asymp;</span>
                        {sense.synonyms!.slice(0, 3).map((syn, synIdx) => (
                          <TagChip key={synIdx} text={syn} color={GREEN_300} bg={GREEN_BG} />
                        ))}
                      </>
                    )}
                    {(sense.antonyms?.length ?? 0) > 0 && (
                      <>
                        <span style={{ fontSize: 12, color: RED_300, marginLeft: 4, marginRight: 2 }}>&ne;</span>
                        {sense.antonyms!.slice(0, 2).map((ant, antIdx) => (
                          <TagChip key={antIdx} text={ant} color={RED_300} bg={RED_BG} />
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
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
  const zhLocalization = card.localizations?.zh;
  const badgeColor = ENTITY_TYPE_COLORS[card.entity_type] || ENTITY_TYPE_COLORS.other;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: FONT }}>
      {/* Header */}
      <div style={{ position: "relative", flexShrink: 0 }}>
        {card.image_url ? (
          <div style={{ height: 160, overflow: "hidden", background: "rgba(0,0,0,0.3)" }}>
            <img src={card.image_url} alt={card.name} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0.2), transparent)" }} />
          </div>
        ) : (
          <div style={{ height: 64, background: "linear-gradient(to right, rgba(255,255,255,0.05), rgba(255,255,255,0.1))" }} />
        )}
        <span style={{
          position: "absolute", top: 8, left: 8,
          padding: "2px 8px", background: badgeColor,
          color: WHITE, fontSize: 12, fontWeight: 500, borderRadius: 4,
        }}>
          {card.entity_type}
        </span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", padding: 16 }}>
        <p style={{ fontSize: 20, fontWeight: 700, color: WHITE, margin: "0 0 4px" }}>{card.name}</p>
        {zhLocalization?.name && zhLocalization.name !== card.name && (
          <p style={{ fontSize: 14, color: YELLOW_80, margin: "0 0 12px" }}>{zhLocalization.name}</p>
        )}
        <p style={{ fontSize: 14, color: WHITE_80, margin: "0 0 12px", lineHeight: 1.6 }}>{card.description}</p>
        {zhLocalization?.description && zhLocalization.description !== card.description && (
          <p style={{ fontSize: 14, color: WHITE_60, margin: "0 0 16px", lineHeight: 1.6 }}>{zhLocalization.description}</p>
        )}

        {/* Links */}
        {(card.wikipedia_url || card.wikidata_url) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
            {card.wikipedia_url && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "4px 10px", background: "rgba(255,255,255,0.1)",
                color: WHITE_80, fontSize: 12, borderRadius: 4,
              }}>
                Wikipedia
              </span>
            )}
            {card.wikidata_url && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "4px 10px", background: "rgba(255,255,255,0.1)",
                color: WHITE_80, fontSize: 12, borderRadius: 4,
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
          padding: "2px 8px", background: categoryColors[card.category] || categoryColors.idiom,
          color: WHITE, fontSize: 12, fontWeight: 500, borderRadius: 4,
        }}>
          {categoryLabels[card.category] || card.category}
        </span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", padding: 16 }}>
        <p style={{ fontSize: 20, fontWeight: 700, color: AMBER_300, margin: "0 0 20px" }}>{card.text}</p>

        {card.meaning_localized && (
          <div style={{ marginBottom: 20 }}>
            <SectionHeader label="释义" />
            <p style={{ fontSize: 14, color: YELLOW_70, margin: 0, lineHeight: 1.6 }}>{card.meaning_localized}</p>
          </div>
        )}

        {card.example_localized && (
          <div style={{ marginBottom: 20 }}>
            <SectionHeader label="例句" />
            <div style={{ paddingLeft: 12, borderLeft: "2px solid rgba(245,158,11,0.3)" }}>
              <p style={{ fontSize: 14, color: YELLOW_70, margin: 0, lineHeight: 1.6 }}>{card.example_localized}</p>
            </div>
          </div>
        )}

        {card.origin_localized && (
          <div style={{ marginBottom: 20 }}>
            <SectionHeader label="来源" />
            <p style={{ fontSize: 14, color: YELLOW_60, margin: 0, lineHeight: 1.6 }}>{card.origin_localized}</p>
          </div>
        )}

        {card.usage_note_localized && (
          <div style={{ marginBottom: 20 }}>
            <SectionHeader label="用法" />
            <p style={{ fontSize: 14, color: YELLOW_60, margin: 0, lineHeight: 1.6 }}>{card.usage_note_localized}</p>
          </div>
        )}
      </div>
    </div>
  );
}
