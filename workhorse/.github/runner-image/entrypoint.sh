#!/usr/bin/env bash
# Register this container as a self-hosted GitHub Actions runner with the "gpu"
# label, then run it. Non-interactive (--unattended) so `docker compose up` works.
set -euo pipefail

cd /opt/actions-runner

if [ ! -f .runner ]; then
  ./config.sh \
    --url "${RUNNER_URL}" \
    --token "${RUNNER_TOKEN}" \
    --labels gpu \
    --unattended
fi

exec ./run.sh
