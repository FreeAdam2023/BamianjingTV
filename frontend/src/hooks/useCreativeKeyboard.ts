import { useEffect, useCallback } from "react";
import type { CreativeStyle, RemotionConfig, SubtitlePosition } from "@/lib/creative-types";

interface UseCreativeKeyboardOptions {
  enabled: boolean;
  config: RemotionConfig;
  onStyleChange: (style: CreativeStyle) => void;
  onConfigChange: (config: RemotionConfig) => void;
}

const STYLE_KEYS: Record<string, CreativeStyle> = {
  "1": "karaoke",
  "2": "popup",
  "3": "slide",
  "4": "typewriter",
  "5": "highlight",
  "6": "fade",
};

const POSITION_ORDER: SubtitlePosition[] = ["bottom", "center", "top"];

export function useCreativeKeyboard({
  enabled,
  config,
  onStyleChange,
  onConfigChange,
}: UseCreativeKeyboardOptions) {
  const cyclePosition = useCallback(() => {
    const currentIndex = POSITION_ORDER.indexOf(config.global.subtitlePosition);
    const nextIndex = (currentIndex + 1) % POSITION_ORDER.length;
    onConfigChange({
      ...config,
      global: {
        ...config.global,
        subtitlePosition: POSITION_ORDER[nextIndex],
      },
    });
  }, [config, onConfigChange]);

  const adjustEntranceDuration = useCallback((delta: number) => {
    const newDuration = Math.max(5, Math.min(30, config.animation.entrance.duration + delta));
    onConfigChange({
      ...config,
      animation: {
        ...config.animation,
        entrance: {
          ...config.animation.entrance,
          duration: newDuration,
        },
      },
    });
  }, [config, onConfigChange]);

  const adjustExitDuration = useCallback((delta: number) => {
    const newDuration = Math.max(5, Math.min(30, config.animation.exit.duration + delta));
    onConfigChange({
      ...config,
      animation: {
        ...config.animation,
        exit: {
          ...config.animation.exit,
          duration: newDuration,
        },
      },
    });
  }, [config, onConfigChange]);

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture if in input field
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      // Style selection: 1-6
      if (STYLE_KEYS[e.key]) {
        e.preventDefault();
        onStyleChange(STYLE_KEYS[e.key]);
        return;
      }

      // Position toggle: P
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        cyclePosition();
        return;
      }

      // Entrance duration: [ and ]
      if (e.key === "[") {
        e.preventDefault();
        adjustEntranceDuration(-2);
        return;
      }
      if (e.key === "]") {
        e.preventDefault();
        adjustEntranceDuration(2);
        return;
      }

      // Exit duration: { and } (Shift + [ and ])
      if (e.key === "{") {
        e.preventDefault();
        adjustExitDuration(-2);
        return;
      }
      if (e.key === "}") {
        e.preventDefault();
        adjustExitDuration(2);
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, onStyleChange, cyclePosition, adjustEntranceDuration, adjustExitDuration]);
}
