import { Citation, LEGAL_DOMAINS } from '../../types'
import clsx from 'clsx'

const RELEVANCE_BADGE: Record<string, string> = {
  strong:    'badge-green',
  weak:      'badge-warm',
  unrelated: 'bg-stone-gray/10 text-stone-gray badge',
}
const RELEVANCE_LABEL: Record<string, string> = {
  strong: '强相关', weak: '弱相关', unrelated: '无关',
}

interface Props { citations: Citation[] }

export default function CitationPanel({ citations }: Props) {
  if (!citations.length) return (
    <div className="text-sm text-stone-gray text-center py-8">
      本轮未命中知识库证据
    </div>
  )

  return (
    <div className="space-y-3">
      {citations.map((c, i) => {
        const domain = LEGAL_DOMAINS.find(d => d.code === c.legal_domain)?.label || c.legal_domain
        const badge = RELEVANCE_BADGE[c.relevance] || 'badge-warm'
        const label = RELEVANCE_LABEL[c.relevance] || c.relevance
        return (
          <div key={i} className="citation-card">
            <div className="flex items-start justify-between gap-2 mb-1.5">
              <div className="flex flex-wrap gap-1">
                <span className="badge-terra">{c.dataset === 'jec-qa' ? 'JEC-QA' : c.dataset === 'cail2018' ? 'CAIL2018' : '文档'}</span>
                {domain && <span className="badge-warm">{domain}</span>}
                {c.source_name && <span className="text-xs text-stone-gray">{c.source_name}</span>}
              </div>
              {c.relevance && <span className={clsx(badge, 'flex-shrink-0')}>{label}</span>}
            </div>
            <p className="text-stone-gray text-xs leading-relaxed line-clamp-3">{c.snippet}</p>
          </div>
        )
      })}
    </div>
  )
}
