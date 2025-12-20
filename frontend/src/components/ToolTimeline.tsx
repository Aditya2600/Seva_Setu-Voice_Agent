import React from 'react'
export type ToolEvt =
  | { kind:'agent_event'; name:string; payload?:any }
  | { kind:'stt'; name:string; payload?:any }
  | { kind:'tool_call'; name:string; payload?:any }
  | { kind:'tool_result'; name:string; payload?:any }

export default function ToolTimeline({ events }:{ events: ToolEvt[] }){
  return (
    <div className="space-y-2">
      <div className="text-xs font-mono text-slate-400">TOOL TIMELINE</div>
      {events.slice(-60).map((e,idx)=>(
        <div key={idx} className="rounded-xl border border-slate-800 bg-slate-900/40 p-2">
          <div className="text-xs text-slate-200"><span className="text-sky-300">{e.kind}</span>: <span className="font-mono">{e.name}</span></div>
          {e.payload!==undefined && <pre className="mt-1 text-[11px] text-slate-400 whitespace-pre-wrap break-words">{JSON.stringify(e.payload,null,2)}</pre>}
        </div>
      ))}
    </div>
  )
}
