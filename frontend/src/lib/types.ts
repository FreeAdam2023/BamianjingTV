/**
 * API types for Hardcore Player
 */

export type SegmentState = "keep" | "drop" | "undecided";
export type ExportProfile = "full" | "essence" | "both";

export interface EditableSegment {
  id: number;
  start: number;
  end: number;
  en: string;
  zh: string;
  speaker: string | null;
  state: SegmentState;
  trim_start: number;
  trim_end: number;
}

export interface Timeline {
  timeline_id: string;
  job_id: string;
  source_url: string;
  source_title: string;
  source_duration: number;
  segments: EditableSegment[];
  is_reviewed: boolean;
  export_profile: ExportProfile;
  use_traditional_chinese: boolean;
  output_full_path: string | null;
  output_essence_path: string | null;
  youtube_video_id: string | null;
  youtube_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimelineSummary {
  timeline_id: string;
  job_id: string;
  source_title: string;
  source_duration: number;
  total_segments: number;
  keep_count: number;
  drop_count: number;
  undecided_count: number;
  review_progress: number;
  is_reviewed: boolean;
  created_at: string;
  updated_at: string;
}

export interface SegmentUpdate {
  state?: SegmentState;
  trim_start?: number;
  trim_end?: number;
  en?: string;
  zh?: string;
}

export interface SegmentBatchUpdate {
  segment_ids: number[];
  state: SegmentState;
}

export interface ExportRequest {
  profile: ExportProfile;
  use_traditional_chinese: boolean;
  upload_to_youtube?: boolean;
  youtube_title?: string;
  youtube_description?: string;
  youtube_tags?: string[];
  youtube_privacy?: "private" | "unlisted" | "public";
}

// Thumbnail Types
export interface CoverFrameResponse {
  timeline_id: string;
  timestamp: number;
  url: string;
  message: string;
}

export interface TitleCandidate {
  index: number;
  main: string;
  sub: string;
  style: string;
}

export interface TitleCandidatesResponse {
  timeline_id: string;
  candidates: TitleCandidate[];
  message: string;
}

export interface ThumbnailGenerateRequest {
  timestamp?: number;  // Custom timestamp
  use_cover_frame?: boolean;  // Use previously captured cover frame
  main_title?: string;  // User-selected main title
  sub_title?: string;  // User-selected sub title
}

export interface ThumbnailResponse {
  timeline_id: string;
  thumbnail_url: string;
  message: string;
}

export interface Job {
  id: string;
  url: string;
  target_language: string;
  status: string;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  title: string | null;
  duration: number | null;
  channel: string | null;
  timeline_id: string | null;
  source_video: string | null;
  output_video: string | null;
}

export interface JobCreate {
  url: string;
  target_language?: string;
  use_traditional_chinese?: boolean;
  skip_diarization?: boolean;
}

// Timeline Editor Types
export type TrackType = 'video' | 'audio_original' | 'audio_dubbing' | 'audio_bgm' | 'subtitle';

export interface TimelineTrack {
  id: string;
  type: TrackType;
  name: string;
  muted: boolean;
  solo: boolean;
  locked: boolean;
  height: number;
  visible: boolean;
}

export interface TimelineClip {
  id: string;
  trackId: string;
  segmentId?: number;      // Link to EditableSegment
  startTime: number;       // Position on timeline (seconds)
  endTime: number;         // End position on timeline (seconds)
  sourceStart: number;     // Trim within source (seconds)
  sourceEnd: number;       // Trim end within source (seconds)
  label?: string;          // Display text (e.g., subtitle text)
  color?: string;          // Override color
}

export interface WaveformData {
  peaks: number[];         // Normalized values (0 to 1)
  sampleRate: number;      // Samples per second (e.g., 1000 = 1ms resolution)
  duration: number;        // Total duration in seconds
}

export interface TimelineState {
  playheadTime: number;    // Current playhead position (seconds)
  zoom: number;            // Pixels per second
  scrollX: number;         // Horizontal scroll offset (pixels)
  selectedClipId: string | null;
  isPlaying: boolean;
  duration: number;        // Total timeline duration (seconds)
}
