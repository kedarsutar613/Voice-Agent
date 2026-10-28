class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
  }
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (samples) {
      for (const value of samples)
        this.buffer.push(Math.max(-1, Math.min(1, value)));
      if (this.buffer.length >= 2400) {
        const pcm = new Int16Array(this.buffer.length);
        this.buffer.forEach((value, index) => {
          pcm[index] = value < 0 ? value * 32768 : value * 32767;
        });
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
        this.buffer = [];
      }
    }
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
