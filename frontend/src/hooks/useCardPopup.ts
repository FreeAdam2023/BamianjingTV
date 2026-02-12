"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { getWordCard, getEntityCard, getIdiomCard, searchEntity } from "@/lib/api";
import type { WordCard, EntityCard, IdiomCard } from "@/lib/types";

export type CardType = "word" | "entity" | "idiom";

export interface CardPopupState {
  isOpen: boolean;
  type: CardType | null;
  loading: boolean;
  error: string | null;
  wordCard: WordCard | null;
  entityCard: EntityCard | null;
  idiomCard: IdiomCard | null;
  position: { x: number; y: number };
  annotationNote?: string | null;
}

export interface OpenWordCardOptions {
  position?: { x: number; y: number };
  lang?: string; // "zh-TW" for Traditional Chinese, "zh-CN" for Simplified Chinese
}

interface UseCardPopupReturn {
  state: CardPopupState;
  openWordCard: (word: string, options?: OpenWordCardOptions) => Promise<void>;
  openEntityCard: (entityIdOrText: string, position?: { x: number; y: number }, forceRefresh?: boolean, annotationNote?: string | null) => Promise<void>;
  openIdiomCard: (idiomText: string, position?: { x: number; y: number }, forceRefresh?: boolean) => Promise<void>;
  close: () => void;
  refresh: () => Promise<void>;
  refreshing: boolean;
}

const initialState: CardPopupState = {
  isOpen: false,
  type: null,
  loading: false,
  error: null,
  wordCard: null,
  entityCard: null,
  idiomCard: null,
  position: { x: 0, y: 0 },
};

// Simple in-memory cache for cards
const wordCache = new Map<string, WordCard | null>();
const entityCache = new Map<string, EntityCard | null>();
const idiomCache = new Map<string, IdiomCard | null>();

export function useCardPopup(): UseCardPopupReturn {
  const [state, setState] = useState<CardPopupState>(initialState);
  const [refreshing, setRefreshing] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Track current card for refresh
  const currentCardRef = useRef<{ type: CardType; id: string } | null>(null);

  // Cancel any pending requests on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const openWordCard = useCallback(async (word: string, options?: OpenWordCardOptions & { forceRefresh?: boolean }) => {
    const normalizedWord = word.toLowerCase().trim();
    const position = options?.position;
    const lang = options?.lang;
    const forceRefresh = options?.forceRefresh ?? false;

    // Include language in cache key for different translations
    const cacheKey = lang ? `${normalizedWord}:${lang}` : normalizedWord;

    // Track current card for refresh
    currentCardRef.current = { type: "word", id: cacheKey };

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Check cache first (unless force refresh)
    if (!forceRefresh && wordCache.has(cacheKey)) {
      const cached = wordCache.get(cacheKey) ?? null;
      setState({
        isOpen: true,
        type: "word",
        loading: false,
        error: cached ? null : "未找到单词",
        wordCard: cached,
        entityCard: null,
        idiomCard: null,
        position: position || { x: 0, y: 0 },
      });
      return;
    }

    // Clear cache entry if force refresh
    if (forceRefresh) {
      wordCache.delete(cacheKey);
    }

    // Show loading state
    setState({
      isOpen: true,
      type: "word",
      loading: true,
      error: null,
      wordCard: null,
      entityCard: null,
      idiomCard: null,
      position: position || { x: 0, y: 0 },
    });

    try {
      const response = await getWordCard(normalizedWord, { lang, forceRefresh });

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

  const openEntityCard = useCallback(async (entityIdOrText: string, position?: { x: number; y: number }, forceRefresh?: boolean, annotationNote?: string | null) => {
    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Check if it's a known entity ID (Wikidata QID or CUSTOM_ prefix)
    const isEntityId = /^(Q\d+|CUSTOM_\w+)$/i.test(entityIdOrText);
    const entityId = isEntityId ? entityIdOrText.toUpperCase() : null;

    // Track current card for refresh
    currentCardRef.current = { type: "entity", id: entityIdOrText };

    // Clear cache entry if force refresh
    if (forceRefresh && entityId) {
      entityCache.delete(entityId);
    }

    // Check cache first (only if we have a QID and not force refresh)
    if (!forceRefresh && entityId && entityCache.has(entityId)) {
      const cached = entityCache.get(entityId) ?? null;
      setState({
        isOpen: true,
        type: "entity",
        loading: false,
        error: cached ? null : "未找到实体",
        wordCard: null,
        entityCard: cached,
        idiomCard: null,
        position: position || { x: 0, y: 0 },
        annotationNote: annotationNote || null,
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
      idiomCard: null,
      position: position || { x: 0, y: 0 },
      annotationNote: annotationNote || null,
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
      const response = await getEntityCard(qid, { forceRefresh: forceRefresh ?? false });

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

  const openIdiomCard = useCallback(async (idiomText: string, position?: { x: number; y: number }, forceRefresh?: boolean) => {
    const normalizedText = idiomText.trim();

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Track current card for refresh
    currentCardRef.current = { type: "idiom", id: normalizedText };

    // Clear cache entry if force refresh
    if (forceRefresh) {
      idiomCache.delete(normalizedText);
    }

    // Check cache first (unless force refresh)
    if (!forceRefresh && idiomCache.has(normalizedText)) {
      const cached = idiomCache.get(normalizedText) ?? null;
      setState({
        isOpen: true,
        type: "idiom",
        loading: false,
        error: cached ? null : "未找到习语",
        wordCard: null,
        entityCard: null,
        idiomCard: cached,
        position: position || { x: 0, y: 0 },
      });
      return;
    }

    // Show loading state
    setState({
      isOpen: true,
      type: "idiom",
      loading: true,
      error: null,
      wordCard: null,
      entityCard: null,
      idiomCard: null,
      position: position || { x: 0, y: 0 },
    });

    try {
      const response = await getIdiomCard(normalizedText, { forceRefresh: forceRefresh ?? false });

      // Always cache on force refresh; otherwise only cache meaningful content
      if (forceRefresh || response.card?.meaning_original) {
        idiomCache.set(normalizedText, response.card);
      }

      setState((prev) => ({
        ...prev,
        loading: false,
        error: response.found ? null : "未找到习语",
        idiomCard: response.card,
      }));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;

      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "获取习语卡片失败",
      }));
    }
  }, []);

  const close = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    currentCardRef.current = null;
    setState(initialState);
  }, []);

  // Refresh current card (bypass cache)
  const refresh = useCallback(async () => {
    if (!currentCardRef.current || !state.isOpen) return;

    setRefreshing(true);
    try {
      const { type, id } = currentCardRef.current;
      if (type === "word") {
        await openWordCard(id, { position: state.position, forceRefresh: true });
      } else if (type === "entity") {
        await openEntityCard(id, state.position, true);
      } else if (type === "idiom") {
        await openIdiomCard(id, state.position, true);
      }
    } finally {
      setRefreshing(false);
    }
  }, [state.isOpen, state.position, openWordCard, openEntityCard, openIdiomCard]);

  return {
    state,
    openWordCard,
    openEntityCard,
    openIdiomCard,
    close,
    refresh,
    refreshing,
  };
}

// Clear cache utility (for testing or memory management)
export function clearCardCache() {
  wordCache.clear();
  entityCache.clear();
  idiomCache.clear();
}
