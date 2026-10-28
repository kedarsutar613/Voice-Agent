import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  Radio,
  ArrowUpRight,
  Plus,
  AudioLines,
  ChevronRight,
  Check,
  Clock,
  ShieldCheck,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api, errorText } from "../services/api";
import { Heading, Empty, CallTable } from "../components/UI";
import { duration } from "../utils/format";
export default function Dashboard({ notify }) {
  const [data, setData] = useState(null),
    [period, setPeriod] = useState("daily"),
    [chart, setChart] = useState([]);
  useEffect(() => {
    Promise.all([
      api.get("/dashboard/stats"),
      api.get("/calls?limit=5"),
      api.get("/agents"),
    ])
      .then(([s, c, a]) =>
        setData({ stats: s.data, calls: c.data.items, agents: a.data }),
      )
      .catch((e) => notify(errorText(e)));
  }, []);
  useEffect(() => {
    api
      .get("/dashboard/analytics?period=" + period)
      .then((r) => setChart(r.data.series))
      .catch((e) => notify(errorText(e)));
  }, [period]);
  if (!data) return <p>Loading dashboard…</p>;
  const { stats: s, calls, agents } = data;
  return (
    <>
      <Heading
        title="Your voice workspace, at a glance"
        description="A little insight into every conversation. A lot of possibility ahead."
      >
        <Link className="button secondary" to="/playground">
          <AudioLines size={16} />
          Try playground
        </Link>
        <Link className="button primary" to="/agents">
          <Plus size={17} />
          Create agent
        </Link>
      </Heading>
      <div className="welcome-banner">
        <div>
          <span className="banner-label">
            <i /> BUILT FOR BETTER CONVERSATIONS
          </span>
          <h2>Great conversations start with a great agent.</h2>
          <p>
            Design your assistant, find its voice, and make every interaction
            count.
          </p>
          <Link to="/agents">
            Meet your AI agents <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="banner-art">
          <div className="orbit one" />
          <div className="orbit two" />
          <div className="art-core">
            <AudioLines size={45} />
          </div>
          <span className="art-bubble">
            <MicIcon /> Natural conversations
          </span>
        </div>
      </div>
      <div className="stat-grid">
        {[
          [Phone, "Total calls", s.total, "All conversations", "purple"],
          [
            PhoneIncoming,
            "Incoming calls",
            s.incoming,
            "Inbound connections",
            "blue",
          ],
          [
            PhoneOutgoing,
            "Outgoing calls",
            s.outgoing,
            "Outbound connections",
            "orange",
          ],
          [Radio, "Active calls", s.active, "Happening right now", "green"],
        ].map(([I, l, v, d, color]) => (
          <div className="stat-card" key={l}>
            <div className="stat-top">
              <span>{l}</span>
              <span className={"stat-icon " + color}>
                <I size={18} />
              </span>
            </div>
            <strong>{v.toLocaleString()}</strong>
            <small>
              {l === "Active calls" && <i className="live-dot" />}
              {d}
            </small>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="section-title">
            <div>
              <h2>Conversation activity</h2>
              <p>A closer look at your call volume</p>
            </div>
            <select
              aria-label="Analytics period"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div className="chart-legend">
            <i /> Total calls{" "}
            <span>
              <i /> Completed
            </span>
          </div>
          <div className="chart">
            {chart.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chart}>
                  <defs>
                    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor="#7360ed"
                        stopOpacity={0.25}
                      />
                      <stop offset="100%" stopColor="#7360ed" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 5"
                    vertical={false}
                    stroke="#eceef5"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="calls"
                    stroke="#7462e7"
                    strokeWidth={3}
                    fill="url(#fill)"
                  />
                  <Area
                    type="monotone"
                    dataKey="completed"
                    stroke="#83c9bc"
                    fill="transparent"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <Empty
                title="Your story starts with a conversation"
                text="Call activity will appear after your first session."
              />
            )}
          </div>
          <div className="chart-foot">
            <span>
              <Clock size={14} /> Average duration{" "}
              <b>{duration(s.average_duration)}</b>
            </span>
            <span>
              <Check size={14} /> Success rate <b>{s.success_rate}%</b>
            </span>
          </div>
        </section>
        <section className="panel agent-overview">
          <div className="section-title">
            <div>
              <h2>Your AI team</h2>
              <p>Voices behind the conversations</p>
            </div>
            <span className="count">{agents.length}</span>
          </div>
          {agents.length ? (
            agents.slice(0, 3).map((a) => (
              <Link className="mini-agent" key={a.id} to="/agents">
                <span className="bot-avatar">
                  <AudioLines size={20} />
                </span>
                <div>
                  <b>{a.name}</b>
                  <small>
                    {a.language} · {a.model}
                  </small>
                </div>
                <i className={a.active ? "live-dot" : "gray-dot"} />
              </Link>
            ))
          ) : (
            <Empty
              title="Meet your first agent"
              text="Give your assistant a name, a voice, and a purpose."
            />
          )}
          <Link to="/agents" className="add-agent">
            <Plus size={16} /> Create an AI agent
          </Link>
          <div className="team-foot">
            <ShieldCheck size={17} />
            <span>
              Designed by you.
              <br />
              <b>Powered by possibility.</b>
            </span>
          </div>
        </section>
      </div>
      <section className="panel recent">
        <div className="section-title">
          <div>
            <h2>Recent calls</h2>
            <p>Every conversation has a story</p>
          </div>
          <Link to="/history" className="text-link">
            View all calls <ChevronRight size={16} />
          </Link>
        </div>
        {calls.length ? (
          <CallTable calls={calls} />
        ) : (
          <Empty
            title="No calls yet"
            text="Start a conversation in the playground to see your first call here."
          >
            <Link to="/playground" className="text-link">
              Start a conversation <ArrowUpRight size={15} />
            </Link>
          </Empty>
        )}
      </section>
    </>
  );
}
function MicIcon() {
  return <AudioLines size={15} />;
}
