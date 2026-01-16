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
    <div className="scheme-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="scheme-title">{title}</div>
          {category && <div className="scheme-meta">{category}</div>}
        </div>
        <div className="scheme-badge">Scheme</div>
      </div>

      {benefits && <div className="scheme-benefits">{benefits}</div>}

      {docList.length > 0 && (
        <div className="mt-3">
          <div className="scheme-docs-title">Documents</div>
          <div className="flex flex-wrap gap-2">
            {docList.map((doc, idx) => (
              <span key={`${doc}-${idx}`} className="scheme-doc">
                {doc}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
