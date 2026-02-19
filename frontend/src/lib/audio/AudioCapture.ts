/**
 * Audio Capture module for microphone input.
 *
 * Captures audio from the microphone and outputs PCM data
 * in base64 format suitable for BidiAgent streaming.
 */

export type AudioChunkCallback = (base64Data: string) => void;

export class AudioCapture {
  private audioContext: AudioContext | null = null;
  private audioStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private onAudioChunk: AudioChunkCallback | null = null;
  private isCapturing: boolean = false;

  // Audio configuration
  private readonly sampleRate = 16000;
  private readonly channels = 1;
  private readonly baseBufferSize = 512; // target chunk size at 16 kHz (~32ms)

  /**
   * Start capturing audio from the microphone.
   *
   * @param onAudioChunk - Callback invoked with base64-encoded PCM audio chunks
   */
  async start(onAudioChunk: AudioChunkCallback): Promise<void> {
    if (this.isCapturing) {
      console.warn('[AudioCapture] Already capturing');
      return;
    }

    this.onAudioChunk = onAudioChunk;

    try {
      // Request microphone access — no sampleRate constraint so the browser
      // delivers the native hardware rate (Firefox rejects mismatched rates)
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: this.channels,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Create audio context at the system default sample rate so it matches
      // the mic stream — we downsample to this.sampleRate in the callback
      this.audioContext = new AudioContext({
        latencyHint: 'interactive',
      });

      // Set up audio processing pipeline
      const source = this.audioContext.createMediaStreamSource(this.audioStream);

      // Scale buffer size so each chunk covers roughly the same duration as
      // baseBufferSize at the target rate (~32ms). ScriptProcessorNode requires
      // a power-of-2 size — round DOWN to keep latency at or below the original.
      // At 48 kHz: ideal 1536 → floor pow2 = 1024 (~21ms, lower latency)
      // At 16 kHz: ideal 512  → stays 512 (~32ms, unchanged)
      const nativeRate = this.audioContext.sampleRate;
      const idealSize = Math.round(nativeRate * (this.baseBufferSize / this.sampleRate));
      const processorBufferSize = Math.pow(2, Math.floor(Math.log2(idealSize)));

      // Note: ScriptProcessorNode is deprecated but still widely supported
      // AudioWorklet is the modern alternative but requires more setup
      this.processor = this.audioContext.createScriptProcessor(
        processorBufferSize,
        this.channels,
        this.channels
      );

      source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);

      // Process audio data — downsample from native rate to target rate
      this.processor.onaudioprocess = (event) => {
        if (!this.isCapturing || !this.onAudioChunk) return;

        const inputData = event.inputBuffer.getChannelData(0);
        const resampled = this.downsample(inputData, this.audioContext!.sampleRate);
        const base64Audio = this.convertToBase64PCM(resampled);
        this.onAudioChunk(base64Audio);
      };

      this.isCapturing = true;
      console.log(
        `[AudioCapture] Started capturing — native ${nativeRate} Hz → target ${this.sampleRate} Hz, bufferSize=${processorBufferSize}`
      );

    } catch (error) {
      console.error('[AudioCapture] Error starting capture:', error);
      this.cleanup();
      throw error;
    }
  }

  /**
   * Stop capturing audio and release resources.
   */
  stop(): void {
    if (!this.isCapturing) {
      return;
    }

    console.log('[AudioCapture] Stopping capture');
    this.cleanup();
  }

  /**
   * Check if audio is being captured.
   */
  get capturing(): boolean {
    return this.isCapturing;
  }

  /**
   * Downsample audio from the native AudioContext rate to the target rate
   * using nearest-neighbour interpolation. Returns the buffer unchanged if
   * rates already match.
   */
  private downsample(buffer: Float32Array, inputSampleRate: number): Float32Array {
    if (inputSampleRate === this.sampleRate) return buffer;
    const ratio = inputSampleRate / this.sampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      result[i] = buffer[Math.round(i * ratio)];
    }
    return result;
  }

  /**
   * Convert Float32Array audio data to base64-encoded 16-bit PCM.
   */
  private convertToBase64PCM(floatData: Float32Array): string {
    // Create buffer for 16-bit PCM data
    const buffer = new ArrayBuffer(floatData.length * 2);
    const pcmData = new DataView(buffer);

    // Convert float samples to 16-bit integers
    for (let i = 0; i < floatData.length; i++) {
      // Clamp to [-1, 1] and convert to 16-bit integer
      const sample = Math.max(-1, Math.min(1, floatData[i]));
      const int16 = Math.round(sample * 32767);
      pcmData.setInt16(i * 2, int16, true); // little-endian
    }

    // Convert to base64 string
    const bytes = new Uint8Array(buffer);
    let binaryString = '';
    for (let i = 0; i < bytes.length; i++) {
      binaryString += String.fromCharCode(bytes[i]);
    }

    return btoa(binaryString);
  }

  /**
   * Clean up all audio resources.
   */
  private cleanup(): void {
    this.isCapturing = false;

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }

    if (this.audioStream) {
      this.audioStream.getTracks().forEach((track) => track.stop());
      this.audioStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.onAudioChunk = null;
  }
}
