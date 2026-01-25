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
}
