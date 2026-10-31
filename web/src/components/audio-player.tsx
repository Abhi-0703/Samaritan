"use client";

import { useEffect, useImperativeHandle, useRef, useState } from "react";
import { useTheme } from "@/components/theme-provider";
import { Pause, Play } from "lucide-react";
import type WaveSurfer from "wavesurfer.js";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatClock } from "@/lib/format";
import type { Severity } from "@/lib/types";

export interface AudioMarker {
  id: string;
  time: number;
  severity: Severity;
}

export interface AudioPlayerHandle {
  seek: (seconds: number, play?: boolean) => void;
}

const SPEEDS = [
  { value: "1", label: "1x" },
  { value: "1.25", label: "1.25x" },
  { value: "1.5", label: "1.5x" },
  { value: "2", label: "2x" },
];

const SEVERITY_VAR: Record<Severity, string> = {
  critical: "--critical-fg",
  high: "--high-fg",
  medium: "--medium-fg",
};

export function AudioPlayer({
  url,
  markers,
  onTime,
  initialSeek,
  onPlayingChange,
  ref,
}: {
  url: string;
  markers: AudioMarker[];
  onTime?: (seconds: number) => void;
  initialSeek?: number | null;
  onPlayingChange?: (playing: boolean) => void;
  ref?: React.Ref<AudioPlayerHandle>;
}) {
  const host = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const onTimeRef = useRef(onTime);
  const onPlayingRef = useRef(onPlayingChange);
  const initialSeekRef = useRef(initialSeek);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState("1");
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    onTimeRef.current = onTime;
    onPlayingRef.current = onPlayingChange;
  });

  useImperativeHandle(
    ref,
    () => ({
      seek: (seconds, play) => {
        const ws = wsRef.current;
        if (!ws) return;
        ws.setTime(Math.max(0, seconds));
        setTime(seconds);
        onTimeRef.current?.(seconds);
        if (play) void ws.play();
      },
    }),
    [],
  );

  const markersKey = JSON.stringify(markers);
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let ws: WaveSurfer | undefined;

    (async () => {
      const [{ default: WaveSurferLib }, { default: RegionsPlugin }] = await Promise.all([
        import("wavesurfer.js"),
        import("wavesurfer.js/plugins/regions"),
      ]);
      if (disposed) return;
      const css = getComputedStyle(document.documentElement);
      const color = (name: string) => css.getPropertyValue(name).trim();
      const tint = (hex: string) => (/^#[0-9a-f]{6}$/i.test(hex) ? `${hex}66` : hex);
      const regions = RegionsPlugin.create();
      ws = WaveSurferLib.create({
        container: el,
        url,
        height: 72,
        waveColor: color("--muted-foreground"),
        progressColor: color("--brand"),
        cursorColor: color("--foreground"),
        barWidth: 2,
        barGap: 1,
        barRadius: 1,
        normalize: true,
        plugins: [regions],
      });
      wsRef.current = ws;
      ws.on("ready", (d) => {
        setDuration(d);
        setStatus("ready");
        for (const m of JSON.parse(markersKey) as AudioMarker[]) {
          regions.addRegion({
            start: m.time,
            end: Math.min(d, m.time + 0.9),
            color: tint(color(SEVERITY_VAR[m.severity])),
            drag: false,
            resize: false,
          });
        }
        const t = initialSeekRef.current;
        if (t != null && t >= 0 && t < d) {
          ws?.setTime(t);
          setTime(t);
          onTimeRef.current?.(t);
        }
      });
      ws.on("timeupdate", (t) => {
        setTime(t);
        onTimeRef.current?.(t);
      });
      ws.on("seeking", (t) => {
        setTime(t);
        onTimeRef.current?.(t);
      });
      const setPlayingState = (p: boolean) => {
        setPlaying(p);
        onPlayingRef.current?.(p);
      };
      ws.on("play", () => setPlayingState(true));
      ws.on("pause", () => setPlayingState(false));
      ws.on("finish", () => setPlayingState(false));
      ws.on("error", () => setStatus("error"));
    })();

    return () => {
      disposed = true;
      wsRef.current = null;
      ws?.destroy();
    };
  }, [url, markersKey, resolvedTheme]);

  return (
    <div className="rounded-lg border p-4">
      <div className="relative">
        <div ref={host} className="waveform-host" aria-label="Audio waveform" />
        {status === "loading" && <Skeleton className="absolute inset-0 h-[72px]" />}
        {status === "error" && (
          <p role="alert" className="absolute inset-0 flex items-center justify-center text-muted-foreground">
            The audio could not be loaded.
          </p>
        )}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Button
          size="icon"
          aria-label={playing ? "Pause" : "Play"}
          disabled={status !== "ready"}
          onClick={() => void wsRef.current?.playPause()}
        >
          {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
        </Button>
        <p className="tnum font-mono text-xs" aria-live="off">
          {formatClock(time)} <span className="text-muted-foreground">/ {formatClock(duration)}</span>
        </p>
        <p className="hidden text-xs text-muted-foreground sm:block">Coloured marks on the waveform are flagged moments.</p>
        <div className="ml-auto">
          <Select
            items={SPEEDS}
            value={speed}
            onValueChange={(v) => {
              const next = String(v ?? "1");
              setSpeed(next);
              wsRef.current?.setPlaybackRate(Number(next), true);
            }}
          >
            <SelectTrigger size="sm" aria-label="Playback speed" className="w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false}>
              {SPEEDS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
