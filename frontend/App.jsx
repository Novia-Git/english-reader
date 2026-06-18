import { useState } from "react";
import ArticlePage from "./pages/ArticlePage";
import VocabPage from "./pages/VocabPage";
import AuthPage from "./pages/AuthPage";

export default function App() {
  const [page, setPage] = useState("article"); // "article" | "vocab" | "auth"
  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [username, setUsername] = useState(() => localStorage.getItem("username") || "");

  const handleLogin = (newToken, newUsername) => {
    setToken(newToken);
    setUsername(newUsername);
    localStorage.setItem("token", newToken);
    localStorage.setItem("username", newUsername);
    setPage("article");
  };

  const handleLogout = () => {
    setToken("");
    setUsername("");
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    setPage("auth");
  };

  if (!token) {
    return <AuthPage onLogin={handleLogin} />;
  }

  return (
    <div style={{ minHeight: "100vh", background: "#F7F4EF" }}>
      {/* Top Nav */}
      <nav style={{
        background: "#F7F4EF",
        borderBottom: "1px solid #E0DBD4",
        padding: "0 24px",
        height: 56,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          <span style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 20,
            fontWeight: 700,
            color: "#1A1A1A",
            letterSpacing: "-0.3px",
          }}>
            ReadEn
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            {[
              { id: "article", label: "Today's Article" },
              { id: "vocab", label: "My Words" },
            ].map(({ id, label }) => (
              <button key={id} onClick={() => setPage(id)} style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "none",
                background: page === id ? "#2D6A4F" : "transparent",
                color: page === id ? "#fff" : "#6B6560",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                fontFamily: "inherit",
              }}>{label}</button>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 13, color: "#6B6560" }}>{username}</span>
          <button onClick={handleLogout} style={{
            padding: "5px 12px", borderRadius: 6,
            border: "1px solid #E0DBD4", background: "transparent",
            color: "#6B6560", fontSize: 12, cursor: "pointer",
          }}>Sign out</button>
        </div>
      </nav>

      {page === "article" && <ArticlePage token={token} />}
      {page === "vocab" && <VocabPage token={token} />}
    </div>
  );
}
