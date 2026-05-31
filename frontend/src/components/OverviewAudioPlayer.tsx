import { useEffect, useMemo, useRef, useState } from "react";
import type { Element, PaperOverview } from "../types/paper";

type AudioLanguage = "en" | "zh";
type AudioSource = "overview" | "selected_paragraph" | "all_paragraphs";
type OverviewPart = "all" | "abstract" | "overall" | "key_points" | "sections" | "highlights";
type ParagraphPart = "all" | "text" | "summary" | "key_points";
type PlayerState = "idle" | "playing" | "paused";

type Props = {
  currentLanguage: AudioLanguage;
  activeElementId: number | null;
  englishOverview?: PaperOverview | null;
  englishElements?: Element[];
  chineseOverview?: PaperOverview | null;
  chineseElements?: Element[];
};

type AudioSegment = {
  text: string;
  lang: AudioLanguage;
  kind?: "content" | "label";
  pauseAfterMs?: number;
};

type PauseSegment = {
  pauseMs: number;
};

type PlaybackUnit = AudioSegment | PauseSegment;

const MAX_SEGMENT_LENGTH = 240;
const DEFAULT_RATE = 1.0;

function isPauseSegment(segment: PlaybackUnit): segment is PauseSegment {
  return "pauseMs" in segment;
}

function isVoiceCompatibleWithLanguage(
  voice: SpeechSynthesisVoice | null | undefined,
  language: AudioLanguage,
) {
  if (!voice) return false;
  const lang = voice.lang.toLowerCase();
  const name = voice.name.toLowerCase();

  if (language === "zh") {
    return lang.startsWith("zh") || name.includes("chinese");
  }

  return lang.startsWith("en");
}

function getLabelText(labelKey: "original" | "summary" | "key_points" | "paragraph", lang: AudioLanguage, index?: number) {
  if (lang === "zh") {
    if (labelKey === "original") return "原文。";
    if (labelKey === "summary") return "摘要。";
    if (labelKey === "key_points") return "重點。";
    return index ? `第 ${index} 段。` : "段落。";
  }

  if (labelKey === "original") return "Original text.";
  if (labelKey === "summary") return "Summary.";
  if (labelKey === "key_points") return "Key points.";
  return index ? `Paragraph ${index}.` : "Paragraph.";
}

function cleanText(value?: string | null, _lang: AudioLanguage = "en") {
  return (value || "")
    .replace(/\s+/g, " ")
    .replace(/\bFig\.\s*/gi, "Figure ")
    .replace(/\bEq\.\s*/gi, "Equation ")
    .replace(/\s+/g, " ")
    .trim();
}

function splitLongText(text: string) {
  const sentenceParts = text
    .split(/(?<=[。！？；.!?;])\s*/)
    .map((part) => part.trim())
    .filter(Boolean);

  const result: string[] = [];

  for (const part of sentenceParts.length ? sentenceParts : [text]) {
    if (part.length <= MAX_SEGMENT_LENGTH) {
      result.push(part);
      continue;
    }

    const pieces = part
      .split(/(?<=[，,、:：])\s*/)
      .map((piece) => piece.trim())
      .filter(Boolean);

    let buffer = "";
    for (const piece of pieces.length ? pieces : [part]) {
      if ((buffer + piece).length > MAX_SEGMENT_LENGTH && buffer) {
        result.push(buffer.trim());
        buffer = "";
      }

      if (piece.length > MAX_SEGMENT_LENGTH) {
        for (let i = 0; i < piece.length; i += MAX_SEGMENT_LENGTH) {
          result.push(piece.slice(i, i + MAX_SEGMENT_LENGTH));
        }
      } else {
        buffer = `${buffer}${buffer ? " " : ""}${piece}`;
      }
    }

    if (buffer.trim()) result.push(buffer.trim());
  }

  return result;
}

function pushPause(segments: PlaybackUnit[], pauseMs = 420) {
  segments.push({ pauseMs });
}

function pushText(
  segments: PlaybackUnit[],
  value: string | null | undefined,
  lang: AudioLanguage,
  options: { label?: string; pauseAfterMs?: number } = {},
) {
  const clean = cleanText(value, lang);
  if (!clean) return;

  if (options.label) {
    segments.push({
      text: options.label,
      lang,
      kind: "label",
      pauseAfterMs: 240,
    });
  }

  splitLongText(clean).forEach((part, index, list) => {
    if (!part) return;
    segments.push({
      text: part,
      lang,
      kind: "content",
      pauseAfterMs: index === list.length - 1 ? options.pauseAfterMs : 0,
    });
  });
}

