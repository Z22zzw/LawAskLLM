import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { Message } from '../../types'
import CitationPanel from './CitationPanel'
import clsx from 'clsx'

interface Props {
  message: Message
  isStreaming?: boolean
}

export default function MessageBubble({ message, isStreaming }: Props) {
  const [showCites, setShowCites] = useState(false)
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="bubble-user">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start mb-4 gap-2">
      <div className={clsx('bubble-ai', isStreaming && 'streaming-cursor')}>
        <div className="prose-law text-sm text-deep-dark">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      </div>

      {!isStreaming && message.citations.length > 0 && (
        <div className="w-full max-w-[85%]">
          <button
            onClick={() => setShowCites(v => !v)}
            className="flex items-center gap-1.5 text-xs text-stone-gray hover:text-olive-gray transition-colors"
          >
            {showCites ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>参考了 {message.citations.length} 条知识库证据</span>
          </button>
          {showCites && (
            <div className="mt-2">
              <CitationPanel citations={message.citations} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
