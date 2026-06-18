import { useState, useEffect, useRef } from "react";
import { apiFetch } from "../hooks/useAPI";
import useTTS from "../hooks/useTTS";

/**
 * T9 WordPopup — 選字後彈出的字典卡片
 * 像夾在書裡的便條紙：輕微紙張質感、細邊框、溫暖色調
 */
export default function WordPopup({ word, position, token, articleId, contextSentence, onClose, onAddedToVocab }) {
  const [state, setState] = useState("loading"); // loading | found | notfound | error
  const [definition, setDefinition] = useState(null);
  const [addStatus, setAddStatus] = useState("idle"); // idle | adding | added | duplicate
  const popupRef = useRef(null);
  const { speakWord } = useTTS();

  // 查字典
  useEffect(() => {
    if (!word) return;
    setState("loading");
    setDefinition(null);
    setAddStatus("idle");

    apiFetch(`/dictionary/${encodeURIComponent(word)}`, token)
      .then(data => { setDefinition(data); setState("found"); })
      .catch(err => {
        if (err.status === 404) setState("notfound");
        else setState("error");
      });
  }, [word]);

  // 點外部關閉
  useEffect(() => {
    const handler = (e) => {
      if (popupRef.current && !popupRef.current.contains(e.target)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  // 加入單字本
  const handleAdd = async () => {
    if (addStatus !== "idle") return;
    setAddStatus("adding");
    try {
      await apiFetch("/vocab", token, {
        method: "POST",
        body: JSON.stringify({ word, article_id: articleId, context_sentence: contextSentence }),
      });
      setAddStatus("added");
      onAddedToVocab?.(word);
    } catch (err) {
      if (err.status === 409) setAddStatus("duplicate");
      else setAddStatus("idle");
    }
  };

  // 計算 popup 位置（確保不超出螢幕邊界）
  const popupStyle = {
    position: "fixed",
    left: Math.min(Math.max(position.x - 160, 12), window.innerWidth - 332),
    top: Math.max(position.y - 220, 12),
    zIndex: 1000,
    width: 320,
    background: "#FFFDF8",
    border: "1px solid #D4CFC7",
    borderRadius: 10,
    boxShadow: "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
    overflow: "hidden",
  };

  return (
    <div ref={popupRef} style={popupStyle}>
      {/* Header */}
      <div style={{
        padding: "14px 16px 10px",
        borderBottom: "1px solid #EBE7E0",
        display: "flex", alignItems: "flex-start", justifyContent: "space-between",
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: 22, fontWeight: 700, color: "#1A1A1A",
            }}>{word}</span>
            {definition?.phonetic && (
              <button onClick={() => speakWord(word)} style={{
                background: "none", border: "none", cursor: "pointer",
                padding: 4, borderRadius: 4,
                color: "#2D6A4F", fontSize: 18, lineHeight: 1,
              }} title="Play pronunciation">🔊</button>
            )}
          </div>
          {definition?.phonetic && (
            <span style={{ fontSize: 13, color: "#6B6560", fontFamily: "monospace" }}>
              {definition.phonetic}
            </span>
          )}
        </div>
        <button onClick={onClose} style={{
          background: "none", border: "none", cursor: "pointer",
          color: "#9E9891", fontSize: 18, padding: 2, lineHeight: 1,
        }}>✕</button>
      </div>

      {/* Body */}
      <div style={{ padding: "12px 16px", maxHeight: 220, overflowY: "auto" }}>
        {state === "loading" && (
          <div style={{ color: "#9E9891", fontSize: 13, textAlign: "center", padding: "16px 0" }}>
            Looking up <em>{word}</em>…
          </div>
        )}

        {state === "notfound" && (
          <div style={{ color: "#9E9891", fontSize: 13 }}>
            No definition found for "<strong>{word}</strong>".
          </div>
        )}

        {state === "error" && (
          <div style={{ color: "#C0392B", fontSize: 13 }}>
            Could not reach the dictionary. Try again later.
          </div>
        )}

        {state === "found" && definition?.definitions?.map((def, i) => (
          <div key={i} style={{ marginBottom: i < definition.definitions.length - 1 ? 12 : 0 }}>
            <span style={{
              display: "inline-block",
              fontSize: 10, fontWeight: 600, textTransform: "uppercase",
              letterSpacing: "0.8px", color: "#fff",
              background: "#2D6A4F", borderRadius: 3,
              padding: "2px 6px", marginBottom: 4,
            }}>{def.part_of_speech}</span>
            <p style={{ margin: "0 0 4px", fontSize: 13.5, color: "#1A1A1A", lineHeight: 1.6 }}>
              {def.definition}
            </p>
            {def.example && (
              <p style={{ margin: 0, fontSize: 12.5, color: "#6B6560", fontStyle: "italic", lineHeight: 1.5 }}>
                "{def.example}"
              </p>
            )}
            {def.synonyms?.length > 0 && (
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "#9E9891" }}>
                Also: {def.synonyms.slice(0, 3).join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Footer — 加入單字本 */}
      <div style={{ padding: "10px 16px", borderTop: "1px solid #EBE7E0" }}>
        {addStatus === "added" ? (
          <div style={{ fontSize: 13, color: "#2D6A4F", fontWeight: 500 }}>
            ✓ Added to your word list
          </div>
        ) : addStatus === "duplicate" ? (
          <div style={{ fontSize: 13, color: "#9E9891" }}>
            Already in your word list
          </div>
        ) : (
          <button onClick={handleAdd} disabled={addStatus === "adding" || state === "loading"} style={{
            width: "100%", padding: "8px 0",
            background: state === "found" ? "#2D6A4F" : "#E8E4DD",
            color: state === "found" ? "#fff" : "#9E9891",
            border: "none", borderRadius: 6,
            fontSize: 13, fontWeight: 500, cursor: state === "found" ? "pointer" : "default",
            fontFamily: "inherit",
            opacity: addStatus === "adding" ? 0.7 : 1,
          }}>
            {addStatus === "adding" ? "Adding…" : "+ Save to word list"}
          </button>
        )}
      </div>
    </div>
  );
}
