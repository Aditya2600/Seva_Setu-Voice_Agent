import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Mic, Square, Volume2 } from 'lucide-react'

type Props = { onAudio:(b64:string,mime:string)=>void; disabled?:boolean; speaking?:boolean }

function toB64(blob: Blob): Promise<string>{
  return new Promise((resolve,reject)=>{
    const r=new FileReader()
    r.onloadend=()=>resolve(String(r.result).split(',')[1])
    r.onerror=reject
    r.readAsDataURL(blob)
  })
}

export default function Recorder({ onAudio, disabled, speaking }: Props){
  const [recording,setRecording]=useState(false)
  const [voice,setVoice]=useState(false)
  const recRef=useRef<MediaRecorder|null>(null)
  const chunks=useRef<BlobPart[]>([])
  const canvasRef=useRef<HTMLCanvasElement|null>(null)
  const accentRef=useRef<string>('')

  const audioCtxRef=useRef<AudioContext|null>(null)
  const analyserRef=useRef<AnalyserNode|null>(null)
  const srcRef=useRef<MediaStreamAudioSourceNode|null>(null)
  const rafRef=useRef<number|null>(null)

  const mimeType = useMemo(()=>{
    if(MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus'
    if(MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm'
    return ''
  },[])

  const draw = () => {
    const canvas=canvasRef.current
    const analyser=analyserRef.current
    if(!canvas || !analyser) return
    const ctx=canvas.getContext('2d'); if(!ctx) return
    const len=analyser.fftSize
    const data=new Uint8Array(len)
    analyser.getByteTimeDomainData(data)

    ctx.clearRect(0,0,canvas.width,canvas.height)
    ctx.lineWidth=2
    if(!accentRef.current){
      const raw=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
      accentRef.current=raw || '#1aa08d'
    }
    ctx.strokeStyle=accentRef.current
    ctx.beginPath()

    const slice = canvas.width / len
    let x=0; let maxDev=0
    for(let i=0;i<len;i++){
      const v=data[i]/128.0
      const y=(v*canvas.height)/2
      const dev=Math.abs(v-1.0)
      if(dev>maxDev) maxDev=dev
      if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y)
      x += slice
    }
    ctx.lineTo(canvas.width, canvas.height/2)
    ctx.stroke()
    setVoice(maxDev>0.05)
    rafRef.current=requestAnimationFrame(draw)
  }

  const stopMeter=()=>{
    if(rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current=null
    analyserRef.current?.disconnect()
    srcRef.current?.disconnect()
    analyserRef.current=null
    srcRef.current=null
    audioCtxRef.current?.close().catch(()=>{})
    audioCtxRef.current=null
  }

  const startMeter=(stream: MediaStream)=>{
    const AudioContextAny=(window as any).AudioContext || (window as any).webkitAudioContext
    const ac=new AudioContextAny()
    audioCtxRef.current=ac
    const an=ac.createAnalyser()
    an.fftSize=2048
    analyserRef.current=an
    const src=ac.createMediaStreamSource(stream)
    srcRef.current=src
    src.connect(an)
    rafRef.current=requestAnimationFrame(draw)
  }

  const start = async ()=>{
    if(disabled) return
    const stream=await navigator.mediaDevices.getUserMedia({ audio:true })
    startMeter(stream)
    chunks.current=[]
    const mr=new MediaRecorder(stream, mimeType?{mimeType}:undefined)
    recRef.current=mr
    mr.ondataavailable=(e)=>chunks.current.push(e.data)
    mr.onstop=async()=>{
      stopMeter()
      const blob=new Blob(chunks.current,{type: mr.mimeType || 'audio/webm'})
      stream.getTracks().forEach(t=>t.stop())
      const b64=await toB64(blob)
      onAudio(b64, blob.type || 'audio/webm')
    }
    mr.start()
    setRecording(true)
  }
  const stop = ()=>{ recRef.current?.stop(); setRecording(false) }

  useEffect(()=>()=>stopMeter(),[])

  return (
    <div className="recorder-card fade-up">
      <div className="recorder-header">
        <div className="recorder-meta">
          <div className="recorder-icon">
            <Mic size={18} />
          </div>
          <div>
            <div className="recorder-title">Voice Input</div>
            <div className="recorder-sub">
              {recording ? (voice ? 'Voice detected ✅' : 'Listening…') : 'Tap to speak'}
            </div>
          </div>
        </div>

        <div className="recorder-actions">
          {speaking && (
            <span className="chip accent">
              <Volume2 size={14} /> Speaking
            </span>
          )}
          {!recording ? (
            <button onClick={start} disabled={disabled} className="btn btn-primary">
              Record
            </button>
          ) : (
            <button onClick={stop} className="btn btn-danger">
              <Square size={14} /> Stop
            </button>
          )}
        </div>
      </div>
      <div className="recorder-meter">
        <canvas ref={canvasRef} width={900} height={90} className="w-full" />
      </div>
    </div>
  )
}
