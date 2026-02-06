"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { getWordCard, getEntityCard, searchEntity } from "@/lib/api";
import type { WordCard, EntityCard } from "@/lib/types";

export type CardType = "word" | "entity";

export interface CardPopupState {
  isOpen: boolean;
  type: CardType | null;
  loading: boolean;
  error: string | null;
  wordCard: WordCard | null;
  entityCard: EntityCard | null;
  position: { x: number; y: number };
}

export interface OpenWordCardOptions {
  position?: { x: number; y: number };
  lang?: string; // "zh-TW" for Traditional Chinese, "zh-CN" for Simplified Chinese
}

interface UseCardPopupReturn {
  state: CardPopupState;
  openWordCard: (word: string, options?: OpenWordCardOptions) => Promise<void>;
  openEntityCard: (entityIdOrText: string, position?: { x: number; y: number }) => Promise<void>;
  close: () => void;
}

const initialState: CardPopupState = {
  isOpen: false,
  type: null,
  loading: false,
  error: null,
  wordCard: null,
  entityCard: null,
  position: { x: 0, y: 0 },
};

// Simple in-memory cache for cards
const wordCache = new Map<string, WordCard | null>();
const entityCache = new Map<string, EntityCard | null>();

export function useCardPopup(): UseCardPopupReturn {
  const [state, setState] = useState<CardPopupState>(initialState);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cancel any pending requests on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const openWordCard = useCallback(async (word: string, options?: OpenWordCardOptions) => {
    const normalizedWord = word.toLowerCase().trim();
    const position = options?.position;
    const lang = options?.lang;

    // Include language in cache key for different translations
    const cacheKey = lang ? `${normalizedWord}:${lang}` : normalizedWord;

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Check cache first
    if (wordCache.has(cacheKey)) {
      const cached = wordCache.get(cacheKey) ?? null;
      setState({
        isOpen: true,
        type: "word",
        loading: false,
        error: cached ? null : "未找到单词",
        wordCard: cached,
        entityCard: null,
        position: position || { x: 0, y: 0 },
      });
      return;
    }

    // Show loading state
    setState({
      isOpen: true,
      type: "word",
      loading: true,
      error: null,
      wordCard: null,
      entityCard: null,
      position: position || { x: 0, y: 0 },
    });

    try {
      const response = await getWordCard(normalizedWord, { lang });

      // Cache the result
      wordCache.set(cacheKey, response.card);

      setState((prev) => ({
        ...prev,
        loading: false,
        error: response.found ? null : "词典中未找到该单词",
        wordCard: response.card,
      }));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;

      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "获取单词卡片失败",
      }));
    }
  }, []);

  const openEntityCard = useCallback(async (entityIdOrText: string, position?: { x: number; y: number }) => {
    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Check if it's a Wikidata QID (starts with Q followed by numbers)
    const isQID = /^Q\d+$/i.test(entityIdOrText);
    const entityId = isQID ? entityIdOrText.toUpperCase() : null;

    // Check cache first (only if we have a QID)
    if (entityId && entityCache.has(entityId)) {
      const cached = entityCache.get(entityId) ?? null;
      setState({
        isOpen: true,
        type: "entity",
        loading: false,
        error: cached ? null : "未找到实体",
        wordCard: null,
        entityCard: cached,
        position: position || { x: 0, y: 0 },
      });
      return;
    }

    // Show loading state
    setState({
      isOpen: true,
      type: "entity",
      loading: true,
      error: null,
      wordCard: null,
      entityCard: null,
      position: position || { x: 0, y: 0 },
    });

    try {
      let qid = entityId;

      // If not a QID, search for it first
      if (!qid) {
        const searchResult = await searchEntity(entityIdOrText);
        if (!searchResult.found || !searchResult.entity_id) {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: "未找到实体",
          }));
          return;
        }
        qid = searchResult.entity_id;
      }

      // Fetch the entity card
      const response = await getEntityCard(qid);

      // Cache the result
      entityCache.set(qid, response.card);

      setState((prev) => ({
        ...prev,
        loading: false,
        error: response.found ? null : "未找到实体",
        entityCard: response.card,
      }));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;

      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "获取实体卡片失败",
      }));
    }
  }, []);

  const close = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setState(initialState);
  }, []);

  return {
    state,
    openWordCard,
    openEntityCard,
    close,
  };
}

// Clear cache utility (for testing or memory management)
export function clearCardCache() {
  wordCache.clear();
  entityCache.clear();
}
