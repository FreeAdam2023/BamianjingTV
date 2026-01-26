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
  Job,
  JobCreate,
  SegmentState,
  WaveformData,
  ThumbnailCandidatesResponse,
  ThumbnailGenerateRequest,
  ThumbnailResponse,
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
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }

  return res.json();
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

export async function generateThumbnailCandidates(
  timelineId: string,
  numCandidates = 6
): Promise<ThumbnailCandidatesResponse> {
  return fetchAPI(`/timelines/${timelineId}/thumbnail/candidates?num_candidates=${numCandidates}`, {
    method: "POST",
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

export function getThumbnailUrl(jobId: string, filename: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/thumbnail/${filename}`;
}

export function getCandidateUrl(jobId: string, filename: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/thumbnail/candidates/${filename}`;
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

// ============ Helper functions ============

export function getVideoUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/video`;
}

export function getExportVideoUrl(jobId: string): string {
  return `${API_BASE || ""}/jobs/${jobId}/video/export`;
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
