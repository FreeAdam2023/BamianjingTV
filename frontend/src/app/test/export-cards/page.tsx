"use client";

import React, { useState, useCallback } from "react";
import { ExportWordCard, ExportEntityCard, ExportIdiomCard } from "../../../../remotion/compositions/ExportCard";
import type { WordCard, EntityCard, IdiomCard } from "@/lib/types";
import { API_BASE } from "@/lib/api";

type CardType = "word" | "entity" | "idiom";

// ============ Hardcoded Demo Data ============

const DEMO_WORD: WordCard = {
  word: "gossip",
  lemma: "gossip",
  pronunciations: [
    { ipa: "/ˈɡɑː.sɪp/", audio_url: null, region: "us" },
    { ipa: "/ˈɡɒs.ɪp/", audio_url: null, region: "uk" },
  ],
  senses: [
    {
      part_of_speech: "noun",
      definition: "Casual or unconstrained conversation or reports about other people, typically involving details that are not confirmed as being true.",
      definition_zh: "八卦；绯闻；闲话",
      examples: [
        "That is the centre of country gossip.",
        "Do you take part in office gossip?",
      ],
      examples_zh: [
        "这就是国别八卦中心。",
        "办公室里的八卦你会参加吗?",
      ],
      synonyms: ["rumor", "chatter", "hearsay"],
      antonyms: ["silence", "secrecy"],
    },
    {
      part_of_speech: "verb",
      definition: "Engage in gossip.",
      definition_zh: "闲聊；说长道短",
      examples: ["They would start gossiping about her behind her back."],
      examples_zh: ["他们会在她背后开始说闲话。"],
      synonyms: ["chat", "tattle"],
      antonyms: [],
    },
  ],
  images: ["https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Gossiping_Women%2C_by_Eugene_de_Blaas.jpg/300px-Gossiping_Women%2C_by_Eugene_de_Blaas.jpg"],
  frequency_rank: 4200,
  cefr_level: "B2",
  source: "demo",
  fetched_at: "2026-02-10T00:00:00Z",
};

const DEMO_ENTITY: EntityCard = {
  entity_id: "Q317521",
  entity_type: "person",
  name: "Elon Musk",
  description: "CEO of Tesla, SpaceX, and X. Entrepreneur and business magnate known for his ambitious ventures in electric vehicles, space exploration, and artificial intelligence.",
  wikipedia_url: "https://en.wikipedia.org/wiki/Elon_Musk",
  wikidata_url: "https://www.wikidata.org/wiki/Q317521",
  image_url: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Elon_Musk_Royal_Society_%28crop2%29.jpg/220px-Elon_Musk_Royal_Society_%28crop2%29.jpg",
  localizations: {
    zh: {
      name: "埃隆·马斯克",
      description: "特斯拉、SpaceX 和 X 的首席执行官。以电动汽车、太空探索和人工智能领域的雄心勃勃的事业而闻名的企业家和商业巨头。",
      aliases: ["马斯克"],
    },
  },
  source: "demo",
  fetched_at: "2026-02-10T00:00:00Z",
};

const DEMO_IDIOM: IdiomCard = {
  text: "break the ice",
  category: "idiom",
  meaning_original: "To do or say something to relieve tension or get conversation going in a strained situation or when strangers meet.",
  meaning_localized: "打破僵局；破冰。指在紧张的气氛或初次见面时，做或说一些事情来缓解紧张气氛或让对话开始进行。",
  example_original: "He told a joke to break the ice at the beginning of the meeting.",
  example_localized: "他在会议开始时讲了个笑话来打破僵局。",
  origin_original: "The phrase dates back to the 17th century and originally referred to breaking ice on waterways to allow passage of boats.",
  origin_localized: "这个短语可以追溯到17世纪，最初是指打破水道上的冰以允许船只通过。",
  usage_note_original: "Commonly used in social and professional contexts when someone initiates conversation or activity to make others feel more comfortable.",
  usage_note_localized: "常用于社交和职业场合，指某人主动发起对话或活动以让他人感到更自在。",
  source: "demo",
  fetched_at: "2026-02-10T00:00:00Z",
};

