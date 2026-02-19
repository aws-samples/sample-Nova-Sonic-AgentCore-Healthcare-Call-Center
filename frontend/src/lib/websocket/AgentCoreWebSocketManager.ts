/**
 * AgentCore WebSocket Manager for speech-to-speech functionality.
 *
 * Connects to Amazon Bedrock AgentCore Runtime via SigV4-signed WebSocket.
 * Handles the BidiAgent protocol for bidirectional streaming voice agents.
 */

import { fetchAuthSession } from 'aws-amplify/auth';
import { AudioCapture } from '../audio/AudioCapture';
import { AudioPlayback } from '../audio/AudioPlayback';

// SigV4 signing utilities
import { SignatureV4 } from '@smithy/signature-v4';
import { Sha256 } from '@aws-crypto/sha256-browser';
import { HttpRequest } from '@smithy/protocol-http';

/**
 * Callback types for event handling
 */
export interface AgentCoreCallbacks {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onTranscript?: (role: 'USER' | 'ASSISTANT', text: string) => void;
  onStatusChange?: (status: string, className: string) => void;
  onError?: (error: Error) => void;
}

/**
 * Configuration for AgentCore WebSocket connection
 */
export interface AgentCoreConfig {
  runtimeArn: string;
  region: string;
}

/**
 * BidiAgent output event types
 * BidiAgent uses a simplified protocol with 'type' field
 *
 * Event types from Strands BidiAgent:
 * - bidi_audio_output / bidi_audio_stream: Audio response chunks
 * - bidi_text_output / bidi_transcript_stream: Transcript text
 * - bidi_response_start: Start of agent response
 * - bidi_response_end: End of agent response
 * - bidi_tool_call: Tool invocation
 * - bidi_tool_result: Tool result
 * - bidi_turn_end: End of turn
 * - bidi_usage: Token usage stats
 * - error: Error message
 */
interface BidiOutputEvent {
  type: string;
  // bidi_audio_output / bidi_audio_stream
  audio?: string;
  format?: string;
  sample_rate?: number;
  // bidi_text_output / bidi_transcript_stream
  text?: string;
  role?: string;
  is_final?: boolean;
  delta?: {
    text?: string;
    role?: string;
  };
  // bidi_tool_call / bidi_tool_result
  tool_name?: string;
  tool_call_id?: string;
  tool_input?: Record<string, unknown>;
  tool_result?: string;
  // bidi_usage
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  // error
  message?: string;
  code?: string;
}

export class AgentCoreWebSocketManager {
  private socket: WebSocket | null = null;
  private audioCapture: AudioCapture;
  private audioPlayback: AudioPlayback;
  private callbacks: AgentCoreCallbacks;
  private config: AgentCoreConfig;

  // Session state
  private isConnected: boolean = false;
  private isProcessing: boolean = false;

  // Reconnection state
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 3;
  private reconnectDelay: number = 1000;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isCleaningUp: boolean = false; // Flag to prevent reconnection during cleanup

  // Debug tracking
  private audioChunkCount: number = 0;

  constructor(config: AgentCoreConfig, callbacks: AgentCoreCallbacks = {}) {
    this.config = config;
    this.callbacks = callbacks;
    this.audioCapture = new AudioCapture();
    this.audioPlayback = new AudioPlayback();

    console.log('[AgentCoreWebSocketManager] Initializing with runtime:', this.config.runtimeArn);
  }

  /**
   * Connect to AgentCore Runtime WebSocket endpoint
   */
  async connect(): Promise<void> {
    try {
      this.updateStatus('Getting credentials...', 'connecting');

      // Get AWS credentials from Amplify Auth
      const session = await fetchAuthSession();
      const credentials = session.credentials;

      if (!credentials) {
        throw new Error('No AWS credentials available');
      }

      // Build the WebSocket URL
      const wsUrl = await this.buildSignedWebSocketUrl(credentials);

      console.log('[AgentCoreWebSocketManager] Connecting to AgentCore...');
      this.updateStatus('Connecting to AgentCore...', 'connecting');

      this.socket = new WebSocket(wsUrl);
      this.setupSocketListeners();

    } catch (error) {
      console.error('[AgentCoreWebSocketManager] Connection error:', error);
      this.updateStatus('Connection failed', 'error');
      this.callbacks.onError?.(error as Error);
      throw error;
    }
  }

