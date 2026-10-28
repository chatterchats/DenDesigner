#!/usr/bin/env bash
# Test executable only; fake transport, no account credentials or live network.
set -euo pipefail
cd "$(dirname "$0")/../.."
compiler=${DD_CLANG:-/usr/lib64/rocm/llvm/bin/clang}
linker=${DD_LLD_LINK:-/usr/lib64/rocm/llvm/bin/lld-link}
wine_sdk=${DD_WINE_SDK:-/home/chats/.local/share/lutris/runners/wine/wine-proton-10.0-4-amd64}
output=${DD_NATIVE_OUTPUT:-"$PWD/dist/build/community-native"}
bash native/community/build.sh
"$compiler" --target=x86_64-pc-windows-msvc -fms-extensions -fno-builtin -fno-stack-protector -Wno-pragma-pack -O2 -I"$wine_sdk/include/wine/msvcrt" -I"$wine_sdk/include/wine/windows" -Inative/community -c native/community/connection-smoke.c -o "$output/connection-smoke.obj"
"$linker" /nodefaultlib /machine:x64 /subsystem:console /entry:mainCRTStartup /out:"$output/connection-smoke.exe" "$output/connection-smoke.obj" "$output/windows.obj" "$output/core.obj" "$output/chkstk.obj" "$wine_sdk/lib/wine/x86_64-windows/libkernel32.a" "$wine_sdk/lib/wine/x86_64-windows/libuser32.a" "$wine_sdk/lib/wine/x86_64-windows/libwinhttp.a" "$wine_sdk/lib/wine/x86_64-windows/libbcrypt.a"
