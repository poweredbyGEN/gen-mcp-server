#!/usr/bin/env bash
# Deploy the HOSTED MCP server (mcp.gen.pro, gen-mcp-hosted.service on app-2)
# directly from this git repository — NOT from PyPI.
#
# Context (mav, 2026-07-30): the downloadable PyPI package is being retired;
# the official MCP is the hosted server only. Until 2026-07-30 the hosted venv
# was installed and drift-reconciled FROM PyPI (gen-api-sync
# redeploy_hosted_mcp: `pip install -U gen-mcp-server`), which froze hosted at
# the last published version (0.1.25) while the repo advanced. This script is
# the replacement install path: build a wheel from an exact merged SHA on the
# orchestrator box, push it to app-2, install into a versioned venv, and flip
# an atomic symlink. The third-party deps (fastmcp, httpx, build backend) still
# come from PyPI — only the gen-mcp-server package itself no longer does.
#
# Layout on app-2 (after the one-time `migrate-layout`):
#   /opt/gen-mcp-hosted/.venv            -> symlink to venvs/<active>
#   /opt/gen-mcp-hosted/venvs/<name>/    one venv per deployed version
#   /opt/gen-mcp-hosted/venvs/<name>/DEPLOY_SHA   provenance stamp
#   /opt/gen-mcp-hosted/previous-venv    rollback pointer (last active name)
#   /opt/gen-mcp-hosted/wheels/          pushed wheels
# The systemd unit keeps pointing at .venv, so activation is symlink+restart
# and rollback is the reverse — no unit edits per deploy.
#
# Usage (run on the orchestrator box, from a checkout of this repo):
#   scripts/deploy_hosted.sh build --sha <40-char-sha>     # build+stage, no traffic change
#   scripts/deploy_hosted.sh activate --sha <40-char-sha>  # flip staged venv live (restart)
#   scripts/deploy_hosted.sh rollback                      # flip back to previous-venv
#   scripts/deploy_hosted.sh migrate-layout                # one-time: real .venv -> symlink
#   scripts/deploy_hosted.sh status                        # what is staged/active/serving
#
# The SHA must be reachable from origin/main (merged code only). `build` never
# touches the live service; only `activate`, `rollback`, and `migrate-layout`
# restart it, and each verifies the MCP initialize handshake afterwards and
# auto-rolls-back on failure.
set -euo pipefail

readonly BOX="${HOSTED_MCP_BOX:-87.99.137.182}"
readonly BASE="/opt/gen-mcp-hosted"
readonly SERVICE="gen-mcp-hosted"
readonly PORT="${GEN_MCP_PORT:-8090}"
readonly STAGE_PORT="${GEN_MCP_STAGE_PORT:-8091}"
readonly SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=15)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR

usage() {
  cat >&2 <<'EOF'
usage (run on the orchestrator box, from a checkout of this repo):
  scripts/deploy_hosted.sh build --sha <40-char-sha>     # build+stage, no traffic change
  scripts/deploy_hosted.sh activate --sha <40-char-sha>  # flip staged venv live (restart)
  scripts/deploy_hosted.sh rollback                      # flip back to previous-venv
  scripts/deploy_hosted.sh migrate-layout                # one-time: real .venv -> symlink
  scripts/deploy_hosted.sh status                        # what is staged/active/serving
EOF
  exit 2
}

box() { ssh "${SSH_OPTS[@]}" "root@${BOX}" "$@"; }

die() { echo "ERROR: $*" >&2; exit 1; }

# MCP liveness = the initialize handshake answers 200 with a serverInfo block.
# (A bare GET/POST without Accept headers returns 406 even when healthy.)
verify_mcp() { # $1 = port (checked on the box, loopback)
  local body
  body=$(box "curl -s --max-time 10 -X POST http://127.0.0.1:$1/mcp \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -d '{\"jsonrpc\":\"2.0\",\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"deploy-verify\",\"version\":\"0\"}},\"id\":1}'") || return 1
  grep -q '"serverInfo"' <<<"$body"
}