const DEMO_WORD_2: WordCard = {
  word: "resilience",
  lemma: "resilience",
  pronunciations: [
    { ipa: "/rɪˈzɪl.i.əns/", audio_url: null, region: "us" },
  ],
  senses: [
    {
      part_of_speech: "noun",
      definition: "The capacity to withstand or to recover quickly from difficulties; toughness.",
      definition_zh: "韧性；恢复力；适应力",
      examples: [
        "The resilience of the human spirit is remarkable.",
        "Children develop resilience through overcoming challenges.",
      ],
      examples_zh: [
        "人类精神的韧性是非凡的。",
        "孩子们通过克服挑战来培养韧性。",
      ],
      synonyms: ["toughness", "adaptability", "grit"],
      antonyms: ["fragility", "vulnerability"],
    },
  ],
  images: [],
  frequency_rank: 5800,
  cefr_level: "C1",
  source: "demo",
  fetched_at: "2026-02-10T00:00:00Z",
};

const DEMO_ENTITY_2: EntityCard = {
  entity_id: "Q180",
  entity_type: "place",
  name: "Tokyo",
  description: "Capital city of Japan and one of the most populous metropolitan areas in the world. A global center of finance, technology, culture, and innovation.",
  wikipedia_url: "https://en.wikipedia.org/wiki/Tokyo",
  wikidata_url: "https://www.wikidata.org/wiki/Q180",
  image_url: null,
  localizations: {
    zh: {
      name: "东京",
      description: "日本首都，世界上人口最多的大都市之一。全球金融、科技、文化和创新的中心。",
      aliases: ["东京都"],
    },
  },
  source: "demo",
  fetched_at: "2026-02-10T00:00:00Z",
};

interface DemoCard {
  type: CardType;
  label: string;
  data: WordCard | EntityCard | IdiomCard;
}

const DEMO_CARDS: DemoCard[] = [
  { type: "word", label: "gossip (with image)", data: DEMO_WORD },
  { type: "word", label: "resilience (no image)", data: DEMO_WORD_2 },
  { type: "entity", label: "Elon Musk (person)", data: DEMO_ENTITY },
  { type: "entity", label: "Tokyo (place, no image)", data: DEMO_ENTITY_2 },
  { type: "idiom", label: "break the ice", data: DEMO_IDIOM },
];

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
      <h2 className="text-lg font-semibold mb-3 text-white/80">Search API</h2>
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
        <h1 className="text-2xl font-bold mb-2">Export Card Preview</h1>
        <p className="text-gray-400 text-sm mb-6">
          ExportCard components with inline styles — exactly what Remotion renderStill outputs as PNG.
        </p>

        {/* Demo Cards Grid */}
        <div className="flex flex-wrap gap-6 mb-12">
          {DEMO_CARDS.map((card, idx) => (
            <div key={idx} className="flex flex-col items-center">
              <div className="mb-2 text-xs text-gray-500 flex items-center gap-2">
                <span className={card.type === "word" ? "text-blue-400" : card.type === "entity" ? "text-cyan-400" : "text-amber-400"}>
                  {card.type}
                </span>
                <span>{card.label}</span>
              </div>
              <div style={{ width: 672, height: 756, background: "#1a2744", position: "relative", overflow: "hidden", borderRadius: 4, border: "1px solid rgba(255,255,255,0.1)" }}>
                {card.type === "word" && <ExportWordCard card={card.data as WordCard} />}
                {card.type === "entity" && <ExportEntityCard card={card.data as EntityCard} />}
                {card.type === "idiom" && <ExportIdiomCard card={card.data as IdiomCard} />}
              </div>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div className="border-t border-gray-800 pt-8">
          <SearchSection />
        </div>
      </div>
    </div>
  );
}
