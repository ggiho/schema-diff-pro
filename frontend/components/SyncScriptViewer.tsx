'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import { Button } from './ui/button'
import { Copy, Download } from 'lucide-react'
import { toast } from 'react-hot-toast'

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

interface SyncScriptViewerProps {
  script: string
}

export function SyncScriptViewer({ script }: SyncScriptViewerProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(script)
      toast.success('Script copied to clipboard')
    } catch (error) {
      toast.error('Failed to copy script')
    }
  }

  const downloadScript = () => {
    const blob = new Blob([script], { type: 'text/sql' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'sync_script.sql'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={`flex flex-col ${isFullscreen ? 'fixed inset-0 z-50 bg-background' : 'h-[600px]'}`}>
      <div className="flex items-center justify-between border-b p-4">
        <h3 className="text-lg font-semibold">SQL Sync Script</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={copyToClipboard}>
            <Copy className="mr-2 h-4 w-4" />
            Copy
          </Button>
          <Button variant="outline" size="sm" onClick={downloadScript}>
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsFullscreen(!isFullscreen)}
          >
            {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          </Button>
        </div>
      </div>

      <div className="flex-1">
        <MonacoEditor
          language="sql"
          theme="vs-dark"
          value={script}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 14,
            lineNumbers: 'on',
            wordWrap: 'on',
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  )
}