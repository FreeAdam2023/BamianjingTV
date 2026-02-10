"use client";

import React, { useState, useCallback, useEffect } from "react";
import { ExportWordCard, ExportEntityCard, ExportIdiomCard } from "../../../../remotion/compositions/ExportCard";
import type { WordCard, EntityCard, IdiomCard } from "@/lib/types";
import { API_BASE } from "@/lib/api";

type CardType = "word" | "entity" | "idiom";

// ============ Job Stills Section ============

interface StillInfo {
  filename: string;
  card_id: string;
  size: number;
  is_subtitle: boolean;
  card_type: string | null;
}

function JobStillsSection() {
  const [jobId, setJobId] = useState("");
  const [stills, setStills] = useState<StillInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSubtitles, setShowSubtitles] = useState(false);

  const loadStills = useCallback(async (id?: string) => {
    const target = id || jobId;
    if (!target.trim()) return;
    setLoading(true);
    setError(null);
    setStills([]);
    try {
      const res = await fetch(`${API_BASE}/jobs/${target.trim()}/stills`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setStills(data.stills || []);
      if ((data.stills || []).length === 0) setError("No stills found for this job");
    } catch (e: unknown) {
      setError(String((e as Error).message || e));
    }
    setLoading(false);
  }, [jobId]);

  // Load from URL hash on mount (e.g., #job=fb0c838c)
  useEffect(() => {
    const hash = window.location.hash;
    const match = hash.match(/job=([a-zA-Z0-9_-]+)/);
    if (match) {
      setJobId(match[1]);
      loadStills(match[1]);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const cardStills = stills.filter(s => !s.is_subtitle);
  const subtitleStills = stills.filter(s => s.is_subtitle);
  const visibleStills = showSubtitles ? stills : cardStills;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3 text-white/80">Job Stills (Real Rendered PNGs)</h2>
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <input
          type="text"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && loadStills()}
          placeholder="Enter job ID (e.g. fb0c838c)"
          className="flex-1 min-w-[250px] bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm"
        />
        <button
          onClick={() => loadStills()}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-1.5 rounded text-sm font-medium"
        >
          {loading ? "Loading..." : "Load Stills"}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded px-4 py-2 mb-4 text-sm text-red-200">{error}</div>
      )}

      {stills.length > 0 && (
        <>
          <div className="flex items-center gap-4 mb-4 text-sm text-gray-400">
            <span>{cardStills.length} cards, {subtitleStills.length} subtitles</span>
            {subtitleStills.length > 0 && (
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showSubtitles}
                  onChange={(e) => setShowSubtitles(e.target.checked)}
                  className="rounded"
                />
                Show subtitles
              </label>
            )}
          </div>
          <div className="flex flex-wrap gap-4">
            {visibleStills.map((still) => (
              <div key={still.filename} className="flex flex-col items-center">
                <div className="mb-1 text-xs text-gray-500 flex items-center gap-2">
                  <span className={
                    still.card_type === "word" ? "text-blue-400" :
                    still.card_type === "entity" ? "text-cyan-400" :
                    still.card_type === "idiom" ? "text-amber-400" :
                    still.is_subtitle ? "text-green-400" : "text-gray-400"
                  }>
                    {still.card_type || (still.is_subtitle ? "subtitle" : "unknown")}
                  </span>
                  <span className="text-gray-600">{still.card_id}</span>
                  <span className="text-gray-700">{(still.size / 1024).toFixed(1)}KB</span>
                </div>
                <img
                  src={`${API_BASE}/jobs/${jobId.trim()}/stills/${still.filename}`}
                  alt={still.card_id}
                  style={{
                    width: still.is_subtitle ? 480 : 336,
                    height: still.is_subtitle ? 89 : 378,
                    objectFit: "contain",
                    background: "#1a2744",
                    borderRadius: 4,
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ============ Search Section ============

function SearchSection() {
  const [query, setQuery] = useState("");
  const [type, setType] = useState<CardType>("word");
  const [result, setResult] = useState<{ type: CardType; data: WordCard | EntityCard | IdiomCard } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let url = "";
      if (type === "word") url = `${API_BASE}/cards/words/${encodeURIComponent(query.trim())}`;
      else if (type === "entity") url = `${API_BASE}/cards/entities/details?entity_id=${encodeURIComponent(query.trim())}`;
      else if (type === "idiom") url = `${API_BASE}/cards/idioms/details?text=${encodeURIComponent(query.trim())}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      if (!data.found || !data.card) throw new Error("Card not found");
      setResult({ type, data: data.card });
    } catch (e: unknown) {
      setError(String((e as Error).message || e));
    }
    setLoading(false);
  }, [type, query]);

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3 text-white/80">Search API + Render Preview</h2>
      <p className="text-gray-500 text-xs mb-3">
        Fetch card data from API and render with ExportCard component (same as Remotion renderStill)
      </p>
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <select value={type} onChange={(e) => setType(e.target.value as CardType)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm">
          <option value="word">Word</option>
          <option value="entity">Entity (QID)</option>
          <option value="idiom">Idiom</option>
        </select>
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder={type === "word" ? "elaborate" : type === "entity" ? "Q317521" : "spill the beans"}
          className="flex-1 min-w-[200px] bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm" />
        <button onClick={search} disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-1.5 rounded text-sm font-medium">
          {loading ? "Loading..." : "Search"}
        </button>
      </div>
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded px-4 py-2 mb-4 text-sm text-red-200">{error}</div>
      )}
      {result && (
        <div className="flex flex-col items-start">
          <div className="mb-2 text-xs text-gray-500">
            <span className={result.type === "word" ? "text-blue-400" : result.type === "entity" ? "text-cyan-400" : "text-amber-400"}>
              {result.type}
            </span>
            {" "}from API
          </div>
          <div style={{ width: 672, height: 756, background: "#1a2744", position: "relative", overflow: "hidden", borderRadius: 4, border: "1px solid rgba(255,255,255,0.1)" }}>
            {result.type === "word" && <ExportWordCard card={result.data as WordCard} />}
            {result.type === "entity" && <ExportEntityCard card={result.data as EntityCard} />}
            {result.type === "idiom" && <ExportIdiomCard card={result.data as IdiomCard} />}
          </div>
        </div>
      )}
    </div>
  );
}

// ============ Main Page ============

export default function ExportCardTestPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-[1800px] mx-auto">
        <h1 className="text-2xl font-bold mb-2">Export Card Test</h1>
        <p className="text-gray-400 text-sm mb-6">
          Verify card rendering pipeline: view real Docker-rendered PNGs and compare with browser ExportCard preview.
        </p>

        {/* Job Stills — real rendered PNGs from Docker */}
        <JobStillsSection />

        {/* Divider */}
        <div className="border-t border-gray-800 mt-10 pt-8">
          <SearchSection />
        </div>
      </div>
    </div>
  );
}
