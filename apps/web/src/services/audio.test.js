import { describe, it, expect, vi, afterEach } from "vitest";
import { RealtimeAudio } from "./audio";
afterEach(() => vi.unstubAllGlobals());
describe("streaming audio lifecycle", () => {
  it("stops microphone tracks and queued playback when a session ends", () => {
    const audio = new RealtimeAudio();
    const stop = vi.fn(),
      trackStop = vi.fn(),
      close = vi.fn(() => Promise.resolve());
    audio.sources.add({ stop });
    audio.stream = { getTracks: () => [{ stop: trackStop }] };
    audio.context = { close };
    audio.next = 42;
    audio.close();
    expect(stop).toHaveBeenCalledOnce();
    expect(trackStop).toHaveBeenCalledOnce();
    expect(close).toHaveBeenCalledOnce();
    expect(audio.sources.size).toBe(0);
    expect(audio.next).toBe(0);
  });
  it("mutes the actual microphone track and resumes it on unmute", () => {
    const audio = new RealtimeAudio();
    const track = { enabled: true };
    audio.stream = { getAudioTracks: () => [track] };
    audio.setMuted(true);
    expect(track.enabled).toBe(false);
    audio.setMuted(false);
    expect(track.enabled).toBe(true);
  });
  it("does not transmit audio while muted or while the socket is congested", () => {
    const audio = new RealtimeAudio();
    audio.worklet = { port: {} };
    const send = vi.fn();
    const socket = { readyState: 1, bufferedAmount: 0, send };
    audio.connect(socket);
    audio.muted = true;
    audio.worklet.port.onmessage({ data: new Int16Array([100, -100]).buffer });
    expect(send).not.toHaveBeenCalled();
    audio.muted = false;
    socket.bufferedAmount = 150000;
    audio.worklet.port.onmessage({ data: new Int16Array([100, -100]).buffer });
    expect(send).not.toHaveBeenCalled();
    socket.bufferedAmount = 0;
    audio.worklet.port.onmessage({ data: new Int16Array([100, -100]).buffer });
    const packet = JSON.parse(send.mock.calls[0][0]);
    expect(packet.type).toBe("audio");
    expect(atob(packet.audio).length).toBe(4);
  });
});
