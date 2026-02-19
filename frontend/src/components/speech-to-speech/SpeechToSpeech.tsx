/**
 * Speech-to-Speech component for the Healthcare Call Center.
 *
 * Connects to Amazon Bedrock AgentCore Runtime via the
 * AgentCoreWebSocketManager for bidirectional voice streaming.
 *
 * The backend BidiAgent handles all system prompts and tools.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { AgentCoreWebSocketManager, AgentCoreCallbacks } from "../../lib/websocket/AgentCoreWebSocketManager";
import { fetchPatients, Patient } from "../../lib/api/appointments";
import "../../styles/speech-to-speech.css";

// Get configuration from environment
const env = window.APP_CONFIG || import.meta.env;

interface ChatMessage {
  id: string;
  role: "USER" | "ASSISTANT";
  message: string;
}

interface SpeechToSpeechProps {
  runtimeArn?: string;
  region?: string;
}

export function SpeechToSpeech({
  runtimeArn = env.VITE_AGENTCORE_RUNTIME_ARN,
  region = env.VITE_AWS_REGION || "us-east-1",
}: SpeechToSpeechProps) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState("Select a patient and click 'Start Call'");
  const [statusClass, setStatusClass] = useState("disconnected");
  const [isInitializing, setIsInitializing] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [isAssistantSpeaking, setIsAssistantSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPatientIndex, setSelectedPatientIndex] = useState<number>(0);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [patientsError, setPatientsError] = useState<string | null>(null);

  const wsManagerRef = useRef<AgentCoreWebSocketManager | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  // Load patients from DynamoDB on mount
  useEffect(() => {
    let cancelled = false;
    setLoadingPatients(true);
    setPatientsError(null);

    fetchPatients()
      .then((result) => {
        if (!cancelled) {
          setPatients(result);
          setLoadingPatients(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("[SpeechToSpeech] Failed to load patients:", err);
          setPatientsError(err instanceof Error ? err.message : "Failed to load patients");
          setLoadingPatients(false);
        }
      });

    return () => { cancelled = true; };
  }, []);

  // Create AgentCore callbacks
  const createCallbacks = useCallback((): AgentCoreCallbacks => ({
    onConnect: () => {
      setIsStreaming(true);
      setIsInitializing(false);
      setError(null);
    },
    onDisconnect: () => {
      setIsStreaming(false);
      setIsInitializing(false);
      setIsUserSpeaking(false);
      setIsAssistantSpeaking(false);
    },
    onTranscript: (role, text) => {
      const messageId = `${role}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      if (role === "USER") {
        setIsUserSpeaking(false);
        setIsAssistantSpeaking(true);
      } else {
        setIsAssistantSpeaking(false);
      }

      setMessages((prev) => {
        // Prevent duplicates
        const isDuplicate = prev.some(
          (msg) => msg.role === role && msg.message === text
        );
        if (isDuplicate) return prev;
        return [...prev, { id: messageId, role, message: text }];
      });
    },
    onStatusChange: (message, className) => {
      setStatus(message);
      setStatusClass(className);
    },
    onError: (err) => {
      console.error("[SpeechToSpeech] Error:", err);
      setError(err.message);
      setIsInitializing(false);
    },
  }), []);

  // Start the voice call
  const startCall = useCallback(async () => {
    if (!runtimeArn) {
      setError("AgentCore Runtime ARN not configured");
      return;
    }

    setIsInitializing(true);
    setError(null);
    setStatus("Connecting to AgentCore...");
    setStatusClass("connecting");

    try {
      const manager = new AgentCoreWebSocketManager(
        { runtimeArn, region },
        createCallbacks()
      );

      await manager.connect();
      await manager.waitForConnection();

      wsManagerRef.current = manager;

    } catch (err) {
      console.error("[SpeechToSpeech] Failed to start call:", err);
      setError(err instanceof Error ? err.message : "Failed to connect");
      setIsInitializing(false);
      setStatus("Failed to connect");
      setStatusClass("error");
    }
  }, [runtimeArn, region, createCallbacks]);

  // Stop the voice call
  const stopCall = useCallback(() => {
    if (wsManagerRef.current) {
      console.log("[SpeechToSpeech] Stopping call");
      wsManagerRef.current.cleanup();
      wsManagerRef.current = null;
    }

    setIsStreaming(false);
    setIsUserSpeaking(false);
    setIsAssistantSpeaking(false);
    setStatus("Select a patient and click 'Start Call'");
    setStatusClass("disconnected");
  }, []);

  // Clear chat history
  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsManagerRef.current) {
        wsManagerRef.current.cleanup();
        wsManagerRef.current = null;
      }
    };
  }, []);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isUserSpeaking, isAssistantSpeaking]);

  // Get the currently selected patient
  const selectedPatient = patients[selectedPatientIndex];

  // Render thinking/speaking indicator
  const renderIndicator = (role: "USER" | "ASSISTANT") => (
    <div className={`message ${role.toLowerCase()}`}>
      <div className="thinking-indicator">
        <span>{role === "USER" ? "Listening" : "Speaking"}</span>
        <div className="thinking-dots">
          <span className="dot"></span>
          <span className="dot"></span>
          <span className="dot"></span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-full gap-0">
      {/* Left Panel — Patient Selection */}
      <div className="flex w-[300px] flex-shrink-0 flex-col bg-surface-elevated border-r border-white/5 p-5">
        <div className="mb-6">
          <h2 className="font-display text-xs font-semibold uppercase tracking-widest text-text-secondary mb-4">
            Patients
          </h2>

          {loadingPatients ? (
            <div className="text-sm text-text-secondary py-2">Loading patients...</div>
          ) : patientsError ? (
            <div className="text-sm text-call-end py-2">{patientsError}</div>
          ) : patients.length === 0 ? (
            <div className="text-sm text-text-secondary py-2">No patients found. Run data_seed.py first.</div>
          ) : (
            <select
              value={selectedPatientIndex}
              onChange={(e) => setSelectedPatientIndex(Number(e.target.value))}
              disabled={isStreaming || isInitializing}
              className="w-full rounded-lg border border-white/8 bg-surface px-3 py-2.5 text-sm text-text-primary
                         focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {patients.map((patient, index) => (
                <option key={patient.patientId} value={index}>
                  {patient.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Patient Details Card */}
        {selectedPatient && (
          <div className="rounded-xl border border-white/5 bg-surface p-4 mb-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-3">
              Patient Details
            </h3>
            <div className="space-y-2.5">
              <div>
                <div className="text-[11px] text-text-secondary">Name</div>
                <div className="text-sm font-medium text-text-primary">{selectedPatient.name}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-secondary">Patient ID</div>
                <div className="font-mono text-xs text-accent">{selectedPatient.patientId}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-secondary">SSN (last 4)</div>
                <div className="text-sm font-medium text-text-primary">***-**-{selectedPatient.ssn4}</div>
              </div>
            </div>
          </div>
        )}

        {/* Auth Hint */}
        {selectedPatient && (
          <div className="rounded-lg border border-accent/10 bg-accent/5 p-3 mt-auto">
            <div className="text-[11px] font-medium text-accent mb-1">Authentication Tip</div>
            <p className="text-xs leading-relaxed text-text-secondary">
              When prompted, say "<span className="text-text-primary font-medium">{selectedPatient.name}</span>" and "<span className="text-text-primary font-medium">{selectedPatient.ssn4}</span>" to verify identity.
            </p>
          </div>
        )}
      </div>

      {/* Right Panel — Call & Transcript */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Status Orb Area */}
        <div className="flex items-center justify-center py-5 border-b border-white/5">
          <div className="relative flex items-center gap-3">
            {/* Pulsing glow behind status when active */}
            {isStreaming && (
              <div className="absolute inset-0 -m-4 rounded-full bg-accent/10 animate-glow-pulse blur-xl" />
            )}
            <div className="relative">
              <div id="status" className={`status ${statusClass}`}>
                {status}
              </div>
              {error && (
                <div className="text-call-end text-xs mt-1.5">
                  {error}
                </div>
              )}
              {!runtimeArn && (
                <div className="text-warning text-xs mt-1.5">
                  AgentCore Runtime ARN not configured.
                </div>
              )}
            </div>
            {isStreaming && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent"></span>
              </span>
            )}
          </div>
        </div>

        {/* Transcript Area */}
        <div
          className="flex-1 overflow-y-auto"
          ref={chatContainerRef}
        >
          <div className="chat-container h-full">
            {messages.length === 0 && !isStreaming && (
              <div className="flex flex-col items-center justify-center h-full text-center py-16">
                <div className="h-16 w-16 rounded-full bg-surface-accent flex items-center justify-center mb-4">
                  <svg className="h-7 w-7 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                  </svg>
                </div>
                <p className="text-sm text-text-secondary mb-1">Outbound Appointment Reminder</p>
                <p className="text-xs text-text-secondary/60">
                  Click <span className="text-accent font-medium">Start Call</span> to initiate a call{selectedPatient ? <> to <span className="text-text-primary font-medium">{selectedPatient.name}</span></> : null}
                </p>
                <p className="text-xs text-text-secondary/50 mt-2">
                  Patients can confirm, cancel, or reschedule appointments.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role.toLowerCase()}`}>
                <div>{msg.message}</div>
              </div>
            ))}

            {isUserSpeaking && renderIndicator("USER")}
            {isAssistantSpeaking && renderIndicator("ASSISTANT")}
          </div>
        </div>

        {/* Controls — sticky bottom */}
        <div className="border-t border-white/5 bg-surface-elevated px-6 py-4">
          <div className="flex items-center justify-center gap-3">
            {!isStreaming ? (
              <button
                onClick={startCall}
                disabled={isInitializing || !runtimeArn || patients.length === 0}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground
                           transition-all hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed
                           focus:outline-none focus:ring-2 focus:ring-accent/40
                           glow-ring hover:glow-ring-active"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                </svg>
                {isInitializing ? "Connecting..." : "Start Call"}
              </button>
            ) : (
              <button
                onClick={stopCall}
                className="inline-flex items-center gap-2 rounded-lg bg-call-end px-5 py-2.5 text-sm font-semibold text-white
                           transition-all hover:brightness-110
                           focus:outline-none focus:ring-2 focus:ring-call-end/40"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                End Call
              </button>
            )}

            <button
              onClick={clearChat}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-4 py-2.5 text-sm font-medium text-text-secondary
                         transition-all hover:bg-white/5 hover:text-text-primary
                         focus:outline-none focus:ring-2 focus:ring-white/10"
            >
              Clear Chat
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
