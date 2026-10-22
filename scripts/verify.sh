#!/usr/bin/env bash
# 一键质量门：任何唤醒点都能跑，结果落盘 scripts/verify.log
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

LOG=scripts/verify.log
: >"$LOG"
fail=0

step() {
    local name="$1"; shift
    echo "== $name ==" | tee -a "$LOG"
    if "$@" 2>&1 | tee -a "$LOG"; then
        echo "[PASS] $name" | tee -a "$LOG"
    else
        echo "[FAIL] $name" | tee -a "$LOG"
        fail=1
    fi
}

step "ruff"        uv run ruff check .
step "pytest"      uv run pytest -q
step "compileall"  uv run python -m compileall -q snowluma_reverse plugin.py
step "coverage"    uv run python scripts/check_snowluma_coverage.py --check

echo "== 汇总 ==" | tee -a "$LOG"
if [ "$fail" -eq 0 ]; then
    echo "ALL PASS" | tee -a "$LOG"
else
    echo "HAS FAILURE（见 $LOG）" | tee -a "$LOG"
fi
exit "$fail"
