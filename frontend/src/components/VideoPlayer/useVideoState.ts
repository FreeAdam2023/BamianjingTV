/**
 * useVideoState - Hook for managing video player state
 */

import { useState, useCallback, useEffect } from "react";
import { SubtitleStyle, DEFAULT_SUBTITLE_STYLE, STORAGE_KEYS } from "./constants";

export function useVideoState() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLooping, setIsLooping] = useState(false);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Subtitle area height ratio (0.3 to 0.7, default 0.5 = 50%)
  const [subtitleHeightRatio, setSubtitleHeightRatio] = useState(0.5);
  const [isDragging, setIsDragging] = useState(false);

  // Watermark
  const [watermarkUrl, setWatermarkUrl] = useState<string | null>(null);

  // Subtitle style
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>(DEFAULT_SUBTITLE_STYLE);

  // Load watermark from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.WATERMARK);
    if (saved) {
      setWatermarkUrl(saved);
    }
  }, []);

  // Load subtitle style from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.SUBTITLE_STYLE);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSubtitleStyle({ ...DEFAULT_SUBTITLE_STYLE, ...parsed });
      } catch (e) {
        console.error("Failed to parse subtitle style:", e);
      }
    }
  }, []);

  // Update subtitle style and persist to localStorage
  const updateSubtitleStyle = useCallback((updates: Partial<SubtitleStyle>) => {
    setSubtitleStyle((prev) => {
      const newStyle = { ...prev, ...updates };
      localStorage.setItem(STORAGE_KEYS.SUBTITLE_STYLE, JSON.stringify(newStyle));
      return newStyle;
    });
  }, []);

  // Reset subtitle style to defaults
  const resetSubtitleStyle = useCallback(() => {
    setSubtitleStyle(DEFAULT_SUBTITLE_STYLE);
    localStorage.setItem(STORAGE_KEYS.SUBTITLE_STYLE, JSON.stringify(DEFAULT_SUBTITLE_STYLE));
  }, []);

  // Handle watermark upload
  const handleWatermarkUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      setWatermarkUrl(dataUrl);
      localStorage.setItem(STORAGE_KEYS.WATERMARK, dataUrl);
    };
    reader.readAsDataURL(file);
  }, []);

  // Remove watermark
  const removeWatermark = useCallback(() => {
    setWatermarkUrl(null);
    localStorage.removeItem(STORAGE_KEYS.WATERMARK);
  }, []);

  // Toggle loop
  const toggleLoop = useCallback(() => {
    setIsLooping((prev) => !prev);
  }, []);

  // Toggle mute
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => !prev);
  }, []);

  return {
    // Playback state
    isPlaying,
    setIsPlaying,
    currentTime,
    setCurrentTime,
    duration,
    setDuration,
    isLooping,
    toggleLoop,
    volume,
    setVolume,
    isMuted,
    setIsMuted,
    toggleMute,

    // Subtitle area
    subtitleHeightRatio,
    setSubtitleHeightRatio,
    isDragging,
    setIsDragging,

    // Watermark
    watermarkUrl,
    handleWatermarkUpload,
    removeWatermark,

    // Subtitle style
    subtitleStyle,
    updateSubtitleStyle,
    resetSubtitleStyle,
  };
}
