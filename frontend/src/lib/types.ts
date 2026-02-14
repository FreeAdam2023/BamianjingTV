/**
 * API types for SceneMind
 */

export type JobMode = "learning" | "watching" | "dubbing" | "creative";
export type SegmentState = "keep" | "drop" | "undecided";
export type ExportProfile = "full" | "essence" | "both";
export type ExportStatus = "idle" | "exporting" | "uploading" | "completed" | "failed";
export type SubtitleStyleMode = "half_screen" | "floating" | "none";
export type SubtitleLanguageMode = "both" | "en" | "zh" | "none";

// Mode-specific configurations
export interface LearningConfig {
  subtitle_style: string;  // half_screen, floating
  generate_cards: boolean;
  card_types: string[];
}

export interface WatchingConfig {
  subtitle_style: string;  // half_screen, floating, none
  enable_observations: boolean;
}

export interface DubbingConfig {
  voice_clone: boolean;
  voice_model: string;  // xtts_v2, gpt_sovits, preset
  voice_preset: string | null;
  voice_similarity: number;
  lip_sync: boolean;
  lip_sync_model: string;  // wav2lip, sadtalker
  keep_bgm: boolean;
  keep_sfx: boolean;
  bgm_volume: number;
  subtitle_style: string;  // none, floating, half_screen
  subtitle_language: string;  // source, target, both
}

export interface EditableSegment {
  id: number;
  start: number;
  end: number;
  en: string;
  zh: string;
  speaker: string | null;
  state: SegmentState;
  subtitle_hidden: boolean;
  bookmarked: boolean;
  trim_start: number;
  trim_end: number;
}

