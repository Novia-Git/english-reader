import { useState, useEffect } from "react";
import { apiFetch } from "../hooks/useAPI";
import useTTS from "../hooks/useTTS";

export default function VocabPage({ token }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("loading");
  const [expandedId, setExpandedId] = useState(null);
  const { speakWord } = useTTS();
  const PAGE_SIZE = 20;

  useEffect(() => {
    loadVocab(page);
  }, [page]);

  const loadVocab = (p) => {
    setStatus("loading");
    apiFetch(`/vocab?page=${p}&page_size=${PAGE_SIZE}`, token)
      .then(data => {
        setItems(data.items);
        setTotal(data.total);
        setStatus("done");
      })
      .catch(() => setStatus("error"));
  };

  const handleDelete = async (id, word) => {
    if (!confirm(`Remove "${word}" from your word list?`)) return;
    try {
      await apiFetch(`/vocab/${id}`, token, { method: "DELETE" });
      setItems(prev => prev.filter(i => i.id !== id));
      setTotal(prev => prev - 1);
    } catch {
      alert("Could not delete. Please try again.");
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "40px 24px 80px" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 28, fontWeight: 700, color: "#1A1A1A",
          margin: "0 0 6px",
        }}>My Word List</h1>
        <p style={{ fontSize: 14, color: "#9E9891", margin: 0 }}>
          {total > 0 ? `${total} word${total !== 1 ? "s" : ""} saved` : "No words saved yet"}
        </p>
      </div>

      {/* States */}
      {status === "loading" && (
        <div style={{ color: "#9E9891", fontSize: 14, padding: "40px 0", textAlign: "center" }}>
          Loading your words…
        </div>
      )}

      {status === "error" && (
        <div style={{ color: "#C0392B", fontSize: 14 }}>
          Couldn't load your word list. <button onClick={() => loadVocab(page)}
            style={{ color: "#2D6A4F", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>
            Try again
          </button>
        </div>
      )}

      {status === "done" && items.length === 0 && (
        <div style={{
          textAlign: "center", padding: "60px 24px",
          background: "#F0EDE8", borderRadius: 12,
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>📖</div>
          <p style={{ fontSize: 15, color: "#6B6560", margin: 0 }}>
            Select words while reading to save them here.
          </p>
        </div>
      )}

      {/* Word List */}
      {status === "done" && items.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {items.map(item => (
            <VocabCard
              key={item.id}
              item={item}
              expanded={expandedId === item.id}
              onToggle={() => setExpandedId(expandedId === item.id ? null : item.id)}
              onDelete={() => handleDelete(item.id, item.word)}
              onSpeak={() => speakWord(item.word)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 32 }}>
          <PageBtn disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</PageBtn>
          <span style={{ fontSize: 13, color: "#9E9891", padding: "8px 4px" }}>
            {page} / {totalPages}
          </span>
          <PageBtn disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next →</PageBtn>
        </div>
      )}
    </main>
  );
}

// ── VocabCard ─────────────────────────────────────────────────────

function VocabCard({ item, expanded, onToggle, onDelete, onSpeak }) {
  const def = item.cached_definition;
  const primaryDef = def?.definitions?.[0];

  return (
    <div style={{
      background: "#FFFDF8",
      border: "1px solid #E8E4DD",
      borderRadius: 8,
      marginBottom: 6,
      overflow: "hidden",
      transition: "box-shadow 0.15s",
    }}>
      {/* Row */}
      <div style={{
        display: "flex", alignItems: "center",
        padding: "14px 16px", gap: 12, cursor: "pointer",
      }} onClick={onToggle}>
        {/* Word + phonetic */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: 17, fontWeight: 600, color: "#1A1A1A",
            }}>{item.word}</span>
            {def?.phonetic && (
              <span style={{ fontSize: 12, color: "#9E9891", fontFamily: "monospace" }}>
                {def.phonetic}
              </span>
            )}
          </div>
          {primaryDef && !expanded && (
            <p style={{
              margin: 0, fontSize: 13, color: "#6B6560",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>
              <span style={{
                fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                background: "#2D6A4F", color: "#fff",
                padding: "1px 5px", borderRadius: 3, marginRight: 6,
              }}>{primaryDef.part_of_speech}</span>
              {primaryDef.definition}
            </p>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 4, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
          <ActionBtn onClick={onSpeak} title="Play pronunciation">🔊</ActionBtn>
          <ActionBtn onClick={onDelete} title="Remove from list" danger>✕</ActionBtn>
        </div>

        {/* Expand chevron */}
        <span style={{ color: "#C8C3BB", fontSize: 12, flexShrink: 0 }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{
          padding: "0 16px 16px",
          borderTop: "1px solid #F0EDE8",
        }}>
          {def ? (
            <>
              {def.definitions.map((d, i) => (
                <div key={i} style={{ marginTop: 12 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                    background: "#2D6A4F", color: "#fff",
                    padding: "2px 6px", borderRadius: 3, marginRight: 6,
                  }}>{d.part_of_speech}</span>
                  <span style={{ fontSize: 13.5, color: "#1A1A1A" }}>{d.definition}</span>
                  {d.example && (
                    <p style={{ margin: "4px 0 0 0", fontSize: 12.5, color: "#6B6560", fontStyle: "italic" }}>
                      "{d.example}"
                    </p>
                  )}
                  {d.synonyms?.length > 0 && (
                    <p style={{ margin: "4px 0 0", fontSize: 12, color: "#9E9891" }}>
                      Also: {d.synonyms.slice(0, 4).join(", ")}
                    </p>
                  )}
                </div>
              ))}
            </>
          ) : (
            <p style={{ marginTop: 12, fontSize: 13, color: "#9E9891" }}>No definition saved.</p>
          )}

          {item.context_sentence && (
            <div style={{
              marginTop: 14, padding: "10px 12px",
              background: "#F7F4EF", borderRadius: 6,
              borderLeft: "3px solid #D4CFC7",
            }}>
              <p style={{ margin: 0, fontSize: 12, color: "#9E9891", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                From the article
              </p>
              <p style={{ margin: 0, fontSize: 13, color: "#6B6560", lineHeight: 1.6, fontStyle: "italic" }}>
                {item.context_sentence}
              </p>
            </div>
          )}

          {item.article_title && (
            <p style={{ margin: "10px 0 0", fontSize: 12, color: "#9E9891" }}>
              Source: {item.article_title}
            </p>
          )}

          <p style={{ margin: "8px 0 0", fontSize: 11, color: "#C8C3BB" }}>
            Saved {new Date(item.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Small UI components ───────────────────────────────────────────

function ActionBtn({ onClick, title, danger, children }) {
  return (
    <button onClick={onClick} title={title} style={{
      background: "none", border: "none", cursor: "pointer",
      color: danger ? "#C8C3BB" : "#9E9891",
      fontSize: 14, padding: "4px 6px", borderRadius: 4,
      fontFamily: "inherit",
    }}
      onMouseEnter={e => e.currentTarget.style.color = danger ? "#C0392B" : "#2D6A4F"}
      onMouseLeave={e => e.currentTarget.style.color = danger ? "#C8C3BB" : "#9E9891"}
    >{children}</button>
  );
}

function PageBtn({ onClick, disabled, children }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: "7px 14px", borderRadius: 6,
      border: "1px solid #E0DBD4",
      background: disabled ? "#F7F4EF" : "transparent",
      color: disabled ? "#C8C3BB" : "#6B6560",
      fontSize: 13, cursor: disabled ? "default" : "pointer",
      fontFamily: "inherit",
    }}>{children}</button>
  );
}
