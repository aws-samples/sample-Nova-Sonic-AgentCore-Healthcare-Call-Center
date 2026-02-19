/**
 * Audio Playback module for streaming audio output.
 *
 * Uses AudioWorklet for smooth, low-latency playback of
 * streamed audio from BidiAgent responses.
 */

// AudioWorklet processor code for intelligent buffering
const audioPlaybackProcessorCode = `
class ExpandableBuffer {
  constructor() {
    this.buffer = new Float32Array(16000); // 1 second at 16kHz (BidiAgent output rate)
    this.readIndex = 0;
    this.writeIndex = 0;
    this.underflowedSamples = 0;
    this.isInitialBuffering = true;
    this.initialBufferLength = 400; // 25ms initial buffer at 16kHz - reduced for lower latency
  }

  write(samples) {
    if (this.writeIndex + samples.length <= this.buffer.length) {
      // Enough space to append
    } else if (samples.length <= this.readIndex) {
      // Shift samples to beginning
      const subarray = this.buffer.subarray(this.readIndex, this.writeIndex);
      this.buffer.set(subarray);
      this.writeIndex -= this.readIndex;
      this.readIndex = 0;
    } else {
      // Expand buffer
      const newLength = (samples.length + this.writeIndex - this.readIndex) * 2;
      const newBuffer = new Float32Array(newLength);
      newBuffer.set(this.buffer.subarray(this.readIndex, this.writeIndex));
      this.buffer = newBuffer;
      this.writeIndex -= this.readIndex;
      this.readIndex = 0;
    }

    this.buffer.set(samples, this.writeIndex);
    this.writeIndex += samples.length;

    if (this.writeIndex - this.readIndex >= this.initialBufferLength) {
      this.isInitialBuffering = false;
    }
  }

  read(destination) {
    let copyLength = 0;

    if (!this.isInitialBuffering) {
      copyLength = Math.min(destination.length, this.writeIndex - this.readIndex);
    }

    destination.set(this.buffer.subarray(this.readIndex, this.readIndex + copyLength));
    this.readIndex += copyLength;

    if (copyLength > 0 && this.underflowedSamples > 0) {
      this.underflowedSamples = 0;
    }

    if (copyLength < destination.length) {
      destination.fill(0, copyLength);
      this.underflowedSamples += destination.length - copyLength;
    }

    if (copyLength === 0) {
      this.isInitialBuffering = true;
    }
  }

  clear() {
    this.readIndex = 0;
    this.writeIndex = 0;
    this.isInitialBuffering = true;
  }

  get bufferedSamples() {
    return this.writeIndex - this.readIndex;
  }
}

class AudioPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.playbackBuffer = new ExpandableBuffer();

    this.port.onmessage = (event) => {
      switch (event.data.type) {
        case 'audio':
          this.playbackBuffer.write(event.data.audioData);
          break;
        case 'clear':
          this.playbackBuffer.clear();
          break;
        case 'initial-buffer-length':
          this.playbackBuffer.initialBufferLength = event.data.bufferLength;
          break;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0][0];
    this.playbackBuffer.read(output);
    return true;
  }
}

registerProcessor('audio-playback-processor', AudioPlaybackProcessor);
`;

export class AudioPlayback {
  private audioContext: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private analyser: AnalyserNode | null = null;
  private isInitialized: boolean = false;
  private isPlaying: boolean = false;

  // Audio configuration - matches BidiAgent output_sample_rate
  private readonly sampleRate = 16000;

  /**
   * Initialize and start the audio playback system.
   */
  async start(): Promise<void> {
    if (this.isInitialized) {
      console.warn('[AudioPlayback] Already initialized');
      return;
    }

    try {
      // Create audio context at output sample rate
      this.audioContext = new AudioContext({ sampleRate: this.sampleRate });

      // Create analyser for visualization
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;

      // Create worklet from inline code
      const blob = new Blob([audioPlaybackProcessorCode], { type: 'application/javascript' });
      const workletUrl = URL.createObjectURL(blob);

      try {
        await this.audioContext.audioWorklet.addModule(workletUrl);

        this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-playback-processor');
        this.workletNode.connect(this.analyser);
        this.analyser.connect(this.audioContext.destination);

        this.isInitialized = true;
        this.isPlaying = true;

        console.log('[AudioPlayback] Started at', this.sampleRate, 'Hz');

      } finally {
        URL.revokeObjectURL(workletUrl);
      }

    } catch (error) {
      console.error('[AudioPlayback] Error starting playback:', error);
      this.cleanup();
      throw error;
    }
  }

  // Track total samples received for debugging
  private totalSamplesEnqueued: number = 0;

  /**
   * Enqueue audio samples for playback.
   *
   * @param samples - Float32Array of audio samples
   */
  enqueue(samples: Float32Array): void {
    if (!this.isInitialized || !this.workletNode) {
      console.warn('[AudioPlayback] Not initialized, dropping', samples.length, 'samples');
      return;
    }

    this.totalSamplesEnqueued += samples.length;

    // Log every ~0.5 seconds of audio (8000 samples at 16kHz)
    if (this.totalSamplesEnqueued % 8000 < samples.length) {
      console.log('[AudioPlayback] Enqueued audio, total samples:', this.totalSamplesEnqueued,
        '(~', (this.totalSamplesEnqueued / this.sampleRate).toFixed(1), 's)');
    }

    this.workletNode.port.postMessage({
      type: 'audio',
      audioData: samples,
    });
  }

  /**
   * Alias for enqueue - matches legacy API.
   */
  playAudio(samples: Float32Array): void {
    this.enqueue(samples);
  }

  /**
   * Clear the playback buffer (for barge-in).
   */
  clear(): void {
    if (this.workletNode) {
      this.workletNode.port.postMessage({ type: 'clear' });
    }
  }

  /**
   * Alias for clear - matches legacy API.
   */
  bargeIn(): void {
    this.clear();
  }

  /**
   * Stop playback and release resources.
   */
  stop(): void {
    if (!this.isInitialized) {
      return;
    }

    console.log('[AudioPlayback] Stopping');
    this.cleanup();
  }

  /**
   * Check if audio is currently playing.
   */
  get playing(): boolean {
    return this.isPlaying;
  }

  /**
   * Get current audio volume level (0-1).
   */
  getVolume(): number {
    if (!this.isInitialized || !this.analyser) {
      return 0;
    }

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    this.analyser.getByteTimeDomainData(dataArray);

    // Calculate RMS
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      const normalized = dataArray[i] / 128 - 1;
      sum += normalized * normalized;
    }

    return Math.sqrt(sum / bufferLength);
  }

  /**
   * Get raw audio samples for visualization.
   */
  getSamples(): number[] | null {
    if (!this.isInitialized || !this.analyser) {
      return null;
    }

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    this.analyser.getByteTimeDomainData(dataArray);

    return Array.from(dataArray).map((e) => e / 128 - 1);
  }

  /**
   * Clean up all audio resources.
   */
  private cleanup(): void {
    this.isInitialized = false;
    this.isPlaying = false;

    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode = null;
    }

    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}
