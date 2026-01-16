import React from 'react'
import type { DebugLog } from '../lib/api'

export type ToolEvt =
  | { kind: 'agent_event'; name: string; payload?: any }
  | { kind: 'stt'; name: string; payload?: any }
  | { kind: 'tool_call'; name: string; payload?: any }
  | { kind: 'tool_result'; name: string; payload?: any }

type Props = {
  events: ToolEvt[]
  logs?: DebugLog[]
}

const formatTime = (ts: number) =>
  new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export default function ToolTimeline({ events, logs = [] }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <div className="debug-section-title">Tool Timeline</div>
        {events.slice(-60).map((e, idx) => (
          <div key={idx} className="debug-item">
            <div className="debug-header">
              <div>
                <span className="debug-kind">{e.kind}</span> <span className="debug-mono">{e.name}</span>
              </div>
            </div>
            {e.payload !== undefined && <pre className="debug-mono debug-payload">{JSON.stringify(e.payload, null, 2)}</pre>}
          </div>
        ))}
      </div>

      <div>
        <div className="debug-section-title">Client Logs</div>
        {logs.slice(-80).map((log, idx) => (
          <div key={idx} className="debug-item">
            <div className="debug-header">
              <div className="debug-mono">{formatTime(log.ts)}</div>
              <div className={`log-level ${log.level}`}>{log.level}</div>
            </div>
            <div className="debug-header">
              <div className="debug-kind">{log.event}</div>
              <div className="debug-mono">{log.message}</div>
            </div>
            {log.payload !== undefined && (
              <pre className="debug-mono debug-payload">{JSON.stringify(log.payload, null, 2)}</pre>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
