import React, { useEffect, useState } from "react";
import {
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
} from "react-router-dom";
import {
  AudioLines,
  LayoutDashboard,
  Bot,
  Mic,
  Phone,
  History,
  MessagesSquare,
  ChartNoAxesCombined,
  Settings,
  ArrowUpRight,
  Plus,
  Search,
  LogOut,
  ChevronDown,
  Headphones,
  Radio,
  Menu,
  X,
} from "lucide-react";
import { api, errorText } from "./services/api";
import Dashboard from "./pages/Dashboard";
import Agents from "./pages/Agents";
import Playground from "./pages/Playground";
import {
  Calls,
  Conversations,
  Analytics,
  Configuration,
  PhoneCalls,
} from "./pages/Records";
const navigation = [
  ["/", "Dashboard", LayoutDashboard],
  ["/agents", "AI Agents", Bot],
  ["/playground", "Voice Playground", Mic],
  ["/phone", "Phone Calls", Phone],
  ["/history", "Call History", History],
  ["/conversations", "Conversations", MessagesSquare],
  ["/analytics", "Analytics", ChartNoAxesCombined],
  ["/settings", "Settings", Settings],
];
export default function App() {
  const [user, setUser] = useState(null),
    [loading, setLoading] = useState(true),
    [toast, setToast] = useState(""),
    [open, setOpen] = useState(false);
  const location = useLocation();
  const notify = (t) => setToast(t);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("session-expired", expired);
    if (sessionStorage.getItem("token"))
      api
        .get("/auth/me")
        .then((r) => setUser(r.data))
        .finally(() => setLoading(false))
        .catch(() => {});
    else setLoading(false);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(""), 5000);
      return () => clearTimeout(t);
    }
  }, [toast]);
  useEffect(() => setOpen(false), [location.pathname]);
  if (loading) return <div className="center">Loading your workspace…</div>;
  if (!user) return <Login onLogin={setUser} />;
  const title =
    navigation.find((n) => n[0] === location.pathname)?.[1] || "Dashboard";
  return (
    <div className="app">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <a className="brand" href="/">
          <span className="brand-icon">
            <AudioLines size={25} />
          </span>
          voice<span className="brand-os">OS</span>
          <small>WORKSPACE</small>
        </a>
        <div className="workspace">
          <span className="workspace-icon">V</span>
          <div>
            <b>My workspace</b>
            <small>Administrator workspace</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {navigation.map(([path, label, Icon]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              <Icon size={18} />
              {label}
              {label === "Voice Playground" && (
                <span className="tiny">LIVE</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-box">
            <span className="help-icon">
              <Headphones size={20} />
            </span>
            <b>Ready for your first call?</b>
            <p>Create an agent and bring your conversations to life.</p>
            <NavLink to="/playground">
              Open playground <ArrowUpRight size={14} />
            </NavLink>
          </div>
          <button
            className="user"
            onClick={() => {
              sessionStorage.removeItem("token");
              setUser(null);
            }}
          >
            <span className="avatar">{user.name[0]}</span>
            <span>
              <b>{user.name}</b>
              <small>{user.role}</small>
            </span>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <div className="main">
        <header>
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="Toggle menu"
              onClick={() => setOpen(!open)}
            >
              <Menu size={20} />
            </button>
            Workspace <span>/</span>
            <b>{title}</b>
          </div>
          <div className="header-right">
            <span className="environment">
              <i /> Local workspace
            </span>
            <span className="avatar small">{user.name[0]}</span>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Dashboard notify={notify} />} />
            <Route path="/agents" element={<Agents notify={notify} />} />
            <Route
              path="/playground"
              element={<Playground notify={notify} />}
            />
            <Route path="/phone" element={<PhoneCalls notify={notify} />} />
            <Route path="/history" element={<Calls notify={notify} />} />
            <Route
              path="/conversations"
              element={<Conversations notify={notify} />}
            />
            <Route path="/analytics" element={<Analytics notify={notify} />} />
            <Route
              path="/settings"
              element={
                <Configuration user={user} setUser={setUser} notify={notify} />
              }
            />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
        <footer>
          <span>VoiceOS · Your conversations, elevated.</span>
          <span>
            <i /> Connected to your workspace
          </span>
        </footer>
      </div>
      {toast && (
        <div role="status" className="toast">
          {toast}
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
function Login({ onLogin }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api.post("/auth/login", { email, password });
      sessionStorage.setItem("token", r.data.access_token);
      onLogin((await api.get("/auth/me")).data);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login">
      <div className="login-story">
        <span className="brand">
          <span className="brand-icon">
            <AudioLines />
          </span>
          voiceOS
        </span>
        <div>
          <span className="eyebrow">CONVERSATIONS THAT CONNECT</span>
          <h1>
            A voice for every
            <br />
            possibility.
          </h1>
          <p>
            Build thoughtful AI agents. Have natural conversations.
            <br />
            Bring a human touch to every interaction.
          </p>
          <div className="wave">
            {Array.from({ length: 36 }, (_, i) => (
              <i key={i} style={{ height: 15 + Math.sin(i * 0.8) ** 2 * 75 }} />
            ))}
          </div>
        </div>
        <small>YOUR NEXT GREAT CONVERSATION STARTS HERE.</small>
      </div>
      <form className="login-form" onSubmit={submit}>
        <span className="eyebrow">YOUR VOICE WORKSPACE</span>
        <h2>Welcome back</h2>
        <p>Sign in to manage your agents and conversations.</p>
        <label>
          Email address
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@example.com"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in to workspace"}
          <ArrowUpRight size={17} />
        </button>
        <small>
          Use the administrator credentials configured on your server.
        </small>
      </form>
    </div>
  );
}