  /**
   * Build SigV4-signed WebSocket URL for AgentCore
   */
  private async buildSignedWebSocketUrl(credentials: {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
  }): Promise<string> {
    const { runtimeArn, region } = this.config;

    // URL encode the ARN for the path
    const encodedArn = encodeURIComponent(runtimeArn);

    // AgentCore WebSocket endpoint
    const host = `bedrock-agentcore.${region}.amazonaws.com`;
    const path = `/runtimes/${encodedArn}/ws`;

    // Create the request to sign
    // NOTE: SigV4 requires signing with 'https:' protocol (canonical request),
    // then converting the final URL to 'wss://' for WebSocket connection
    const request = new HttpRequest({
      method: 'GET',
      protocol: 'https:',
      hostname: host,
      path: path,
      headers: {
        host: host,
      },
      query: {},
    });

    // Create the signer
    const signer = new SignatureV4({
      service: 'bedrock-agentcore',
      region: region,
      credentials: {
        accessKeyId: credentials.accessKeyId,
        secretAccessKey: credentials.secretAccessKey,
        sessionToken: credentials.sessionToken,
      },
      sha256: Sha256,
    });

    // Sign the request
    const signedRequest = await signer.presign(request, {
      expiresIn: 300, // URL valid for 5 minutes
    });

    // Build the signed URL
    const queryParams = new URLSearchParams(signedRequest.query as Record<string, string>);
    const signedUrl = `wss://${host}${path}?${queryParams.toString()}`;

    console.log('[AgentCoreWebSocketManager] Built signed WebSocket URL');
    return signedUrl;
  }

  /**
   * Set up WebSocket event listeners
   */
  private setupSocketListeners(): void {
    if (!this.socket) return;

    this.socket.onopen = async () => {
      console.log('[AgentCoreWebSocketManager] WebSocket connected');
      this.isConnected = true;
      this.isProcessing = true;
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;

      this.updateStatus('Connected - Starting session', 'connected');
      this.callbacks.onConnect?.();

      // Start the BidiAgent session
      await this.startSession();
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as BidiOutputEvent;
        this.handleMessage(data);
      } catch (e) {
        console.error('[AgentCoreWebSocketManager] Error parsing message:', e);
      }
    };

    this.socket.onerror = (error) => {
      console.error('[AgentCoreWebSocketManager] WebSocket error:', error);
      this.updateStatus('Connection error', 'error');
      this.isProcessing = false;
      this.stopAudioProcessing();
    };

