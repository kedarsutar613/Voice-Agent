import React, { useEffect, useState } from "react";
import {
  Download,
  Phone,
  Search,
  Save,
  RefreshCw,
  ArrowUpRight,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { api, errorText } from "../services/api";
import {
  Heading,
  Empty,
  CallTable,
  Modal,
  Transcript,
  Badge,
} from "../components/UI";
import { date, duration } from "../utils/format";
async function download(notify) {
  try {
    const r = await api.get("/reports/calls.csv", { responseType: "blob" });
    const u = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = u;
    a.download = "calls.csv";
    a.click();
    URL.revokeObjectURL(u);
  } catch (e) {
    notify(errorText(e));
  }
}
export function Calls({ notify }) {
  const [data, setData] = useState({ items: [], total: 0 }),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [page, setPage] = useState(1),
    [detail, setDetail] = useState(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let canceled = false;
    setLoading(true);
    const t = setTimeout(
      () =>
        api
          .get("/calls", { params: { search, status, page, limit: 15 } })
          .then((r) => {
            if (!canceled) setData(r.data);
          })
          .catch((e) => notify(errorText(e)))
          .finally(() => {
            if (!canceled) setLoading(false);
          }),
      200,
    );
    return () => {
      canceled = true;
      clearTimeout(t);
    };
  }, [search, status, page]);
  return (
    <>
      <Heading
        title="Call history"
        description="Every connection, all in one place."
      >
        <button className="secondary" onClick={() => download(notify)}>
          <Download size={16} />
          Export CSV
        </button>
      </Heading>
      <section className="panel">
        <div className="filter-bar">
          <div className="search-field">
            <Search size={17} />
            <input
              aria-label="Search caller"
              placeholder="Search by caller number…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <select
            aria-label="Call status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            {[
              "",
              "completed",
              "active",
              "failed",
              "interrupted",
              "ringing",
              "busy",
              "no-answer",
            ].map((s) => (
              <option key={s} value={s}>
                {s || "All statuses"}
              </option>
            ))}
          </select>
        </div>
        {loading ? (
          <p className="padded">Loading calls…</p>
        ) : data.items.length ? (
          <CallTable
            calls={data.items}
            onSelect={async (c) => {
              try {
                setDetail((await api.get("/calls/" + c.id)).data);
              } catch (e) {
                notify(errorText(e));
              }
            }}
          />
        ) : (
          <Empty
            title="No calls found"
            text="Calls matching your filters will appear here."
          />
        )}
        <div className="pagination">
          <span>{data.total} calls</span>
          <div>
            <button
              className="secondary"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              className="secondary"
              disabled={page * 15 >= data.total}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
      {detail && (
        <Modal title={"Call #" + detail.id} onClose={() => setDetail(null)}>
          <div className="detail-summary">
            <b>{detail.agent_name}</b>
            <Badge status={detail.status} />
            <span>{duration(detail.duration)}</span>
          </div>
          <Transcript messages={detail.messages} />
          <p className="hint">
            Audio recording is disabled. Text transcripts are available to
            authorized users only.
          </p>
        </Modal>
      )}
    </>
  );
}
export function Conversations({ notify }) {
  const [list, setList] = useState(null),
    [detail, setDetail] = useState(null);
  useEffect(() => {
    api
      .get("/conversations")
      .then((r) => setList(r.data))
      .catch((e) => notify(errorText(e)));
  }, []);
  return (
    <>
      <Heading
        title="Conversations"
        description="Keep the context. Find the insight."
      />
      <section className="panel">
        {!list ? (
          <p className="padded">Loading conversations…</p>
        ) : list.length ? (
          <div className="conversation-list">
            {list.map((c) => (
              <button
                key={c.id}
                onClick={async () => {
                  try {
                    setDetail((await api.get("/conversations/" + c.id)).data);
                  } catch (e) {
                    notify(errorText(e));
                  }
                }}
              >
                <span className="bot-avatar">#{c.id}</span>
                <span>
                  <b>Conversation · Call #{c.call_id}</b>
                  <small>
                    {date(c.created_at)} · {c.language}
                  </small>
                </span>
                <span>{c.message_count} messages</span>
                <ArrowUpRight size={17} />
              </button>
            ))}
          </div>
        ) : (
          <Empty
            title="A fresh start"
            text="Your saved conversations will live here."
          />
        )}
      </section>
      {detail && (
        <Modal
          title={"Conversation #" + detail.id}
          onClose={() => setDetail(null)}
        >
          <Transcript messages={detail.messages} />
        </Modal>
      )}
    </>
  );
}
export function Analytics({ notify }) {
  const [data, setData] = useState(null),
    [stats, setStats] = useState(null),
    [period, setPeriod] = useState("daily");
  useEffect(() => {
    api
      .get("/dashboard/analytics?period=" + period)
      .then((r) => setData(r.data))
      .catch((e) => notify(errorText(e)));
    api
      .get("/dashboard/stats")
      .then((r) => setStats(r.data))
      .catch((e) => notify(errorText(e)));
  }, [period]);
  return (
    <>
      <Heading
        title="Conversation insights"
        description="Make your next conversation even better."
      >
        <select
          aria-label="Report period"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        >
          {["daily", "weekly", "monthly"].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <button className="secondary" onClick={() => download(notify)}>
          <Download size={16} />
          Export CSV
        </button>
      </Heading>
      {stats && (
        <div className="stat-grid">
          {[
            ["Completed", stats.completed],
            ["Failed", stats.failed],
            ["Success rate", stats.success_rate + "%"],
            ["Average duration", duration(stats.average_duration)],
          ].map(([l, v]) => (
            <div className="stat-card" key={l}>
              <span>{l}</span>
              <strong>{v}</strong>
            </div>
          ))}
        </div>
      )}
      <section className="panel">
        <div className="section-title">
          <h2>Call performance</h2>
        </div>
        <div className="chart">
          {data?.series.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.series}>
                <CartesianGrid strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="completed" fill="#7560df" radius={[4, 4, 0, 0]} />
                <Bar dataKey="failed" fill="#ed8992" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty
              title="Insights are on their way"
              text="Complete a conversation to begin building your analytics."
            />
          )}
        </div>
      </section>
      <section className="panel top-space">
        <div className="section-title">
          <h2>Agent performance</h2>
        </div>
        {data?.agents.length ? (
          <table>
            <thead>
              <tr>
                <th>AGENT</th>
                <th>CALLS</th>
                <th>TOTAL DURATION</th>
              </tr>
            </thead>
            <tbody>
              {data.agents.map((a) => (
                <tr key={a.name}>
                  <td>{a.name}</td>
                  <td>{a.calls}</td>
                  <td>{duration(a.duration)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty title="No agent activity yet" />
        )}
      </section>
    </>
  );
}
export function Configuration({ user, setUser, notify }) {
  const [config, setConfig] = useState(null),
    [name, setName] = useState(user.name);
  useEffect(() => {
    api
      .get("/settings")
      .then((r) => setConfig(r.data))
      .catch((e) => notify(errorText(e)));
  }, []);
  return (
    <>
      <Heading
        title="Workspace settings"
        description="The details that make your workspace yours."
      />
      <div className="settings-grid">
        <section className="panel padded">
          <h2>Your profile</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.put("/auth/me", { name });
                setUser({ ...user, name });
                notify("Profile updated");
              } catch (e) {
                notify(errorText(e));
              }
            }}
          >
            <label>
              Name
              <input
                required
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Email
              <input disabled value={user.email} />
            </label>
            <button className="primary">
              <Save size={16} />
              Save profile
            </button>
          </form>
        </section>
        <section className="panel padded">
          <h2>Provider connections</h2>
          {config && (
            <>
              <div className="config-row">
                <span>OpenAI</span>
                <Badge
                  status={config.ai_configured ? "active" : "not configured"}
                />
              </div>
              <div className="config-row">
                <span>Twilio</span>
                <Badge
                  status={
                    config.twilio_configured ? "active" : "not configured"
                  }
                />
              </div>
              <div className="config-row">
                <span>Outbound calls</span>
                <Badge
                  status={config.outbound_enabled ? "active" : "disabled"}
                />
              </div>
              <p className="hint">
                Configure provider credentials in the backend .env file and
                restart the API. Secrets are never sent to the browser.
              </p>
            </>
          )}
        </section>
        <section className="panel padded">
          <h2>Voice & language</h2>
          <p>
            English, Hindi, and Marathi are configurable for each agent.
            Available recognition and synthesis voices depend on the selected
            browser or phone provider.
          </p>
          <p className="hint">
            Browser: Web Speech or OpenAI Realtime.
            <br />
            Phone: Twilio Gather or bidirectional Media Streams.
            <br />
            OpenAI Realtime: live audio streaming (select on the agent).
          </p>
        </section>
        <section className="panel padded">
          <h2>Security & call safeguards</h2>
          {config && (
            <>
              <div className="config-row">
                <span>Daily outbound limit</span>
                <b>{config.daily_call_limit}</b>
              </div>
              <div className="config-row">
                <span>Maximum call duration</span>
                <b>{config.max_call_seconds}s</b>
              </div>
              <div className="config-row">
                <span>Audio recording</span>
                <b>Disabled</b>
              </div>
            </>
          )}
          <p className="hint">
            JWT sessions expire after 8 hours. Outbound numbers must be
            allowlisted. Transcript consent is required before conversations
            begin. Change credentials and safeguards on the server.
          </p>
        </section>
      </div>
    </>
  );
}
export function PhoneCalls({ notify }) {
  const [agents, setAgents] = useState([]),
    [config, setConfig] = useState(null),
    [id, setId] = useState(""),
    [to, setTo] = useState(""),
    [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [call, setCall] = useState(null),
    [confirm, setConfirm] = useState(false),
    [incoming, setIncoming] = useState("");
  useEffect(() => {
    api
      .get("/agents")
      .then((r) => setAgents(r.data.filter((a) => a.active)))
      .catch((e) => notify(errorText(e)));
    api
      .get("/settings")
      .then((r) => setConfig(r.data))
      .catch((e) => notify(errorText(e)));
  }, []);
  async function dial() {
    setConfirm(false);
    setBusy(true);
    try {
      setCall(
        (
          await api.post("/calls/outbound", {
            agent_id: Number(id),
            to,
            consent,
          })
        ).data,
      );
      notify("Call request accepted by Twilio");
    } catch (e) {
      notify(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Phone calls"
        description="Take the conversation beyond your browser."
      />
      <div className="settings-grid">
        <section className="panel padded">
          <h2>Start an outbound call</h2>
          <p>Connect your AI agent to an allowlisted phone number.</p>
          {config && !config.outbound_enabled && (
            <div className="notice">
              Outbound calling is disabled. Configure Twilio credentials, a
              public HTTPS URL, and an approved recipient allowlist on the
              backend.
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setConfirm(true);
            }}
          >
            <label>
              Agent
              <select
                required
                value={id}
                onChange={(e) => setId(e.target.value)}
              >
                <option value="">Select an agent</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Recipient phone number
              <input
                type="tel"
                required
                pattern="\+[1-9][0-9]{7,14}"
                placeholder="+919876543210"
                value={to}
                onChange={(e) => setTo(e.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                required
              />
              The recipient has consented to this AI call and transcript
              storage.
            </label>
            <button
              className="primary"
              disabled={!config?.outbound_enabled || busy || !consent}
            >
              <Phone size={16} />
              {busy ? "Requesting call…" : "Place call"}
            </button>
          </form>
          {call && (
            <div className="call-result">
              <b>Call #{call.id}</b>
              <Badge status={call.status} />
              <p>Provider SID: {call.provider_sid}</p>
              <div className="actions">
                <button
                  className="secondary"
                  onClick={async () => {
                    try {
                      setCall((await api.get("/calls/" + call.id)).data);
                    } catch (e) {
                      notify(errorText(e));
                    }
                  }}
                >
                  <RefreshCw size={14} />
                  Refresh status
                </button>
                <button
                  className="end-button"
                  onClick={async () => {
                    try {
                      setCall(
                        (await api.post("/calls/" + call.id + "/end")).data,
                      );
                    } catch (e) {
                      notify(errorText(e));
                    }
                  }}
                >
                  End call
                </button>
              </div>
            </div>
          )}
        </section>
        <section className="panel padded">
          <h2>Incoming call routing</h2>
          <p>Assign a Twilio-owned phone number to the selected agent.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.post("/phone-numbers", {
                  number: incoming,
                  agent_id: Number(id),
                });
                notify("Incoming number assigned");
              } catch (e) {
                notify(errorText(e));
              }
            }}
          >
            <label>
              Twilio phone number
              <input
                type="tel"
                required
                pattern="\+[1-9][0-9]{7,14}"
                value={incoming}
                onChange={(e) => setIncoming(e.target.value)}
                placeholder="+12345678900"
              />
            </label>
            <p className="hint">
              Choose an agent in the outbound form, then save this assignment.
              Set the number’s Twilio voice webhook to POST
              /api/v1/twilio/incoming and its status callback to POST
              /api/v1/twilio/incoming-status on your public API URL.
            </p>
            <button className="secondary" disabled={!id}>
              Save number assignment
            </button>
          </form>
          <div className="notice">
            Phone calls use real Twilio APIs and may incur provider charges. A
            call is only marked completed following provider confirmation.
          </div>
        </section>
      </div>
      {confirm && (
        <Modal
          title="Place a real phone call?"
          onClose={() => setConfirm(false)}
        >
          <p>
            Call {to} using {agents.find((a) => a.id === Number(id))?.name}?
            Twilio and AI provider charges may apply.
          </p>
          <div className="actions">
            <button className="secondary" onClick={() => setConfirm(false)}>
              Cancel
            </button>
            <button className="primary" onClick={dial}>
              Place call
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
