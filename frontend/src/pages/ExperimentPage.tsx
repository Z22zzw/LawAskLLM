import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Clock, Loader2, FlaskConical, History } from 'lucide-react'
import { api } from '../lib/api'
import { LEGAL_DOMAINS } from '../types'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface PresetRow {
  id: string
  group: string
  name: string
  description: string
}

interface CompareArm {
  preset_id: string
  label: string
  group: string
  latency_ms: number
  citation_count: number
  answer_length: number
  intent: string
  skipped_retrieval?: boolean
  answer: string
  chain_trace_len: number
  llm_accuracy?: number | null
  llm_evidence?: number | null
  llm_explainability?: number | null
  llm_stability?: number | null
  llm_note?: string | null
}

interface CompareArmAnalysis {
  preset_id: string
  label: string
  group: string
  llm_avg: number | null
  latency_ms: number
  latency_score_0_1: number
  citation_count: number
  citation_score_0_1: number
  chain_trace_len: number
  trace_score_0_1: number
  composite_0_1: number
  rank_composite: number
}

interface CompareAnalysis {
  arms_analysis: CompareArmAnalysis[]
  recommendation: string
  best_for_quality_preset_id?: string | null
  best_for_speed_preset_id?: string | null
  best_balanced_preset_id?: string | null
}

interface CompareResult {
  question: string
  legal_domain: string
  arms: CompareArm[]
  llm_score_note?: string | null
  run_id?: number | null
  analysis?: CompareAnalysis | null
}

interface ExperimentHistoryItem {
  id: number
  question_preview: string
  legal_domain: string
  preset_ids: string[]
  arm_count: number
  llm_score_enabled: boolean
  created_at: string
  best_balanced_label?: string | null
}

const RADAR_COLORS = ['#c96442', '#5e5d59', '#3898ec', '#87867f']

function buildRadarData(arms: CompareArm[]) {
  const labels = ['准确性', '证据', '可解释', '稳定']
  const keys: (keyof CompareArm)[] = ['llm_accuracy', 'llm_evidence', 'llm_explainability', 'llm_stability']
  return labels.map((dimension, i) => {
    const row: Record<string, string | number> = { dimension }
    arms.forEach((a, j) => {
      const v = a[keys[i]]
      row[`arm${j}`] = typeof v === 'number' ? v : 0
    })
    return row
  })
}

function hasAnyLlmScores(arms: CompareArm[]) {
  return arms.some(
    (a) =>
      typeof a.llm_accuracy === 'number' ||
      typeof a.llm_evidence === 'number' ||
      typeof a.llm_explainability === 'number' ||
      typeof a.llm_stability === 'number'
  )
}

const EVAL_HINTS = [
  { name: '准确性', desc: '结论是否与法律事实/规则一致。', rule: '0–2 错误；3 部分正确；4–5 基本/完全正确。' },
  { name: '证据充分性', desc: '结论是否有足够证据支撑。', rule: '0–2 无证据或错配；3 不充分；4–5 充分且对应明确。' },
  { name: '可解释性', desc: '是否区分知识库证据与通用知识。', rule: '0–2 无法追溯；3 部分；4–5 可追溯且边界清晰。' },
  { name: '稳定性', desc: '异常场景下是否稳定返回可用结果。', rule: '0–2 频繁失败；3 偶发；4–5 稳定。' },
]

