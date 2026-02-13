"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import PageHeader from "@/components/ui/PageHeader";
import {
  getStudioStatus,
  setStudioScene,
  setStudioWeather,
  setStudioPrivacy,
  setStudioLighting,
  setStudioCharacter,
  setStudioScreenContent,
} from "@/lib/api";
import type {
  StudioState,
  ScenePreset,
  WeatherType,
  CharacterAction,
  CharacterExpression,
  ScreenContentType,
} from "@/lib/types";

const SCENE_LABELS: Record<ScenePreset, { label: string; icon: string }> = {
  modern_office: { label: "现代办公室", icon: "🏢" },
  news_desk: { label: "新闻演播台", icon: "📺" },
  podcast_studio: { label: "播客录音室", icon: "🎙" },
  classroom: { label: "教室", icon: "📚" },
  home_study: { label: "书房", icon: "🪑" },
};

const WEATHER_LABELS: Record<WeatherType, { label: string; icon: string }> = {
  clear: { label: "晴天", icon: "☀" },
  cloudy: { label: "多云", icon: "⛅" },
  rain: { label: "雨天", icon: "🌧" },
  snow: { label: "雪天", icon: "❄" },
  night: { label: "夜晚", icon: "🌙" },
};

const ACTION_LABELS: Record<CharacterAction, string> = {
  idle: "空闲",
  talking: "说话",
  nodding: "点头",
  thinking: "思考",
  waving: "挥手",
  writing: "写字",
};

const EXPRESSION_LABELS: Record<CharacterExpression, string> = {
  neutral: "自然",
  smile: "微笑",
  serious: "严肃",
  surprised: "惊讶",
};

const SCREEN_CONTENT_LABELS: Record<ScreenContentType, { label: string; icon: string }> = {
  screen_capture: { label: "屏幕采集", icon: "🖥" },
  web_url: { label: "网页", icon: "🌐" },
  custom_image: { label: "自定义图片", icon: "🖼" },
  off: { label: "关闭", icon: "⬛" },
};

const SCENES_WITH_MONITOR: ScenePreset[] = ["modern_office", "home_study", "news_desk"];

/** Debounce helper: always calls the latest callback after `delay` ms of inactivity. */
function useDebouncedCallback<T extends (...args: never[]) => void>(callback: T, delay: number) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  return useCallback(
    (...args: Parameters<T>) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => callbackRef.current(...args), delay);
    },
    [delay],
  ) as (...args: Parameters<T>) => void;
}

