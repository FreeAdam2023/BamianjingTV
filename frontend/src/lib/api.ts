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

export async function markTimelineReviewed(
  timelineId: string
): Promise<{ message: string }> {
  return fetchAPI(`/timelines/${timelineId}/mark-reviewed`, {
    method: "POST",
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