function getReadableElementPreview(element: Element) {
  const source = cleanText(element.summary || element.text || element.intro_text || element.items?.[0] || "", "en");
  return source.length > 58 ? `${source.slice(0, 58)}...` : source || `Paragraph ${element.paragraph_id}`;
}

function getReadableElements(elements: Element[]) {
  return elements.filter((element) => element.type === "paragraph" || element.type === "bullet_list");
}

function buildOverviewSegments(
  overview: PaperOverview | null | undefined,
  lang: AudioLanguage,
  overviewPart: OverviewPart,
) {
  const segments: PlaybackUnit[] = [];
  if (!overview) return segments;

  const include = (part: OverviewPart) => overviewPart === "all" || overviewPart === part;

  if (include("abstract")) {
    pushText(segments, overview.abstract_summary, lang, {
      label: lang === "zh" ? "摘要總覽。" : "Abstract summary.",
      pauseAfterMs: 500,
    });
  }

  if (include("overall")) {
    pushText(segments, overview.overall_summary, lang, {
      label: lang === "zh" ? "全文總覽。" : "Paper overview.",
      pauseAfterMs: 500,
    });
  }

  if (include("key_points") && overview.overall_key_points?.length) {
    pushText(segments, lang === "zh" ? "整體重點。" : "Key points.", lang, { pauseAfterMs: 240 });
    overview.overall_key_points.forEach((point) => pushText(segments, point, lang, { pauseAfterMs: 240 }));
    pushPause(segments, 500);
  }

  if (include("sections") && overview.section_summaries?.length) {
    pushText(segments, lang === "zh" ? "主要章節。" : "Main sections.", lang, { pauseAfterMs: 240 });
    overview.section_summaries.forEach((section) => {
      pushText(segments, section.section_title, lang, { pauseAfterMs: 180 });
      pushText(segments, section.summary, lang, { pauseAfterMs: 500 });
    });
  }

  if (include("highlights") && overview.highlight_summaries?.length) {
    pushText(segments, lang === "zh" ? "重點整理。" : "Highlights.", lang, { pauseAfterMs: 240 });
    overview.highlight_summaries.forEach((highlight) => {
      pushText(segments, highlight.title, lang, { pauseAfterMs: 160 });
      pushText(segments, highlight.summary, lang, { pauseAfterMs: 450 });
    });
  }

  return segments;
}

function pushElementOriginalText(segments: PlaybackUnit[], element: Element, lang: AudioLanguage) {
  if (element.type === "bullet_list") {
    pushText(segments, element.intro_text, lang, {
      label: getLabelText("original", lang),
      pauseAfterMs: 240,
    });
    element.items?.forEach((item) => pushText(segments, item, lang, { pauseAfterMs: 180 }));
    pushPause(segments, 450);
    return;
  }

  pushText(segments, element.text, lang, {
    label: getLabelText("original", lang),
    pauseAfterMs: 520,
  });
}

function pushElementSummary(segments: PlaybackUnit[], element: Element, lang: AudioLanguage) {
  pushText(segments, element.summary, lang, {
    label: getLabelText("summary", lang),
    pauseAfterMs: 520,
  });
}

function pushElementKeyPoints(segments: PlaybackUnit[], element: Element, lang: AudioLanguage) {
  if (!element.key_points?.length) return;

  pushText(segments, getLabelText("key_points", lang), lang, { pauseAfterMs: 240 });
  element.key_points.forEach((point) => pushText(segments, point, lang, { pauseAfterMs: 220 }));
  pushPause(segments, 520);
}

function buildParagraphSegments(
  element: Element | null | undefined,
  lang: AudioLanguage,
  paragraphPart: ParagraphPart,
  paragraphIndex?: number,
) {
  const segments: PlaybackUnit[] = [];
  if (!element) return segments;

  if (paragraphIndex != null) {
    pushText(segments, getLabelText("paragraph", lang, paragraphIndex), lang, { pauseAfterMs: 260 });
  }

  if (paragraphPart === "all" || paragraphPart === "text") {
    pushElementOriginalText(segments, element, lang);
  }

  if (paragraphPart === "all" || paragraphPart === "summary") {
    pushElementSummary(segments, element, lang);
  }

  if (paragraphPart === "all" || paragraphPart === "key_points") {
    pushElementKeyPoints(segments, element, lang);
  }

  return segments;
}

