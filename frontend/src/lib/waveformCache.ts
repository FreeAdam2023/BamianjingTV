/**
 * IndexedDB cache for waveform data.
 *
 * Stores waveform peaks locally to avoid repeated API calls.
 * Cache is keyed by timeline ID and track type.
 */

import { openDB, DBSchema, IDBPDatabase } from "idb";
import type { WaveformData } from "./types";

interface WaveformCacheDB extends DBSchema {
  waveforms: {
    key: string; // Format: "{timelineId}_{trackType}"
    value: WaveformCacheEntry;
    indexes: {
      byTimeline: string;
      byTimestamp: number;
    };
  };
}

interface WaveformCacheEntry {
  key: string;
  timelineId: string;
  trackType: string;
  data: WaveformData;
  timestamp: number;
  version: number;
}

const DB_NAME = "hardcore-player-cache";
const DB_VERSION = 1;
const CACHE_VERSION = 1;
const MAX_CACHE_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const MAX_CACHE_ENTRIES = 50;

let dbInstance: IDBPDatabase<WaveformCacheDB> | null = null;

/**
 * Get or create the database instance.
 */
async function getDB(): Promise<IDBPDatabase<WaveformCacheDB>> {
  if (dbInstance) {
    return dbInstance;
  }

  dbInstance = await openDB<WaveformCacheDB>(DB_NAME, DB_VERSION, {
    upgrade(db) {
      // Create waveforms store
      const store = db.createObjectStore("waveforms", { keyPath: "key" });
      store.createIndex("byTimeline", "timelineId");
      store.createIndex("byTimestamp", "timestamp");
    },
  });

  return dbInstance;
}

/**
 * Generate cache key from timeline ID and track type.
 */
function getCacheKey(timelineId: string, trackType: string): string {
  return `${timelineId}_${trackType}`;
}

/**
 * Get cached waveform data.
 *
 * @param timelineId - Timeline ID
 * @param trackType - Track type (original, dubbing, bgm)
 * @returns Cached waveform data or null if not found/expired
 */
export async function getCachedWaveform(
  timelineId: string,
  trackType: string
): Promise<WaveformData | null> {
  try {
    const db = await getDB();
    const key = getCacheKey(timelineId, trackType);
    const entry = await db.get("waveforms", key);

    if (!entry) {
      return null;
    }

    // Check if expired
    const age = Date.now() - entry.timestamp;
    if (age > MAX_CACHE_AGE_MS) {
      // Delete expired entry
      await db.delete("waveforms", key);
      return null;
    }

    // Check version compatibility
    if (entry.version !== CACHE_VERSION) {
      await db.delete("waveforms", key);
      return null;
    }

    return entry.data;
  } catch (error) {
    console.warn("Failed to read waveform cache:", error);
    return null;
  }
}

/**
 * Store waveform data in cache.
 *
 * @param timelineId - Timeline ID
 * @param trackType - Track type (original, dubbing, bgm)
 * @param data - Waveform data to cache
 */
export async function setCachedWaveform(
  timelineId: string,
  trackType: string,
  data: WaveformData
): Promise<void> {
  try {
    const db = await getDB();
    const key = getCacheKey(timelineId, trackType);

    const entry: WaveformCacheEntry = {
      key,
      timelineId,
      trackType,
      data,
      timestamp: Date.now(),
      version: CACHE_VERSION,
    };

    await db.put("waveforms", entry);

    // Cleanup old entries if needed
    await cleanupCache();
  } catch (error) {
    console.warn("Failed to write waveform cache:", error);
  }
}

/**
 * Delete cached waveform data.
 *
 * @param timelineId - Timeline ID
 * @param trackType - Track type (optional, deletes all tracks if not specified)
 */
export async function deleteCachedWaveform(
  timelineId: string,
  trackType?: string
): Promise<void> {
  try {
    const db = await getDB();

    if (trackType) {
      const key = getCacheKey(timelineId, trackType);
      await db.delete("waveforms", key);
    } else {
      // Delete all tracks for this timeline
      const tx = db.transaction("waveforms", "readwrite");
      const index = tx.store.index("byTimeline");
      let cursor = await index.openCursor(IDBKeyRange.only(timelineId));

      while (cursor) {
        await cursor.delete();
        cursor = await cursor.continue();
      }

      await tx.done;
    }
  } catch (error) {
    console.warn("Failed to delete waveform cache:", error);
  }
}

/**
 * Clear all cached waveform data.
 */
export async function clearWaveformCache(): Promise<void> {
  try {
    const db = await getDB();
    await db.clear("waveforms");
  } catch (error) {
    console.warn("Failed to clear waveform cache:", error);
  }
}

/**
 * Cleanup old cache entries to stay within size limits.
 */
async function cleanupCache(): Promise<void> {
  try {
    const db = await getDB();
    const tx = db.transaction("waveforms", "readwrite");
    const store = tx.store;
    const count = await store.count();

    if (count <= MAX_CACHE_ENTRIES) {
      return;
    }

    // Delete oldest entries
    const index = store.index("byTimestamp");
    let cursor = await index.openCursor();
    let deleted = 0;
    const toDelete = count - MAX_CACHE_ENTRIES;

    while (cursor && deleted < toDelete) {
      await cursor.delete();
      deleted++;
      cursor = await cursor.continue();
    }

    await tx.done;
  } catch (error) {
    console.warn("Failed to cleanup waveform cache:", error);
  }
}

/**
 * Get cache statistics.
 */
export async function getCacheStats(): Promise<{
  count: number;
  totalSize: number;
}> {
  try {
    const db = await getDB();
    const all = await db.getAll("waveforms");

    let totalSize = 0;
    for (const entry of all) {
      // Estimate size: peaks array is the main contributor
      totalSize += entry.data.peaks.length * 8; // 8 bytes per float64
    }

    return {
      count: all.length,
      totalSize,
    };
  } catch (error) {
    console.warn("Failed to get cache stats:", error);
    return { count: 0, totalSize: 0 };
  }
}
