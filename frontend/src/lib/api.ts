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
} from "./types";

const API_BASE = "/api";

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
  return `${API_BASE}/jobs/${jobId}/video`;
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