require_sha() {
  [[ "${SHA:-}" =~ ^[0-9a-f]{40}$ ]] || die "need --sha <full 40-char sha>"
  git -C "$REPO_DIR" fetch origin --quiet
  git -C "$REPO_DIR" merge-base --is-ancestor "$SHA" origin/main \
    || die "sha $SHA is not reachable from origin/main — deploy merged code only"
}

venv_name_for_sha() { # version from pyproject AT that sha + short sha
  local ver
  ver=$(git -C "$REPO_DIR" show "$SHA:pyproject.toml" \
    | sed -n 's/^version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$ver" ] || die "cannot read version from pyproject.toml at $SHA"
  echo "v${ver}-${SHA:0:9}"
}

cmd_build() {
  require_sha
  local name scratch wheel
  name=$(venv_name_for_sha)
  # Big scratch belongs on disk, never on the tmpfs. Expand $scratch NOW
  # (double quotes): a deferred single-quoted expansion reads the local var
  # after it is out of scope at EXIT time, which under `set -u` turns a fully
  # successful build into exit 1 (and skips the cleanup).
  scratch=$(mktemp -d "${TMPDIR:-/mnt/data/tmp}/gen-mcp-build.XXXXXX")
  # shellcheck disable=SC2064
  trap "rm -rf '$scratch'" EXIT
  echo "build: exporting $SHA and building wheel in $scratch"
  git -C "$REPO_DIR" archive "$SHA" | tar -x -C "$scratch"
  python3 -m pip wheel --no-deps --wheel-dir "$scratch/dist" "$scratch" >/dev/null
  wheel=$(ls "$scratch"/dist/gen_mcp_server-*.whl) || die "wheel build produced no artifact"
  echo "build: staging $name on $BOX"
  box "mkdir -p $BASE/venvs $BASE/wheels"
  scp "${SSH_OPTS[@]}" -q "$wheel" "root@${BOX}:$BASE/wheels/"
  box "set -e
    rm -rf $BASE/venvs/$name
    python3 -m venv $BASE/venvs/$name
    $BASE/venvs/$name/bin/pip install --quiet $BASE/wheels/$(basename "$wheel")
    echo $SHA > $BASE/venvs/$name/DEPLOY_SHA
    $BASE/venvs/$name/bin/python -c 'import gen_mcp_server'"
  echo "build: boot-smoking staged venv on :$STAGE_PORT"
  box "ss -ltn 2>/dev/null | grep -q ':$STAGE_PORT '" \
    && die "stage port $STAGE_PORT is already in use on $BOX — refusing"
  box "GEN_MCP_HOST=127.0.0.1 GEN_MCP_PORT=$STAGE_PORT \
       nohup $BASE/venvs/$name/bin/gen-mcp-server --http >/tmp/gen-mcp-stage-smoke.log 2>&1 </dev/null & \
       echo \$! > /tmp/gen-mcp-stage-smoke.pid"
  sleep 4
  local ok=0
  verify_mcp "$STAGE_PORT" && ok=1
  box "kill \$(cat /tmp/gen-mcp-stage-smoke.pid) 2>/dev/null; rm -f /tmp/gen-mcp-stage-smoke.pid"
  [ "$ok" = 1 ] || die "staged venv $name failed the MCP initialize handshake (see /tmp/gen-mcp-stage-smoke.log on $BOX)"
  echo "build: OK — $name staged and boot-verified. Activate with:"
  echo "  scripts/deploy_hosted.sh activate --sha $SHA"
}

require_symlink_layout() {
  box "[ -L $BASE/.venv ]" \
    || die "$BASE/.venv is not a symlink — run 'migrate-layout' once first"
}

flip_and_verify() { # $1 = venv name to activate, $2 = name to record as previous
  box "echo '$2' > $BASE/previous-venv
       ln -sfn venvs/$1 $BASE/.venv
       systemctl restart $SERVICE"
  sleep 4
  if verify_mcp "$PORT" && box "systemctl is-active --quiet $SERVICE"; then
    echo "OK: $SERVICE serving from venvs/$1 (verified initialize handshake on :$PORT)"
    return 0
  fi
  echo "VERIFY FAILED for venvs/$1 — rolling back to venvs/$2" >&2
  box "ln -sfn venvs/$2 $BASE/.venv && systemctl restart $SERVICE"
  sleep 4
  verify_mcp "$PORT" || die "ROLLBACK ALSO FAILED — $SERVICE is unhealthy, intervene NOW"
  die "activation of venvs/$1 failed; rolled back to venvs/$2 (verified healthy)"
}

cmd_activate() {
  require_sha
  require_symlink_layout
  local name current
  name=$(venv_name_for_sha)
  box "[ -x $BASE/venvs/$name/bin/gen-mcp-server ]" \
    || die "venvs/$name is not staged — run 'build --sha $SHA' first"
  current=$(box "basename \$(readlink -f $BASE/.venv)")
  [ "$current" = "$name" ] && { echo "venvs/$name is already active"; return 0; }
  flip_and_verify "$name" "$current"
}

cmd_rollback() {
  require_symlink_layout
  local prev current
  prev=$(box "cat $BASE/previous-venv 2>/dev/null") || die "no previous-venv recorded"
  [ -n "$prev" ] || die "previous-venv is empty"
  current=$(box "basename \$(readlink -f $BASE/.venv)")
  flip_and_verify "$prev" "$current"
}

cmd_migrate_layout() {
  # One-time migration: the original install is a REAL venv at $BASE/.venv.
  # Move it under venvs/ and re-point .venv as a symlink. Venv shebangs
  # reference $BASE/.venv/bin/python3, which keeps resolving through the
  # symlink, so the moved venv stays runnable without a reinstall.
  box "[ -L $BASE/.venv ]" && die "already migrated — $BASE/.venv is a symlink"
  box "[ -d $BASE/.venv ]" || die "$BASE/.venv missing on $BOX"
  local ver name
  ver=$(box "$BASE/.venv/bin/pip show gen-mcp-server 2>/dev/null | awk '/^Version:/{print \$2}'")
  [ -n "$ver" ] || die "cannot read installed version from $BASE/.venv"
  name="v${ver}-pypi"
  echo "migrate-layout: $BASE/.venv (gen-mcp-server $ver) -> venvs/$name + symlink"
  box "set -e
    mkdir -p $BASE/venvs $BASE/wheels
    mv $BASE/.venv $BASE/venvs/$name
    ln -sfn venvs/$name $BASE/.venv
    echo '$name' > $BASE/previous-venv
    systemctl restart $SERVICE"
  sleep 4
  if verify_mcp "$PORT"; then
    echo "migrate-layout: OK — $SERVICE serving from venvs/$name through the symlink"
  else
    echo "migrate-layout VERIFY FAILED — restoring real-dir layout" >&2
    box "rm -f $BASE/.venv && mv $BASE/venvs/$name $BASE/.venv && systemctl restart $SERVICE"
    sleep 4
    verify_mcp "$PORT" || die "RESTORE ALSO FAILED — $SERVICE unhealthy, intervene NOW"
    die "migration failed; original layout restored (verified healthy)"
  fi
}

cmd_status() {
  echo "active: $(box "readlink $BASE/.venv 2>/dev/null || echo '(real dir — not migrated)'")"
  echo "version: $(box "$BASE/.venv/bin/pip show gen-mcp-server 2>/dev/null | awk '/^Version:/{print \$2}'")"
  echo "deploy_sha: $(box "cat \$(readlink -f $BASE/.venv)/DEPLOY_SHA 2>/dev/null || echo '(none — pre-git install)'")"
  echo "previous: $(box "cat $BASE/previous-venv 2>/dev/null || echo '(none)'")"
  echo "staged: $(box "ls $BASE/venvs 2>/dev/null | tr '\n' ' ' || true")"
  if verify_mcp "$PORT"; then echo "serving: OK (initialize handshake on :$PORT)"; else echo "serving: FAILED"; fi
}

CMD="${1:-}"; shift || true
SHA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --sha) SHA="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

case "$CMD" in
  build)          cmd_build ;;
  activate)       cmd_activate ;;
  rollback)       cmd_rollback ;;
  migrate-layout) cmd_migrate_layout ;;
  status)         cmd_status ;;
  *) usage ;;
esac
