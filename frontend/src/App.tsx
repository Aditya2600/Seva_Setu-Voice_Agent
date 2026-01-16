import React, { useEffect, useRef, useState } from 'react'
import { client } from './lib/api'
import type { DebugLog } from './lib/api'
import Recorder from './components/Recorder'
import Chip from './components/Chip'
import SchemeCard from './components/SchemeCard'
import ToolTimeline, { ToolEvt } from './components/ToolTimeline'
import { Bot, User, AlertCircle, FileText, Activity } from 'lucide-react'

// Chat Message Type
type ChatMessage = {
  role: 'user' | 'assistant'
  text: string
  cards?: any[]
  uiIntent?: string
  eligibility?: any
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [interimText, setInterimText] = useState('')
  const interimRef = useRef('') // ✅ keeps latest STT safely for AGENT_START
  const lastSttPushedRef = useRef('') // ✅ dedupe timeline spam
  const [status, setStatus] = useState('Connecting...')
  const [speaking, setSpeaking] = useState(false)

  const [toolEvents, setToolEvents] = useState<ToolEvt[]>([])
  const [showDebug, setShowDebug] = useState(true)
  const [debugLogs, setDebugLogs] = useState<DebugLog[]>([])

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const addLocalLog = (level: DebugLog['level'], event: string, message: string, payload?: any) => {
    setDebugLogs((prev) => [...prev, { ts: Date.now(), level, event, message, payload }].slice(-120))
  }

  // ✅ IMPORTANT FIX: Subscribe ONCE (no dependency on interimText)
  useEffect(() => {
    const unsubDebug = client.onDebug((entry) => {
      setDebugLogs((prev) => [...prev, entry].slice(-120))

      if (entry.event === 'ws_open') setStatus('Online')

      if (entry.event === 'ws_close' || entry.event === 'ws_error') {
        setStatus('Reconnecting...')
        setSpeaking(false)
        if (audioRef.current) {
          try {
            audioRef.current.pause()
          } catch {}
          audioRef.current = null
        }
      }
    })

    client.connect()
    setStatus('Connecting...')

    const unsub = client.onMessage((msg) => {
      if (msg.type === 'hello_ack') {
        setStatus('Online')
        return
      }

      // 1) STT results
      if (msg.type === 'stt_result') {
        const t = msg.text || ''
        interimRef.current = t
        setInterimText(t)

        // push to timeline only for final-ish STT and only if changed
        const conf = Number(msg.confidence ?? 0)
        if (t && conf > 0 && t !== lastSttPushedRef.current) {
          lastSttPushedRef.current = t
          setToolEvents((p) => [...p, { kind: 'stt', name: 'stt_result', payload: { text: t, confidence: conf } }])
        }
      }

      // 2) agent events
      if (msg.type === 'agent_event') {
        setToolEvents((p) => [...p, { kind: 'agent_event', name: msg.event, payload: msg.payload }])

        // When agent starts, commit the user message once
        if (msg.event === 'AGENT_START') {
          const userText = (interimRef.current || '').trim()
          if (!userText) return

          setMessages((prev) => {
            // dedupe if last message already same user text
            if (prev.length > 0 && prev[prev.length - 1].role === 'user' && prev[prev.length - 1].text === userText) {
              return prev
            }
            return [...prev, { role: 'user', text: userText }]
          })
        }

        // Show planner json in timeline if present
        if (msg.event === 'PLAN') {
          setToolEvents((p) => [...p, { kind: 'plan', name: 'plan', payload: msg.payload }])
        }
      }

      // 3) tool calls / results
      if (msg.type === 'tool_call') {
        setToolEvents((p) => [...p, { kind: 'tool_call', name: msg.tool, payload: msg.payload }])
      }
      if (msg.type === 'tool_result') {
        setToolEvents((p) => [...p, { kind: 'tool_result', name: msg.tool, payload: msg.payload }])
      }

      // 4) assistant response
      if (msg.type === 'assistant_message') {
        setInterimText('')
        interimRef.current = ''

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: msg.text,
            cards: msg.ui?.cards || [],
            uiIntent: msg.ui?.ui_intent,
            eligibility: msg.ui?.eligibility,
          },
        ])

        // Auto-play audio
        if (msg.ttsAudioB64) {
          addLocalLog('info', 'tts_play', 'Playing TTS audio', {
            bytes: msg.ttsAudioB64.length,
            mime: msg.ttsMime || 'audio/wav',
          })
          if (audioRef.current) {
            audioRef.current.pause()
            audioRef.current = null
          }
          const snd = new Audio(`data:${msg.ttsMime || 'audio/wav'};base64,${msg.ttsAudioB64}`)
          audioRef.current = snd
          setSpeaking(true)
          snd.onended = () => {
            setSpeaking(false)
            addLocalLog('debug', 'tts_end', 'TTS playback ended')
          }
          snd.play().catch((e) => {
            addLocalLog('error', 'tts_play_error', 'TTS playback blocked', { error: String(e) })
            console.error('Audio blocked:', e)
          })
        }
      }

      // 5) backend error
      if (msg.type === 'error') {
        addLocalLog('error', 'backend_error', msg.message || 'Unknown backend error', msg)
        setToolEvents((p) => [...p, { kind: 'agent_event', name: 'ERROR', payload: msg }])
        setStatus('Error')
      }
    })

    return () => {
      unsub()
      unsubDebug()
      setSpeaking(false)
      if (audioRef.current) {
        try {
          audioRef.current.pause()
        } catch {}
        audioRef.current = null
      }
    }
  }, [])

  // auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, interimText])

  const handleAudio = (b64: string, mime: string) => {
    client.sendAudio(b64, mime)
  }

  return (
    <div className="app-shell">
      <div className={`chat-pane ${showDebug ? 'shifted' : ''}`}>
        <header className="app-header">
          <div className="header-inner">
            <div className="brand-row">
              <div className="brand-mark">
                <Bot size={18} />
              </div>
              <div>
                <div className="brand-title">SevaSetu</div>
                <div className="brand-subtitle">Marathi welfare voice agent</div>
              </div>
              <Chip className="accent">मराठी</Chip>
            </div>
            <div className="header-actions">
              <button onClick={() => setShowDebug(!showDebug)} className="btn btn-ghost">
                <Activity size={14} /> {showDebug ? 'Hide Debug' : 'Show Debug'}
              </button>
              <div className={`status-pill ${status === 'Online' ? '' : 'offline'}`}>{status}</div>
            </div>
          </div>
        </header>

        <main className="chat-main">
          <div className="chat-inner">
            {messages.length === 0 && (
              <div className="intro-card fade-up">
                <div className="intro-title">नमस्कार! मी सेवासेतू आहे.</div>
                <div className="intro-sub">मी तुम्हाला सरकारी योजना शोधण्यात आणि अर्ज करण्यात मदत करू शकतो.</div>
                <div className="prompt-row">
                  <Chip className="accent">मला शिष्यवृत्ती योजना हवी आहे</Chip>
                  <Chip className="accent">लाडकी बहीण योजना</Chip>
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div
                key={i}
                className={`message-row ${m.role === 'user' ? 'user' : ''} fade-up`}
                style={{ animationDelay: `${i * 0.04}s` }}
              >
                <div className={`message-avatar ${m.role === 'user' ? 'user' : ''}`}>
                  {m.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
                </div>

                <div className="message-stack">
                  <div className="message-bubble">{m.text}</div>

                  {m.cards && m.cards.length > 0 && (
                    <div className="card-grid">
                      {m.cards.map((c, idx) => (
                        <SchemeCard
                          key={idx}
                          title={c.title}
                          category={c.category || 'कल्याणकारी योजना'}
                          benefits={c.benefits}
                          documents={c.documents || []}
                        />
                      ))}
                    </div>
                  )}

                  {m.eligibility?.status === 'not_eligible' && (
                    <div className="alert-card danger">
                      <AlertCircle className="alert-icon danger" size={18} />
                      <div className="text-sm text-slate-700 space-y-1">
                        <div className="alert-title">पात्रता निकष पूर्ण होत नाहीत:</div>
                        {(m.eligibility.reasons_mr || []).map((r: string, ix: number) => (
                          <div key={ix}>• {r}</div>
                        ))}
                      </div>
                    </div>
                  )}

                  {m.eligibility?.apply_result && (
                    <div className="alert-card success">
                      <FileText className="alert-icon success" size={18} />
                      <div className="text-sm text-emerald-800">
                        <div className="alert-title">अर्ज यशस्वीरित्या सबमिट झाला!</div>
                        <div className="debug-mono">ID: {m.eligibility.apply_result.application_id}</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {interimText && (
              <div className="message-row user fade-up">
                <div className="message-avatar user">
                  <User size={16} />
                </div>
                <div className="message-bubble subtle">{interimText}...</div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </main>

        <footer className="chat-footer">
          <div className="chat-inner">
            <Recorder onAudio={handleAudio} disabled={status !== 'Online'} speaking={speaking} />
          </div>
        </footer>
      </div>

      <aside className={`debug-panel ${showDebug ? 'open' : ''}`}>
        <ToolTimeline events={toolEvents} logs={debugLogs} />
      </aside>
    </div>
  )
}
