"use client";

/**
 * VoiceConfig - Configure voice settings for dubbing
 */

import { useState } from "react";
import type { DubbingConfig, DubbingConfigUpdate, SpeakerVoiceConfig } from "@/lib/types";
import { updateDubbingConfig, updateDubbingSpeaker } from "@/lib/api";

interface VoiceConfigProps {
  timelineId: string;
  config: DubbingConfig;
  speakers: SpeakerVoiceConfig[];
  onConfigChange: (config: DubbingConfig) => void;
  onSpeakerChange: (speaker: SpeakerVoiceConfig) => void;
}

export default function VoiceConfig({
  timelineId,
  config,
  speakers,
  onConfigChange,
  onSpeakerChange,
}: VoiceConfigProps) {
  const [saving, setSaving] = useState(false);

  const handleConfigUpdate = async (update: DubbingConfigUpdate) => {
    try {
      const updated = await updateDubbingConfig(timelineId, update);
      onConfigChange(updated);
    } catch (err) {
      console.error("Failed to update config:", err);
    }
  };

  const handleVolumeChange = async (key: keyof DubbingConfig, value: number) => {
    await handleConfigUpdate({ [key]: value });
  };

  const handleToggle = async (key: "keep_bgm" | "keep_sfx" | "voice_clone", value: boolean) => {
    await handleConfigUpdate({ [key]: value });
  };

  const handleSpeakerToggle = async (speakerId: string, enabled: boolean) => {
    try {
      const updated = await updateDubbingSpeaker(timelineId, speakerId, { is_enabled: enabled });
      onSpeakerChange(updated);
    } catch (err) {
      console.error("Failed to update speaker:", err);
    }
  };

  const handleSpeakerRename = async (speakerId: string, name: string) => {
    try {
      const updated = await updateDubbingSpeaker(timelineId, speakerId, { display_name: name });
      onSpeakerChange(updated);
    } catch (err) {
      console.error("Failed to rename speaker:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Voice Settings */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Voice Settings</h3>

        <div className="space-y-4">
          {/* Voice Clone Toggle */}
          <div className="flex items-center justify-between">
            <label className="text-sm text-gray-400">Voice Cloning</label>
            <input
              type="checkbox"
              checked={config.voice_clone}
              onChange={(e) => handleToggle("voice_clone", e.target.checked)}
              className="rounded bg-gray-700 border-gray-600 text-blue-500"
            />
          </div>

          {/* Voice Model */}
          <div>
            <label className="text-sm text-gray-400 block mb-1">Voice Model</label>
            <select
              value={config.voice_model}
              onChange={(e) => handleConfigUpdate({ voice_model: e.target.value })}
              disabled={!config.voice_clone}
              className="select w-full disabled:opacity-50"
            >
              <option value="xtts_v2">XTTS v2</option>
              <option value="gpt_sovits">GPT-SoVITS</option>
              <option value="preset">Preset Voice</option>
            </select>
          </div>

          {/* Voice Similarity Slider */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-400">Voice Similarity</label>
              <span className="text-sm text-gray-500">{Math.round(config.voice_similarity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={config.voice_similarity * 100}
              onChange={(e) => handleConfigUpdate({ voice_similarity: parseInt(e.target.value) / 100 })}
              disabled={!config.voice_clone}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-1">
              <span>More natural</span>
              <span>More similar</span>
            </div>
          </div>
        </div>
      </div>

      {/* Volume Controls */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Audio Mix</h3>

        <div className="space-y-4">
          {/* Vocal Volume */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-400">Dubbed Voice</label>
              <span className="text-sm text-gray-500">{Math.round(config.vocal_volume * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={config.vocal_volume * 100}
              onChange={(e) => handleVolumeChange("vocal_volume", parseInt(e.target.value) / 100)}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* BGM Volume */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.keep_bgm}
                  onChange={(e) => handleToggle("keep_bgm", e.target.checked)}
                  className="rounded bg-gray-700 border-gray-600 text-blue-500"
                />
                <label className="text-sm text-gray-400">Background Music</label>
              </div>
              <span className="text-sm text-gray-500">{Math.round(config.bgm_volume * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={config.bgm_volume * 100}
              onChange={(e) => handleVolumeChange("bgm_volume", parseInt(e.target.value) / 100)}
              disabled={!config.keep_bgm}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
            />
          </div>

          {/* SFX Volume */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.keep_sfx}
                  onChange={(e) => handleToggle("keep_sfx", e.target.checked)}
                  className="rounded bg-gray-700 border-gray-600 text-blue-500"
                />
                <label className="text-sm text-gray-400">Sound Effects</label>
              </div>
              <span className="text-sm text-gray-500">{Math.round(config.sfx_volume * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={config.sfx_volume * 100}
              onChange={(e) => handleVolumeChange("sfx_volume", parseInt(e.target.value) / 100)}
              disabled={!config.keep_sfx}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
            />
          </div>
        </div>
      </div>

      {/* Speaker Configuration */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Speakers</h3>

        {speakers.length === 0 ? (
          <p className="text-sm text-gray-500">No speakers detected in this video.</p>
        ) : (
          <div className="space-y-3">
            {speakers.map((speaker) => (
              <div
                key={speaker.speaker_id}
                className="flex items-center justify-between p-3 bg-[var(--background)] rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={speaker.is_enabled}
                    onChange={(e) => handleSpeakerToggle(speaker.speaker_id, e.target.checked)}
                    className="rounded bg-gray-700 border-gray-600 text-blue-500"
                  />
                  <div>
                    <input
                      type="text"
                      value={speaker.display_name}
                      onChange={(e) => handleSpeakerRename(speaker.speaker_id, e.target.value)}
                      className="bg-transparent text-gray-200 text-sm font-medium focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1"
                    />
                    <p className="text-xs text-gray-500">{speaker.speaker_id}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {speaker.voice_sample_path ? (
                    <span className="text-xs text-green-500">Sample ready</span>
                  ) : (
                    <span className="text-xs text-gray-500">No sample</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Language Selection */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Target Language</h3>
        <select
          value={config.target_language}
          onChange={(e) => handleConfigUpdate({ target_language: e.target.value })}
          className="select"
        >
          <option value="zh-cn">Chinese (Simplified)</option>
          <option value="zh-tw">Chinese (Traditional)</option>
          <option value="en">English</option>
          <option value="ja">Japanese</option>
          <option value="ko">Korean</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="de">German</option>
        </select>
      </div>

      {/* Lip Sync Settings */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Lip Sync</h3>
        <div>
          <label className="text-sm text-gray-400 block mb-1">Lip Sync Model</label>
          <select
            value={config.lip_sync_model}
            onChange={(e) => handleConfigUpdate({ lip_sync_model: e.target.value })}
            className="select w-full"
          >
            <option value="wav2lip">Wav2Lip</option>
            <option value="sadtalker">SadTalker</option>
          </select>
        </div>
      </div>
    </div>
  );
}