export default function ExperimentPage() {
  const [matrix, setMatrix] = useState<PresetRow[]>([])
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [question, setQuestion] = useState('')
  const [domain, setDomain] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CompareResult | null>(null)
  const [chartMetric, setChartMetric] = useState<
    'latency_ms' | 'citation_count' | 'llm_avg' | 'composite_0_1'
  >('composite_0_1')
  const [enableLlmScore, setEnableLlmScore] = useState(true)
  const [historyItems, setHistoryItems] = useState<ExperimentHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activeHistoryId, setActiveHistoryId] = useState<number | null>(null)

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const { data } = await api.get<ExperimentHistoryItem[]>('/experiments/compare/history', { params: { limit: 50 } })
      setHistoryItems(Array.isArray(data) ? data : [])
    } catch {
      setHistoryItems([])
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    api.get('/experiments/presets').then((r) => {
      const m = (r.data.matrix || []) as PresetRow[]
      setMatrix(m)
      const sel: Record<string, boolean> = {}
      m.forEach((row) => { sel[row.id] = ['baseline_rag_basic', 'system_full'].includes(row.id) })
      setSelected(sel)
    }).catch(() => setMatrix([]))
    loadHistory()
  }, [loadHistory])

  const chartData = useMemo(() => {
    if (!result?.arms) return []
    const byId = new Map((result.analysis?.arms_analysis || []).map((x) => [x.preset_id, x]))
    return result.arms.map((a) => {
      const dims = [a.llm_accuracy, a.llm_evidence, a.llm_explainability, a.llm_stability].filter(
        (x): x is number => typeof x === 'number'
      )
      const llm_avg = dims.length ? Math.round((dims.reduce((s, x) => s + x, 0) / dims.length) * 10) / 10 : 0
      const an = byId.get(a.preset_id)
      return {
        name: a.label.length > 14 ? `${a.label.slice(0, 12)}…` : a.label,
        fullLabel: a.label,
        latency_ms: a.latency_ms,
        citation_count: a.citation_count,
        answer_length: a.answer_length,
        llm_avg,
        composite_0_1: an ? Math.round(an.composite_0_1 * 1000) / 1000 : 0,
      }
    })
  }, [result])

  const openHistoryRun = async (id: number) => {
    setHistoryLoading(true)
    setActiveHistoryId(id)
    try {
      const { data } = await api.get<CompareResult>(`/experiments/compare/history/${id}`)
      setResult(data)
      setQuestion(data.question || '')
      setDomain(data.legal_domain || '')
    } catch {
      alert('加载历史记录失败')
    } finally {
      setHistoryLoading(false)
    }
  }

  const runCompare = async () => {
    const ids = matrix.filter((m) => selected[m.id]).map((m) => m.id)
    if (ids.length < 2) {
      alert('请至少勾选 2 个预设')
      return
    }
    if (!question.trim()) {
      alert('请输入对照问题')
      return
    }
    setLoading(true)
    setResult(null)
    setActiveHistoryId(null)
    try {
      const { data } = await api.post<CompareResult>(
        '/experiments/compare',
        {
          question: question.trim(),
          legal_domain: domain,
          preset_ids: ids,
          llm_score: enableLlmScore,
        },
        { timeout: 900_000 }
      )
      setResult(data)
      if (data.run_id) setActiveHistoryId(data.run_id)
      loadHistory()
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '对照失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-parchment p-6 md:p-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex items-start gap-3">
          <div className="rounded-lg bg-terracotta/10 p-2.5 text-terracotta">
            <FlaskConical size={22} />
          </div>
          <div>
            <h1 className="font-serif text-2xl text-deep-dark">实验对照</h1>
            <p className="text-sm text-stone-gray mt-1 max-w-2xl leading-relaxed">
              并行跑多预设对照，自动保存历史；提供归一化分析、雷达图与综合分柱状图，并给出如何择优的说明。
            </p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1 space-y-4">
            <div className="card p-4">
              <div className="flex items-center gap-2 text-deep-dark mb-2">
                <History size={16} className="text-terracotta" />
                <h2 className="font-serif text-sm font-medium">历史记录</h2>
              </div>
              <p className="text-[11px] text-stone-gray mb-2 leading-relaxed">
                点击恢复该次对照的问题、分析与各臂回答（只读快照）。
              </p>
              <button
                type="button"
                className="btn-secondary text-xs py-1 px-2 mb-2"
                onClick={() => loadHistory()}
                disabled={historyLoading}
              >
                刷新列表
              </button>
              <div className="max-h-52 overflow-y-auto space-y-1.5 border-t border-border-cream pt-2">
                {historyItems.length === 0 && !historyLoading && (
                  <p className="text-xs text-stone-gray">暂无记录，运行一次对照后会自动保存。</p>
                )}
                {historyItems.map((h) => (
                  <button
                    key={h.id}
                    type="button"
                    onClick={() => openHistoryRun(h.id)}
                    className={`w-full text-left rounded-md border px-2 py-1.5 text-xs transition-colors ${
                      activeHistoryId === h.id
                        ? 'border-terracotta bg-terracotta/10 text-deep-dark'
                        : 'border-border-cream bg-ivory hover:bg-warm-sand/50 text-olive-gray'
                    }`}
                  >
                    <span className="flex items-center gap-1 text-stone-gray text-[10px]">
                      <Clock size={10} />
                      {h.created_at.replace('T', ' ').slice(0, 16)}
                      {h.llm_score_enabled ? '' : ' · 无LLM分'}
                    </span>
                    <span className="block text-deep-dark mt-0.5 line-clamp-2">{h.question_preview}</span>
                    {h.best_balanced_label && (
                      <span className="text-[10px] text-stone-gray mt-0.5 block">综合推荐：{h.best_balanced_label}</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
            <div className="card p-4">
              <label className="text-xs text-stone-gray block mb-1">法律领域</label>
              <select value={domain} onChange={(e) => setDomain(e.target.value)} className="input text-sm w-full">
                {LEGAL_DOMAINS.map((d) => (
                  <option key={d.code} value={d.code}>{d.label}</option>
                ))}
              </select>
            </div>
            <div className="card p-4 max-h-[min(70vh,520px)] overflow-y-auto">
              <p className="text-xs font-medium text-olive-gray mb-3">实验预设（按组多选）</p>
              {['baseline', 'strategy', 'ablation'].map((grp) => {
                const rows = matrix.filter((m) => m.group === grp)
                if (!rows.length) return null
                return (
                  <div key={grp} className="mb-4">
                    <p className="text-[10px] uppercase tracking-wider text-stone-gray mb-2">{grp}</p>
                    <ul className="space-y-2">
                      {rows.map((row) => (
                        <li key={row.id}>
                          <label className="flex gap-2 text-xs text-deep-dark cursor-pointer leading-snug">
                            <input
                              type="checkbox"
                              className="mt-0.5 rounded border-border-warm"
                              checked={!!selected[row.id]}
                              onChange={(e) => setSelected((s) => ({ ...s, [row.id]: e.target.checked }))}
                            />
                            <span>
                              <span className="font-medium">{row.name}</span>
                              {row.description && (
                                <span className="block text-stone-gray mt-0.5">{row.description}</span>
                              )}
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <div className="card p-4">
              <label className="text-xs text-stone-gray block mb-1">对照问题</label>
              <textarea
                className="input w-full min-h-[100px] text-sm"
                placeholder="输入同一道法律或场景问题…"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
              <label className="mt-3 flex items-center gap-2 text-xs text-olive-gray cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-border-warm"
                  checked={enableLlmScore}
                  onChange={(e) => setEnableLlmScore(e.target.checked)}
                />
                启用大模型四维评分（准确性 / 证据 / 可解释性 / 稳定性，0–5）
              </label>
              <button
                type="button"
                onClick={runCompare}
                disabled={loading}
                className="btn-primary mt-3 inline-flex items-center gap-2"
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                运行对照
              </button>
            </div>

            {result && (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs text-stone-gray">
                  {result.run_id != null && result.run_id !== undefined && (
                    <span className="rounded-md border border-border-cream bg-ivory px-2 py-1">
                      已保存记录 #{result.run_id}
                    </span>
                  )}
                  <span className="text-olive-gray">
                    领域：{result.legal_domain || '（综合）'} · {result.arms.length} 臂对照
                  </span>
                </div>
                {result.llm_score_note && (
                  <div className="rounded-lg border border-border-warm bg-ivory px-3 py-2 text-xs text-olive-gray">
                    {result.llm_score_note}
                  </div>
                )}

                {result.analysis && (
                  <div className="card p-4 border-l-4 border-l-terracotta">
                    <h2 className="font-serif text-lg text-deep-dark mb-2">如何选择更优秀</h2>
                    <p className="text-[11px] text-stone-gray mb-3 leading-relaxed">
                      以下为基于本次各臂数据的<strong>横向归一化</strong>与默认权重给出的参考结论，不构成法律意见；
                      最终仍应结合业务场景、合规要求与人工抽检。
                    </p>
                    <div className="prose-law text-sm text-olive-gray leading-relaxed max-h-72 overflow-y-auto">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.analysis.recommendation}</ReactMarkdown>
                    </div>
                  </div>
                )}

                {result.analysis && result.analysis.arms_analysis.length > 0 && (
                  <div className="card p-4">
                    <h2 className="font-serif text-lg text-deep-dark mb-2">归一化与综合排名</h2>
                    <p className="text-[11px] text-stone-gray mb-3">
                      「速度分」「引用分」「链深度分」均为本次对照内的相对值（0–1，越高越好）；延迟为绝对毫秒。
                      综合分按后端公式将质量（大模型均分）与上述相对指标加权合成，排名 1 为综合推荐。
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left border-collapse">
                        <thead>
                          <tr className="border-b border-border-cream text-stone-gray">
                            <th className="py-2 pr-2 font-medium">排名</th>
                            <th className="py-2 pr-2 font-medium">预设</th>
                            <th className="py-2 pr-2 font-medium">综合分</th>
                            <th className="py-2 pr-2 font-medium">LLM均分</th>
                            <th className="py-2 pr-2 font-medium">延迟</th>
                            <th className="py-2 pr-2 font-medium">速度分</th>
                            <th className="py-2 pr-2 font-medium">引用</th>
                            <th className="py-2 pr-2 font-medium">引用分</th>
                            <th className="py-2 pr-2 font-medium">链步骤</th>
                            <th className="py-2 font-medium">链深度分</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...result.analysis.arms_analysis]
                            .sort((a, b) => a.rank_composite - b.rank_composite)
                            .map((row) => (
                              <tr
                                key={row.preset_id}
                                className="border-b border-border-cream/80 text-charcoal odd:bg-ivory/60"
                              >
                                <td className="py-1.5 pr-2 font-medium text-deep-dark">{row.rank_composite}</td>
                                <td className="py-1.5 pr-2 max-w-[140px] truncate" title={row.label}>{row.label}</td>
                                <td className="py-1.5 pr-2">{row.composite_0_1}</td>
                                <td className="py-1.5 pr-2">{row.llm_avg ?? '—'}</td>
                                <td className="py-1.5 pr-2">{row.latency_ms} ms</td>
                                <td className="py-1.5 pr-2">{row.latency_score_0_1}</td>
                                <td className="py-1.5 pr-2">{row.citation_count}</td>
                                <td className="py-1.5 pr-2">{row.citation_score_0_1}</td>
                                <td className="py-1.5 pr-2">{row.chain_trace_len}</td>
                                <td className="py-1.5">{row.trace_score_0_1}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {hasAnyLlmScores(result.arms) && (
                  <div className="card p-4">
                    <h2 className="font-serif text-lg text-deep-dark mb-1">大模型四维雷达（0–5）</h2>
                    <p className="text-[11px] text-stone-gray mb-3">缺维时按 0 绘制；仅作同题多臂形状对比。</p>
                    <div className="h-72 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart data={buildRadarData(result.arms)} cx="50%" cy="50%" outerRadius="78%">
                          <PolarGrid stroke="#e8e6dc" />
                          <PolarAngleAxis dataKey="dimension" tick={{ fill: '#5e5d59', fontSize: 11 }} />
                          <PolarRadiusAxis angle={30} domain={[0, 5]} tick={{ fill: '#87867f', fontSize: 10 }} />
                          <Tooltip contentStyle={{ background: '#faf9f5', border: '1px solid #f0eee6', borderRadius: 8 }} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          {result.arms.map((a, j) => (
                            <Radar
                              key={a.preset_id}
                              name={a.label.length > 10 ? `${a.label.slice(0, 8)}…` : a.label}
                              dataKey={`arm${j}`}
                              stroke={RADAR_COLORS[j % RADAR_COLORS.length]}
                              fill={RADAR_COLORS[j % RADAR_COLORS.length]}
                              fillOpacity={0.12}
                            />
                          ))}
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                <div className="card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                    <h2 className="font-serif text-lg text-deep-dark">柱状图对比</h2>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <button
                        type="button"
                        className={chartMetric === 'composite_0_1' ? 'btn-primary py-1 px-2' : 'btn-secondary py-1 px-2'}
                        onClick={() => setChartMetric('composite_0_1')}
                      >
                        综合分 (0–1)
                      </button>
                      <button
                        type="button"
                        className={chartMetric === 'latency_ms' ? 'btn-primary py-1 px-2' : 'btn-secondary py-1 px-2'}
                        onClick={() => setChartMetric('latency_ms')}
                      >
                        延迟 (ms)
                      </button>
                      <button
                        type="button"
                        className={chartMetric === 'citation_count' ? 'btn-primary py-1 px-2' : 'btn-secondary py-1 px-2'}
                        onClick={() => setChartMetric('citation_count')}
                      >
                        引用条数
                      </button>
                      <button
                        type="button"
                        className={chartMetric === 'llm_avg' ? 'btn-primary py-1 px-2' : 'btn-secondary py-1 px-2'}
                        onClick={() => setChartMetric('llm_avg')}
                      >
                        大模型均分
                      </button>
                    </div>
                  </div>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e8e6dc" />
                        <XAxis dataKey="name" tick={{ fill: '#87867f', fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={60} />
                        <YAxis tick={{ fill: '#87867f', fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{ background: '#faf9f5', border: '1px solid #f0eee6', borderRadius: 8 }}
                          formatter={(v: number) => [
                            v,
                            chartMetric === 'latency_ms'
                              ? 'ms'
                              : chartMetric === 'citation_count'
                                ? '条'
                                : chartMetric === 'composite_0_1'
                                  ? '综合分'
                                  : '分',
                          ]}
                          labelFormatter={(_, p) => (p?.[0]?.payload?.fullLabel as string) || ''}
                        />
                        <Legend />
                        <Bar
                          dataKey={chartMetric}
                          fill="#c96442"
                          name={
                            chartMetric === 'latency_ms'
                              ? '耗时(ms)'
                              : chartMetric === 'citation_count'
                                ? '引用数'
                                : chartMetric === 'composite_0_1'
                                  ? '综合分(0–1)'
                                  : '大模型均分(0–5)'
                          }
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="card p-4">
                  <h2 className="font-serif text-lg text-deep-dark mb-3">各预设回答</h2>
                  <div className="space-y-4">
                    {result.arms.map((a) => (
                      <div key={a.preset_id} className="rounded-lg border border-border-cream bg-ivory/80 p-4">
                        <div className="flex flex-wrap gap-2 text-xs text-stone-gray mb-2">
                          <span className="badge-warm">{a.group}</span>
                          <span>{a.latency_ms} ms</span>
                          <span>引用 {a.citation_count}</span>
                          <span>意图 {a.intent || '—'}</span>
                          <span>链步骤 {a.chain_trace_len}</span>
                        </div>
                        {(typeof a.llm_accuracy === 'number' ||
                          typeof a.llm_evidence === 'number' ||
                          typeof a.llm_explainability === 'number' ||
                          typeof a.llm_stability === 'number') && (
                          <div className="mb-2 rounded-md bg-warm-sand/40 px-2 py-1.5 text-[11px] text-charcoal leading-relaxed">
                            <span className="font-medium text-deep-dark">大模型评分：</span>
                            准确性 {a.llm_accuracy ?? '—'} · 证据 {a.llm_evidence ?? '—'} · 可解释性{' '}
                            {a.llm_explainability ?? '—'} · 稳定性 {a.llm_stability ?? '—'}
                            {a.llm_note && (
                              <span className="block text-stone-gray mt-1 border-t border-border-cream pt-1">{a.llm_note}</span>
                            )}
                          </div>
                        )}
                        <p className="text-sm font-medium text-deep-dark mb-2">{a.label}</p>
                        <div className="prose-law text-sm text-olive-gray max-h-64 overflow-y-auto border-t border-border-cream pt-2">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{a.answer || '（空）'}</ReactMarkdown>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            <div className="card p-4">
              <h2 className="font-serif text-lg text-deep-dark mb-2">人工评分说明（参考）</h2>
              <ul className="space-y-2 text-xs text-olive-gray leading-relaxed">
                {EVAL_HINTS.map((h) => (
                  <li key={h.name} className="border-b border-border-cream pb-2 last:border-0">
                    <span className="font-medium text-deep-dark">{h.name}</span>：{h.desc}
                    <span className="text-stone-gray block mt-0.5">{h.rule}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