function buildAllParagraphSegments(elements: Element[], lang: AudioLanguage, paragraphPart: ParagraphPart) {
  const readableElements = getReadableElements(elements);
  const segments: PlaybackUnit[] = [];

  readableElements.forEach((element, index) => {
    buildParagraphSegments(element, lang, paragraphPart, index + 1).forEach((segment) => segments.push(segment));
    pushPause(segments, 650);
  });

  return segments;
}

function findBestVoice(voices: SpeechSynthesisVoice[], language: AudioLanguage) {
  const compatibleVoices = voices.filter((voice) =>
    isVoiceCompatibleWithLanguage(voice, language),
  );

  const preferred = language === "zh"
    ? ["zh-TW", "zh-Hant", "zh-HK", "zh-CN", "Google 國語", "Google 中文", "Microsoft Hsiao", "Microsoft Hanhan", "Ting-Ting", "Mei-Jia"]
    : ["en-US", "en-GB", "Google US English", "Google UK English", "Microsoft Aria", "Microsoft Jenny", "Microsoft David", "Samantha", "Alex"];

  for (const keyword of preferred) {
    const lowerKeyword = keyword.toLowerCase();
    const match = compatibleVoices.find((voice) =>
      voice.lang.toLowerCase().includes(lowerKeyword) ||
      voice.name.toLowerCase().includes(lowerKeyword),
    );
    if (match) return match;
  }

  return compatibleVoices[0] || null;
}

function getContentSegmentCount(segments: PlaybackUnit[]) {
  return segments.filter((segment) => !isPauseSegment(segment)).length;
}

function getCurrentSpeakableIndex(segments: PlaybackUnit[], currentIndex: number) {
  if (currentIndex < 0) return 0;
  let count = 0;
  for (let i = 0; i <= currentIndex && i < segments.length; i += 1) {
    if (!isPauseSegment(segments[i])) count += 1;
  }
  return count;
}

function getNextContentIndex(segments: PlaybackUnit[], fromIndex: number, direction: 1 | -1) {
  let index = fromIndex + direction;
  while (index >= 0 && index < segments.length) {
    if (!isPauseSegment(segments[index])) return index;
    index += direction;
  }

  return Math.min(Math.max(fromIndex, 0), Math.max(segments.length - 1, 0));
}

