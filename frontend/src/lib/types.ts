/**
 * API types for Hardcore Player
 */

export type SegmentState = "keep" | "drop" | "undecided";
export type ExportProfile = "full" | "essence" | "both";
export type ExportStatus = "idle" | "exporting" | "uploading" | "completed" | "failed";

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
  // Cover frame for thumbnail
  cover_frame_time: number | null;
  // Export progress tracking
  export_status: ExportStatus;
  export_progress: number;
  export_message: string | null;
  export_error: string | null;
  export_started_at: string | null;
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
  // Export progress tracking
  export_status: ExportStatus;
  export_progress: number;
  export_message: string | null;
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

export interface ChineseConversionResponse {
  timeline_id: string;
  converted_count: number;
  target: "traditional" | "simplified";
  message: string;
}

export interface YouTubeMetadataResponse {
  timeline_id: string;
  title: string;
  description: string;
  tags: string[];
  message: string;
}

export interface UnifiedMetadataRequest {
  instruction?: string;
  num_title_candidates?: number;
}

export interface UnifiedMetadataResponse {
  timeline_id: string;
  youtube_title: string;
  youtube_description: string;
  youtube_tags: string[];
  thumbnail_candidates: TitleCandidate[];
  message: string;
}

export interface MetadataDraft {
  youtube_title: string | null;
  youtube_description: string | null;
  youtube_tags: string[] | null;
  thumbnail_candidates: TitleCandidate[] | null;
  instruction: string | null;
  selected_title: TitleCandidate | null;
  thumbnail_url: string | null;
}

export interface MetadataDraftResponse {
  timeline_id: string;
  draft: MetadataDraft;
  has_draft: boolean;
  message: string;
}

export interface ExportStatusResponse {
  timeline_id: string;
  status: ExportStatus;
  progress: number;
  message: string | null;
  error: string | null;
  youtube_url: string | null;
  full_video_path: string | null;
  essence_video_path: string | null;
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

// ============ Channel / Publication Types ============

export type ChannelType = "youtube" | "telegram" | "bilibili";
export type ChannelStatus = "active" | "disconnected" | "error";
export type PublicationStatus = "draft" | "publishing" | "published" | "failed" | "deleted";

export interface Channel {
  channel_id: string;
  name: string;
  type: ChannelType;
  status: ChannelStatus;
  youtube_channel_id: string | null;
  youtube_channel_name: string | null;
  youtube_credentials_file: string | null;
  telegram_chat_id: string | null;
  telegram_bot_token: string | null;
  default_privacy: string;
  default_tags: string[];
  description_template: string | null;
  total_publications: number;
  last_published_at: string | null;
  // OAuth status
  is_authorized: boolean;
  oauth_token_file: string | null;
  authorized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChannelSummary {
  channel_id: string;
  name: string;
  type: ChannelType;
  status: ChannelStatus;
  youtube_channel_name: string | null;
  total_publications: number;
  last_published_at: string | null;
  is_authorized?: boolean;
}

export interface OAuthStartResponse {
  auth_url: string;
  state: string;
  message: string;
}

export interface OAuthStatusResponse {
  channel_id: string;
  is_authorized: boolean;
  youtube_channel_id: string | null;
  youtube_channel_name: string | null;
  authorized_at: string | null;
  message: string;
}

export interface ChannelCreate {
  name: string;
  type: ChannelType;
  youtube_channel_id?: string;
  youtube_credentials_file?: string;
  default_privacy?: string;
  default_tags?: string[];
  description_template?: string;
}

export interface ChannelUpdate {
  name?: string;
  status?: ChannelStatus;
  default_privacy?: string;
  default_tags?: string[];
  description_template?: string;
}

export interface Publication {
  publication_id: string;
  timeline_id: string;
  channel_id: string;
  status: PublicationStatus;
  title: string;
  description: string;
  tags: string[];
  privacy: string;
  thumbnail_main_title: string | null;
  thumbnail_sub_title: string | null;
  thumbnail_url: string | null;
  platform_video_id: string | null;
  platform_url: string | null;
  platform_views: number;
  platform_likes: number;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  published_at: string | null;
  updated_at: string;
}

export interface PublicationSummary {
  publication_id: string;
  timeline_id: string;
  channel_id: string;
  channel_name: string;
  title: string;
  status: PublicationStatus;
  platform_url: string | null;
  platform_views: number;
  created_at: string;
  published_at: string | null;
}

export interface PublicationCreate {
  timeline_id: string;
  channel_id: string;
  title: string;
  description: string;
  tags?: string[];
  privacy?: string;
  thumbnail_main_title?: string;
  thumbnail_sub_title?: string;
}

export interface PublicationUpdate {
  title?: string;
  description?: string;
  tags?: string[];
  privacy?: string;
  thumbnail_main_title?: string;
  thumbnail_sub_title?: string;
}

export interface GenerateMetadataForChannelRequest {
  channel_id: string;
  instruction?: string;
}

export interface GenerateMetadataForChannelResponse {
  timeline_id: string;
  channel_id: string;
  channel_name: string;
  title: string;
  description: string;
  tags: string[];
  thumbnail_candidates: TitleCandidate[];
  message: string;
}
