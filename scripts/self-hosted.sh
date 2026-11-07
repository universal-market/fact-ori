#!/usr/bin/env bash
# Trusted maintainer only. Never run contributor code with deployment authority.
set -euo pipefail
cd "$(dirname "$0")/.."
compose=(docker compose --env-file /dev/null -f deploy/self-hosted/compose.yaml)
case "${1:-}" in
  prepare)
    mkdir -p local/self-hosted
    python3 -B scripts/export_api_seed.py > local/self-hosted/seed.json
    "${compose[@]}" up -d backend gateway
    "${compose[@]}" build deploy
    # Keep the instance-local key exclusively in a pipe and ephemeral container.
    # Do not add xtrace, tee, an env dump or a Docker socket mount.
    "${compose[@]}" exec -T backend ./generate_admin_key.sh |
      "${compose[@]}" run --rm -T deploy
    node scripts/probe-public-api.mjs http://127.0.0.1:43211
    ;;
  publish)
    # Check effective mode and approved data WITHOUT attempting a queue write.
    node scripts/probe-public-api.mjs http://127.0.0.1:43211
    "${compose[@]}" --profile public up -d tunnel
    ;;
  status) "${compose[@]}" --profile public ps ;;
  stop) "${compose[@]}" --profile public stop tunnel gateway backend ;;
  *) printf '%s\n' 'Usage: bash scripts/self-hosted.sh prepare|publish|status|stop'; exit 2 ;;
esac
