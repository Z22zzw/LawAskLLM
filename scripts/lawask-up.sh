#!/usr/bin/env bash
# LawAskLLM：后台启动全栈（SSH 断开后仍运行，依赖容器 restart 策略）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

echo "==> 宿主机 Nginx 应将 49.235.100.186:80 反代到 127.0.0.1:18080（见 deploy/nginx-host-lawaskllm.conf）"
echo "==> 检查本机 18080（law_nginx）是否在构建完成后已监听："
if command -v ss >/dev/null 2>&1; then
  ss -tlnp | grep -E ':18080\s' || true
fi

echo "==> 构建并启动（-d 后台）..."
"${DC[@]}" up -d --build

PUB_IP="${LAWASK_PUBLIC_IP:-49.235.100.186}"
echo ""
echo "=== LawAskLLM 已启动（detach）==="
echo "  前端登录:     http://${PUB_IP}/login"
echo "  对话页面:     http://${PUB_IP}/chat"
echo "  知识库管理:   http://${PUB_IP}/kb"
echo "  实验对照:     http://${PUB_IP}/experiments"
echo "  API 文档:     http://${PUB_IP}/api/docs"
echo ""
echo "默认管理员（仅首次无 superadmin 时自动创建）: admin / Admin@123456"
echo "MySQL root 密码见 .env 中 MYSQL_PASSWORD（默认常与 compose 一致）"
echo "日志: $ROOT/scripts/lawask-logs.sh"
echo "停止: $ROOT/scripts/lawask-down.sh"
