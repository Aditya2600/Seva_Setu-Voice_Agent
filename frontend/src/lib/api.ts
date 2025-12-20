import { v4 as uuidv4 } from 'uuid'
type MessageHandler = (msg:any)=>void
export class AgentClient {
  private ws: WebSocket | null = null
  private handlers: MessageHandler[] = []
  public sessionId: string
  private url: string
  constructor(){
    this.url = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000/ws'
    this.sessionId = localStorage.getItem('agent_session') || `sess_${uuidv4().slice(0,8)}`
    localStorage.setItem('agent_session', this.sessionId)
  }
  connect(){
    if(this.ws) return
    this.ws = new WebSocket(this.url)
    this.ws.onopen = () => this.send({ type:'hello', sessionId:this.sessionId, language:'Marathi' })
    this.ws.onmessage = (ev) => { try{ const d=JSON.parse(ev.data); this.handlers.forEach(h=>h(d)) }catch(e){ console.error(e) } }
    this.ws.onclose = () => { this.ws=null; setTimeout(()=>this.connect(), 1200) }
  }
  onMessage(cb: MessageHandler){ this.handlers.push(cb); return ()=>this.handlers=this.handlers.filter(h=>h!==cb) }
  send(payload:any){ if(this.ws?.readyState===WebSocket.OPEN) this.ws.send(JSON.stringify(payload)) }
  sendAudio(b64:string, mimeType:string){ this.send({ type:'audio', data:b64, mimeType, sessionId:this.sessionId }) }
}
export const client = new AgentClient()
