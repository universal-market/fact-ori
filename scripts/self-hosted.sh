#!/usr/bin/env bash
# Trusted maintainer only. Never run contributor code with deployment authority.
set -euo pipefail
cd "$(dirname "$0")/.."
compose=(docker compose --env-file /dev/null -f deploy/self-hosted/compose.yaml)
case "${1:-}" in
  operator)
    "${compose[@]}" exec -T backend ./generate_admin_key.sh |
      "${compose[@]}" run --rm -T deploy operator "$2" "$3"
    ;;
  outbox)
    "${compose[@]}" exec -T backend ./generate_admin_key.sh |
      "${compose[@]}" run --rm -T deploy operator checks:listQueued "{\"now\":$(date +%s000)}"
    ;;
  prepare)
    mkdir -p local/self-hosted
    python3 -B scripts/export_api_seed.py > local/self-hosted/seed.json
    "${compose[@]}" up -d backend inference
    for model in nomic-embed-text:v1.5 qwen2.5:14b-instruct; do
      "${compose[@]}" exec -T inference ollama pull "$model" >/dev/null 2>&1 || {
        printf 'Model download failed for %s\n' "$model"; exit 1;
      }
    done
    "${compose[@]}" build deploy semantic
    # Keep the instance-local key exclusively in a pipe and ephemeral container.
    # Do not add xtrace, tee, an env dump or a Docker socket mount.
    "${compose[@]}" exec -T backend ./generate_admin_key.sh |
      "${compose[@]}" run --rm -T deploy
    "${compose[@]}" up -d semantic
    # Rebind replaced configuration files: reload alone can retain an old inode.
    "${compose[@]}" up -d --force-recreate --no-deps gateway
    "${compose[@]}" exec -T gateway nginx -t
    "${compose[@]}" exec -T gateway nginx -s reload
    node --input-type=module -e '
      import {engineFingerprint} from "./service/engine.mjs";
      for (let attempt=0; attempt<60; attempt++) {
        try {
          const response=await fetch("http://127.0.0.1:43211/health");
          const health=await response.json();
          if (response.ok && health.status === "ready" && health.semantic_search === true &&
              health.claim_decomposition === true && health.engine_revision === engineFingerprint()) process.exit(0);
        } catch {}
        await new Promise(resolve=>setTimeout(resolve,2000));
      }
      throw new Error("Semantic API did not become ready");
    '
    node scripts/probe-public-api.mjs http://127.0.0.1:43211 --intake-enabled
    ;;
  publish)
    # Check effective mode and approved data WITHOUT attempting a queue write.
    node scripts/probe-public-api.mjs http://127.0.0.1:43211 --intake-enabled
    "${compose[@]}" --profile public up -d tunnel
    ;;
  status) "${compose[@]}" --profile public ps ;;
  stop) "${compose[@]}" --profile public stop tunnel gateway semantic inference backend ;;
  *) printf '%s\n' 'Usage: bash scripts/self-hosted.sh prepare|publish|outbox|operator FUNCTION JSON|status|stop'; exit 2 ;;
esac
