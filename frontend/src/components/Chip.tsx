import React from 'react'

type ChipProps = {
  children: React.ReactNode
  className?: string
}

export default function Chip({ children, className = '' }: ChipProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-[11px] text-slate-300 ${className}`}
    >
      {children}
    </span>
  )
}
