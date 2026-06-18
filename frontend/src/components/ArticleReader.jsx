import { useCallback, useState } from "react";
import useTextSelection from "../hooks/useTextSelection";
import WordPopup from "./WordPopup";

/**
 * T8 ArticleReader
 * - 渲染文章，highlight_words 用琥珀底色標記
 * - 選字後顯示 WordPopup
 * - TTS 朗讀時對應 word index 高亮目前朗讀位置
 */
export default function ArticleReader({ article, token, tts }) {
  const [popup, setPopup] = useState(null); // { word, position, contextSentence }
  const [savedWords, setSavedWords] = useState(new Set());

  const handleSelect = useCallback((word, position) => {
    // 找到選字所在的句子作為 context
    const sentences = article.content.replace(/\*\*/g, "").split(/(?<=[.!?])\s+/);
    const contextSentence = sentences.find(s =>
      s.toLowerCase().includes(word.toLowerCase())
    ) || "";

    setPopup({ word, position, contextSentence });
  }, [article.content]);

  const containerRef = useTextSelection(handleSelect);

  // 把 content 解析成 word spans，供 TTS 高亮用
  const renderContent = () => {
    const paragraphs = article.content.split("\n\n").filter(Boolean);
    let globalWordIdx = 0;

    return paragraphs.map((para, pi) => {
      // 清掉 ** 標記，但記住哪些是 highlight words
      const highlightSet = new Set(article.highlight_words?.map(w => w.toLowerCase()) || []);

      const tokens = para.split(/(\s+)/);
      const spans = tokens.map((token, ti) => {
        if (/^\s+$/.test(token)) return token; // 空白直接回傳

        const wordIdx = globalWordIdx++;
        const cleanWord = token.replace(/\*\*/g, "").replace(/[^a-zA-Z'-]/g, "").toLowerCase();
        const isHighlight = highlightSet.has(cleanWord);
        const isCurrentlyReading = tts.speaking && tts.currentWordIndex === wordIdx;
        const isSaved = savedWords.has(cleanWord);

        return (
          <span key={`${pi}-${ti}`} style={{
            background: isCurrentlyReading
              ? "#B7E4C7"   // 朗讀高亮：淡綠
              : isHighlight
              ? "#FFF3CD"   // 學習重點：淡琥珀
              : "transparent",
            borderRadius: 2,
            padding: isHighlight || isCurrentlyReading ? "0 2px" : 0,
            fontWeight: isHighlight ? 500 : "inherit",
            borderBottom: isSaved ? "2px solid #2D6A4F" : "none",
            cursor: "text",
            transition: "background 0.15s",
          }}>
            {token.replace(/\*\*/g, "")}
          </span>
        );
      });

      return (
        <p key={pi} style={{
          margin: "0 0 1.4em",
          lineHeight: 1.85,
          fontSize: 17,
          color: "#1A1A1A",
          fontFamily: "'Source Serif 4', 'Georgia', serif",
        }}>
          {spans}
        </p>
      );
    });
  };

  return (
    <div style={{ position: "relative" }}>
      {/* 文章本體 */}
      <div ref={containerRef} style={{ cursor: "text", userSelect: "text" }}>
        {renderContent()}
      </div>

      {/* 選字 Popup */}
      {popup && (
        <WordPopup
          word={popup.word}
          position={popup.position}
          token={token}
          articleId={article.id}
          contextSentence={popup.contextSentence}
          onClose={() => setPopup(null)}
          onAddedToVocab={(word) => {
            setSavedWords(prev => new Set([...prev, word]));
            setPopup(null);
          }}
        />
      )}
    </div>
  );
}
