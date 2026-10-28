import React from "react";
import { AudioLines, X } from "lucide-react";
import { duration, date } from "../utils/format";
export function Heading({ title, description, children }) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">YOUR VOICE, AMPLIFIED</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="actions">{children}</div>
    </div>
  );
}
export function Empty({
  title = "Nothing here yet",
  text = "Your workspace activity will appear here.",
  children,
}) {
  return (
    <div className="empty">
      <span>
        <AudioLines size={27} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}
export function Badge({ status }) {
  return (
    <span
      className={
        "badge " +
        (status === "completed" || status === "active"
          ? "green"
          : status === "failed"
            ? "red"
            : "neutral")
      }
    >
      <i />
      {status}
    </span>
  );
}
export function CallTable({ calls, onSelect }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {[
              "CONTACT",
              "AGENT",
              "DIRECTION",
              "DURATION",
              "STATUS",
              "DATE & TIME",
            ].map((x) => (
              <th key={x}>{x}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {calls.map((c) => (
            <tr
              key={c.id}
              onClick={() => onSelect?.(c)}
              tabIndex={onSelect ? 0 : undefined}
              onKeyDown={(e) => e.key === "Enter" && onSelect?.(c)}
            >
              <td>
                <b>{c.caller_number}</b>
                <small>Call #{c.id}</small>
              </td>
              <td>
                <span className="agent-dot" />
                {c.agent_name}
              </td>
              <td className="capitalize">
                {c.direction === "incoming"
                  ? "↙ "
                  : c.direction === "outgoing"
                    ? "↗ "
                    : "◉ "}
                {c.direction}
              </td>
              <td>{duration(c.duration)}</td>
              <td>
                <Badge status={c.status} />
              </td>
              <td className="muted">{date(c.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Modal({ title, children, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-title">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function Transcript({ messages }) {
  return (
    <div className="transcript">
      {messages.length ? (
        messages.map((m, i) => (
          <div key={i} className={"message " + m.role}>
            <span>{m.role === "assistant" ? "AI ASSISTANT" : "YOU"}</span>
            <p>{m.content}</p>
          </div>
        ))
      ) : (
        <Empty
          title="No transcript"
          text="Messages will appear when a conversation begins."
        />
      )}
    </div>
  );
}