export interface Timeline {
  timeline_id: string;
  job_id: string;
  mode: JobMode;
  source_url: string;
  source_title: string;
  source_duration: number;
  segments: EditableSegment[];
  is_reviewed: boolean;
  export_profile: ExportProfile;
  use_traditional_chinese: boolean;
  subtitle_area_ratio: number;  // fixed 0.33
  subtitle_style_mode: SubtitleStyleMode;  // half_screen, floating, none
  subtitle_language_mode: SubtitleLanguageMode;  // both, en, zh, none
  // Video-level trim (independent of subtitle segments)
  video_trim_start: number;  // Video starts from this time (seconds)
  video_trim_end: number | null;  // Video ends at this time (null = full duration)
  speaker_names: Record<string, string>;  // Maps speaker IDs to display names
  output_full_path: string | null;
  output_essence_path: string | null;
  youtube_video_id: string | null;
  youtube_url: string | null;
  // Cover frame for thumbnail
  cover_frame_time: number | null;
  // Observations (for WATCHING mode)
  observations: Observation[];
  // Entity annotations cache (keyed by segment_id)
  segment_annotations: Record<number, SegmentAnnotations>;
  // Pinned cards for export
  pinned_cards: PinnedCard[];
  card_display_duration: number;  // Default display duration in seconds
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
  mode: JobMode;
  source_title: string;
  source_duration: number;
  total_segments: number;
  keep_count: number;
  drop_count: number;
  undecided_count: number;
  review_progress: number;
  is_reviewed: boolean;
  // Observation count (for WATCHING mode)
  observation_count: number;
  // Export progress tracking
  export_status: ExportStatus;
  export_progress: number;
  export_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SegmentUpdate {
  state?: SegmentState;
  subtitle_hidden?: boolean;
  bookmarked?: boolean;
  trim_start?: number;
  trim_end?: number;
  en?: string;
  zh?: string;
  start?: number;
  end?: number;
}

export interface SegmentBatchUpdate {
  segment_ids: number[];
  state: SegmentState;
}

export interface SubtitleStyleOptions {
  en_font_size?: number;
  zh_font_size?: number;
  en_color?: string;  // Hex color like "#ffffff"
  zh_color?: string;  // Hex color like "#facc15"
  font_weight?: string;  // "400", "500", "600", "700"
  background_color?: string;  // Hex color like "#1a2744"
}

export interface ExportRequest {
  profile: ExportProfile;
  use_traditional_chinese: boolean;
  subtitle_style_mode?: SubtitleStyleMode;  // half_screen, floating, none
  subtitle_style?: SubtitleStyleOptions;
  test_seconds?: number;  // Quick test: limit export to first N seconds
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

export interface StepTiming {
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
}

export interface ApiCost {
  service: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  audio_seconds: number;
  cost_usd: number;
  description: string | null;
  timestamp: string;
}

export interface Job {
  id: string;
  url: string;
  mode: JobMode;
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
  // Mode-specific configs
  learning_config?: LearningConfig | null;
  watching_config?: WatchingConfig | null;
  dubbing_config?: DubbingConfig | null;
  // Processing stats
  step_timings?: Record<string, StepTiming>;
  api_costs?: ApiCost[];
  total_processing_seconds?: number | null;
  total_cost_usd?: number | null;
}

export type WhisperModel = "tiny" | "base" | "small" | "medium" | "large-v3";

export interface JobCreate {
  url: string;
  mode?: JobMode;
  target_language?: string;
  use_traditional_chinese?: boolean;
  skip_diarization?: boolean;
  whisper_model?: WhisperModel;
  learning_config?: Partial<LearningConfig>;
  watching_config?: Partial<WatchingConfig>;
  dubbing_config?: Partial<DubbingConfig>;
}

// ============ Observation Types (for WATCHING mode) ============

export type ObservationType = "slang" | "prop" | "character" | "music" | "visual" | "general";

export interface CropRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Observation {
  id: string;
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
  tag: ObservationType;
  crop_region?: CropRegion;
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

// ============ Card System Types ============

export interface Pronunciation {
  ipa: string;
  audio_url: string | null;
  region: string;
}

export interface WordSense {
  part_of_speech: string;
  definition: string;
  definition_zh: string | null;
  examples: string[];
  examples_zh: string[];
  synonyms: string[];
  antonyms: string[];
}

export interface WordCard {
  word: string;
  lemma: string;
  pronunciations: Pronunciation[];
  senses: WordSense[];
  images: string[];
  frequency_rank: number | null;
  cefr_level: string | null;
  source: string;
  fetched_at: string;
}

export interface EntityLocalization {
  name: string;
  description: string | null;
  aliases: string[];
}

export interface EntityCard {
  entity_id: string;
  entity_type: string;
  name: string;
  description: string;
  wikipedia_url: string | null;
  wikidata_url: string | null;
  image_url: string | null;
  localizations: Record<string, EntityLocalization>;
  source: string;
  fetched_at: string;
}

export interface InsightCard {
  title: string;
  content: string;
  category: string;  // general, vocabulary, expression, culture, etc.
  related_text: string | null;  // The text/line being discussed
  frame_data: string | null;  // Base64 image if screenshot was included
}

export interface WordCardResponse {
  word: string;
  found: boolean;
  card: WordCard | null;
  error: string | null;
}

export interface EntityCardResponse {
  entity_id: string;
  found: boolean;
  card: EntityCard | null;
  error: string | null;
}

export interface CardGenerateResponse {
  timeline_id: string;
  words_extracted: number;
  entities_extracted: number;
  cards_generated: number;
  message: string;
}

// ============ Memory Book Types ============

export type MemoryItemType = "word" | "entity" | "observation";

export interface MemoryItem {
  item_id: string;
  book_id: string;
  target_type: MemoryItemType;
  target_id: string;
  source_timeline_id: string | null;
  source_timecode: number | null;
  source_segment_text: string | null;
  user_notes: string;
  tags: string[];
  card_data: Record<string, unknown> | null;
  created_at: string;
}

export interface MemoryBook {
  book_id: string;
  name: string;
  description: string;
  item_count: number;
  items: MemoryItem[];
  created_at: string;
  updated_at: string;
}

export interface MemoryBookSummary {
  book_id: string;
  name: string;
  description: string;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface MemoryBookCreate {
  name: string;
  description?: string;
}

export interface MemoryBookUpdate {
  name?: string;
  description?: string;
}

export interface MemoryItemCreate {
  target_type: MemoryItemType;
  target_id: string;
  source_timeline_id?: string;
  source_timecode?: number;
  source_segment_text?: string;
  user_notes?: string;
  tags?: string[];
  card_data?: Record<string, unknown>;
}

export interface MemoryItemUpdate {
  user_notes?: string;
  tags?: string[];
}

export interface MemoryItemExistsResponse {
  exists: boolean;
  item_id: string | null;
}

// ============ Dubbing Types ============

export interface DubbingConfig {
  bgm_volume: number;
  sfx_volume: number;
  vocal_volume: number;
  target_language: string;
  keep_bgm: boolean;
  keep_sfx: boolean;
  voice_clone: boolean;
  voice_model: string;  // xtts_v2, gpt_sovits, preset
  voice_preset: string | null;
  voice_similarity: number;  // 0-1
  lip_sync_model: string;  // wav2lip, sadtalker
}

export interface DubbingConfigUpdate {
  bgm_volume?: number;
  sfx_volume?: number;
  vocal_volume?: number;
  target_language?: string;
  keep_bgm?: boolean;
  keep_sfx?: boolean;
  voice_clone?: boolean;
  voice_model?: string;
  voice_preset?: string;
  voice_similarity?: number;
  lip_sync_model?: string;
}

export interface SpeakerVoiceConfig {
  speaker_id: string;
  display_name: string;
  voice_sample_path: string | null;
  is_enabled: boolean;
}

export interface SpeakerVoiceUpdate {
  display_name?: string;
  is_enabled?: boolean;
}

export interface SeparationStatus {
  status: "pending" | "processing" | "completed" | "failed";
  vocals_path: string | null;
  bgm_path: string | null;
  sfx_path: string | null;
  error: string | null;
}

export interface DubbingStatus {
  status: "pending" | "separating" | "extracting_samples" | "synthesizing" | "mixing" | "completed" | "failed";
  progress: number;
  current_step: string | null;
  dubbed_segments: number;
  total_segments: number;
  error: string | null;
}

export interface LipSyncStatus {
  status: "pending" | "detecting_faces" | "processing" | "completed" | "failed" | "skipped";
  progress: number;
  current_step: string | null;
  faces_detected: number;
  error: string | null;
}

export interface PreviewRequest {
  segment_id: number;
  text?: string;
}

export interface PreviewResponse {
  segment_id: number;
  audio_url: string;
  duration: number;
}

// ============ NER Annotation Types ============

export interface WordAnnotation {
  word: string;
  lemma: string;
  start_char: number;
  end_char: number;
  is_vocabulary: boolean;
  difficulty_level: string | null;
}

export interface EntityAnnotation {
  text: string;
  entity_id: string | null;  // Wikidata QID if resolved
  entity_type: string;  // person, place, organization, etc.
  start_char: number;
  end_char: number;
  confidence: number;
  note?: string | null;  // User note for this entity in context
}

export interface IdiomAnnotation {
  text: string;
  start_char: number;
  end_char: number;
  confidence: number;
  category: string;  // idiom, phrasal_verb, slang, colloquial, proverb, expression
}

export interface IdiomCard {
  text: string;
  category: string;  // idiom, phrasal_verb, slang, colloquial, proverb, expression
  meaning_original: string;
  meaning_localized: string;
  example_original: string;
  example_localized: string;
  origin_original: string;
  origin_localized: string;
  usage_note_original: string;
  usage_note_localized: string;
  source: string;
  fetched_at: string;
}

export interface IdiomCardResponse {
  text: string;
  found: boolean;
  card: IdiomCard | null;
  error: string | null;
}

export interface SegmentAnnotations {
  segment_id: number;
  words: WordAnnotation[];
  entities: EntityAnnotation[];
  idioms?: IdiomAnnotation[];
}

export interface TimelineAnnotations {
  timeline_id: string;
  segments: SegmentAnnotations[];
  unique_words: string[];
  unique_entities: string[];
  processed_at: string;
  model_used: string;
}

// ============ Pinned Card Types ============

export type PinnedCardType = "word" | "entity" | "idiom" | "insight";

export interface PinnedCard {
  id: string;
  card_type: PinnedCardType;
  card_id: string;  // Word string or entity QID
  segment_id: number;
  timestamp: number;  // When card was pinned (seconds)
  display_start: number;  // When to show in video
  display_end: number;  // When to hide in video
  card_data: WordCard | EntityCard | IdiomCard | InsightCard | null;  // Cached card data
  note?: string | null;  // User note for this pinned card
  created_at: string;
}

export interface PinnedCardCreate {
  card_type: PinnedCardType;
  card_id: string;
  segment_id: number;
  timestamp: number;
  card_data?: WordCard | EntityCard | IdiomCard | InsightCard | null;
}

export interface PinnedCardCheckResponse {
  is_pinned: boolean;
  pin_id?: string;
}

// ============ Music Types ============

export type MusicTrackStatus = "generating" | "ready" | "failed";
export type MusicModelSize = "small" | "medium" | "large";
export type AmbientMode = "mix" | "sequence";

export interface MusicTrack {
  id: string;
  title: string;
  prompt: string;
  duration_seconds: number;
  model_size: MusicModelSize;
  status: MusicTrackStatus;
  file_path: string | null;
  created_at: string;
  file_size_bytes: number | null;
  error: string | null;
  ambient_sounds: string[];
  ambient_mode: AmbientMode | null;
}

export interface MusicGenerateRequest {
  prompt: string;
  duration_seconds?: number;
  model_size?: MusicModelSize;
  title?: string;
  ambient_sounds?: string[];
  ambient_mode?: AmbientMode;
  ambient_volume?: number;
}

export interface MusicGenerateResponse {
  track: MusicTrack;
  message: string;
}

export interface AmbientSound {
  name: string;
  label: string;
  label_zh: string;
  available: boolean;
  duration_seconds: number | null;
}

// ============ Studio Types ============

export type ScenePreset = "modern_office" | "news_desk" | "podcast_studio" | "classroom" | "home_study";
export type WeatherType = "clear" | "cloudy" | "rain" | "snow" | "night";
export type CharacterAction = "idle" | "talking" | "nodding" | "thinking" | "waving" | "writing";
export type CharacterExpression = "neutral" | "smile" | "serious" | "surprised";
export type LightingPreset = "interview" | "dramatic" | "soft" | "natural";
export type ScreenContentType = "screen_capture" | "web_url" | "custom_image" | "off";

export interface StudioState {
  scene: ScenePreset;
  weather: WeatherType;
  time_of_day: number;
  privacy_level: number;
  lighting_key: number;
  lighting_fill: number;
  lighting_back: number;
  lighting_temperature: number;
  character_action: CharacterAction;
  character_expression: CharacterExpression;
  screen_content_type: ScreenContentType;
  screen_url: string | null;
  screen_brightness: number;
  ue_connected: boolean;
  ue_fps: number | null;
  ue_gpu_usage: number | null;
  pixel_streaming_url: string;
}

export interface StudioPresets {
  scenes: string[];
  weather_types: string[];
  character_actions: string[];
  character_expressions: string[];
  lighting_presets: string[];
  screen_content_types: string[];
}

export interface StudioCommandResponse {
  success: boolean;
  message: string;
  state: StudioState;
}
