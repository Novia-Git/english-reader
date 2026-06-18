import { useState, useRef, useCallback } from "react";

export default function useTTS() {
  const [speaking, setSpeaking] = useState(false);
  const [currentWordIndex, setCurrentWordIndex] = useState(-1);
  const utteranceRef = useRef(null);

  const stop = useCallback(() => {
    window.speechSynthesis.cancel();
    setSpeaking(false);
    setCurrentWordIndex(-1);
  }, []);

  // 朗讀整段文字，同時追蹤目前播到的位置
  const speak = useCallback((text) => {
    if (!window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    const words = text.replace(/\*\*/g, "").split(/\s+/);
    const utterance = new SpeechSynthesisUtterance(text.replace(/\*\*/g, ""));
    utterance.lang = "en-US";
    utterance.rate = 0.9;

    utterance.onboundary = (e) => {
      if (e.name === "word") {
        // 用 charIndex 找目前是第幾個 word
        const spoken = text.replace(/\*\*/g, "").slice(0, e.charIndex);
        const idx = spoken.split(/\s+/).filter(Boolean).length;
        setCurrentWordIndex(idx);
      }
    };
    utterance.onend = () => { setSpeaking(false); setCurrentWordIndex(-1); };
    utterance.onerror = () => { setSpeaking(false); setCurrentWordIndex(-1); };

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }, []);

  // 朗讀單一單字（WordPopup 的音標按鈕用）
  const speakWord = useCallback((word) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(word);
    u.lang = "en-US";
    u.rate = 0.8;
    window.speechSynthesis.speak(u);
  }, []);

  return { speaking, currentWordIndex, speak, speakWord, stop };
}