export default function StudioPage() {
  const [state, setState] = useState<StudioState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  // Local slider values (smooth dragging before commit)
  const [localPrivacy, setLocalPrivacy] = useState(0);
  const [localTimeOfDay, setLocalTimeOfDay] = useState(14);
  const [localKey, setLocalKey] = useState(0.8);
  const [localFill, setLocalFill] = useState(0.4);
  const [localBack, setLocalBack] = useState(0.6);
  const [localTemp, setLocalTemp] = useState(5500);
  const [localScreenBrightness, setLocalScreenBrightness] = useState(1.0);
  const [screenUrl, setScreenUrl] = useState("");

  // Refs for latest slider values (avoids stale closures in onChange handlers)
  const lightingRef = useRef({ key: localKey, fill: localFill, back: localBack, temp: localTemp });
  lightingRef.current = { key: localKey, fill: localFill, back: localBack, temp: localTemp };

  // Track whether user is dragging a slider (suppress polling sync)
  const dragging = useRef(false);

  // Auto-dismiss error after 5 seconds
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(t);
  }, [error]);

  // Auto-dismiss success flash after 2 seconds
  useEffect(() => {
    if (!lastSuccess) return;
    const t = setTimeout(() => setLastSuccess(null), 2000);
    return () => clearTimeout(t);
  }, [lastSuccess]);

  const syncLocals = useCallback((s: StudioState) => {
    if (!dragging.current) {
      setLocalPrivacy(s.privacy_level);
      setLocalTimeOfDay(s.time_of_day);
      setLocalKey(s.lighting_key);
      setLocalFill(s.lighting_fill);
      setLocalBack(s.lighting_back);
      setLocalTemp(s.lighting_temperature);
      setLocalScreenBrightness(s.screen_brightness);
      setScreenUrl(s.screen_url || "");
    }
  }, []);

  const loadState = useCallback(async () => {
    try {
      const s = await getStudioStatus();
      setState(s);
      syncLocals(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load studio state");
    } finally {
      setLoading(false);
    }
  }, [syncLocals]);

  useEffect(() => {
    loadState();
  }, [loadState]);

  // Auto-refresh status every 10s (don't overwrite sliders while dragging)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const s = await getStudioStatus();
        setState(s);
        syncLocals(s);
      } catch {
        // ignore polling errors
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [syncLocals]);

  // --- Command handlers ---

  async function handleScene(preset: string) {
    setSending(true);
    try {
      const res = await setStudioScene(preset);
      setState(res.state);
      syncLocals(res.state);
      if (res.success) {
        setLastSuccess("场景已切换");
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  async function handleWeather(type: string) {
    setSending(true);
    try {
      const res = await setStudioWeather(type, localTimeOfDay);
      setState(res.state);
      syncLocals(res.state);
      if (res.success) {
        setLastSuccess("天气已更新");
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  const commitTimeOfDay = useDebouncedCallback(
    async (value: number) => {
      dragging.current = false;
      try {
        const res = await setStudioWeather(state?.weather || "clear", value);
        setState(res.state);
      } catch { /* ignore */ }
    },
    300,
  );

  const commitPrivacy = useDebouncedCallback(
    async (value: number) => {
      dragging.current = false;
      try {
        const res = await setStudioPrivacy(value);
        setState(res.state);
      } catch { /* ignore */ }
    },
    300,
  );

  const commitLighting = useDebouncedCallback(
    async (k: number, f: number, b: number, t: number) => {
      dragging.current = false;
      try {
        const res = await setStudioLighting({ key: k, fill: f, back: b, temperature: t });
        setState(res.state);
      } catch { /* ignore */ }
    },
    300,
  );

  async function handleAction(action: string) {
    setSending(true);
    try {
      const res = await setStudioCharacter({ action });
      setState(res.state);
      if (res.success) {
        setLastSuccess("动作已切换");
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  async function handleExpression(expression: string) {
    setSending(true);
    try {
      const res = await setStudioCharacter({ expression });
      setState(res.state);
      if (res.success) {
        setLastSuccess("表情已切换");
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  async function handleScreenContent(contentType: string) {
    setSending(true);
    try {
      const res = await setStudioScreenContent({
        content_type: contentType,
        url: screenUrl || undefined,
        brightness: localScreenBrightness,
      });
      setState(res.state);
      syncLocals(res.state);
      if (res.success) {
        setLastSuccess("显示器内容已更新");
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  async function handleScreenUrlSubmit() {
    if (!state) return;
    setSending(true);
    try {
      const res = await setStudioScreenContent({
        content_type: state.screen_content_type,
        url: screenUrl || undefined,
        brightness: localScreenBrightness,
      });
      setState(res.state);
      syncLocals(res.state);
      if (res.success) {
        setLastSuccess("URL 已更新");
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  const commitScreenBrightness = useDebouncedCallback(
    async (value: number) => {
      dragging.current = false;
      try {
        const res = await setStudioScreenContent({
          content_type: state?.screen_content_type || "off",
          url: screenUrl || undefined,
          brightness: value,
        });
        setState(res.state);
      } catch { /* ignore */ }
    },
    300,
  );

  function formatTime(hour: number): string {
    const h = Math.floor(hour);
    const m = Math.round((hour - h) * 60);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="spinner mx-auto mb-4" />
          <p className="text-gray-400">加载中...</p>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Shared PageHeader */}
      <PageHeader
        title="虚拟演播室"
        subtitle="Virtual Studio"
        icon="🎬"
        iconGradient="from-cyan-500 to-blue-600"
        backHref="/"
        actions={
          <span
            className={`inline-flex items-center gap-1.5 text-sm ${
              state?.ue_connected ? "text-green-400" : "text-yellow-400"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                state?.ue_connected ? "bg-green-400" : "bg-yellow-400 animate-pulse"
              }`}
            />
            {state?.ue_connected ? "UE5 已连接" : "UE5 离线"}
          </span>
        }
      />

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Success toast */}
        {lastSuccess && (
          <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg animate-fade-in">
            <p className="text-green-400 text-sm flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {lastSuccess}
            </p>
          </div>
        )}

        {/* Error banner — auto-dismisses after 5s */}
        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex justify-between items-center animate-fade-in">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-300"
              aria-label="关闭错误提示"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Right column on desktop, FIRST on mobile for preview visibility */}
          <div className="order-first lg:order-last space-y-6">
            {/* Pixel Streaming Preview */}
            <div className="card animate-fade-in">
              <h2 className="text-lg font-semibold mb-4">预览</h2>
              <div className="aspect-video bg-gray-900 rounded-lg overflow-hidden border border-gray-700 flex items-center justify-center">
                {state?.ue_connected && state.pixel_streaming_url ? (
                  <iframe
                    src={state.pixel_streaming_url}
                    className="w-full h-full"
                    title="Pixel Streaming Preview"
                    allow="autoplay"
                  />
                ) : (
                  <div className="text-center text-gray-500">
                    <svg className="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <p className="text-sm">UE5 未连接</p>
                    <p className="text-xs mt-1">启动渲染服务器后可预览</p>
                  </div>
                )}
              </div>
            </div>

            {/* Status Panel */}
            <div className="card animate-fade-in" style={{ animationDelay: "50ms" }}>
              <h2 className="text-lg font-semibold mb-4">状态</h2>
              <div className="space-y-3 text-sm">
                <StatusRow
                  label="UE5 连接"
                  value={state?.ue_connected ? "已连接" : "离线"}
                  color={state?.ue_connected ? "text-green-400" : "text-yellow-400"}
                />
                <StatusRow
                  label="FPS"
                  value={state?.ue_fps != null ? `${state.ue_fps.toFixed(0)}` : "-"}
                />
                <StatusRow
                  label="GPU 占用"
                  value={state?.ue_gpu_usage != null ? `${state.ue_gpu_usage.toFixed(0)}%` : "-"}
                />
                <div className="border-t border-gray-700 my-2" />
                <StatusRow label="场景" value={SCENE_LABELS[state?.scene || "modern_office"].label} />
                <StatusRow
                  label="天气"
                  value={WEATHER_LABELS[state?.weather || "clear"].label}
                />
                <StatusRow label="时间" value={formatTime(state?.time_of_day || 14)} />
                <StatusRow
                  label="隐私雾化"
                  value={`${Math.round((state?.privacy_level || 0) * 100)}%`}
                />
                <StatusRow
                  label="动作"
                  value={ACTION_LABELS[state?.character_action || "idle"]}
                />
                <StatusRow
                  label="表情"
                  value={EXPRESSION_LABELS[state?.character_expression || "neutral"]}
                />
                {state && SCENES_WITH_MONITOR.includes(state.scene) && (
                  <>
                    <div className="border-t border-gray-700 my-2" />
                    <StatusRow
                      label="显示器"
                      value={SCREEN_CONTENT_LABELS[state.screen_content_type || "off"].label}
                    />
                    <StatusRow
                      label="屏幕亮度"
                      value={`${Math.round((state.screen_brightness ?? 1) * 100)}%`}
                    />
                  </>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="card animate-fade-in" style={{ animationDelay: "100ms" }}>
              <h2 className="text-lg font-semibold mb-4">快捷操作</h2>
              <div className="space-y-2">
                <button
                  onClick={() => { setLocalPrivacy(0); commitPrivacy(0); }}
                  disabled={sending}
                  className="btn btn-secondary w-full text-sm disabled:opacity-50"
                >
                  清除隐私雾化
                </button>
                <button
                  onClick={() => { setLocalPrivacy(1); commitPrivacy(1); }}
                  disabled={sending}
                  className="btn btn-secondary w-full text-sm disabled:opacity-50"
                >
                  最大隐私雾化
                </button>
                <button
                  onClick={loadState}
                  className="btn btn-secondary w-full text-sm"
                >
                  刷新状态
                </button>
              </div>
            </div>
          </div>

          {/* Left column: Controls */}
          <div className="lg:col-span-2 space-y-6">
            {/* Scene Presets */}
            <div className="card animate-fade-in" style={{ animationDelay: "50ms" }}>
              <h2 className="text-lg font-semibold mb-4">场景预设</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {(Object.entries(SCENE_LABELS) as [ScenePreset, { label: string; icon: string }][]).map(
                  ([preset, { label, icon }]) => (
                    <button
                      key={preset}
                      onClick={() => handleScene(preset)}
                      disabled={sending}
                      aria-pressed={state?.scene === preset}
                      className={`p-4 rounded-xl border-2 transition-all text-center disabled:opacity-50 ${
                        state?.scene === preset
                          ? "border-blue-500 bg-blue-500/10 text-blue-300"
                          : "border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600 hover:text-gray-300"
                      }`}
                    >
                      <div className="text-2xl mb-2">{icon}</div>
                      <div className="text-sm font-medium">{label}</div>
                    </button>
                  )
                )}
              </div>
            </div>

            {/* Weather & Time */}
            <div className="card animate-fade-in" style={{ animationDelay: "100ms" }}>
              <h2 className="text-lg font-semibold mb-4">天气 / 时间</h2>
              <div className="flex flex-wrap gap-2 mb-4">
                {(Object.entries(WEATHER_LABELS) as [WeatherType, { label: string; icon: string }][]).map(
                  ([type, { label, icon }]) => (
                    <button
                      key={type}
                      onClick={() => handleWeather(type)}
                      disabled={sending}
                      aria-pressed={state?.weather === type}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                        state?.weather === type
                          ? "bg-blue-600 text-white"
                          : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                      }`}
                    >
                      {icon} {label}
                    </button>
                  )
                )}
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1" htmlFor="time-of-day">
                  时间：{formatTime(localTimeOfDay)}
                </label>
                <input
                  id="time-of-day"
                  type="range"
                  min={0}
                  max={24}
                  step={0.5}
                  value={localTimeOfDay}
                  aria-label={`时间 ${formatTime(localTimeOfDay)}`}
                  aria-valuemin={0}
                  aria-valuemax={24}
                  aria-valuenow={localTimeOfDay}
                  aria-valuetext={formatTime(localTimeOfDay)}
                  onChange={(e) => {
                    dragging.current = true;
                    const v = Number(e.target.value);
                    setLocalTimeOfDay(v);
                    commitTimeOfDay(v);
                  }}
                  className="w-full accent-blue-500"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>00:00</span>
                  <span>06:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                  <span>24:00</span>
                </div>
              </div>
            </div>

            {/* Privacy Blur */}
            <div className="card animate-fade-in" style={{ animationDelay: "150ms" }}>
              <h2 className="text-lg font-semibold mb-4">隐私雾化</h2>
              <div className="flex items-center gap-4">
                <span className="text-sm text-gray-400 w-12">
                  {Math.round(localPrivacy * 100)}%
                </span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={localPrivacy}
                  aria-label={`隐私雾化 ${Math.round(localPrivacy * 100)}%`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(localPrivacy * 100)}
                  aria-valuetext={`${Math.round(localPrivacy * 100)}%`}
                  onChange={(e) => {
                    dragging.current = true;
                    const v = Number(e.target.value);
                    setLocalPrivacy(v);
                    commitPrivacy(v);
                  }}
                  className="flex-1 accent-purple-500"
                />
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>清晰</span>
                <span>完全模糊</span>
              </div>
            </div>

            {/* Lighting */}
            <div className="card animate-fade-in" style={{ animationDelay: "200ms" }}>
              <h2 className="text-lg font-semibold mb-4">灯光</h2>
              <div className="space-y-4">
                {[
                  { label: "主光", ariaLabel: "主光强度", value: localKey, setter: setLocalKey },
                  { label: "补光", ariaLabel: "补光强度", value: localFill, setter: setLocalFill },
                  { label: "轮廓光", ariaLabel: "轮廓光强度", value: localBack, setter: setLocalBack },
                ].map(({ label, ariaLabel, value, setter }) => (
                  <div key={label}>
                    <label className="block text-sm text-gray-400 mb-1">
                      {label}：{Math.round(value * 100)}%
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={value}
                      aria-label={`${ariaLabel} ${Math.round(value * 100)}%`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(value * 100)}
                      aria-valuetext={`${Math.round(value * 100)}%`}
                      onChange={(e) => {
                        dragging.current = true;
                        const v = Number(e.target.value);
                        setter(v);
                        // Read latest values from ref to avoid stale closures
                        const latest = { ...lightingRef.current };
                        if (label === "主光") latest.key = v;
                        else if (label === "补光") latest.fill = v;
                        else if (label === "轮廓光") latest.back = v;
                        commitLighting(latest.key, latest.fill, latest.back, latest.temp);
                      }}
                      className="w-full accent-amber-500"
                    />
                  </div>
                ))}
                <div>
                  <label className="block text-sm text-gray-400 mb-1" htmlFor="color-temp">
                    色温：{localTemp}K
                  </label>
                  <input
                    id="color-temp"
                    type="range"
                    min={2000}
                    max={10000}
                    step={100}
                    value={localTemp}
                    aria-label={`色温 ${localTemp}K`}
                    aria-valuemin={2000}
                    aria-valuemax={10000}
                    aria-valuenow={localTemp}
                    aria-valuetext={`${localTemp}K`}
                    onChange={(e) => {
                      dragging.current = true;
                      const v = Number(e.target.value);
                      setLocalTemp(v);
                      const latest = lightingRef.current;
                      commitLighting(latest.key, latest.fill, latest.back, v);
                    }}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>2000K 暖色</span>
                    <span>5500K 日光</span>
                    <span>10000K 冷色</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Character */}
            <div className="card animate-fade-in" style={{ animationDelay: "250ms" }}>
              <h2 className="text-lg font-semibold mb-4">角色</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">动作</label>
                  <div className="flex flex-wrap gap-2" role="group" aria-label="角色动作">
                    {(Object.entries(ACTION_LABELS) as [CharacterAction, string][]).map(
                      ([action, label]) => (
                        <button
                          key={action}
                          onClick={() => handleAction(action)}
                          disabled={sending}
                          aria-pressed={state?.character_action === action}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                            state?.character_action === action
                              ? "bg-green-600 text-white"
                              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                          }`}
                        >
                          {label}
                        </button>
                      )
                    )}
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">表情</label>
                  <div className="flex flex-wrap gap-2" role="group" aria-label="角色表情">
                    {(Object.entries(EXPRESSION_LABELS) as [CharacterExpression, string][]).map(
                      ([expr, label]) => (
                        <button
                          key={expr}
                          onClick={() => handleExpression(expr)}
                          disabled={sending}
                          aria-pressed={state?.character_expression === expr}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                            state?.character_expression === expr
                              ? "bg-green-600 text-white"
                              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                          }`}
                        >
                          {label}
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Screen Content — only shown for scenes with monitors */}
            {state && SCENES_WITH_MONITOR.includes(state.scene) && (
              <div className="card animate-fade-in" style={{ animationDelay: "300ms" }}>
                <h2 className="text-lg font-semibold mb-4">显示器内容</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">内容源</label>
                    <div className="flex flex-wrap gap-2" role="group" aria-label="显示器内容源">
                      {(Object.entries(SCREEN_CONTENT_LABELS) as [ScreenContentType, { label: string; icon: string }][]).map(
                        ([type, { label, icon }]) => (
                          <button
                            key={type}
                            onClick={() => handleScreenContent(type)}
                            disabled={sending}
                            aria-pressed={state?.screen_content_type === type}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                              state?.screen_content_type === type
                                ? "bg-cyan-600 text-white"
                                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                            }`}
                          >
                            {icon} {label}
                          </button>
                        )
                      )}
                    </div>
                  </div>

                  {(state.screen_content_type === "web_url" || state.screen_content_type === "custom_image") && (
                    <div>
                      <label className="block text-sm text-gray-400 mb-1" htmlFor="screen-url">
                        {state.screen_content_type === "web_url" ? "网页 URL" : "图片 URL"}
                      </label>
                      <div className="flex gap-2">
                        <input
                          id="screen-url"
                          type="url"
                          value={screenUrl}
                          onChange={(e) => setScreenUrl(e.target.value)}
                          placeholder={state.screen_content_type === "web_url" ? "https://example.com" : "https://example.com/image.png"}
                          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                        />
                        <button
                          onClick={handleScreenUrlSubmit}
                          disabled={sending || !screenUrl}
                          className="px-4 py-2 bg-cyan-600 text-white rounded-lg text-sm font-medium hover:bg-cyan-500 disabled:opacity-50 transition-colors"
                        >
                          应用
                        </button>
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">
                      亮度：{Math.round(localScreenBrightness * 100)}%
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={localScreenBrightness}
                      aria-label={`显示器亮度 ${Math.round(localScreenBrightness * 100)}%`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(localScreenBrightness * 100)}
                      aria-valuetext={`${Math.round(localScreenBrightness * 100)}%`}
                      onChange={(e) => {
                        dragging.current = true;
                        const v = Number(e.target.value);
                        setLocalScreenBrightness(v);
                        commitScreenBrightness(v);
                      }}
                      className="w-full accent-cyan-500"
                    />
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>关闭</span>
                      <span>最亮</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusRow({
  label,
  value,
  color = "text-gray-300",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className={color}>{value}</span>
    </div>
  );
}
