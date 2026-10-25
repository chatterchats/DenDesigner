#!/bin/bash
# Build and execute native Blueprint data tests. Never installs or touches game saves.
set -euo pipefail
cd "$(dirname "$0")/../.."
repo=$(pwd)
existing=0
case "${1:-}" in
    "") ;;
    --existing) existing=1 ;;
    *) echo "Usage: $0 [--existing]" >&2; exit 2 ;;
esac
root=${SWZC_ROOT:-/run/media/chats/0c7bd812-03b4-405c-9602-31282b68fd64}
kit=${SWZC_KIT:-"$root/SWZC Merged Kit"}
log="$repo/dist/build/runtime-logs/native-test.log"
mkdir -p "$(dirname "$log")"
[ -e "$kit/Mods/DenDesignerGF" ] || ln -s "$repo/unreal/DenDesignerGF" "$kit/Mods/DenDesignerGF"
[ "$(readlink -f "$kit/Mods/DenDesignerGF")" = "$repo/unreal/DenDesignerGF" ] || exit 1
python3 -I "$repo/unreal/specs/runtime.py"
DENDESIGNER_REPO="$repo" DENDESIGNER_TEST_SAVED="$kit/Saved" DENDESIGNER_EXISTING="$existing" \
    "$root/UnrealEngine/Engine/Binaries/Linux/UnrealEditor-Cmd" "$kit/SWZeroCompany.uproject" \
    -run=pythonscript -script="$repo/tests/unreal/test_runtime.py" \
    -unattended -nop4 -nosplash -NullRHI -stdout -FullStdOutLogOutput -NoCrashDialog > "$log" 2>&1 || true
rg 'DENNATIVE_RESULT|DENNATIVE_CHECK FAIL|LogPython: Error|ZCOMAUTH.*(error|warning|FAILED)' "$log" || true
rg -q 'DENNATIVE_RESULT ok' "$log"
