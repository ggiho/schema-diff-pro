'use client'

import dynamic from 'next/dynamic'
import { useState } from 'react'
import { Button } from './ui/button'

const DiffEditor = dynamic(
  () => import('@monaco-editor/react').then((mod) => mod.DiffEditor),
  { ssr: false }
)

interface DiffViewerProps {
  original: string
  modified: string
  language?: string
}

export function DiffViewer({ original, modified, language = 'sql' }: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<'side-by-side' | 'inline'>('side-by-side')

  return (
    <div className="h-[600px] space-y-4">
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setViewMode(viewMode === 'side-by-side' ? 'inline' : 'side-by-side')}
        >
          {viewMode === 'side-by-side' ? 'Inline View' : 'Side by Side'}
        </Button>
      </div>

      <div className="h-full rounded-lg border overflow-hidden">
        <DiffEditor
          original={original}
          modified={modified}
          language={language}
          theme="vs-dark"
          options={{
            readOnly: true,
            renderSideBySide: viewMode === 'side-by-side',
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 14,
          }}
        />
      </div>
    </div>
  )
}