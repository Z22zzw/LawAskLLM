const KB_INDEX_KEY = 'kb_index_job'
const DATASET_BUILD_KEY = 'dataset_build_job_id'

type KbIndexPayload = {
  kbId: number
  jobId: string
}

export function persistKbIndexJob(kbId: number, jobId: string) {
  localStorage.setItem(KB_INDEX_KEY, JSON.stringify({ kbId, jobId } satisfies KbIndexPayload))
}

export function getKbIndexJob(): KbIndexPayload | null {
  const raw = localStorage.getItem(KB_INDEX_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as KbIndexPayload
    if (typeof parsed?.kbId === 'number' && typeof parsed?.jobId === 'string') return parsed
    return null
  } catch {
    return null
  }
}

export function clearKbIndexJob() {
  localStorage.removeItem(KB_INDEX_KEY)
}

export function persistDatasetBuildJob(jobId: string) {
  localStorage.setItem(DATASET_BUILD_KEY, jobId)
}

export function getDatasetBuildJobId(): string | null {
  return localStorage.getItem(DATASET_BUILD_KEY)
}

export function clearDatasetBuildJob() {
  localStorage.removeItem(DATASET_BUILD_KEY)
}
