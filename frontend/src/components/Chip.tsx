import React from 'react'

type ChipProps = {
  children: React.ReactNode
  className?: string
}

export default function Chip({ children, className = '' }: ChipProps) {
  return (
    <span
      className={`chip ${className}`}
    >
      {children}
    </span>
  )
}
