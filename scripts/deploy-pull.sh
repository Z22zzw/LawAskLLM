#!/usr/bin/env bash
# 生产机定时拉取部署：仅在有新提交时执行 rebuild（避免空转 docker compose）
set -euo pipefail

ROOT_DIR="${1:-${LAWASK_ROOT:-/data/LawAskLLM}}"
BRANCH="${2:-main}"

cd "$ROOT_DIR"

git remote update --prune origin
if ! git rev-parse "refs/remotes/origin/${BRANCH}" >/dev/null 2>&1; then
  echo "==> Error: no origin/${BRANCH}. Check git remote and default branch."
  exit 1
fi

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "refs/remotes/origin/${BRANCH}")"
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "==> Pull deploy: already on origin/${BRANCH} (${LOCAL:0:7}), skip."
  exit 0
fi

echo "==> Pull deploy: ${LOCAL:0:7} -> ${REMOTE:0:7}, running deploy-prod..."
exec bash "$ROOT_DIR/scripts/deploy-prod.sh" "$ROOT_DIR" "$BRANCH"
