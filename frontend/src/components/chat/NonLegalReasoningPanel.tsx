import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

export interface IntentRouteInfo {
  intent?: string
  routed_by?: string
  route_reason?: string
  search_queries?: string[]
  needs_clarification?: boolean
  allow_common_sense?: boolean
}

interface Props {
  intentRoute: IntentRouteInfo
  traceSteps: string[]
}

export default function NonLegalReasoningPanel({ intentRoute, traceSteps }: Props) {
  const [open, setOpen] = useState(true)
  const [traceOpen, setTraceOpen] = useState(true)

  return (
    <div className="mb-4 max-w-[min(100%,42rem)] rounded-lg border border-border-cream bg-warm-sand/40 px-4 py-3">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-xs font-medium uppercase tracking-wide text-olive-gray">非法律问题 · 处理说明</span>
        {open ? <ChevronUp size={14} className="text-stone-gray" /> : <ChevronDown size={14} className="text-stone-gray" />}
      </button>
      {open && (
        <div className="mt-3 space-y-3 text-sm text-olive-gray leading-relaxed">
          {(intentRoute.route_reason || intentRoute.routed_by) && (
            <div className="rounded-md border border-border-cream bg-ivory/90 px-3 py-2">
              {intentRoute.routed_by ? (
                <p><span className="text-stone-gray">路由方式：</span>{intentRoute.routed_by}</p>
              ) : null}
              {intentRoute.route_reason ? (
                <p className="mt-1"><span className="text-stone-gray">说明：</span>{intentRoute.route_reason}</p>
              ) : null}
            </div>
          )}
          <button
            type="button"
            onClick={() => setTraceOpen(v => !v)}
            className="flex w-full items-center justify-between text-xs font-medium text-deep-dark"
          >
            <span>推理步骤（{traceSteps.length}）</span>
            {traceOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {traceOpen && traceSteps.length > 0 && (
            <ol className="space-y-2 border-l-2 border-terracotta/40 pl-3 ml-0.5">
              {traceSteps.map((step, i) => (
                <li key={i} className="text-xs text-stone-gray relative">
                  <span className="absolute -left-[calc(0.75rem+2px)] top-1.5 h-1.5 w-1.5 rounded-full bg-terracotta/80" />
                  {step}
                </li>
              ))}
            </ol>
          )}
          {traceSteps.length === 0 && (
            <p className="text-xs text-stone-gray">暂无链式追踪文本。</p>
          )}
        </div>
      )}
    </div>
  )
}
