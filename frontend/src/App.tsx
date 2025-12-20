import React, { useEffect, useRef, useState } from 'react'
import { client } from './lib/api'
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
  const [status, setStatus] = useState('Connecting...')
  const [speaking, setSpeaking] = useState(false)

  const [toolEvents, setToolEvents] = useState<ToolEvt[]>([])
  const [showDebug, setShowDebug] = useState(true)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // ✅ IMPORTANT FIX: Subscribe ONCE (no dependency on interimText)
  useEffect(() => {
    client.connect()
    setStatus('Online')

    const unsub = client.onMessage((msg) => {
      // 1) STT results
      if (msg.type === 'stt_result') {
        const t = msg.text || ''
        interimRef.current = t
        setInterimText(t)

        // add to timeline
        setToolEvents((p) => [...p, { kind: 'stt', name: 'stt_result', payload: { text: t, confidence: msg.confidence } }])
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
          if (audioRef.current) {
            audioRef.current.pause()
            audioRef.current = null
          }
          const snd = new Audio(`data:${msg.ttsMime || 'audio/wav'};base64,${msg.ttsAudioB64}`)
          audioRef.current = snd
          setSpeaking(true)
          snd.onended = () => setSpeaking(false)
          snd.play().catch((e) => console.error('Audio blocked:', e))
        }
      }
    })

    return () => unsub()
  }, [])

  // auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, interimText])

  const handleAudio = (b64: string, mime: string) => {
    client.sendAudio(b64, mime)
  }

  return (
    <div className="min-h-screen font-sans selection:bg-sky-500/30 flex bg-slate-950 text-slate-100">
      {/* LEFT: Main Chat */}
      <div className={`flex-1 flex flex-col relative transition-all duration-300 ${showDebug ? 'mr-80' : ''}`}>
        {/* Header */}
        <header className="fixed top-0 left-0 right-0 z-20 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-md">
          <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-sky-500/20">
                <Bot className="text-white" size={20} />
              </div>
              <span className="font-bold tracking-tight text-slate-100">SevaSetu</span>
              <Chip>मराठी</Chip>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setShowDebug(!showDebug)}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
              >
                <Activity size={14} /> {showDebug ? 'Hide Debug' : 'Show Debug'}
              </button>
              <div className="text-xs font-mono text-slate-500">{status}</div>
            </div>
          </div>
        </header>

        {/* Chat Stream */}
        <main className="pt-20 pb-48 px-4 max-w-2xl mx-auto w-full space-y-8">
          {messages.length === 0 && (
            <div className="text-center mt-20 opacity-60">
              <p className="text-slate-300 text-lg">👋 नमस्कार! मी सेवासेतू आहे.</p>
              <p className="text-sm text-slate-500 mt-2">मी तुम्हाला सरकारी योजना शोधण्यात आणि अर्ज करण्यात मदत करू शकतो.</p>
              <p className="text-xs text-slate-600 mt-3">उदा: “मला शिष्यवृत्ती योजना हवी आहे” किंवा “लाडकी बहीण योजना”</p>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex gap-4 ${m.role === 'user' ? 'flex-row-reverse' : ''} animate-in fade-in slide-in-from-bottom-2 duration-300`}
            >
              {/* Avatar */}
              <div
                className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-lg ${
                  m.role === 'assistant' ? 'bg-slate-800 text-sky-400' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {m.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
              </div>

              <div className="space-y-3 max-w-[85%]">
                {/* Bubble */}
                <div
                  className={`px-5 py-3 rounded-2xl text-[15px] leading-relaxed whitespace-pre-wrap shadow-md ${
                    m.role === 'user'
                      ? 'bg-slate-800 text-slate-200 rounded-tr-none'
                      : 'bg-slate-900/50 border border-slate-800 text-slate-300 rounded-tl-none'
                  }`}
                >
                  {m.text}
                </div>

                {/* Cards */}
                {m.cards && m.cards.length > 0 && (
                  <div className="grid grid-cols-1 gap-3 mt-2">
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

                {/* Eligibility alerts */}
                {m.eligibility?.status === 'not_eligible' && (
                  <div className="p-4 bg-rose-950/20 border border-rose-900/30 rounded-2xl flex gap-3">
                    <AlertCircle className="text-rose-500 shrink-0 mt-0.5" size={18} />
                    <div className="text-sm text-rose-200 space-y-1">
                      <div className="font-semibold text-rose-400">पात्रता निकष पूर्ण होत नाहीत:</div>
                      {(m.eligibility.reasons_mr || []).map((r: string, ix: number) => (
                        <div key={ix}>• {r}</div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Application success */}
                {m.eligibility?.apply_result && (
                  <div className="p-4 bg-emerald-950/20 border border-emerald-900/30 rounded-2xl flex gap-3">
                    <FileText className="text-emerald-500 shrink-0 mt-0.5" size={18} />
                    <div className="text-sm text-emerald-200">
                      <div className="font-bold text-emerald-400">अर्ज यशस्वीरित्या सबमिट झाला!</div>
                      <div className="opacity-80 mt-1 font-mono">ID: {m.eligibility.apply_result.application_id}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Interim STT */}
          {interimText && (
            <div className="flex flex-row-reverse gap-4 opacity-60 animate-pulse">
              <div className="w-8 h-8 bg-slate-800 rounded-full flex items-center justify-center">
                <User size={16} />
              </div>
              <div className="px-5 py-3 bg-slate-800/50 rounded-2xl rounded-tr-none text-[15px] text-slate-400">
                {interimText}...
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </main>

        {/* Footer Input */}
        <footer className="fixed bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent z-10">
          <div className={`max-w-2xl mx-auto transition-all duration-300 ${showDebug ? 'mr-[340px]' : ''}`}>
            <Recorder onAudio={handleAudio} disabled={status !== 'Online'} speaking={speaking} />
          </div>
        </footer>
      </div>

      {/* RIGHT: Debug Sidebar */}
      <div
        className={`fixed right-0 top-14 bottom-0 w-80 bg-slate-950 border-l border-slate-800/60 p-4 overflow-y-auto transition-transform duration-300 ${
          showDebug ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <ToolTimeline events={toolEvents} />
      </div>
    </div>
  )
}