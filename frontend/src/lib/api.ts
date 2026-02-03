/**
 * API client for Hardcore Player backend
 */

import type {
  Timeline,
  TimelineSummary,
  EditableSegment,
  SegmentUpdate,
  SegmentBatchUpdate,
  ExportRequest,
  ExportStatusResponse,
  Job,
  JobCreate,
  SegmentState,
  WaveformData,
  CoverFrameResponse,
  TitleCandidatesResponse,
  ThumbnailGenerateRequest,
  ThumbnailResponse,
  ChineseConversionResponse,
  YouTubeMetadataResponse,
  UnifiedMetadataRequest,
  UnifiedMetadataResponse,
  MetadataDraft,
  MetadataDraftResponse,
  Channel,
  ChannelSummary,
  ChannelCreate,
  ChannelUpdate,
  ChannelType,
  ChannelStatus,
  Publication,
  PublicationSummary,
  PublicationCreate,
  PublicationUpdate,
  PublicationStatus,
  GenerateMetadataForChannelRequest,
  GenerateMetadataForChannelResponse,
  OAuthStartResponse,
  OAuthStatusResponse,
  // Cards
  WordCardResponse,
  EntityCardResponse,
  CardGenerateResponse,
  // Observations
  Observation,
  ObservationCreate,
  ObservationType,
  // Memory Books
  MemoryBook,
  MemoryBookSummary,
  MemoryBookCreate,
  MemoryBookUpdate,
  MemoryItem,
  MemoryItemCreate,
  MemoryItemUpdate,
  MemoryItemType,
  MemoryItemExistsResponse,
  // Dubbing
  DubbingConfig,
  DubbingConfigUpdate,
  SpeakerVoiceConfig,
  SpeakerVoiceUpdate,
  SeparationStatus,
  DubbingStatus,
  LipSyncStatus,
  PreviewRequest,
  PreviewResponse,
} from "./types";

// Get API URL: use env var or derive from current host with port 8000
function getApiBase(): string {
  // Server-side: use env var
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  }
  // Client-side: use same host with port 8000
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

const API_BASE = getApiBase();

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const method = options?.method || "GET";
  const startTime = performance.now();
  console.log(`[API] ${method} ${endpoint}`);

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    const elapsed = (performance.now() - startTime).toFixed(0);

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      console.error(`[API] ${method} ${endpoint} FAILED (${elapsed}ms):`, error);
      throw new Error(error.detail || "API request failed");
    }

    const data = await res.json();
    console.log(`[API] ${method} ${endpoint} OK (${elapsed}ms)`);
    return data;
  } catch (err) {
    const elapsed = (performance.now() - startTime).toFixed(0);
    console.error(`[API] ${method} ${endpoint} ERROR (${elapsed}ms):`, err);
    throw err;
  }
}

// ============ Timeline API ============

export async function listTimelines(
  reviewedOnly = false,
  unreviewedOnly = false,
  limit = 100
): Promise<TimelineSummary[]> {
  const params = new URLSearchParams();
  if (reviewedOnly) params.set("reviewed_only", "true");
  if (unreviewedOnly) params.set("unreviewed_only", "true");
  params.set("limit", limit.toString());

  return fetchAPI<TimelineSummary[]>(`/timelines?${params}`);
}

export async function getTimeline(timelineId: string): Promise<Timeline> {
  return fetchAPI<Timeline>(`/timelines/${timelineId}`);
}

export async function getTimelineByJob(jobId: string): Promise<Timeline> {
  return fetchAPI<Timeline>(`/timelines/by-job/${jobId}`);
}

export async function updateSegment(
  timelineId: string,
  segmentId: number,
  update: SegmentUpdate
): Promise<EditableSegment> {
  return fetchAPI<EditableSegment>(
    `/timelines/${timelineId}/segments/${segmentId}`,
    {
      method: "PATCH",
      body: JSON.stringify(update),
    }
  );
}

export async function batchUpdateSegments(
  timelineId: string,
  batch: SegmentBatchUpdate
): Promise<{ updated: number; state: string }> {
  return fetchAPI(`/timelines/${timelineId}/segments/batch`, {
    method: "POST",
    body: JSON.stringify(batch),
  });
}

