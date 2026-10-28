#!/usr/bin/env bash
# Builds separate test outputs containing an inert waiting worker. Never install.
set -euo pipefail
cd "$(dirname "$0")/../.."
compiler=${DD_CLANG:-/usr/lib64/rocm/llvm/bin/clang}
linker=${DD_LLD_LINK:-/usr/lib64/rocm/llvm/bin/lld-link}
wine_sdk=${DD_WINE_SDK:-/home/chats/.local/share/lutris/runners/wine/wine-proton-10.0-4-amd64}
base=${DD_NATIVE_OUTPUT:-"$PWD/dist/build/community-native"}
output="$base/lifecycle-smoke"
mkdir -p "$output"
flags=(--target=x86_64-pc-windows-msvc -fms-extensions -fno-builtin -fno-stack-protector -Wno-pragma-pack -O2 -I"$wine_sdk/include/wine/msvcrt" -I"$wine_sdk/include/wine/windows" -Inative/community)
"$compiler" "${flags[@]}" -c native/community/lifecycle-smoke.c -o "$output/observer.obj"
"$compiler" "${flags[@]}" -DDD_HANG_WORKER -c native/community/lifecycle-smoke.c -o "$output/hang.obj"
for name in observer hang; do
    target=community-lifecycle.exe
    if [ "$name" = hang ]; then target=den-community.exe; fi
    "$linker" /nodefaultlib /machine:x64 /subsystem:console /entry:mainCRTStartup /out:"$output/$target" "$output/$name.obj" "$base/windows.obj" "$base/chkstk.obj" "$wine_sdk/lib/wine/x86_64-windows/libkernel32.a" "$wine_sdk/lib/wine/x86_64-windows/libbcrypt.a"
done
cp "$base/version.dll" "$output/version.dll"
