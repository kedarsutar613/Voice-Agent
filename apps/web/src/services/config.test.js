import { describe, it, expect } from "vitest";
import { voiceSocketUrl } from "./config";

describe("frontend API and WebSocket deployment configuration", () => {
  it("uses the current origin for a relative API path", () => {
    const url = new URL(voiceSocketUrl("ticket", "/api/v1", ""));
    expect(url.host).toBe(window.location.host);
    expect(url.pathname).toBe("/api/v1/voice/ws");
    expect(url.searchParams.get("ticket")).toBe("ticket");
  });
  it("connects to the configured HTTPS backend using WSS", () => {
    expect(
      voiceSocketUrl("ticket", "https://api.example.com/api/v1/", ""),
    ).toBe("wss://api.example.com/api/v1/voice/ws?ticket=ticket");
  });
  it("honors a separate voice endpoint and safely encodes the ticket", () => {
    const url = new URL(
      voiceSocketUrl(
        "a+b&c",
        "/api/v1",
        "wss://voice.example.com/stream?region=in",
      ),
    );
    expect(url.host).toBe("voice.example.com");
    expect(url.searchParams.get("ticket")).toBe("a+b&c");
    expect(url.searchParams.get("region")).toBe("in");
  });
  it("supports a local backend on a different port", () => {
    expect(voiceSocketUrl("ticket", "http://127.0.0.1:8000/api/v1", "")).toBe(
      "ws://127.0.0.1:8000/api/v1/voice/ws?ticket=ticket",
    );
  });
});