export async function keepAllSegments(
  timelineId: string
): Promise<{ updated: number; state: string }> {
  return fetchAPI(`/timelines/${timelineId}/segments/keep-all`, {
    method: "POST",
  });
}

export async function dropAllSegments(
  timelineId: string
): Promise<{ updated: number; state: string }> {
  return fetchAPI(`/timelines/${timelineId}/segments/drop-all`, {
    method: "POST",
  });
}

export async function resetAllSegments(
  timelineId: string
): Promise<{ updated: number; state: string }> {
  return fetchAPI(`/timelines/${timelineId}/segments/reset-all`, {
    method: "POST",
  });
}

export async function dropSegmentsBefore(
  timelineId: string,
  time: number
): Promise<{ updated: number; state: string; time: number }> {
  return fetchAPI(`/timelines/${timelineId}/segments/drop-before?time=${time}`, {
    method: "POST",
  });
}

export async function dropSegmentsAfter(
  timelineId: string,
  time: number
): Promise<{ updated: number; state: string; time: number }> {
  return fetchAPI(`/timelines/${timelineId}/segments/drop-after?time=${time}`, {
    method: "POST",
  });
}

// ============ Video Trim API ============

export interface VideoTrimInfo {
  timeline_id: string;
  trim_start: number;
  trim_end: number | null;
  source_duration: number;
  effective_duration: number;
  message?: string;
}

export async function getVideoTrim(timelineId: string): Promise<VideoTrimInfo> {
  return fetchAPI(`/timelines/${timelineId}/trim`);
}