    this.socket.onclose = async (event) => {
      console.log('[AgentCoreWebSocketManager] WebSocket closed:', event.code, event.reason);
      this.isConnected = false;
      this.isProcessing = false;
      this.stopAudioProcessing();

      if (this.shouldAttemptReconnect(event)) {
        this.updateStatus(`Connection lost - Reconnecting... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`, 'reconnecting');
        await this.attemptReconnect();
      } else {
        this.updateStatus('Disconnected', 'disconnected');
        this.callbacks.onDisconnect?.();
      }
    };
  }

  /**
   * Start BidiAgent session
   *
   * BidiAgent manages the Nova Sonic session internally.
   * For OUTBOUND calls, we send a session_start event to trigger the agent to speak first.
   */
  private async startSession(): Promise<void> {
    try {
      console.log('[AgentCoreWebSocketManager] Starting BidiAgent session');

      // Reset debug counters for new session
      this.audioChunkCount = 0;

      // Initialize audio playback first
      await this.audioPlayback.start();

      // Initialize audio capture and send as bidi_audio_input events
      await this.audioCapture.start((audioData) => {
        this.sendAudioChunk(audioData);
      });

      // OUTBOUND CALL: Send session start event to trigger agent greeting
      // This tells the agent the "patient has picked up" and it should introduce itself
      console.log('[AgentCoreWebSocketManager] Sending session_start to trigger agent greeting');
      this.sendEvent({
        type: 'bidi_session_start',
        context: {
          call_type: 'outbound',
          reason: 'appointment_reminder',
        },
      });

      this.updateStatus('Connected - Agent speaking...', 'speaking');

    } catch (error) {
      console.error('[AgentCoreWebSocketManager] Error starting session:', error);
      this.updateStatus('Error initializing session', 'error');
      this.callbacks.onError?.(error as Error);
    }
  }

  /**
   * Handle incoming messages from BidiAgent
   *
   * BidiAgent returns BidiOutputEvents with 'type' field:
   * - bidi_audio_output / bidi_audio_stream: Audio response chunks
   * - bidi_text_output / bidi_transcript_stream: Transcript text
   * - bidi_response_start: Start of agent response
   * - bidi_response_end: End of agent response
   * - bidi_tool_call: Tool invocation
   * - bidi_tool_result: Tool result
   * - bidi_turn_end: End of turn
   * - bidi_usage: Token usage stats
   * - error: Error message
   */
  private handleMessage(data: BidiOutputEvent): void {
    const eventType = data.type;

    if (!eventType) {
      console.warn('[AgentCoreWebSocketManager] Received message without type:', data);
      return;
    }

    // Log non-audio events (audio events are too frequent)
    if (!eventType.includes('audio')) {
      console.log(`[AgentCoreWebSocketManager] Received: ${eventType}`);
    }

    switch (eventType) {
      // Audio output events - handle both naming conventions
      case 'bidi_audio_output':
      case 'bidi_audio_stream':
        if (data.audio && this.isProcessing) {
          const audioData = this.base64ToFloat32Array(data.audio);
          // Log first audio chunk and periodically thereafter
          this.audioChunkCount++;
          if (this.audioChunkCount === 1 || this.audioChunkCount % 50 === 0) {
            console.log(`[AgentCoreWebSocketManager] Audio chunk #${this.audioChunkCount}:`, {
              base64Length: data.audio.length,
              samplesLength: audioData.length,
              format: data.format,
              sampleRate: data.sample_rate,
            });
          }
          this.audioPlayback.enqueue(audioData);
        } else if (!data.audio) {
          console.warn('[AgentCoreWebSocketManager] Audio event without audio data:', eventType);
        }
        break;

      // Text/transcript output events - handle both naming conventions
      case 'bidi_text_output':
      case 'bidi_transcript_stream':
        // For transcript_stream, only show final transcripts to avoid duplicates
        if (data.text) {
          // Show all transcripts (final and streaming) for responsiveness
          const role = (data.role?.toUpperCase() === 'USER' ? 'USER' : 'ASSISTANT') as 'USER' | 'ASSISTANT';

          // BARGE-IN: When user speaks, clear audio buffer to stop agent voice
          if (role === 'USER') {
            console.log('[AgentCoreWebSocketManager] User speaking - barge-in triggered');
            this.audioPlayback.clear();
          }

          // For streaming transcripts, show final ones to avoid duplicates
          if (eventType === 'bidi_transcript_stream') {
            if (data.is_final) {
              console.log(`[AgentCoreWebSocketManager] Final transcript [${role}]:`, data.text.substring(0, 50) + '...');
              this.callbacks.onTranscript?.(role, data.text);
            }
          } else {
            // bidi_text_output - always show
            this.callbacks.onTranscript?.(role, data.text);
          }
        }
        break;

      // Response lifecycle events
      case 'bidi_response_start':
        console.log('[AgentCoreWebSocketManager] Agent response starting');
        this.updateStatus('Agent speaking...', 'speaking');
        break;

      case 'bidi_response_end':
        console.log('[AgentCoreWebSocketManager] Agent response ended');
        this.updateStatus('Ready - Speak to continue', 'ready');
        break;

      // Tool events
      case 'bidi_tool_call':
        console.log('[AgentCoreWebSocketManager] Tool call:', data.tool_name, data.tool_input);
        this.updateStatus(`Using tool: ${data.tool_name}`, 'processing');
        break;

      case 'bidi_tool_result':
        console.log('[AgentCoreWebSocketManager] Tool result:', data.tool_name);
        break;

      // Turn lifecycle
      case 'bidi_turn_end':
        console.log('[AgentCoreWebSocketManager] Turn ended');
        this.updateStatus('Ready - Speak to continue', 'ready');
        break;

      // Usage stats
      case 'bidi_usage':
        console.log('[AgentCoreWebSocketManager] Usage:', {
          inputTokens: data.inputTokens,
          outputTokens: data.outputTokens,
          totalTokens: data.totalTokens,
        });
        break;

      // Error handling
      case 'error':
        console.error('[AgentCoreWebSocketManager] Error:', data.message, data.code);
        this.updateStatus(`Error: ${data.message}`, 'error');
        this.callbacks.onError?.(new Error(data.message || 'Unknown error'));
        break;

      default:
        // Log unknown events for debugging but don't spam
        console.log('[AgentCoreWebSocketManager] Unhandled event type:', eventType);
    }
  }

  /**
   * Send an event to AgentCore
   */
  private sendEvent(event: Record<string, unknown>): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn('[AgentCoreWebSocketManager] Cannot send event - socket not ready');
      return;
    }

    try {
      this.socket.send(JSON.stringify(event));
    } catch (error) {
      console.error('[AgentCoreWebSocketManager] Error sending event:', error);
    }
  }

  /**
   * Send audio chunk to BidiAgent as BidiAudioInputEvent
   *
   * BidiAgent expects: {"type": "bidi_audio_input", "audio": "base64...", "format": "pcm", "sample_rate": 16000, "channels": 1}
   */
  private sendAudioChunk(base64Data: string): void {
    if (!this.isProcessing || !this.isConnected) {
      return;
    }

    // Send as BidiAudioInputEvent format
    this.sendEvent({
      type: 'bidi_audio_input',
      audio: base64Data,
      format: 'pcm',
      sample_rate: 16000,
      channels: 1,
    });
  }

  /**
   * Convert base64 LPCM audio to Float32Array for playback
   */
  private base64ToFloat32Array(base64String: string): Float32Array {
    const binaryString = atob(base64String);
    const bytes = new Uint8Array(binaryString.length);

    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    const int16Array = new Int16Array(bytes.buffer);
    const float32Array = new Float32Array(int16Array.length);

    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 32768.0;
    }

    return float32Array;
  }

  /**
   * Stop audio processing and clear buffers
   */
  private stopAudioProcessing(): void {
    console.log('[AgentCoreWebSocketManager] Stopping audio processing');
    this.audioPlayback.clear();
  }

  /**
   * Determine if reconnection should be attempted
   */
  private shouldAttemptReconnect(event: CloseEvent): boolean {
    // Don't reconnect if we're cleaning up (user ended the call)
    if (this.isCleaningUp) {
      console.log('[AgentCoreWebSocketManager] Cleanup in progress, not reconnecting');
      return false;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[AgentCoreWebSocketManager] Max reconnection attempts reached');
      return false;
    }

    // Normal closure - don't reconnect
    if (event.code === 1000) return false;

    // Authentication failure - don't reconnect
    if (event.code === 1008 || event.code === 4001) return false;

    return true;
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private async attemptReconnect(): Promise<void> {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }

    this.reconnectAttempts++;

    console.log(`[AgentCoreWebSocketManager] Reconnecting ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${this.reconnectDelay}ms`);

    await new Promise(resolve => setTimeout(resolve, this.reconnectDelay));

    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 10000);

    try {
      await this.connect();
    } catch (error) {
      console.error('[AgentCoreWebSocketManager] Reconnection failed:', error);
    }
  }

  /**
   * Update connection status
   */
  private updateStatus(message: string, className: string): void {
    this.callbacks.onStatusChange?.(message, className);

    // Also update DOM element for backward compatibility
    const statusDiv = document.getElementById('status');
    if (statusDiv) {
      statusDiv.textContent = message;
      statusDiv.className = `status ${className}`;
    }
  }

  /**
   * Wait for connection to be established
   */
  async waitForConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.isConnected) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        reject(new Error('WebSocket connection timeout'));
      }, 10000);

      const checkConnection = () => {
        if (this.isConnected) {
          clearTimeout(timeout);
          resolve();
        } else if (this.socket?.readyState === WebSocket.CLOSED) {
          clearTimeout(timeout);
          reject(new Error('WebSocket connection failed'));
        } else {
          setTimeout(checkConnection, 100);
        }
      };

      checkConnection();
    });
  }

  /**
   * Check if currently connected
   */
  get connected(): boolean {
    return this.isConnected;
  }

  /**
   * Clean up resources and close connection
   */
  cleanup(): void {
    console.log('[AgentCoreWebSocketManager] Cleaning up resources');

    // Set cleanup flag to prevent reconnection attempts
    this.isCleaningUp = true;
    this.isProcessing = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    // Clean up audio first
    this.audioCapture.stop();
    this.audioPlayback.stop();

    // Close WebSocket with normal closure code (1000)
    if (this.socket) {
      try {
        this.socket.close(1000, 'User ended call');
      } catch (e) {
        console.warn('[AgentCoreWebSocketManager] Error closing socket:', e);
      }
      this.socket = null;
    }

    // Reset state
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    this.isCleaningUp = false; // Reset for future connections
  }
}
