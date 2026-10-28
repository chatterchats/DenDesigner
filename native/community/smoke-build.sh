#!/usr/bin/env bash
# Separate native smoke harness. No game/prefix installation.
set -euo pipefail
cd "$(dirname "$0")/../.."
bash native/community/build.sh
compiler=${DD_CLANG:-/usr/lib64/rocm/llvm/bin/clang}
linker=${DD_LLD_LINK:-/usr/lib64/rocm/llvm/bin/lld-link}
wine_sdk=${DD_WINE_SDK:-/home/chats/.local/share/lutris/runners/wine/wine-proton-10.0-4-amd64}
output=${DD_NATIVE_OUTPUT:-"$PWD/dist/build/community-native"}
"$compiler" --target=x86_64-pc-windows-msvc -fms-extensions -fno-builtin -fno-stack-protector -Wno-pragma-pack -O2 -I"$wine_sdk/include/wine/msvcrt" -I"$wine_sdk/include/wine/windows" -Inative/community -c native/community/smoke.c -o "$output/smoke.obj"
"$linker" /nodefaultlib /machine:x64 /subsystem:console /entry:mainCRTStartup /out:"$output/community-smoke.exe" "$output/smoke.obj" "$output/windows.obj" "$output/chkstk.obj" "$wine_sdk/lib/wine/x86_64-windows/libkernel32.a" "$wine_sdk/lib/wine/x86_64-windows/libbcrypt.a"