export async function setVideoTrim(
  timelineId: string,
  trimStart?: number,
  trimEnd?: number | null
): Promise<VideoTrimInfo> {
  const body: { trim_start?: number; trim_end?: number | null } = {};
  if (trimStart !== undefined) body.trim_start = trimStart;
  if (trimEnd !== undefined) body.trim_end = trimEnd;

  return fetchAPI(`/timelines/${timelineId}/trim`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function resetVideoTrim(timelineId: string): Promise<VideoTrimInfo> {
  return fetchAPI(`/timelines/${timelineId}/trim`, {
    method: "DELETE",
  });
}

export async function markTimelineReviewed(
  timelineId: string
): Promise<{ message: string }> {
  return fetchAPI(`/timelines/${timelineId}/mark-reviewed`, {
    method: "POST",
  });
}

export async function setSubtitleAreaRatio(
  timelineId: string,
  ratio: number
): Promise<{ timeline_id: string; subtitle_area_ratio: number; message: string }> {
  return fetchAPI(`/timelines/${timelineId}/subtitle-ratio?ratio=${ratio}`, {
    method: "POST",
  });
}

// Subtitle style mode APIs
import type { SubtitleStyleMode } from "./types";

export interface SubtitleStyleModeResponse {
  timeline_id: string;
  subtitle_style_mode: SubtitleStyleMode;
  modes: Record<SubtitleStyleMode, string>;
}

export async function getSubtitleStyleMode(
  timelineId: string
): Promise<SubtitleStyleModeResponse> {
  return fetchAPI(`/timelines/${timelineId}/subtitle-style-mode`);
}

export async function setSubtitleStyleMode(
  timelineId: string,
  mode: SubtitleStyleMode
): Promise<{ timeline_id: string; subtitle_style_mode: SubtitleStyleMode; message: string }> {
  return fetchAPI(`/timelines/${timelineId}/subtitle-style-mode?mode=${mode}`, {
    method: "POST",
  });
}

// Helper for subtitle style mode labels
export const SUBTITLE_STYLE_MODES: Record<SubtitleStyleMode, { label: string; description: string }> = {
  half_screen: {
    label: "Learning Mode",
    description: "Video on top, subtitles in dedicated bottom area",
  },
  floating: {
    label: "Watching Mode",
    description: "Transparent subtitles overlaid on video",
  },
  none: {
    label: "Dubbing Mode",
    description: "No subtitles rendered",
  },
};

// Speaker naming APIs
export interface SpeakerInfo {
  speaker_id: string;
  display_name: string;
  segment_count: number;
}

export interface SpeakersResponse {
  timeline_id: string;
  speakers: SpeakerInfo[];
  speaker_names: Record<string, string>;
}

export async function getSpeakers(timelineId: string): Promise<SpeakersResponse> {
  return fetchAPI(`/timelines/${timelineId}/speakers`);
}

export async function updateSpeakerNames(
  timelineId: string,
  speakerNames: Record<string, string>
): Promise<{ timeline_id: string; speaker_names: Record<string, string>; message: string }> {
  return fetchAPI(`/timelines/${timelineId}/speakers`, {
    method: "POST",
    body: JSON.stringify({ speaker_names: speakerNames }),
  });
}

export async function triggerExport(
  timelineId: string,
  request: ExportRequest
): Promise<{ timeline_id: string; status: string; message: string }> {
  return fetchAPI(`/timelines/${timelineId}/export`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getExportStatus(
  timelineId: string
): Promise<ExportStatusResponse> {
  return fetchAPI<ExportStatusResponse>(`/timelines/${timelineId}/export/status`);
}

export async function captureCoverFrame(
  timelineId: string,
  timestamp: number
): Promise<CoverFrameResponse> {
  return fetchAPI(`/timelines/${timelineId}/cover/capture?timestamp=${timestamp}`, {
    method: "POST",
  });
}

export async function generateTitleCandidates(
  timelineId: string,
  instruction?: string,
  numCandidates = 5
): Promise<TitleCandidatesResponse> {
  return fetchAPI(`/timelines/${timelineId}/titles/generate?num_candidates=${numCandidates}`, {
    method: "POST",
    body: instruction ? JSON.stringify({ instruction }) : undefined,
  });
}

export async function convertChineseSubtitles(
  timelineId: string,
  toTraditional: boolean
): Promise<ChineseConversionResponse> {
  return fetchAPI(`/timelines/${timelineId}/convert-chinese`, {
    method: "POST",
    body: JSON.stringify({ to_traditional: toTraditional }),
  });
}

export async function generateThumbnail(
  timelineId: string,
  request?: ThumbnailGenerateRequest
): Promise<ThumbnailResponse> {
  return fetchAPI(`/timelines/${timelineId}/thumbnail`, {
    method: "POST",
    body: request ? JSON.stringify(request) : undefined,
  });
}

export async function generateYouTubeMetadata(
  timelineId: string
): Promise<YouTubeMetadataResponse> {
  return fetchAPI(`/timelines/${timelineId}/youtube-metadata/generate`, {
    method: "POST",
  });
}

export async function generateUnifiedMetadata(
  timelineId: string,
  request?: UnifiedMetadataRequest
): Promise<UnifiedMetadataResponse> {
  return fetchAPI(`/timelines/${timelineId}/metadata/generate`, {
    method: "POST",
    body: request ? JSON.stringify(request) : undefined,
  });
}

export async function getMetadataDraft(
  timelineId: string
): Promise<MetadataDraftResponse> {
  return fetchAPI<MetadataDraftResponse>(`/timelines/${timelineId}/metadata/draft`);
}

export async function saveMetadataDraft(
  timelineId: string,
  draft: MetadataDraft
): Promise<MetadataDraftResponse> {
  return fetchAPI<MetadataDraftResponse>(`/timelines/${timelineId}/metadata/draft`, {
    method: "POST",
    body: JSON.stringify(draft),
  });
}

export function getThumbnailUrl(jobId: string, filename: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/thumbnail/${filename}`;
}

export function getCoverFrameUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/cover`;
}

// ============ Job API ============

export async function listJobs(
  status?: string,
  limit = 100
): Promise<Job[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("limit", limit.toString());

  return fetchAPI<Job[]>(`/jobs?${params}`);
}

export async function getJob(jobId: string): Promise<Job> {
  return fetchAPI<Job>(`/jobs/${jobId}`);
}

export async function createJob(job: JobCreate): Promise<Job> {
  return fetchAPI<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify(job),
  });
}

export async function retryJob(jobId: string): Promise<{ message: string }> {
  return fetchAPI(`/jobs/${jobId}/retry`, {
    method: "POST",
  });
}

export async function deleteJob(jobId: string): Promise<{ message: string }> {
  return fetchAPI(`/jobs/${jobId}`, {
    method: "DELETE",
  });
}

export async function cancelJob(jobId: string): Promise<{ message: string }> {
  return fetchAPI(`/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export interface RegenerateTranslationProgress {
  type: "progress" | "complete" | "error";
  current?: number;
  total?: number;
  updated?: number;
  message?: string;
  updated_count?: number;
}

export async function regenerateTranslationWithProgress(
  timelineId: string,
  onProgress: (progress: RegenerateTranslationProgress) => void
): Promise<{ message: string; updated_count: number }> {
  const response = await fetch(`${API_BASE}/timelines/${timelineId}/regenerate-translation`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "API request failed");
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let result = { message: "", updated_count: 0 };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6)) as RegenerateTranslationProgress;
          onProgress(data);

          if (data.type === "complete") {
            result = {
              message: data.message || "",
              updated_count: data.updated_count || 0,
            };
          } else if (data.type === "error") {
            throw new Error(data.message || "Translation failed");
          }
        } catch (e) {
          if (e instanceof SyntaxError) continue; // Skip invalid JSON
          throw e;
        }
      }
    }
  }

  return result;
}

// ============ Waveform API ============

export async function getWaveform(
  timelineId: string,
  trackType: "original" | "dubbing" | "bgm" = "original"
): Promise<WaveformData> {
  return fetchAPI<WaveformData>(`/timelines/${timelineId}/waveform/${trackType}`);
}

export async function generateWaveform(
  timelineId: string,
  trackType: "original" | "dubbing" | "bgm" = "original"
): Promise<{ timeline_id: string; track_type: string; status: string; message: string }> {
  return fetchAPI(`/timelines/${timelineId}/waveform/generate?track_type=${trackType}`, {
    method: "POST",
  });
}

// ============ Stats API ============

export async function getStats(): Promise<{
  jobs: Record<string, number>;
  queue: Record<string, unknown>;
  timelines: Record<string, number>;
}> {
  return fetchAPI("/stats");
}

// ============ Channel API ============

export async function listChannels(
  type?: ChannelType,
  status?: ChannelStatus
): Promise<ChannelSummary[]> {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (status) params.set("status", status);
  const query = params.toString();
  return fetchAPI<ChannelSummary[]>(`/channels${query ? `?${query}` : ""}`);
}

export async function getChannel(channelId: string): Promise<Channel> {
  return fetchAPI<Channel>(`/channels/${channelId}`);
}

export async function createChannel(channel: ChannelCreate): Promise<Channel> {
  return fetchAPI<Channel>("/channels", {
    method: "POST",
    body: JSON.stringify(channel),
  });
}

export async function updateChannel(
  channelId: string,
  update: ChannelUpdate
): Promise<Channel> {
  return fetchAPI<Channel>(`/channels/${channelId}`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export async function deleteChannel(
  channelId: string
): Promise<{ message: string }> {
  return fetchAPI(`/channels/${channelId}`, {
    method: "DELETE",
  });
}

// ============ Publication API ============

export async function listPublications(
  timelineId?: string,
  channelId?: string,
  status?: PublicationStatus,
  limit = 100
): Promise<PublicationSummary[]> {
  const params = new URLSearchParams();
  if (timelineId) params.set("timeline_id", timelineId);
  if (channelId) params.set("channel_id", channelId);
  if (status) params.set("status", status);
  params.set("limit", limit.toString());
  return fetchAPI<PublicationSummary[]>(`/publications?${params}`);
}

export async function getPublication(publicationId: string): Promise<Publication> {
  return fetchAPI<Publication>(`/publications/${publicationId}`);
}

export async function createPublication(
  publication: PublicationCreate
): Promise<Publication> {
  return fetchAPI<Publication>("/publications", {
    method: "POST",
    body: JSON.stringify(publication),
  });
}

export async function updatePublication(
  publicationId: string,
  update: PublicationUpdate
): Promise<Publication> {
  return fetchAPI<Publication>(`/publications/${publicationId}`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export async function deletePublication(
  publicationId: string
): Promise<{ message: string }> {
  return fetchAPI(`/publications/${publicationId}`, {
    method: "DELETE",
  });
}

export async function publishPublication(
  publicationId: string
): Promise<{ publication_id: string; status: string; message: string }> {
  return fetchAPI(`/publications/${publicationId}/publish`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getTimelinePublications(
  timelineId: string
): Promise<PublicationSummary[]> {
  return fetchAPI<PublicationSummary[]>(`/timelines/${timelineId}/publications`);
}

export async function getChannelPublications(
  channelId: string
): Promise<PublicationSummary[]> {
  return fetchAPI<PublicationSummary[]>(`/channels/${channelId}/publications`);
}

export async function generateMetadataForChannel(
  timelineId: string,
  request: GenerateMetadataForChannelRequest
): Promise<GenerateMetadataForChannelResponse> {
  return fetchAPI<GenerateMetadataForChannelResponse>(
    `/timelines/${timelineId}/generate-for-channel`,
    {
      method: "POST",
      body: JSON.stringify(request),
    }
  );
}

// ============ OAuth API ============

export async function startChannelOAuth(
  channelId: string
): Promise<OAuthStartResponse> {
  return fetchAPI<OAuthStartResponse>(`/channels/${channelId}/oauth/start`);
}

export async function getChannelOAuthStatus(
  channelId: string
): Promise<OAuthStatusResponse> {
  return fetchAPI<OAuthStatusResponse>(`/channels/${channelId}/oauth/status`);
}

export async function revokeChannelOAuth(
  channelId: string
): Promise<{ message: string }> {
  return fetchAPI(`/channels/${channelId}/oauth/revoke`, {
    method: "POST",
  });
}

// ============ Helper functions ============

export function getVideoUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/video`;
}

export function getExportVideoUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/video/export`;
}

export function getPreviewFullVideoUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/video/preview/full`;
}

export function getPreviewEssenceVideoUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/video/preview/essence`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);

  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function getStateColor(state: SegmentState): string {
  switch (state) {
    case "keep":
      return "bg-green-500";
    case "drop":
      return "bg-red-500";
    case "undecided":
    default:
      return "bg-gray-400";
  }
}

// ============ Cards API ============

export async function getWordCard(word: string): Promise<WordCardResponse> {
  return fetchAPI<WordCardResponse>(`/cards/words/${encodeURIComponent(word)}`);
}

export async function getEntityCard(entityId: string): Promise<EntityCardResponse> {
  return fetchAPI<EntityCardResponse>(`/cards/entities/${encodeURIComponent(entityId)}`);
}

export async function searchEntity(query: string, lang: string = "en"): Promise<{
  query: string;
  found: boolean;
  entity_id: string | null;
}> {
  return fetchAPI(`/cards/entities/search/${encodeURIComponent(query)}?lang=${lang}`);
}

export async function generateCardsForTimeline(
  timelineId: string,
  options?: {
    word_limit?: number;
    entity_limit?: number;
  }
): Promise<CardGenerateResponse> {
  return fetchAPI<CardGenerateResponse>(`/cards/timelines/${timelineId}/generate`, {
    method: "POST",
    body: JSON.stringify(options || {}),
  });
}

export async function getCardCacheStats(): Promise<{
  words_cached: number;
  entities_cached: number;
  total_cached: number;
  cache_dir: string;
}> {
  return fetchAPI(`/cards/cache/stats`);
}

// ============ Observations API (for WATCHING mode) ============

export async function addObservation(
  timelineId: string,
  data: ObservationCreate
): Promise<Observation> {
  return fetchAPI<Observation>(`/timelines/${timelineId}/observations`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getObservations(timelineId: string): Promise<Observation[]> {
  return fetchAPI<Observation[]>(`/timelines/${timelineId}/observations`);
}

export async function getObservation(
  timelineId: string,
  observationId: string
): Promise<Observation> {
  return fetchAPI<Observation>(`/timelines/${timelineId}/observations/${observationId}`);
}

export async function deleteObservation(
  timelineId: string,
  observationId: string
): Promise<{ message: string; observation_id: string }> {
  return fetchAPI(`/timelines/${timelineId}/observations/${observationId}`, {
    method: "DELETE",
  });
}

export function getObservationFrameUrl(
  timelineId: string,
  observationId: string,
  crop: boolean = false
): string {
  const base = getApiBase();
  return `${base}/timelines/${timelineId}/observations/${observationId}/frame?crop=${crop}`;
}

// Observation tag helpers
export const OBSERVATION_TAGS: ObservationType[] = [
  "slang",
  "prop",
  "character",
  "music",
  "visual",
  "general",
];

export function getObservationTagLabel(tag: ObservationType): string {
  const labels: Record<ObservationType, string> = {
    slang: "Slang",
    prop: "Prop",
    character: "Character",
    music: "Music",
    visual: "Visual",
    general: "General",
  };
  return labels[tag] || tag;
}

export function getObservationTagColor(tag: ObservationType): string {
  const colors: Record<ObservationType, string> = {
    slang: "bg-purple-500",
    prop: "bg-blue-500",
    character: "bg-green-500",
    music: "bg-pink-500",
    visual: "bg-orange-500",
    general: "bg-gray-500",
  };
  return colors[tag] || "bg-gray-500";
}

// ============ Memory Books API ============

export async function listMemoryBooks(): Promise<MemoryBookSummary[]> {
  return fetchAPI<MemoryBookSummary[]>("/memory-books");
}

export async function createMemoryBook(data: MemoryBookCreate): Promise<MemoryBook> {
  return fetchAPI<MemoryBook>("/memory-books", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDefaultMemoryBook(): Promise<MemoryBook> {
  return fetchAPI<MemoryBook>("/memory-books/default");
}

export async function getMemoryBook(bookId: string): Promise<MemoryBook> {
  return fetchAPI<MemoryBook>(`/memory-books/${bookId}`);
}

export async function updateMemoryBook(
  bookId: string,
  data: MemoryBookUpdate
): Promise<MemoryBook> {
  return fetchAPI<MemoryBook>(`/memory-books/${bookId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteMemoryBook(bookId: string): Promise<{ status: string; book_id: string }> {
  return fetchAPI(`/memory-books/${bookId}`, {
    method: "DELETE",
  });
}

// Memory Items

export async function listMemoryItems(bookId: string): Promise<MemoryItem[]> {
  return fetchAPI<MemoryItem[]>(`/memory-books/${bookId}/items`);
}

export async function addMemoryItem(
  bookId: string,
  data: MemoryItemCreate
): Promise<MemoryItem> {
  return fetchAPI<MemoryItem>(`/memory-books/${bookId}/items`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMemoryItem(
  bookId: string,
  itemId: string
): Promise<MemoryItem> {
  return fetchAPI<MemoryItem>(`/memory-books/${bookId}/items/${itemId}`);
}

export async function updateMemoryItem(
  bookId: string,
  itemId: string,
  data: MemoryItemUpdate
): Promise<MemoryItem> {
  return fetchAPI<MemoryItem>(`/memory-books/${bookId}/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteMemoryItem(
  bookId: string,
  itemId: string
): Promise<{ status: string; item_id: string }> {
  return fetchAPI(`/memory-books/${bookId}/items/${itemId}`, {
    method: "DELETE",
  });
}

export async function checkMemoryItemExists(
  bookId: string,
  targetType: MemoryItemType,
  targetId: string
): Promise<MemoryItemExistsResponse> {
  return fetchAPI<MemoryItemExistsResponse>(
    `/memory-books/${bookId}/items/check/${targetType}/${encodeURIComponent(targetId)}`
  );
}

// Anki Export

export function getAnkiExportUrl(bookId: string): string {
  return `${getApiBase()}/memory-books/${bookId}/export/anki`;
}

export async function exportMemoryBookToAnki(bookId: string): Promise<Blob> {
  const response = await fetch(getAnkiExportUrl(bookId));
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Export failed");
  }
  return response.blob();
}

// Memory item type helpers
export const MEMORY_ITEM_TYPES: MemoryItemType[] = ["word", "entity", "observation"];

export function getMemoryItemTypeLabel(type: MemoryItemType): string {
  const labels: Record<MemoryItemType, string> = {
    word: "Word",
    entity: "Entity",
    observation: "Observation",
  };
  return labels[type] || type;
}

export function getMemoryItemTypeIcon(type: MemoryItemType): string {
  const icons: Record<MemoryItemType, string> = {
    word: "📝",
    entity: "🏷️",
    observation: "📸",
  };
  return icons[type] || "📌";
}

// ============ Dubbing API ============

export async function getDubbingConfig(timelineId: string): Promise<DubbingConfig> {
  return fetchAPI<DubbingConfig>(`/timelines/${timelineId}/dubbing/config`);
}

export async function updateDubbingConfig(
  timelineId: string,
  update: DubbingConfigUpdate
): Promise<DubbingConfig> {
  return fetchAPI<DubbingConfig>(`/timelines/${timelineId}/dubbing/config`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export async function getDubbingSpeakers(timelineId: string): Promise<SpeakerVoiceConfig[]> {
  return fetchAPI<SpeakerVoiceConfig[]>(`/timelines/${timelineId}/dubbing/speakers`);
}

export async function updateDubbingSpeaker(
  timelineId: string,
  speakerId: string,
  update: SpeakerVoiceUpdate
): Promise<SpeakerVoiceConfig> {
  return fetchAPI<SpeakerVoiceConfig>(
    `/timelines/${timelineId}/dubbing/speakers/${speakerId}`,
    {
      method: "PATCH",
      body: JSON.stringify(update),
    }
  );
}

export async function getSeparationStatus(timelineId: string): Promise<SeparationStatus> {
  return fetchAPI<SeparationStatus>(`/timelines/${timelineId}/dubbing/separation/status`);
}

export async function triggerSeparation(
  timelineId: string
): Promise<{ message: string; status: string }> {
  return fetchAPI(`/timelines/${timelineId}/dubbing/separate`, {
    method: "POST",
  });
}

export async function getDubbingStatus(timelineId: string): Promise<DubbingStatus> {
  return fetchAPI<DubbingStatus>(`/timelines/${timelineId}/dubbing/status`);
}

export async function generateDubbing(
  timelineId: string
): Promise<{ message: string; status: string }> {
  return fetchAPI(`/timelines/${timelineId}/dubbing/generate`, {
    method: "POST",
  });
}

export async function previewDubbedSegment(
  timelineId: string,
  request: PreviewRequest
): Promise<PreviewResponse> {
  return fetchAPI<PreviewResponse>(`/timelines/${timelineId}/dubbing/preview`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getDubbingAudioUrl(timelineId: string, audioType: string): string {
  return `${getApiBase()}/timelines/${timelineId}/dubbing/audio/${audioType}`;
}

export function getDubbingPreviewUrl(timelineId: string, segmentId: number): string {
  return `${getApiBase()}/timelines/${timelineId}/dubbing/preview/${segmentId}`;
}

export function getDubbedVideoUrl(timelineId: string): string {
  return `${getApiBase()}/timelines/${timelineId}/dubbing/output`;
}

// ============ Lip Sync API ============

export async function getLipSyncStatus(timelineId: string): Promise<LipSyncStatus> {
  return fetchAPI<LipSyncStatus>(`/timelines/${timelineId}/dubbing/lip-sync/status`);
}

export async function triggerLipSync(
  timelineId: string
): Promise<{ message: string; status: string }> {
  return fetchAPI(`/timelines/${timelineId}/dubbing/lip-sync`, {
    method: "POST",
  });
}

export function getLipSyncedVideoUrl(timelineId: string): string {
  return `${getApiBase()}/timelines/${timelineId}/dubbing/lip-sync/output`;
}
