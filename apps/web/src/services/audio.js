export class RealtimeAudio {
  constructor() {
    this.sources = new Set();
    this.next = 0;
    this.muted = false;
  }
  async prepare() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
      });
      this.context = new AudioContext({ sampleRate: 24000 });
      if (this.context.sampleRate !== 24000)
        throw new Error(
          "This browser cannot capture 24kHz audio. Use a browser speech agent instead.",
        );
      await this.context.resume();
      await this.context.audioWorklet.addModule("/pcm-capture.js");
      this.input = this.context.createMediaStreamSource(this.stream);
      this.worklet = new AudioWorkletNode(this.context, "pcm-capture");
      this.input.connect(this.worklet);
      this.silence = this.context.createGain();
      this.silence.gain.value = 0;
      this.worklet.connect(this.silence);
      this.silence.connect(this.context.destination);
    } catch (error) {
      this.close();
      throw error;
    }
  }
  connect(socket) {
    this.worklet.port.onmessage = ({ data }) => {
      if (
        this.muted ||
        socket.readyState !== WebSocket.OPEN ||
        socket.bufferedAmount > 128000
      )
        return;
      let binary = "";
      for (const byte of new Uint8Array(data))
        binary += String.fromCharCode(byte);
      socket.send(JSON.stringify({ type: "audio", audio: btoa(binary) }));
    };
  }
  play(base64) {
    const raw = atob(base64);
    const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    const samples = new Int16Array(bytes.buffer);
    const buffer = this.context.createBuffer(1, samples.length, 24000);
    const channel = buffer.getChannelData(0);
    samples.forEach((v, i) => {
      channel[i] = v / 32768;
    });
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    this.next = Math.max(this.next, this.context.currentTime);
    source.start(this.next);
    this.next += buffer.duration;
    this.sources.add(source);
    source.onended = () => this.sources.delete(source);
  }
  interrupt() {
    for (const source of this.sources) {
      try {
        source.stop();
      } catch {}
    }
    this.sources.clear();
    this.next = 0;
  }
  setMuted(value) {
    this.muted = value;
    this.stream?.getAudioTracks().forEach((t) => {
      t.enabled = !value;
    });
  }
  close() {
    this.interrupt();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.worklet?.disconnect();
    this.input?.disconnect();
    this.context?.close().catch(() => {});
  }
}
