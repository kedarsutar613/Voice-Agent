import React, { useState, useEffect } from "react";
import { Plus, Bot, Pencil, Trash2, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "../services/api";
import { Heading, Empty, Modal, Badge } from "../components/UI";
const blank = {
  name: "",
  description: "",
  system_prompt: "You are a helpful voice assistant. Keep replies brief.",
  model: "gpt-4o-mini",
  voice_provider: "browser",
  voice: "",
  language: "en-IN",
  welcome_message: "Hello! How can I help you today?",
  temperature: 0.7,
  max_duration: 300,
  active: true,
};
export default function Agents({ notify }) {
  const [agents, setAgents] = useState([]),
    [form, setForm] = useState(null),
    [busy, setBusy] = useState(false),
    [remove, setRemove] = useState(null),
    [loading, setLoading] = useState(true);
  const load = () =>
    api
      .get("/agents")
      .then((r) => setAgents(r.data))
      .catch((e) => notify(errorText(e)))
      .finally(() => setLoading(false));
  useEffect(() => {
    load();
  }, []);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await (form.id
        ? api.put("/agents/" + form.id, form)
        : api.post("/agents", form));
      setForm(null);
      notify("Agent saved");
      load();
    } catch (e) {
      notify(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  const field = (key, label, type = "text") => (
    <label>
      {label}
      <input
        required={["name", "model"].includes(key)}
        type={type}
        value={form[key]}
        onChange={(e) =>
          setForm({
            ...form,
            [key]: type === "number" ? Number(e.target.value) : e.target.value,
          })
        }
        {...(key === "temperature"
          ? { min: 0, max: 2, step: 0.1 }
          : key === "max_duration"
            ? { min: 30, max: 3600 }
            : {})}
      />
    </label>
  );
  return (
    <>
      <Heading
        title="Your AI agents"
        description="Give every conversation a voice and a purpose."
      >
        <button className="primary" onClick={() => setForm({ ...blank })}>
          <Plus size={17} />
          Create agent
        </button>
      </Heading>
      {loading ? (
        <p>Loading agents…</p>
      ) : agents.length ? (
        <div className="agent-grid">
          {agents.map((a) => (
            <article className="panel agent-card" key={a.id}>
              <div className="section-title">
                <span className="large-bot">
                  <Bot size={28} />
                </span>
                <Badge status={a.active ? "active" : "inactive"} />
              </div>
              <h2>{a.name}</h2>
              <p>{a.description || "Your AI voice assistant"}</p>
              <div className="tags">
                <span>{a.language}</span>
                <span>{a.model}</span>
              </div>
              <div className="agent-actions">
                <button className="secondary" onClick={() => setForm({ ...a })}>
                  <Pencil size={14} />
                  Configure
                </button>
                <Link to={"/playground?agent=" + a.id} className="text-link">
                  Try agent <ArrowUpRight size={14} />
                </Link>
                <button
                  className="icon-button danger"
                  aria-label={"Delete " + a.name}
                  onClick={() => setRemove(a)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <section className="panel">
          <Empty
            title="Your next teammate is a conversation away"
            text="Create an AI agent to start exploring your voice workspace."
          >
            <button className="primary" onClick={() => setForm({ ...blank })}>
              <Plus size={16} />
              Create your first agent
            </button>
          </Empty>
        </section>
      )}
      {form && (
        <Modal
          title={form.id ? "Configure agent" : "Create an AI agent"}
          onClose={() => setForm(null)}
        >
          <form onSubmit={save} className="form-grid">
            {field("name", "Agent name")}
            {field("model", "OpenAI model")}
            <label className="full">
              Description
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>
            <label className="full">
              System prompt
              <textarea
                rows={4}
                required
                value={form.system_prompt}
                onChange={(e) =>
                  setForm({ ...form, system_prompt: e.target.value })
                }
              />
            </label>
            <label>
              Language
              <select
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                <option value="en-IN">English (India)</option>
                <option value="hi-IN">Hindi</option>
                <option value="mr-IN">Marathi</option>
              </select>
            </label>
            <label>
              Voice provider
              <select
                value={form.voice_provider}
                onChange={(e) =>
                  setForm({
                    ...form,
                    voice_provider: e.target.value,
                    model:
                      e.target.value === "openai_realtime"
                        ? "gpt-realtime"
                        : "gpt-4o-mini",
                    voice: "",
                  })
                }
              >
                <option value="browser">Browser speech synthesis</option>
                <option value="openai_realtime">
                  OpenAI Realtime (streaming audio)
                </option>
              </select>
            </label>
            {field("voice", "Voice name (browser or OpenAI Realtime)")}
            {field("temperature", "Temperature", "number")}
            {field("max_duration", "Maximum duration (seconds)", "number")}
            {field("welcome_message", "Welcome message")}
            <label className="check full">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm({ ...form, active: e.target.checked })}
              />
              Agent is active
            </label>
            <p className="hint full">
              Realtime agents need a compatible realtime model and voice
              (default: alloy). Temperature applies to browser speech agents
              only. Browser voices depend on your operating system. Phone agents
              use either Twilio speech or OpenAI Realtime according to this
              selection.
            </p>
            <div className="actions full">
              <button
                type="button"
                className="secondary"
                onClick={() => setForm(null)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy}>
                {busy ? "Saving…" : "Save agent"}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {remove && (
        <Modal title="Delete agent?" onClose={() => setRemove(null)}>
          <p>
            Delete {remove.name}? Agents with call history must be deactivated
            instead.
          </p>
          <div className="actions">
            <button className="secondary" onClick={() => setRemove(null)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={async () => {
                try {
                  await api.delete("/agents/" + remove.id);
                  setRemove(null);
                  load();
                  notify("Agent deleted");
                } catch (e) {
                  notify(errorText(e));
                  setRemove(null);
                }
              }}
            >
              Delete agent
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
