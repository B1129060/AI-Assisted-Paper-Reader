import { useEffect, useMemo, useRef, useState } from "react";
import type { PaperOverview } from "../types/paper";

type Props = {
  overview: PaperOverview;
  language: "en" | "zh";
};

type PlayerState = "idle" | "playing" | "paused";

function buildSegments(overview: PaperOverview, language: "en" | "zh"): string[] {
  const segments: string[] = [];
  const zh = language === "zh";

  const pushIfExists = (value?: string) => {
    const clean = (value || "").trim();
    if (clean) segments.push(clean);
  };

  pushIfExists(overview.abstract_summary);
  pushIfExists(overview.overall_summary);

  if (overview.overall_key_points?.length) {
    overview.overall_key_points.forEach((point) => pushIfExists(point));
  }

  if (overview.highlight_summaries?.length) {
    overview.highlight_summaries.forEach((item) => {
      pushIfExists(item.title);
      pushIfExists(item.summary);
    });
  }

  if (overview.section_summaries?.length) {
    overview.section_summaries.forEach((item) => {
      pushIfExists(item.section_title);
      pushIfExists(item.summary);
    });
  }

  if (zh) {
    return segments.map((text) =>
      text
        .replace(/\b1\./g, "第一點，")
        .replace(/\b2\./g, "第二點，")
        .replace(/\b3\./g, "第三點，")
        .replace(/\b4\./g, "第四點，")
    );
  }

  return segments;
}

export default function OverviewAudioPlayer({ overview, language }: Props) {
  const [open, setOpen] = useState(false);
  const [playerState, setPlayerState] = useState<PlayerState>("idle");
  const [currentIndex, setCurrentIndex] = useState<number>(-1);

  const synthRef = useRef<SpeechSynthesis | null>(null);
  const segmentsRef = useRef<string[]>([]);
  const stopRequestedRef = useRef(false);

  const segments = useMemo(() => buildSegments(overview, language), [overview, language]);

  useEffect(() => {
    synthRef.current = window.speechSynthesis;

    return () => {
      stopRequestedRef.current = true;
      synthRef.current?.cancel();
    };
  }, []);

  useEffect(() => {
    stopRequestedRef.current = true;
    synthRef.current?.cancel();
    setPlayerState("idle");
    setCurrentIndex(-1);
    segmentsRef.current = segments;
  }, [segments, language]);

  function speakFrom(index: number) {
    const synth = synthRef.current;
    if (!synth) return;
    if (stopRequestedRef.current) return;

    if (index >= segmentsRef.current.length) {
      setPlayerState("idle");
      setCurrentIndex(-1);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(segmentsRef.current[index]);
    utterance.lang = language === "zh" ? "zh-TW" : "en-US";
    utterance.rate = language === "zh" ? 0.95 : 1.0;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      setCurrentIndex(index);
      setPlayerState("playing");
    };

    utterance.onend = () => {
      if (stopRequestedRef.current) return;
      speakFrom(index + 1);
    };

    utterance.onerror = () => {
      if (stopRequestedRef.current) return;
      speakFrom(index + 1);
    };

    synth.speak(utterance);
  }

  function handlePlay() {
    const synth = synthRef.current;
    if (!synth || !segments.length) return;

    stopRequestedRef.current = false;
    synth.cancel();
    segmentsRef.current = segments;
    speakFrom(0);
  }

  function handlePauseResume() {
    const synth = synthRef.current;
    if (!synth) return;

    if (playerState === "playing") {
      synth.pause();
      setPlayerState("paused");
      return;
    }

    if (playerState === "paused") {
      synth.resume();
      setPlayerState("playing");
    }
  }

  function handleStop() {
    const synth = synthRef.current;
    if (!synth) return;

    stopRequestedRef.current = true;
    synth.cancel();
    setPlayerState("idle");
    setCurrentIndex(-1);
  }

  const total = segments.length;
  const current = currentIndex >= 0 ? currentIndex + 1 : 0;

  return (
    <div className="audio-dropdown">
      <button
        className="audio-toggle-button"
        onClick={() => setOpen((prev) => !prev)}
      >
        {language === "zh" ? "Audio ▼" : "Audio ▼"}
      </button>

      {open && (
        <div className="audio-dropdown-panel">
          <div className="overview-audio-controls">
            <button onClick={handlePlay} disabled={!total}>
              {language === "zh" ? "播放" : "Play"}
            </button>
            <button onClick={handlePauseResume} disabled={playerState === "idle"}>
              {playerState === "paused"
                ? language === "zh"
                  ? "繼續"
                  : "Resume"
                : language === "zh"
                ? "暫停"
                : "Pause"}
            </button>
            <button onClick={handleStop} disabled={playerState === "idle"}>
              {language === "zh" ? "停止" : "Stop"}
            </button>
          </div>

          <div className="overview-audio-status">
            {playerState === "idle"
              ? language === "zh"
                ? `可朗讀 ${total} 段`
                : `${total} segments ready`
              : language === "zh"
              ? `正在朗讀第 ${current} / ${total} 段`
              : `Reading ${current} / ${total}`}
          </div>
        </div>
      )}
    </div>
  );
}