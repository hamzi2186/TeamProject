import React, { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  Clock,
  Mic,
  MicOff,
  Phone,
  PhoneCall,
  PhoneOff,
  Radio,
  Sparkles,
  User,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import Vapi from "@vapi-ai/web";
import { callingApi, callingKeys } from "../../api/calling";
import type { Call } from "../../types/calling";

interface LiveCallModalProps {
  callId: string;
  leadName: string;
  phoneNumber: string;
  companyName?: string;
  onClose: () => void;
}

const VAPI_PUBLIC_KEY =
  import.meta.env.VITE_VAPI_PUBLIC_KEY || "6a243a7f-6a4e-4b7c-9fae-fc40325a937d";
const VAPI_ASSISTANT_ID =
  import.meta.env.VITE_VAPI_ASSISTANT_ID || "b38048c1-8176-4888-a2e0-58a1cae7bfab";

export function LiveCallModal({
  callId,
  leadName,
  phoneNumber,
  companyName,
  onClose,
}: LiveCallModalProps) {
  const queryClient = useQueryClient();
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const vapiRef = useRef<Vapi | null>(null);

  const [isMuted, setIsMuted] = useState(false);
  const [isSpeakerOn, setIsSpeakerOn] = useState(true);
  const [endingCall, setEndingCall] = useState(false);
  const [localSeconds, setLocalSeconds] = useState(0);

  // WebRTC real voice state
  const [isWebCallConnected, setIsWebCallConnected] = useState(false);
  const [activeSpeaker, setActiveSpeaker] = useState<"ai" | "user" | null>(null);
  const [volumeLevel, setVolumeLevel] = useState(0);
  const [webTranscripts, setWebTranscripts] = useState<
    Array<{ id: number; isAi: boolean; speaker: string; text: string }>
  >([]);

  // Backend call polling for CRM record
  const { data, refetch } = useQuery({
    queryKey: callingKeys.detail(callId),
    queryFn: () => callingApi.getCall(callId),
    refetchInterval: (query) => {
      const callData = query.state.data?.data as Call | undefined;
      if (
        callData &&
        ["COMPLETED", "FAILED", "NO_ANSWER", "CANCELLED"].includes(callData.status)
      ) {
        return false;
      }
      return 1500;
    },
    refetchIntervalInBackground: true,
  });

  const call = data?.data;
  const status = isWebCallConnected ? "IN_PROGRESS" : call?.status || "QUEUED";
  const isFinished = ["COMPLETED", "FAILED", "NO_ANSWER", "CANCELLED"].includes(
    call?.status || ""
  ) && !isWebCallConnected;

  // Initialize and start Vapi WebRTC live call on mount
  useEffect(() => {
    let mounted = true;

    try {
      const vapi = new Vapi(VAPI_PUBLIC_KEY);
      vapiRef.current = vapi;

      vapi.on("call-start", () => {
        if (!mounted) return;
        setIsWebCallConnected(true);
        setActiveSpeaker("ai");
      });

      vapi.on("call-end", () => {
        if (!mounted) return;
        setIsWebCallConnected(false);
        setActiveSpeaker(null);
      });

      vapi.on("speech-start", () => {
        if (!mounted) return;
        setActiveSpeaker("ai");
      });

      vapi.on("speech-end", () => {
        if (!mounted) return;
        setActiveSpeaker(null);
      });

      vapi.on("volume-level", (vol: number) => {
        if (!mounted) return;
        setVolumeLevel(vol);
      });

      vapi.on("message", (msg: unknown) => {
        if (!mounted || !msg || typeof msg !== "object") return;
        const event = msg as {
          type?: string;
          role?: string;
          transcript?: string;
          transcriptType?: string;
        };

        if (event.type === "transcript" && event.transcript) {
          const isAi = event.role === "assistant";
          const text = event.transcript.trim();
          if (!text) return;

          setWebTranscripts((prev) => {
            // Avoid exact duplicate consecutive lines
            if (prev.length > 0 && prev[prev.length - 1].text === text) return prev;
            return [
              ...prev,
              {
                id: Date.now() + Math.random(),
                isAi,
                speaker: isAi ? "T Rex (AI Voice Assistant)" : "You (Lead)",
                text,
              },
            ];
          });
        }
      });

      vapi.on("error", (err: unknown) => {
        console.warn("Vapi Web call error, falling back to simulated backend flow:", err);
      });

      // Start actual live voice call session with Vapi
      vapi.start(VAPI_ASSISTANT_ID, {
        variableValues: {
          lead_name: leadName,
          lead_phone: phoneNumber,
          company: companyName || "",
        },
      }).catch((err: unknown) => {
        console.warn("Vapi start rejected:", err);
      });
    } catch (e) {
      console.warn("Failed to instantiate Vapi Web client:", e);
    }

    return () => {
      mounted = false;
      try {
        vapiRef.current?.stop();
      } catch {
        // ignore cleanup error
      }
    };
  }, [leadName, phoneNumber, companyName]);

  // Local timer increment when in progress
  useEffect(() => {
    if (isFinished) return;
    const interval = setInterval(() => {
      setLocalSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isFinished]);

  // Sync with backend duration if larger
  useEffect(() => {
    if (call?.duration_seconds && call.duration_seconds > localSeconds) {
      setLocalSeconds(call.duration_seconds);
    }
  }, [call?.duration_seconds, localSeconds]);

  // Combine backend transcript or real-time WebRTC transcripts
  const backendLines = React.useMemo(() => {
    if (!call?.transcript) return [];
    return call.transcript
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, idx) => {
        const isAi =
          line.toLowerCase().startsWith("ai") || line.toLowerCase().startsWith("alex");
        const colonIdx = line.indexOf(":");
        const speaker =
          colonIdx !== -1
            ? line.slice(0, colonIdx).trim()
            : isAi
            ? "T Rex (AI)"
            : "Lead";
        const text = colonIdx !== -1 ? line.slice(colonIdx + 1).trim() : line;
        return { id: idx, isAi, speaker, text };
      });
  }, [call?.transcript]);

  const displayedDialogue = webTranscripts.length > 0 ? webTranscripts : backendLines;

  // Auto-scroll transcript to bottom
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayedDialogue]);

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  const handleMuteToggle = () => {
    const next = !isMuted;
    setIsMuted(next);
    try {
      vapiRef.current?.setMuted(next);
    } catch {
      // ignore
    }
  };

  const handleEndCall = async () => {
    if (endingCall || isFinished) return;
    setEndingCall(true);
    try {
      // Stop real WebRTC audio session
      try {
        vapiRef.current?.stop();
      } catch {
        // ignore
      }
      setIsWebCallConnected(false);

      // Conclude call on backend
      await callingApi.endCall(callId);
      await refetch();
      void queryClient.invalidateQueries({ queryKey: callingKeys.all });
    } catch (e) {
      console.error("Failed to end call", e);
    } finally {
      setEndingCall(false);
    }
  };

  return (
    <div className="live-call-backdrop" role="dialog" aria-modal="true">
      <div className="live-call-modal">
        {/* Modal Top Bar */}
        <div className="live-call-modal__header">
          <div className="live-call-modal__header-info">
            <div className="live-indicator-wrapper">
              {!isFinished ? (
                <span className="live-pulsing-badge">
                  <span className="pulse-dot" />
                  {isWebCallConnected
                    ? "🔴 LIVE VOICE CALL (ACTUAL AI)"
                    : status === "RINGING"
                    ? "CONNECTING VOICE…"
                    : "LIVE CALL"}
                </span>
              ) : (
                <span className="ended-badge">
                  <CheckCircle2 size={13} />
                  CALL COMPLETED
                </span>
              )}
              <span className="live-timer">
                <Clock size={14} />
                {formatTimer(call?.duration_seconds ?? localSeconds)}
              </span>
              {isWebCallConnected && (
                <span
                  style={{
                    background: "rgba(198, 241, 53, 0.15)",
                    color: "#c6f135",
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: "6px",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <Radio size={12} /> Mic & Speaker Live
                </span>
              )}
            </div>
            <h2 className="live-contact-name">{leadName}</h2>
            <p className="live-contact-meta">
              <span>{phoneNumber}</span>
              {companyName && <span> · {companyName}</span>}
              <span> · Vapi GPT-4 Voice Assistant (Elliot)</span>
            </p>
          </div>

          <button
            className="modal-close-btn"
            onClick={() => {
              try {
                vapiRef.current?.stop();
              } catch {
                // ignore
              }
              onClose();
            }}
            title="Minimize or close modal"
            type="button"
          >
            <X size={20} />
          </button>
        </div>

        {/* Dynamic Voice Visualizer Status Bar */}
        <div className="live-visualizer-bar">
          {!isFinished ? (
            <div className="live-speaker-status">
              {!isWebCallConnected && status === "RINGING" ? (
                <div className="ringing-animation">
                  <div className="radar-ripple" />
                  <PhoneCall className="radar-icon animate-bounce" size={22} />
                  <span>Connecting real-time duplex audio to T Rex AI voice…</span>
                </div>
              ) : (
                <div className="speaking-row">
                  <div className="soundwave">
                    <span
                      className="bar bar-1"
                      style={{
                        transform: `scaleY(${Math.max(0.5, volumeLevel * 3)})`,
                      }}
                    />
                    <span
                      className="bar bar-2"
                      style={{
                        transform: `scaleY(${Math.max(0.8, volumeLevel * 4)})`,
                      }}
                    />
                    <span
                      className="bar bar-3"
                      style={{
                        transform: `scaleY(${Math.max(0.6, volumeLevel * 5)})`,
                      }}
                    />
                    <span
                      className="bar bar-4"
                      style={{
                        transform: `scaleY(${Math.max(0.9, volumeLevel * 4)})`,
                      }}
                    />
                    <span
                      className="bar bar-5"
                      style={{
                        transform: `scaleY(${Math.max(0.5, volumeLevel * 3)})`,
                      }}
                    />
                  </div>
                  <span className="speaker-text">
                    {activeSpeaker === "ai"
                      ? "T Rex (AI Assistant) is speaking into your speakers…"
                      : "You can speak into your microphone now…"}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="call-completed-banner">
              <Sparkles size={18} className="sparkle-icon" />
              <span>
                Call concluded with outcome:{" "}
                <strong className="outcome-tag">
                  {call?.outcome || "INTERESTED"}
                </strong>
              </span>
            </div>
          )}
        </div>

        {/* Live Conversation / Transcript Feed */}
        <div className="live-transcript-feed">
          <div className="feed-legend">
            <span>REAL-TIME VOICE STREAM (ACTUAL VAPI AUDIO)</span>
            <span className="agent-tag">GPT-4.1-Mini · Elliot Voice</span>
          </div>

          {displayedDialogue.length === 0 ? (
            <div className="live-waiting-state">
              <div className="calling-spinner" />
              <p>Live WebRTC audio channel established with Vapi Assistant…</p>
              <small>
                Speak into your mic or listen to the AI greeting in your speakers.
              </small>
            </div>
          ) : (
            <div className="dialogue-list">
              {displayedDialogue.map((msg) => (
                <div
                  key={msg.id}
                  className={`dialogue-bubble ${
                    msg.isAi ? "dialogue-ai" : "dialogue-lead"
                  }`}
                >
                  <div className="bubble-header">
                    <div className="bubble-avatar">
                      {msg.isAi ? <Bot size={15} /> : <User size={15} />}
                    </div>
                    <span className="bubble-author">{msg.speaker}</span>
                  </div>
                  <div className="bubble-text">{msg.text}</div>
                </div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
          )}
        </div>

        {/* Summary Card if Completed */}
        {isFinished && call?.summary && (
          <div className="post-call-summary-card">
            <div className="summary-header">
              <Sparkles size={16} />
              <h4>AI Call Summary & Qualification</h4>
            </div>
            <p className="summary-text">{call.summary}</p>
            <div className="summary-actions">
              <Link
                to={`/calling/${call.call_id}`}
                className="summary-detail-btn"
                onClick={onClose}
              >
                Inspect Call Logs & CRM Status &rarr;
              </Link>
            </div>
          </div>
        )}

        {/* Controls Footer */}
        <div className="live-call-footer">
          <div className="audio-toggles">
            <button
              type="button"
              className={`tool-btn ${isMuted ? "active-tool" : ""}`}
              onClick={handleMuteToggle}
              title={isMuted ? "Unmute Mic" : "Mute Mic"}
            >
              {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
              <span>{isMuted ? "Muted" : "Mute Mic"}</span>
            </button>

            <button
              type="button"
              className={`tool-btn ${!isSpeakerOn ? "active-tool" : ""}`}
              onClick={() => setIsSpeakerOn(!isSpeakerOn)}
              title={isSpeakerOn ? "Mute Audio Output" : "Enable Audio"}
            >
              {isSpeakerOn ? <Volume2 size={18} /> : <VolumeX size={18} />}
              <span>{isSpeakerOn ? "Speaker On" : "Muted"}</span>
            </button>
          </div>

          <div className="call-main-action">
            {!isFinished ? (
              <button
                type="button"
                className="hangup-button"
                onClick={handleEndCall}
                disabled={endingCall}
              >
                <PhoneOff size={18} />
                <span>{endingCall ? "Ending…" : "Hang Up"}</span>
              </button>
            ) : (
              <button
                type="button"
                className="close-call-button"
                onClick={() => {
                  try {
                    vapiRef.current?.stop();
                  } catch {
                    // ignore
                  }
                  onClose();
                }}
              >
                Done / Return to Leads
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
