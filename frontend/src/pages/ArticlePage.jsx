import { useState, useEffect } from "react";
import { apiFetch } from "../hooks/useAPI";
import ArticleReader from "../components/ArticleReader";
import useTTS from "../hooks/useTTS";

export default function ArticlePage({ token }) {
  const [article, setArticle] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | found | empty | error | generating
  const tts = useTTS();

  useEffect(() => {
    loadToday();
  }, []);

  const loadToday = () => {
    setStatus("loading");
    apiFetch("/articles/today", token)
      .then(data => { setArticle(data); setStatus("found"); })
      .catch(err => {
        if (err.status === 404) setStatus("empty");
        else setStatus("error");
      });
  };

  const handleGenerate = async () => {
    setStatus("generating");
    try {
      await apiFetch("/articles/generate-today", token, { method: "POST" });
      loadToday();
    } catch (err) {
      if (err.status === 409) loadToday(); // 已有文章
      else setStatus("error");
    }
  };

  const handleTTS = () => {
    if (tts.speaking) { tts.stop(); return; }
    // iOS 要求直接在 click handler 裡呼叫
    tts.speak(article.content);
  };

  if (status === "loading") return (
    <PageShell>
      <div style={{ textAlign: "center", padding: "80px 0", color: "#9E9891" }}>
        <LoadingDots />
        <p style={{ marginTop: 12, fontSize: 14 }}>Loading today's article…</p>
      </div>
    </PageShell>
  );

  if (status === "generating") return (
    <PageShell>
      <div style={{ textAlign: "center", padding: "80px 0", color: "#6B6560" }}>
        <LoadingDots />
        <p style={{ marginTop: 12, fontSize: 14, fontWeight: 500 }}>
          Generating today's article with AI…
        </p>
        <p style={{ fontSize: 13, color: "#9E9891", marginTop: 4 }}>
          This takes about 15–30 seconds.
        </p>
      </div>
    </PageShell>
  );

  if (status === "empty") return (
    <PageShell>
      <div style={{ textAlign: "center", padding: "80px 24px" }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>📰</div>
        <h2 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 24, fontWeight: 700, color: "#1A1A1A", marginBottom: 8,
        }}>No article yet today</h2>
        <p style={{ color: "#6B6560", fontSize: 14, marginBottom: 24 }}>
          Generate today's article from the latest news.
        </p>
        <button onClick={handleGenerate} style={primaryBtn}>
          Generate today's article
        </button>
      </div>
    </PageShell>
  );

  if (status === "error") return (
    <PageShell>
      <div style={{ textAlign: "center", padding: "80px 24px" }}>
        <p style={{ color: "#C0392B", marginBottom: 16 }}>Something went wrong. Check the server is running.</p>
        <button onClick={loadToday} style={primaryBtn}>Try again</button>
      </div>
    </PageShell>
  );

  if (!article) return null;

  const wordCount = article.word_count || 0;
  const readingMins = Math.ceil(wordCount / 180);

  return (
    <PageShell>
      {/* Article Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <span style={badgeStyle}>{article.difficulty_level}</span>
          <span style={{ fontSize: 12, color: "#9E9891" }}>·</span>
          <span style={{ fontSize: 12, color: "#9E9891" }}>{wordCount} words</span>
          <span style={{ fontSize: 12, color: "#9E9891" }}>·</span>
          <span style={{ fontSize: 12, color: "#9E9891" }}>{readingMins} min read</span>
          <span style={{ fontSize: 12, color: "#9E9891" }}>·</span>
          <a href={article.source_url} target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 12, color: "#2D6A4F", textDecoration: "none" }}>
            {article.source_name} ↗
          </a>
        </div>

        <h1 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: "clamp(24px, 4vw, 36px)",
          fontWeight: 700, lineHeight: 1.25,
          color: "#1A1A1A", margin: "0 0 16px",
          letterSpacing: "-0.3px",
        }}>{article.title}</h1>

        {article.summary && (
          <p style={{
            fontSize: 15, color: "#6B6560", lineHeight: 1.7,
            margin: "0 0 20px",
            borderLeft: "3px solid #2D6A4F",
            paddingLeft: 14,
          }}>{article.summary}</p>
        )}

        {/* TTS 控制 + 進度說明 */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <button onClick={handleTTS} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "7px 14px", borderRadius: 20,
            border: "1.5px solid " + (tts.speaking ? "#2D6A4F" : "#D4CFC7"),
            background: tts.speaking ? "#EAF4EF" : "transparent",
            color: tts.speaking ? "#2D6A4F" : "#6B6560",
            fontSize: 13, fontWeight: 500, cursor: "pointer",
            fontFamily: "inherit",
          }}>
            {tts.speaking ? "⏹ Stop reading" : "▶ Read aloud"}
          </button>

          {tts.speaking && (
            <span style={{ fontSize: 12, color: "#9E9891" }}>
              Reading aloud — words highlighted as they're spoken
            </span>
          )}
        </div>

        {/* Highlight words 說明 */}
        {article.highlight_words?.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, color: "#9E9891" }}>Key words:</span>
            {article.highlight_words.map(w => (
              <span key={w} style={{
                fontSize: 12, background: "#FFF3CD",
                padding: "2px 8px", borderRadius: 3,
                color: "#6B6560", fontWeight: 500,
              }}>{w}</span>
            ))}
          </div>
        )}
      </div>

      {/* Divider */}
      <hr style={{ border: "none", borderTop: "1px solid #E8E4DD", marginBottom: 28 }} />

      {/* T8 文章本體 */}
      <ArticleReader article={article} token={token} tts={tts} />

      {/* 底部提示 */}
      <div style={{
        marginTop: 40, padding: "16px 20px",
        background: "#F0EDE8", borderRadius: 8,
        fontSize: 13, color: "#6B6560",
      }}>
        💡 Select any word to look it up and save it to your word list.
      </div>
    </PageShell>
  );
}

// ── Shared UI ─────────────────────────────────────────────────────

function PageShell({ children }) {
  return (
    <main style={{
      maxWidth: 720, margin: "0 auto",
      padding: "40px 24px 80px",
    }}>
      {children}
    </main>
  );
}

function LoadingDots() {
  return (
    <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 8, height: 8, borderRadius: "50%",
          background: "#C8C3BB",
          animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
      <style>{`@keyframes pulse { 0%,80%,100%{transform:scale(0.8);opacity:0.5} 40%{transform:scale(1);opacity:1} }`}</style>
    </div>
  );
}

const primaryBtn = {
  padding: "10px 24px", borderRadius: 8,
  border: "none", background: "#2D6A4F",
  color: "#fff", fontSize: 14, fontWeight: 500,
  cursor: "pointer", fontFamily: "inherit",
};

const badgeStyle = {
  display: "inline-block",
  fontSize: 11, fontWeight: 700, letterSpacing: "0.5px",
  padding: "2px 7px", borderRadius: 4,
  background: "#2D6A4F", color: "#fff",
};
