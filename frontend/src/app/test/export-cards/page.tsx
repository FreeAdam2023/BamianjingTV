"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ExportWordCard, ExportEntityCard, ExportIdiomCard } from "../../../../remotion/compositions/ExportCard";
import type { WordCard, EntityCard, IdiomCard } from "@/lib/types";
import { API_BASE } from "@/lib/api";

type CardType = "word" | "entity" | "idiom";

interface LoadedCard {
  type: CardType;
  query: string;
  data: WordCard | EntityCard | IdiomCard;
}

interface StillInfo {
  filename: string;
  card_id: string;
  size: number;
  is_subtitle: boolean;
  card_type: string | null;
}

const SAMPLE_WORDS = ["gossip", "resilience", "ambiguous", "elaborate", "paradigm"];
const SAMPLE_IDIOMS = ["break the ice", "piece of cake", "spill the beans"];

// ---- Tab: React Preview ----
function ReactPreviewTab() {
  const [cards, setCards] = useState<LoadedCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customQuery, setCustomQuery] = useState("");
  const [customType, setCustomType] = useState<CardType>("word");
  const [bgColor, setBgColor] = useState("#1a2744");

  const fetchCard = useCallback(async (type: CardType, query: string): Promise<LoadedCard | null> => {
    try {
      let url = "";
      if (type === "word") url = `${API_BASE}/cards/words/${encodeURIComponent(query)}`;
      else if (type === "entity") url = `${API_BASE}/cards/entities/details?entity_id=${encodeURIComponent(query)}`;
      else if (type === "idiom") url = `${API_BASE}/cards/idioms/details?text=${encodeURIComponent(query)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      if (!data.found || !data.card) return null;
      return { type, query, data: data.card };
    } catch (e) {
      console.error(`Failed to fetch ${type} "${query}":`, e);
      return null;
    }
  }, []);

  const loadSamples = useCallback(async () => {
    setLoading(true);
    setError(null);
    const results: LoadedCard[] = [];
    const fetches = [
      fetchCard("word", SAMPLE_WORDS[0]),
      fetchCard("word", SAMPLE_WORDS[1]),
      fetchCard("idiom", SAMPLE_IDIOMS[0]),
    ];
    const settled = await Promise.allSettled(fetches);
    for (const r of settled) {
      if (r.status === "fulfilled" && r.value) results.push(r.value);
    }
    if (results.length === 0) setError("No cards loaded. Is the API running?");
    setCards(results);
    setLoading(false);
  }, [fetchCard]);

  const addCard = useCallback(async () => {
    if (!customQuery.trim()) return;
    setLoading(true);
    const result = await fetchCard(customType, customQuery.trim());
    if (result) setCards((prev) => [...prev, result]);
    else setError(`Card not found: ${customType} "${customQuery}"`);
    setLoading(false);
  }, [customType, customQuery, fetchCard]);

  useEffect(() => { loadSamples(); }, [loadSamples]);

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-6 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Type</label>
          <select value={customType} onChange={(e) => setCustomType(e.target.value as CardType)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm">
            <option value="word">Word</option>
            <option value="entity">Entity (QID)</option>
            <option value="idiom">Idiom</option>
          </select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-gray-500 mb-1">
            {customType === "word" ? "Word" : customType === "entity" ? "Wikidata QID (e.g. Q317521)" : "Idiom text"}
          </label>
          <input type="text" value={customQuery} onChange={(e) => setCustomQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCard()}
            placeholder={customType === "word" ? "gossip" : customType === "entity" ? "Q317521" : "break the ice"}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm" />
        </div>
        <button onClick={addCard} disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-1.5 rounded text-sm font-medium">Add Card</button>
        <button onClick={loadSamples} disabled={loading}
          className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-4 py-1.5 rounded text-sm font-medium">Reset</button>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Background</label>
          <select value={bgColor} onChange={(e) => setBgColor(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm">
            <option value="#1a2744">Navy (export default)</option>
            <option value="rgba(0,0,0,0.8)">Dark (80% black)</option>
            <option value="#ff0000">Red (debug)</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded px-4 py-2 mb-4 text-sm text-red-200">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-red-300">×</button>
        </div>
      )}
      {loading && <div className="text-gray-400 mb-4">Loading cards...</div>}

      <div className="flex flex-wrap gap-6">
        {cards.map((card, idx) => (
          <div key={`${card.type}-${card.query}-${idx}`} className="flex flex-col items-center">
            <div className="mb-2 text-xs text-gray-500 flex items-center gap-2">
              <span className={card.type === "word" ? "text-blue-400" : card.type === "entity" ? "text-cyan-400" : "text-amber-400"}>
                {card.type}
              </span>
              <span>&quot;{card.query}&quot;</span>
              <button onClick={() => setCards((prev) => prev.filter((_, i) => i !== idx))} className="text-gray-600 hover:text-red-400">×</button>
            </div>
            <div style={{ width: 672, height: 756, background: bgColor, position: "relative", overflow: "hidden", borderRadius: 4, border: "1px solid rgba(255,255,255,0.1)" }}>
              {card.type === "word" && <ExportWordCard card={card.data as WordCard} />}
              {card.type === "entity" && <ExportEntityCard card={card.data as EntityCard} />}
              {card.type === "idiom" && <ExportIdiomCard card={card.data as IdiomCard} />}
            </div>
            <div className="mt-1 text-[10px] text-gray-600 max-w-[672px] truncate">
              keys: [{Object.keys(card.data).join(", ")}]
            </div>
          </div>
        ))}
      </div>
      {cards.length === 0 && !loading && (
        <div className="text-gray-600 text-center py-20">No cards loaded. Add a card or click &quot;Reset&quot;.</div>
      )}
    </div>
  );
}

// ---- Tab: Job Stills (actual PNGs) ----
function JobStillsTab() {
  const [jobId, setJobId] = useState("");
  const [stills, setStills] = useState<StillInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "cards" | "subtitles">("cards");
  const [showCount, setShowCount] = useState(20);

  const loadStills = useCallback(async (id?: string) => {
    const jid = id || jobId;
    if (!jid.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/jobs/${jid.trim()}/stills`);
      if (!res.ok) throw new Error(`${res.status}: ${(await res.json()).detail || res.statusText}`);
      const data = await res.json();
      setStills(data.stills || []);
      setJobId(jid.trim());
    } catch (e: unknown) {
      setError(String((e as Error).message || e));
      setStills([]);
    }
    setLoading(false);
  }, [jobId]);

  const filtered = stills.filter((s) => {
    if (filter === "cards") return !s.is_subtitle;
    if (filter === "subtitles") return s.is_subtitle;
    return true;
  });

  const cardCount = stills.filter((s) => !s.is_subtitle).length;
  const subCount = stills.filter((s) => s.is_subtitle).length;
  const allSameSize = filtered.length > 1 && filtered.every((s) => s.size === filtered[0].size);

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-6 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-gray-500 mb-1">Job ID</label>
          <input type="text" value={jobId} onChange={(e) => setJobId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadStills()}
            placeholder="fb0c838c"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm font-mono" />
        </div>
        <button onClick={() => loadStills()} disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-1.5 rounded text-sm font-medium">
          Load Stills
        </button>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Filter</label>
          <select value={filter} onChange={(e) => setFilter(e.target.value as "all" | "cards" | "subtitles")}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm">
            <option value="cards">Cards ({cardCount})</option>
            <option value="subtitles">Subtitles ({subCount})</option>
            <option value="all">All ({stills.length})</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded px-4 py-2 mb-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {allSameSize && (
        <div className="bg-yellow-900/50 border border-yellow-700 rounded px-4 py-2 mb-4 text-sm text-yellow-200">
          All {filtered.length} images are the same size ({filtered[0].size} bytes) — likely blank renders!
        </div>
      )}

      {loading && <div className="text-gray-400 mb-4">Loading...</div>}

      <div className="flex flex-wrap gap-4">
        {filtered.slice(0, showCount).map((still) => (
          <div key={still.filename} className="flex flex-col items-center">
            <div className="mb-1 text-xs text-gray-500 flex items-center gap-2">
              {still.card_type && (
                <span className={
                  still.card_type === "word" ? "text-blue-400" :
                  still.card_type === "entity" ? "text-cyan-400" : "text-amber-400"
                }>{still.card_type}</span>
              )}
              {still.is_subtitle && <span className="text-green-400">subtitle</span>}
              <span className="font-mono">{still.card_id.slice(0, 8)}</span>
              <span className="text-gray-600">{still.size}b</span>
            </div>
            {/* Actual PNG image from backend */}
            <div style={{
              width: still.is_subtitle ? 480 : 336,
              height: still.is_subtitle ? 89 : 378,
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 4,
              overflow: "hidden",
              background: "#0a0a0a",
            }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${API_BASE}/jobs/${jobId}/stills/${still.filename}`}
                alt={still.card_id}
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
              />
            </div>
          </div>
        ))}
      </div>

      {filtered.length > showCount && (
        <button onClick={() => setShowCount((c) => c + 20)}
          className="mt-4 bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded text-sm">
          Show more ({filtered.length - showCount} remaining)
        </button>
      )}

      {stills.length === 0 && !loading && (
        <div className="text-gray-600 text-center py-20">
          Enter a Job ID and click &quot;Load Stills&quot; to view rendered PNGs.
        </div>
      )}
    </div>
  );
}

// ---- Main Page ----
export default function ExportCardTestPage() {
  const [tab, setTab] = useState<"preview" | "stills">("stills");

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-2">Export Card Test</h1>
        <p className="text-gray-400 text-sm mb-4">
          Preview ExportCard components or inspect actual rendered PNG stills from a job.
        </p>

        {/* Tab switcher */}
        <div className="flex gap-1 mb-6 border-b border-gray-800">
          <button
            onClick={() => setTab("stills")}
            className={`px-4 py-2 text-sm font-medium rounded-t ${tab === "stills" ? "bg-gray-800 text-white" : "text-gray-500 hover:text-gray-300"}`}
          >
            Job Stills (PNG)
          </button>
          <button
            onClick={() => setTab("preview")}
            className={`px-4 py-2 text-sm font-medium rounded-t ${tab === "preview" ? "bg-gray-800 text-white" : "text-gray-500 hover:text-gray-300"}`}
          >
            React Preview
          </button>
        </div>

        {tab === "stills" && <JobStillsTab />}
        {tab === "preview" && <ReactPreviewTab />}
      </div>
    </div>
  );
}
