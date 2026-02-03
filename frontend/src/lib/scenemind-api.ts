/**
 * SceneMind API client and types
 */

// ============ Types ============

export type SessionStatus = "watching" | "paused" | "completed";
export type ObservationType = "slang" | "prop" | "character" | "music" | "visual" | "general";

export interface CropRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Session {
  session_id: string;
  show_name: string;
  season: number;
  episode: number;
  title: string;
  video_path: string;
  duration: number;
  status: SessionStatus;
  current_time: number;
  observation_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionSummary {
  session_id: string;
  show_name: string;
  season: number;
  episode: number;
  title: string;
  duration: number;
  status: SessionStatus;
  current_time: number;
  observation_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionCreate {
  show_name: string;
  season: number;
  episode: number;
  title: string;
  video_path: string;
  duration: number;
}

export interface Observation {
  id: string;
  session_id: string;
  timecode: number;
  frame_path: string;
  crop_path: string | null;
  crop_region: CropRegion | null;
  note: string;
  tag: ObservationType;
  created_at: string;
}

export interface ObservationCreate {
  timecode: number;
  note: string;
  tag?: ObservationType;
  crop_region?: CropRegion;
}

export interface VideoInfo {
  duration: number;
  width: number;
  height: number;
}

export interface SceneMindStats {
  total: number;
  watching: number;
  completed: number;
  total_observations: number;
}

// ============ API Base ============

function getApiBase(): string {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  }
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
  console.log(`[SceneMind API] ${method} ${endpoint}`);

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
      console.error(`[SceneMind API] ${method} ${endpoint} FAILED (${elapsed}ms):`, error);
      throw new Error(error.detail || "API request failed");
    }

    const data = await res.json();
    console.log(`[SceneMind API] ${method} ${endpoint} OK (${elapsed}ms)`);
    return data;
  } catch (err) {
    const elapsed = (performance.now() - startTime).toFixed(0);
    console.error(`[SceneMind API] ${method} ${endpoint} ERROR (${elapsed}ms):`, err);
    throw err;
  }
}

// ============ Session API ============

export async function createSession(data: SessionCreate): Promise<Session> {
  return fetchAPI<Session>("/scenemind/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listSessions(
  status?: SessionStatus,
  showName?: string,
  limit = 100
): Promise<SessionSummary[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (showName) params.set("show_name", showName);
  params.set("limit", limit.toString());
  return fetchAPI<SessionSummary[]>(`/scenemind/sessions?${params}`);
}

export async function getSession(sessionId: string): Promise<Session> {
  return fetchAPI<Session>(`/scenemind/sessions/${sessionId}`);
}

export async function deleteSession(sessionId: string): Promise<{ message: string }> {
  return fetchAPI(`/scenemind/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function completeSession(sessionId: string): Promise<Session> {
  return fetchAPI<Session>(`/scenemind/sessions/${sessionId}/complete`, {
    method: "POST",
  });
}

export async function updateSessionTime(
  sessionId: string,
  currentTime: number
): Promise<Session> {
  return fetchAPI<Session>(
    `/scenemind/sessions/${sessionId}/time?current_time=${currentTime}`,
    {
      method: "POST",
    }
  );
}

// ============ Observation API ============

export async function addObservation(
  sessionId: string,
  data: ObservationCreate
): Promise<Observation> {
  return fetchAPI<Observation>(`/scenemind/sessions/${sessionId}/observations`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getObservations(sessionId: string): Promise<Observation[]> {
  return fetchAPI<Observation[]>(`/scenemind/sessions/${sessionId}/observations`);
}

export async function getObservation(
  sessionId: string,
  observationId: string
): Promise<Observation> {
  return fetchAPI<Observation>(
    `/scenemind/sessions/${sessionId}/observations/${observationId}`
  );
}

export async function deleteObservation(
  sessionId: string,
  observationId: string
): Promise<{ message: string }> {
  return fetchAPI(`/scenemind/sessions/${sessionId}/observations/${observationId}`, {
    method: "DELETE",
  });
}

// ============ Media URLs ============

export function getVideoUrl(sessionId: string): string {
  return `${API_BASE}/scenemind/sessions/${sessionId}/video`;
}

export function getFrameUrl(sessionId: string, filename: string): string {
  return `${API_BASE}/scenemind/sessions/${sessionId}/frames/${filename}`;
}

export function getFrameUrlFromPath(sessionId: string, framePath: string): string {
  const filename = framePath.split("/").pop() || "";
  return getFrameUrl(sessionId, filename);
}

// ============ Stats API ============

export async function getSceneMindStats(): Promise<SceneMindStats> {
  return fetchAPI<SceneMindStats>("/scenemind/stats");
}

// ============ Video Info API ============

export async function getVideoInfo(videoPath: string): Promise<VideoInfo> {
  return fetchAPI<VideoInfo>(`/scenemind/video-info?video_path=${encodeURIComponent(videoPath)}`, {
    method: "POST",
  });
}

// ============ Helper Functions ============

export function formatTimecode(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function formatEpisode(season: number, episode: number): string {
  return `S${season.toString().padStart(2, "0")}E${episode.toString().padStart(2, "0")}`;
}

export function getTagColor(tag: ObservationType): string {
  switch (tag) {
    case "slang":
      return "bg-purple-500";
    case "prop":
      return "bg-blue-500";
    case "character":
      return "bg-green-500";
    case "music":
      return "bg-pink-500";
    case "visual":
      return "bg-orange-500";
    case "general":
    default:
      return "bg-gray-500";
  }
}

export function getTagLabel(tag: ObservationType): string {
  switch (tag) {
    case "slang":
      return "Slang";
    case "prop":
      return "Prop";
    case "character":
      return "Character";
    case "music":
      return "Music";
    case "visual":
      return "Visual";
    case "general":
    default:
      return "General";
  }
}
