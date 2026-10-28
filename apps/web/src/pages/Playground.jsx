import React, { useEffect, useRef, useState } from "react";
import { Mic, MicOff, PhoneOff, AudioLines, Send, Square } from "lucide-react";
import { RealtimeAudio } from "../services/audio";
import { api, errorText } from "../services/api";
import { Heading, Transcript } from "../components/UI";
export default function Playground({ notify }) {
  const [agents, setAgents] = useState([]),
    [id, setId] = useState(
      new URLSearchParams(location.search).get("agent") || "",
    ),
    [state, setState] = useState("disconnected"),
    [messages, setMessages] = useState([]),
    [text, setText] = useState(""),
    [consent, setConsent] = useState(false),
    [muted, setMuted] = useState(false),
    [listening, setListening] = useState(false),
    [pending, setPending] = useState(false),
    [voices, setVoices] = useState([]);
  const socket = useRef(null),
    recognition = useRef(null),
    audio = useRef(null),
    pendingRef = useRef(false),
    agentRef = useRef(null);
  const agent = agents.find((a) => a.id === Number(id));
  const realtime = agent?.voice_provider === "openai_realtime";
  const supported = Boolean(
    window.SpeechRecognition || window.webkitSpeechRecognition,
  );
  useEffect(() => {
    api
      .get("/agents")
      .then((r) => {
        setAgents(r.data.filter((a) => a.active));
        if (!id) setId(String(r.data.find((a) => a.active)?.id || ""));
      })
      .catch((e) => notify(errorText(e)));
    const update = () => setVoices(window.speechSynthesis?.getVoices() || []);
    update();
    window.speechSynthesis?.addEventListener("voiceschanged", update);
    return () => {
      socket.current?.close();
      recognition.current?.abort();
      audio.current?.close();
      window.speechSynthesis?.cancel();
      window.speechSynthesis?.removeEventListener("voiceschanged", update);
    };
  }, []);
  function speak(value) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(value);
    u.lang = agentRef.current.language;
    const voice =
      voices.find((v) => v.name === agentRef.current.voice) ||
      voices.find((v) => v.lang === u.lang);
    if (voice) u.voice = voice;
    window.speechSynthesis.speak(u);
  }
  function send(value) {
    if (
      !value.trim() ||
      pendingRef.current ||
      socket.current?.readyState !== WebSocket.OPEN
    )
      return;
    window.speechSynthesis?.cancel();
    audio.current?.interrupt();
    socket.current.send(JSON.stringify({ type: "text", text: value }));
    setMessages((m) => [...m, { role: "user", content: value }]);
    setText("");
    setPending(true);
    pendingRef.current = true;
  }
  async function start() {
    if (!agent || !consent) return;
    setState("connecting");
    agentRef.current = agent;
    try {
      setMuted(false);
      if (realtime) {
        audio.current = new RealtimeAudio();
        await audio.current.prepare();
      }
      const r = await api.post("/voice/ticket");
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v1/voice/ws?ticket=${r.data.ticket}`,
      );
      socket.current = ws;
      ws.onopen = () =>
        ws.send(JSON.stringify({ agent_id: agent.id, consent }));
      ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.type === "error") {
          notify(d.message);
          return;
        }
        if (d.type === "ready") {
          setState("connected");
          if (d.realtime) {
            setMessages([]);
            audio.current.connect(ws);
            setListening(true);
          } else {
            setMessages([{ role: "assistant", content: d.text }]);
            speak(d.text);
          }
        }
        if (d.type === "response") {
          setMessages((m) => [...m, { role: "assistant", content: d.text }]);
          setPending(false);
          pendingRef.current = false;
          if (!d.realtime) speak(d.text);
        }
        if (d.type === "audio") audio.current?.play(d.audio);
        if (d.type === "interrupted") audio.current?.interrupt();
        if (d.type === "input_transcript")
          setMessages((m) => [...m, { role: "user", content: d.text }]);
      };
      ws.onclose = () => {
        setState("disconnected");
        setPending(false);
        pendingRef.current = false;
        recognition.current?.abort();
        audio.current?.close();
        setListening(false);
        window.speechSynthesis?.cancel();
      };
      ws.onerror = () =>
        notify("Voice connection failed. Check the backend connection.");
    } catch (e) {
      audio.current?.close();
      setState("disconnected");
      notify(errorText(e));
    }
  }
  function stop() {
    audio.current?.close();
    recognition.current?.abort();
    window.speechSynthesis?.cancel();
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify({ type: "stop" }));
    setState("stopping");
  }
  function listen() {
    if (!supported || muted || state !== "connected") return;
    if (listening) {
      recognition.current?.stop();
      return;
    }
    window.speechSynthesis?.cancel();
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    const r = new R();
    recognition.current = r;
    r.lang = agent.language;
    r.interimResults = false;
    r.onstart = () => setListening(true);
    r.onend = () => setListening(false);
    r.onresult = (e) => send(e.results[0][0].transcript);
    r.onerror = (e) => {
      setListening(false);
      notify("Speech recognition: " + e.error);
    };
    r.start();
  }
  return (
    <>
      <Heading
        title="Voice playground"
        description="One conversation. Endless possibilities. Get to know your agent."
      />
      <div className="playground-grid">
        <section className="panel voice-stage">
          <div className="section-title">
            <h2>Live conversation</h2>
            <span
              className={
                "badge " + (state === "connected" ? "green" : "neutral")
              }
            >
              <i />
              {state}
            </span>
          </div>
          <label>
            Choose an agent
            <select
              value={id}
              disabled={state !== "disconnected"}
              onChange={(e) => setId(e.target.value)}
            >
              <option value="">Select an active agent</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} · {a.language}
                </option>
              ))}
            </select>
          </label>
          <div className={"voice-orb " + (listening ? "listening" : "")}>
            <AudioLines size={70} />
          </div>
          <h2>{agent?.name || "Your voice starts here"}</h2>
          <p>
            {pending
              ? "Thinking…"
              : listening
                ? "Listening to you…"
                : state === "connected"
                  ? "Ready when you are."
                  : "Choose an agent and start a conversation."}
          </p>
          <div className="wave small-wave">
            {Array.from({ length: 25 }, (_, i) => (
              <i key={i} style={{ height: 8 + Math.sin(i * 0.8) ** 2 * 25 }} />
            ))}
          </div>
          <label className="check consent">
            <input
              type="checkbox"
              checked={consent}
              disabled={state !== "disconnected"}
              onChange={(e) => setConsent(e.target.checked)}
            />
            I agree to AI processing and storage of this conversation’s text
            transcript.
          </label>
          <div className="voice-controls">
            {state === "disconnected" ? (
              <button
                className="primary"
                disabled={!agent || !consent}
                onClick={start}
              >
                <Mic size={17} />
                Start conversation
              </button>
            ) : (
              <>
                <button
                  className="secondary"
                  disabled={
                    realtime ||
                    state !== "connected" ||
                    !supported ||
                    muted ||
                    pending
                  }
                  onClick={listen}
                >
                  {listening ? <Square size={17} /> : <Mic size={17} />}{" "}
                  {realtime
                    ? "Live microphone"
                    : listening
                      ? "Finish speaking"
                      : "Speak"}
                </button>
                <button
                  className="secondary"
                  aria-label={muted ? "Unmute microphone" : "Mute microphone"}
                  onClick={() => {
                    setMuted(!muted);
                    audio.current?.setMuted(!muted);
                    recognition.current?.abort();
                  }}
                >
                  {muted ? <MicOff size={17} /> : <Mic size={17} />}
                </button>
                <button className="end-button" onClick={stop}>
                  <PhoneOff size={17} />
                  End
                </button>
              </>
            )}
          </div>
          <p className="hint">
            {realtime
              ? "Live audio is sent to OpenAI while connected. Speak naturally to interrupt the agent. "
              : supported
                ? "Click Speak for each turn. Speech recognition may use your browser’s cloud service."
                : "Speech recognition is unavailable in this browser. Use the text input to converse."}{" "}
            Available voices vary by device. Stop playback to interrupt the
            agent.
          </p>
          <button
            className="text-link"
            onClick={() => {
              window.speechSynthesis?.cancel();
              audio.current?.interrupt();
              if (realtime && socket.current?.readyState === WebSocket.OPEN)
                socket.current.send(JSON.stringify({ type: "interrupt" }));
            }}
          >
            Stop voice playback
          </button>
        </section>
        <section className="panel transcript-panel">
          <div className="section-title">
            <div>
              <h2>Live transcript</h2>
              <p>A record of your conversation</p>
            </div>
            <span className="count">{messages.length} messages</span>
          </div>
          <Transcript messages={messages} />
          {pending && <p className="hint">Agent is preparing a response…</p>}
          <form
            className="message-input"
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
          >
            <input
              aria-label="Message"
              value={text}
              maxLength={4000}
              onChange={(e) => setText(e.target.value)}
              placeholder="Or type your message…"
              disabled={state !== "connected" || pending}
            />
            <button
              className="primary"
              aria-label="Send message"
              disabled={!text.trim() || state !== "connected" || pending}
            >
              <Send size={17} />
            </button>
          </form>
        </section>
      </div>
    </>
  );
}
