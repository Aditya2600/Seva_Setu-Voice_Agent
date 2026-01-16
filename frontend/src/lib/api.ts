import { v4 as uuidv4 } from 'uuid'

type MessageHandler = (msg: any) => void
type DebugHandler = (log: DebugLog) => void

export type DebugLevel = 'debug' | 'info' | 'warn' | 'error'
export type DebugLog = {
  ts: number
  level: DebugLevel
  event: string
  message: string
  payload?: any
}

export class AgentClient {
  private ws: WebSocket | null = null
  private handlers: MessageHandler[] = []
  private debugHandlers: DebugHandler[] = []
  public sessionId: string
  private url: string

  constructor() {
    this.url = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000/ws'
    this.sessionId = localStorage.getItem('agent_session') || `sess_${uuidv4().slice(0, 8)}`
    localStorage.setItem('agent_session', this.sessionId)
  }

  private emitDebug(level: DebugLevel, event: string, message: string, payload?: any) {
    const entry: DebugLog = { ts: Date.now(), level, event, message, payload }
    this.debugHandlers.forEach((h) => h(entry))
    if (level === 'error') console.error(message, payload)
    else if (level === 'warn') console.warn(message, payload)
    else if (level === 'info') console.info(message, payload)
    else console.debug(message, payload)
  }

  connect() {
    if (this.ws) return
    this.emitDebug('info', 'ws_connect', 'Connecting to WebSocket', { url: this.url })
    this.ws = new WebSocket(this.url)
    this.ws.onopen = () => {
      this.emitDebug('info', 'ws_open', 'WebSocket connected')
      this.send({ type: 'hello', sessionId: this.sessionId, language: 'Marathi' })
    }
    this.ws.onmessage = (ev) => {
      if (typeof ev.data !== 'string') {
        this.emitDebug('warn', 'ws_message_non_text', 'Non-text WebSocket message', { type: typeof ev.data })
        return
      }
      const raw = ev.data
      if (raw) {
        this.emitDebug('debug', 'ws_message', 'WebSocket message received', { bytes: raw.length })
      }
      try {
        const d = JSON.parse(raw)
        this.emitDebug('debug', 'ws_message_parsed', 'WebSocket message parsed', { type: d?.type || d?.event })
        this.handlers.forEach((h) => h(d))
      } catch (e) {
        this.emitDebug('error', 'ws_message_error', 'Failed to parse WebSocket message', { error: String(e) })
      }
    }
    this.ws.onerror = (ev) => {
      this.emitDebug('error', 'ws_error', 'WebSocket error', { ev: String(ev) })
    }
    this.ws.onclose = (ev) => {
      this.emitDebug('warn', 'ws_close', 'WebSocket closed', { code: ev.code, reason: ev.reason })
      this.ws = null
      setTimeout(() => this.connect(), 1200)
    }
  }

  disconnect() {
    if (!this.ws) return
    try {
      this.emitDebug('info', 'ws_disconnect', 'WebSocket disconnect requested')
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onerror = null
      this.ws.onclose = null
      this.ws.close()
    } catch (e) {
      this.emitDebug('warn', 'ws_disconnect_error', 'Error while closing WebSocket', { error: String(e) })
    } finally {
      this.ws = null
    }
  }

  onMessage(cb: MessageHandler) {
    this.handlers.push(cb)
    return () => (this.handlers = this.handlers.filter((h) => h !== cb))
  }

  onDebug(cb: DebugHandler) {
    this.debugHandlers.push(cb)
    return () => (this.debugHandlers = this.debugHandlers.filter((h) => h !== cb))
  }

  send(payload: any) {
    const message = JSON.stringify(payload)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(message)
      this.emitDebug('debug', 'ws_send', 'WebSocket message sent', {
        type: payload?.type,
        bytes: message.length,
        preview: message.slice(0, 200),
      })
    } else {
      this.emitDebug('warn', 'ws_send_skipped', 'WebSocket not ready', {
        type: payload?.type,
        readyState: this.ws?.readyState,
      })
    }
  }

  sendAudio(b64: string, mimeType: string) {
    this.emitDebug('info', 'audio_send', 'Audio captured', { sessionId: this.sessionId, bytes: b64.length, mimeType })
    this.send({ type: 'audio', data: b64, mimeType, sessionId: this.sessionId })
  }
}
export const client = new AgentClient()