export default function OverviewAudioPlayer({
  currentLanguage,
  activeElementId,
  englishOverview = null,
  englishElements = [],
  chineseOverview = null,
  chineseElements = [],
}: Props) {
  const [open, setOpen] = useState(false);
  const [playerState, setPlayerState] = useState<PlayerState>("idle");
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const [readLanguage, setReadLanguage] = useState<AudioLanguage>(currentLanguage);
  const [audioSource, setAudioSource] = useState<AudioSource>("overview");
  const [overviewPart, setOverviewPart] = useState<OverviewPart>("all");
  const [paragraphPart, setParagraphPart] = useState<ParagraphPart>("all");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceName, setSelectedVoiceName] = useState<string>("auto");
  const [rate, setRate] = useState(DEFAULT_RATE);

  const synthRef = useRef<SpeechSynthesis | null>(null);
  const segmentsRef = useRef<PlaybackUnit[]>([]);
  const stopRequestedRef = useRef(false);
  const pauseTimerRef = useRef<number | null>(null);
  const currentIndexRef = useRef(-1);
  const playbackRunIdRef = useRef(0);

  const sourceOverview = readLanguage === "zh" ? chineseOverview : englishOverview;
  const sourceElements = readLanguage === "zh" ? chineseElements : englishElements;
  const readableElements = useMemo(() => getReadableElements(sourceElements), [sourceElements]);

  const selectedParagraph = useMemo(() => {
    return readableElements.find((element) => element.id === activeElementId) || null;
  }, [activeElementId, readableElements]);

  const selectedParagraphIndex = useMemo(() => {
    if (!selectedParagraph) return undefined;
    const index = readableElements.findIndex((element) => element.id === selectedParagraph.id);
    return index >= 0 ? index + 1 : undefined;
  }, [readableElements, selectedParagraph]);

  const segments = useMemo(() => {
    if (audioSource === "overview") {
      return buildOverviewSegments(sourceOverview, readLanguage, overviewPart);
    }

    if (audioSource === "all_paragraphs") {
      return buildAllParagraphSegments(sourceElements, readLanguage, paragraphPart);
    }

    return buildParagraphSegments(selectedParagraph, readLanguage, paragraphPart, selectedParagraphIndex);
  }, [audioSource, overviewPart, paragraphPart, readLanguage, selectedParagraph, selectedParagraphIndex, sourceElements, sourceOverview]);

  const bestVoice = useMemo(() => findBestVoice(voices, readLanguage), [voices, readLanguage]);
  const selectedVoice = useMemo(() => {
    if (selectedVoiceName === "auto") return bestVoice;

    const selected = voices.find((voice) => voice.name === selectedVoiceName) || null;
    if (!selected) return bestVoice;

    return isVoiceCompatibleWithLanguage(selected, readLanguage)
      ? selected
      : bestVoice;
  }, [bestVoice, readLanguage, selectedVoiceName, voices]);

  useEffect(() => {
    const synth = window.speechSynthesis;
    synthRef.current = synth;

    const loadVoices = () => {
      setVoices(synth.getVoices());
    };

    loadVoices();
    synth.addEventListener?.("voiceschanged", loadVoices);
    synth.onvoiceschanged = loadVoices;

    return () => {
      playbackRunIdRef.current += 1;
      stopRequestedRef.current = true;
      if (pauseTimerRef.current) {
        window.clearTimeout(pauseTimerRef.current);
      }
      synth.cancel();
      synth.removeEventListener?.("voiceschanged", loadVoices);
      if (synth.onvoiceschanged === loadVoices) {
        synth.onvoiceschanged = null;
      }
    };
  }, []);

  useEffect(() => {
    if (selectedVoiceName === "auto") return;

    const selected = voices.find((voice) => voice.name === selectedVoiceName);
    if (!selected) return;

    if (!isVoiceCompatibleWithLanguage(selected, readLanguage)) {
      setSelectedVoiceName("auto");
    }
  }, [readLanguage, selectedVoiceName, voices]);

  useEffect(() => {
    if (playerState === "idle") {
      segmentsRef.current = segments;
      setCurrentIndex(-1);
      currentIndexRef.current = -1;
    }
  }, [playerState, segments]);

  function clearPauseTimer() {
    if (pauseTimerRef.current) {
      window.clearTimeout(pauseTimerRef.current);
      pauseTimerRef.current = null;
    }
  }

  function getVoiceForSegment(segment: AudioSegment) {
    if (
      selectedVoiceName !== "auto" &&
      selectedVoice &&
      isVoiceCompatibleWithLanguage(selectedVoice, segment.lang)
    ) {
      return selectedVoice;
    }

    return findBestVoice(voices, segment.lang) || null;
  }

  function invalidateCurrentPlayback() {
    playbackRunIdRef.current += 1;
    stopRequestedRef.current = true;
    clearPauseTimer();
    synthRef.current?.cancel();
    return playbackRunIdRef.current;
  }

  function isPlaybackRunActive(runId: number) {
    return playbackRunIdRef.current === runId && !stopRequestedRef.current;
  }

  function speakFrom(index: number, runId: number) {
    const synth = synthRef.current;
    if (!synth) return;
    if (!isPlaybackRunActive(runId)) return;

    if (index >= segmentsRef.current.length) {
      if (!isPlaybackRunActive(runId)) return;
      setPlayerState("idle");
      setCurrentIndex(-1);
      currentIndexRef.current = -1;
      return;
    }

    const segment = segmentsRef.current[index];
    setCurrentIndex(index);
    currentIndexRef.current = index;

    if (isPauseSegment(segment)) {
      pauseTimerRef.current = window.setTimeout(() => {
        pauseTimerRef.current = null;
        if (isPlaybackRunActive(runId)) speakFrom(index + 1, runId);
      }, segment.pauseMs);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(segment.text);
    const voice = getVoiceForSegment(segment);

    if (voice && isVoiceCompatibleWithLanguage(voice, segment.lang)) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    } else {
      utterance.lang = segment.lang === "zh" ? "zh-TW" : "en-US";
    }

    utterance.rate = rate;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      if (!isPlaybackRunActive(runId)) return;
      setCurrentIndex(index);
      currentIndexRef.current = index;
      setPlayerState("playing");
    };

    utterance.onend = () => {
      if (!isPlaybackRunActive(runId)) return;

      if (segment.pauseAfterMs && segment.pauseAfterMs > 0) {
        pauseTimerRef.current = window.setTimeout(() => {
          pauseTimerRef.current = null;
          if (isPlaybackRunActive(runId)) speakFrom(index + 1, runId);
        }, segment.pauseAfterMs);
        return;
      }

      speakFrom(index + 1, runId);
    };

    utterance.onerror = () => {
      if (!isPlaybackRunActive(runId)) return;
      speakFrom(index + 1, runId);
    };

    synth.speak(utterance);
  }

  function startPlayback(index = 0) {
    const synth = synthRef.current;
    if (!synth || !segments.length) return;

    const runId = invalidateCurrentPlayback();
    const queue = [...segments];

    window.setTimeout(() => {
      playbackRunIdRef.current = runId;
      stopRequestedRef.current = false;
      segmentsRef.current = queue;
      setPlayerState("playing");
      speakFrom(Math.max(0, Math.min(index, queue.length - 1)), runId);
    }, 0);
  }

  function handlePlay() {
    startPlayback(0);
  }

  function jumpToIndex(index: number) {
    const synth = synthRef.current;
    const queue = segmentsRef.current.length ? [...segmentsRef.current] : [...segments];
    if (!synth || !queue.length) return;

    const runId = invalidateCurrentPlayback();

    window.setTimeout(() => {
      playbackRunIdRef.current = runId;
      stopRequestedRef.current = false;
      segmentsRef.current = queue;
      setPlayerState("playing");
      speakFrom(Math.max(0, Math.min(index, queue.length - 1)), runId);
    }, 0);
  }

  function handlePrevious() {
    const baseIndex = currentIndexRef.current >= 0 ? currentIndexRef.current : 0;
    jumpToIndex(getNextContentIndex(segmentsRef.current, baseIndex, -1));
  }

  function handleNext() {
    const baseIndex = currentIndexRef.current >= 0 ? currentIndexRef.current : 0;
    jumpToIndex(getNextContentIndex(segmentsRef.current, baseIndex, 1));
  }

  function handleRestartCurrent() {
    const baseIndex = currentIndexRef.current >= 0 ? currentIndexRef.current : 0;
    jumpToIndex(baseIndex);
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
    invalidateCurrentPlayback();
    setPlayerState("idle");
    setCurrentIndex(-1);
    currentIndexRef.current = -1;
  }

  function handleReadLanguageChange(nextLanguage: AudioLanguage) {
    if (nextLanguage === readLanguage) return;
    handleStop();
    setReadLanguage(nextLanguage);
  }

  function handleOpenToggle() {
    setOpen((prev) => !prev);
  }

  const totalUnits = segments.length;
  const totalSpeakable = getContentSegmentCount(segments);
  const current = getCurrentSpeakableIndex(segmentsRef.current.length ? segmentsRef.current : segments, currentIndex);
  const hasCurrentLanguageData = readLanguage === "zh"
    ? !!chineseOverview || chineseElements.length > 0
    : !!englishOverview || englishElements.length > 0;
  const selectedParagraphLabel = selectedParagraph ? getReadableElementPreview(selectedParagraph) : "No paragraph selected";
  const compatibleVoices = voices.filter((voice) =>
    isVoiceCompatibleWithLanguage(voice, readLanguage),
  );

  return (
    <div className="audio-dropdown">
      <button
        className={`audio-toggle-button ${playerState !== "idle" ? "active" : ""}`}
        onClick={handleOpenToggle}
        title="Open audio panel"
      >
        Audio ▼
      </button>

      {open && (
        <div className="audio-dropdown-panel audio-control-panel">
          <div className="audio-panel-header">
            <div>
              <div className="audio-panel-title">Read aloud</div>
              <div className="audio-panel-subtitle">
                Choose a range and control playback without adding buttons to every paragraph.
              </div>
            </div>
          </div>

          <div className="audio-panel-grid">
            <label className="audio-field">
              <span>Language</span>
              <select
                value={readLanguage}
                onChange={(e) => handleReadLanguageChange(e.target.value as AudioLanguage)}
              >
                <option value="en">English</option>
                <option value="zh" disabled={!chineseOverview && chineseElements.length === 0}>中文</option>
              </select>
            </label>

            <label className="audio-field">
              <span>Range</span>
              <select
                value={audioSource}
                onChange={(e) => {
                  handleStop();
                  setAudioSource(e.target.value as AudioSource);
                }}
              >
                <option value="overview">Overview</option>
                <option value="selected_paragraph">Selected paragraph</option>
                <option value="all_paragraphs">All paragraphs</option>
              </select>
            </label>
          </div>

          {audioSource === "overview" ? (
            <label className="audio-field audio-field-full">
              <span>Overview content</span>
              <select
                value={overviewPart}
                onChange={(e) => {
                  handleStop();
                  setOverviewPart(e.target.value as OverviewPart);
                }}
              >
                <option value="all">All overview</option>
                <option value="abstract">Abstract summary</option>
                <option value="overall">Paper overview</option>
                <option value="key_points">Key points</option>
                <option value="sections">Main sections</option>
                <option value="highlights">Highlights</option>
              </select>
            </label>
          ) : (
            <>
              <label className="audio-field audio-field-full">
                <span>Paragraph content</span>
                <select
                  value={paragraphPart}
                  onChange={(e) => {
                    handleStop();
                    setParagraphPart(e.target.value as ParagraphPart);
                  }}
                >
                  <option value="all">Original text + summary + key points</option>
                  <option value="text">Original text only</option>
                  <option value="summary">Summary only</option>
                  <option value="key_points">Key points only</option>
                </select>
              </label>

              {audioSource === "selected_paragraph" && (
                <div className="audio-selected-paragraph">
                  Selected: {selectedParagraphLabel}
                </div>
              )}
            </>
          )}

          <div className="audio-panel-grid">
            <label className="audio-field">
              <span>Voice</span>
              <select
                value={selectedVoiceName}
                onChange={(e) => {
                  handleStop();
                  setSelectedVoiceName(e.target.value);
                }}
              >
                <option value="auto">Auto best voice</option>
                {compatibleVoices.map((voice) => (
                  <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
                    {voice.name} ({voice.lang})
                  </option>
                ))}
              </select>
            </label>

            <label className="audio-field">
              <span>Speed {rate.toFixed(2)}x</span>
              <input
                type="range"
                min="0.75"
                max="1.15"
                step="0.05"
                value={rate}
                onChange={(e) => {
                  handleStop();
                  setRate(Number(e.target.value));
                }}
              />
            </label>
          </div>

          <div className="overview-audio-controls audio-panel-controls">
            <button onClick={handlePlay} disabled={!totalUnits || !hasCurrentLanguageData}>
              Play
            </button>
            <button onClick={handlePauseResume} disabled={playerState === "idle"}>
              {playerState === "paused" ? "Resume" : "Pause"}
            </button>
            <button onClick={handleStop} disabled={playerState === "idle"}>
              Stop
            </button>
          </div>

          <div className="overview-audio-controls audio-panel-controls audio-panel-skip-controls">
            <button onClick={handlePrevious} disabled={playerState === "idle"}>
              ← Previous
            </button>
            <button onClick={handleRestartCurrent} disabled={playerState === "idle"}>
              Replay current
            </button>
            <button onClick={handleNext} disabled={playerState === "idle"}>
              Next →
            </button>
          </div>

          <div className="overview-audio-status audio-panel-status">
            {!hasCurrentLanguageData
              ? "This language is not loaded yet. Switch to it once or wait for translation data."
              : playerState === "idle"
              ? `${totalSpeakable} parts ready${selectedVoice ? ` · ${selectedVoice.name}` : ""}`
              : `Reading ${current} / ${totalSpeakable}${selectedVoice ? ` · ${selectedVoice.name}` : ""}`}
          </div>

          {readLanguage === "zh" && (
            <div className="audio-panel-hint">
              中文朗讀品質取決於你的瀏覽器與系統安裝的中文 voice；如果聲音太機械，可以在 Voice 選單換其他語音。
            </div>
          )}
        </div>
      )}
    </div>
  );
}
