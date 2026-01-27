"use client";

/**
 * SpeakerEditor - Component for naming speakers in multi-speaker videos
 */

import { useState, useEffect, useCallback } from "react";
import { getSpeakers, updateSpeakerNames, type SpeakerInfo } from "@/lib/api";
import { useToast } from "@/components/ui";

interface SpeakerEditorProps {
  timelineId: string;
  onSpeakerNamesChange?: (names: Record<string, string>) => void;
}

export default function SpeakerEditor({ timelineId, onSpeakerNamesChange }: SpeakerEditorProps) {
  const toast = useToast();
  const [speakers, setSpeakers] = useState<SpeakerInfo[]>([]);
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Load speakers on mount
  useEffect(() => {
    async function loadSpeakers() {
      try {
        const data = await getSpeakers(timelineId);
        setSpeakers(data.speakers);
        setSpeakerNames(data.speaker_names);
      } catch (err) {
        console.error("Failed to load speakers:", err);
      } finally {
        setLoading(false);
      }
    }
    loadSpeakers();
  }, [timelineId]);

  // Save speaker names (debounced)
  const saveSpeakerNames = useCallback(async (names: Record<string, string>) => {
    setSaving(true);
    try {
      await updateSpeakerNames(timelineId, names);
      onSpeakerNamesChange?.(names);
    } catch (err) {
      console.error("Failed to save speaker names:", err);
      toast.error("保存说话人名称失败");
    } finally {
      setSaving(false);
    }
  }, [timelineId, onSpeakerNamesChange, toast]);

  const handleNameChange = (speakerId: string, name: string) => {
    const newNames = { ...speakerNames, [speakerId]: name };
    setSpeakerNames(newNames);
  };

  const handleSave = () => {
    // Filter out empty names
    const validNames: Record<string, string> = {};
    for (const [id, name] of Object.entries(speakerNames)) {
      if (name.trim()) {
        validNames[id] = name.trim();
      }
    }
    saveSpeakerNames(validNames);
    toast.success("说话人名称已保存");
  };

  // Don't show if only one speaker or loading
  if (loading || speakers.length <= 1) {
    return null;
  }

  return (
    <div className="border-b border-gray-700">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2 flex items-center justify-between text-sm hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-gray-400">👥</span>
          <span className="text-gray-300">说话人标注</span>
          <span className="text-xs text-gray-500">({speakers.length} 人)</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="px-4 py-3 bg-gray-800/30 space-y-3">
          <p className="text-xs text-gray-500 mb-2">
            为每个说话人设置显示名称，将在字幕中显示
          </p>

          {speakers.map((speaker) => (
            <div key={speaker.speaker_id} className="flex items-center gap-3">
              <div className="w-24 text-xs text-gray-500 truncate" title={speaker.speaker_id}>
                {speaker.speaker_id}
              </div>
              <input
                type="text"
                value={speakerNames[speaker.speaker_id] || ""}
                onChange={(e) => handleNameChange(speaker.speaker_id, e.target.value)}
                placeholder={`说话人名称...`}
                className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm focus:border-blue-500 focus:outline-none"
              />
              <span className="text-xs text-gray-500 whitespace-nowrap">
                {speaker.segment_count} 句
              </span>
            </div>
          ))}

          <div className="flex justify-end pt-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded flex items-center gap-1"
            >
              {saving ? (
                <>
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  保存中...
                </>
              ) : (
                "保存名称"
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
