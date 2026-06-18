import { useState } from "react";
import { apiFetch } from "../hooks/useAPI";

export default function AuthPage({ onLogin }) {
  const [mode, setMode] = useState("login"); // login | register
  const [form, setForm] = useState({ email: "", username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handle = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  const submit = async () => {
    setError(""); setLoading(true);
    try {
      if (mode === "register") {
        await apiFetch("/auth/register", "", {
          method: "POST",
          body: JSON.stringify({ email: form.email, username: form.username, password: form.password }),
        });
        setMode("login");
        setError(""); // 清掉，切換到 login 提示
        return;
      }
      // login — OAuth2PasswordRequestForm 要用 form-urlencoded
      const res = await fetch("http://localhost:8000/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: form.email, password: form.password }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Login failed");
      }
      const data = await res.json();
      onLogin(data.access_token, data.username);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", background: "#F7F4EF",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      <div style={{ width: "100%", maxWidth: 380 }}>
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <h1 style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 36, fontWeight: 700, color: "#1A1A1A",
            margin: "0 0 8px", letterSpacing: "-0.5px",
          }}>ReadEn</h1>
          <p style={{ fontSize: 14, color: "#9E9891", margin: 0 }}>
            Read the news. Learn English naturally.
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: "#FFFDF8", borderRadius: 12,
          border: "1px solid #E8E4DD",
          padding: "28px 28px 24px",
          boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
        }}>
          {/* Tab */}
          <div style={{ display: "flex", marginBottom: 24, borderBottom: "1px solid #E8E4DD" }}>
            {["login", "register"].map(m => (
              <button key={m} onClick={() => { setMode(m); setError(""); }} style={{
                flex: 1, padding: "8px 0", border: "none", background: "none",
                borderBottom: mode === m ? "2px solid #2D6A4F" : "2px solid transparent",
                color: mode === m ? "#2D6A4F" : "#9E9891",
                fontSize: 14, fontWeight: mode === m ? 600 : 400,
                cursor: "pointer", fontFamily: "inherit",
                marginBottom: -1,
              }}>
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          {/* Fields */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Field label="Email" type="email" value={form.email} onChange={handle("email")}
              onEnter={submit} placeholder="you@example.com" />
            {mode === "register" && (
              <Field label="Username" type="text" value={form.username} onChange={handle("username")}
                onEnter={submit} placeholder="Your display name" />
            )}
            <Field label="Password" type="password" value={form.password} onChange={handle("password")}
              onEnter={submit} placeholder="••••••••" />
          </div>

          {/* Error */}
          {error && (
            <p style={{ margin: "12px 0 0", fontSize: 13, color: "#C0392B" }}>{error}</p>
          )}

          {/* Submit */}
          <button onClick={submit} disabled={loading} style={{
            width: "100%", marginTop: 20,
            padding: "11px 0", borderRadius: 8,
            border: "none", background: "#2D6A4F",
            color: "#fff", fontSize: 14, fontWeight: 600,
            cursor: loading ? "default" : "pointer",
            fontFamily: "inherit", opacity: loading ? 0.75 : 1,
          }}>
            {loading ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, type, value, onChange, onEnter, placeholder }) {
  return (
    <div>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#6B6560", marginBottom: 4 }}>
        {label}
      </label>
      <input
        type={type} value={value} onChange={onChange} placeholder={placeholder}
        onKeyDown={e => e.key === "Enter" && onEnter()}
        style={{
          width: "100%", padding: "9px 12px", borderRadius: 7,
          border: "1px solid #D4CFC7", background: "#FAF8F5",
          fontSize: 14, color: "#1A1A1A",
          outline: "none", fontFamily: "inherit",
          boxSizing: "border-box",
        }}
        onFocus={e => e.target.style.borderColor = "#2D6A4F"}
        onBlur={e => e.target.style.borderColor = "#D4CFC7"}
      />
    </div>
  );
}
