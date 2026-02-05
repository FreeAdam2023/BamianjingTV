import { useState, useCallback, useMemo } from "react";
import type {
  RemotionConfig,
  CreativeStyle,
  GlobalConfig,
  AnimationConfig,
} from "@/lib/creative-types";
import {
  createDefaultConfig,
  applyStylePreset,
  DEFAULT_GLOBAL_CONFIG,
  STYLE_PRESETS,
} from "@/lib/creative-types";

interface UseCreativeConfigOptions {
  initialStyle?: CreativeStyle;
  onConfigChange?: (config: RemotionConfig) => void;
}

interface UseCreativeConfigReturn {
  config: RemotionConfig;
  style: CreativeStyle;
  setConfig: (config: RemotionConfig) => void;
  setStyle: (style: CreativeStyle) => void;
  updateGlobal: (updates: Partial<GlobalConfig>) => void;
  updateAnimation: (updates: Partial<AnimationConfig>) => void;
  resetConfig: () => void;
  resetToPreset: (style: CreativeStyle) => void;
  isModified: boolean;
}

export function useCreativeConfig({
  initialStyle = "karaoke",
  onConfigChange,
}: UseCreativeConfigOptions = {}): UseCreativeConfigReturn {
  const [config, setConfig] = useState<RemotionConfig>(() =>
    createDefaultConfig(initialStyle)
  );

  // Track if config has been modified from preset
  const isModified = useMemo(() => {
    const preset = STYLE_PRESETS[config.style];
    const globalDefault = DEFAULT_GLOBAL_CONFIG;

    // Check if global settings differ
    const globalModified = Object.keys(globalDefault).some(
      (key) =>
        config.global[key as keyof GlobalConfig] !==
        globalDefault[key as keyof GlobalConfig]
    );

    // Check if animation settings differ from preset
    const animationModified =
      JSON.stringify(config.animation) !== JSON.stringify(preset);

    return globalModified || animationModified;
  }, [config]);

  const updateConfig = useCallback(
    (newConfig: RemotionConfig) => {
      setConfig(newConfig);
      onConfigChange?.(newConfig);
    },
    [onConfigChange]
  );

  const setStyle = useCallback(
    (style: CreativeStyle) => {
      const newConfig = applyStylePreset(config, style);
      updateConfig(newConfig);
    },
    [config, updateConfig]
  );

  const updateGlobal = useCallback(
    (updates: Partial<GlobalConfig>) => {
      const newConfig: RemotionConfig = {
        ...config,
        global: {
          ...config.global,
          ...updates,
        },
      };
      updateConfig(newConfig);
    },
    [config, updateConfig]
  );

  const updateAnimation = useCallback(
    (updates: Partial<AnimationConfig>) => {
      const newConfig: RemotionConfig = {
        ...config,
        animation: {
          ...config.animation,
          ...updates,
        },
      };
      updateConfig(newConfig);
    },
    [config, updateConfig]
  );

  const resetConfig = useCallback(() => {
    updateConfig(createDefaultConfig(initialStyle));
  }, [initialStyle, updateConfig]);

  const resetToPreset = useCallback(
    (style: CreativeStyle) => {
      updateConfig(createDefaultConfig(style));
    },
    [updateConfig]
  );

  return {
    config,
    style: config.style,
    setConfig: updateConfig,
    setStyle,
    updateGlobal,
    updateAnimation,
    resetConfig,
    resetToPreset,
    isModified,
  };
}
