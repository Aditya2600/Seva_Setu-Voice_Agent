import React from 'react'

type SchemeCardProps = {
  title?: string
  category?: string
  benefits?: string
  documents?: string[]
}

export default function SchemeCard({
  title = 'Scheme',
  category,
  benefits,
  documents = [],
}: SchemeCardProps) {
  const docList = documents.filter(Boolean)
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4 shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-100">{title}</div>
          {category && <div className="text-xs text-slate-400 mt-0.5">{category}</div>}
        </div>
        <div className="text-[11px] text-sky-300 border border-sky-500/30 bg-sky-500/10 rounded-full px-2 py-0.5">
          Scheme
        </div>
      </div>

      {benefits && (
        <div className="mt-3 text-sm text-slate-300 whitespace-pre-wrap">{benefits}</div>
      )}

      {docList.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-slate-400 mb-1">Documents</div>
          <div className="flex flex-wrap gap-2">
            {docList.map((doc, idx) => (
              <span
                key={`${doc}-${idx}`}
                className="text-xs text-slate-300 border border-slate-800 bg-slate-950/60 rounded-full px-2 py-0.5"
              >
                {doc}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
