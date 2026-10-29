#!/usr/bin/env bash
# Wine end-to-end test of the HoloNet bridge. Builds a test version.dll from
# the same sources (pointed at a local fake HoloNet, with -DDD_FAULT_TEST crash
# points), loads it in a stand-in game process and drives the mailbox the way
# the game does: browse, import, connect, My Shares, share, timeouts, cancels,
# caught crashes, and fuzzed mailbox files and server replies.
#   bash native/community/e2e/run.sh [scenario ...]
# Needs wine, python3 and a host C compiler (cc). Uses its own Wine prefix under
# dist/state; never touches the game or a Proton prefix.
set -euo pipefail
cd "$(dirname "$0")/../../.."
compiler=${DD_CLANG:-/usr/lib64/rocm/llvm/bin/clang}
linker=${DD_LLD_LINK:-/usr/lib64/rocm/llvm/bin/lld-link}
wine_sdk=${DD_WINE_SDK:-/home/chats/.local/share/lutris/runners/wine/wine-proton-10.0-4-amd64}
export DD_E2E_STATE=${DD_E2E_STATE:-"$PWD/dist/state/holonet-e2e"}
source_dir="$PWD/native/community"
output="$DD_E2E_STATE/bin"
mkdir -p "$output"
flags=(--target=x86_64-pc-windows-msvc -fms-extensions -fno-builtin -fno-stack-protector -Wno-pragma-pack -O2 -I"$wine_sdk/include/wine/msvcrt" -I"$wine_sdk/include/wine/windows" -I"$source_dir"
       '-DDD_SERVICE_HOST="127.0.0.1"' -DDD_SERVICE_PORT=18080 -DDD_SERVICE_SECURE=0 -DDD_FAULT_TEST)
for file in core windows worker proxy connection; do
    "$compiler" "${flags[@]}" -c "$source_dir/$file.c" -o "$output/$file.obj"
done
"$compiler" --target=x86_64-pc-windows-msvc -c "$source_dir/chkstk.S" -o "$output/chkstk.obj"
"$compiler" "${flags[@]}" -c "$source_dir/e2e/host.c" -o "$output/host.obj"
libs=()
for lib in kernel32 user32 winhttp bcrypt ntdll; do libs+=("$wine_sdk/lib/wine/x86_64-windows/lib$lib.a"); done
"$linker" /dll /nodefaultlib /machine:x64 /entry:DllMain /dynamicbase /nxcompat /def:"$source_dir/version.def" /out:"$output/version.dll" "$output/proxy.obj" "$output/worker.obj" "$output/connection.obj" "$output/windows.obj" "$output/core.obj" "$output/chkstk.obj" "${libs[@]}"
"$linker" /nodefaultlib /machine:x64 /subsystem:console /entry:mainCRTStartup /out:"$output/host.exe" "$output/host.obj" "${libs[0]}"
rm -f "$DD_E2E_STATE/http.log" "$DD_E2E_STATE/control.json"
python3 -I "$source_dir/e2e/server.py" "$DD_E2E_STATE" &
server=$!
trap 'kill $server 2>/dev/null' EXIT
sleep 1
python3 "$source_dir/e2e/scenarios.py" "$@"
