#!/usr/bin/env bash
# Build the optional Windows-only standalone transport. Does not install it.
set -euo pipefail
cd "$(dirname "$0")/../.."
source_dir="$PWD/native/community"
compiler=${DD_CLANG:-/usr/lib64/rocm/llvm/bin/clang}
linker=${DD_LLD_LINK:-/usr/lib64/rocm/llvm/bin/lld-link}
wine_sdk=${DD_WINE_SDK:-/home/chats/.local/share/lutris/runners/wine/wine-proton-10.0-4-amd64}
output=${DD_NATIVE_OUTPUT:-"$PWD/dist/build/community-native"}
mkdir -p "$output"
flags=(--target=x86_64-pc-windows-msvc -fms-extensions -fno-builtin -fno-stack-protector -Wno-pragma-pack -O2 -I"$wine_sdk/include/wine/msvcrt" -I"$wine_sdk/include/wine/windows" -I"$source_dir")
for file in core windows worker proxy connection; do
    "$compiler" "${flags[@]}" -c "$source_dir/$file.c" -o "$output/$file.obj"
done
"$compiler" --target=x86_64-pc-windows-msvc -c "$source_dir/chkstk.S" -o "$output/chkstk.obj"
system_libs=("$wine_sdk/lib/wine/x86_64-windows/libkernel32.a" "$wine_sdk/lib/wine/x86_64-windows/libwinhttp.a" "$wine_sdk/lib/wine/x86_64-windows/libbcrypt.a")
"$linker" /nodefaultlib /machine:x64 /subsystem:console /entry:mainCRTStartup /dynamicbase /nxcompat /timestamp:0 /out:"$output/den-community.exe" "$output/worker.obj" "$output/connection.obj" "$wine_sdk/lib/wine/x86_64-windows/libuser32.a" "$output/windows.obj" "$output/core.obj" "$output/chkstk.obj" "${system_libs[@]}"
"$linker" /dll /nodefaultlib /machine:x64 /entry:DllMain /dynamicbase /nxcompat /timestamp:0 /def:"$source_dir/version.def" /out:"$output/version.dll" "$output/proxy.obj" "$output/windows.obj" "$output/core.obj" "$output/chkstk.obj" "${system_libs[@]}"
sha256sum "$output/version.dll" "$output/den-community.exe" > "$output/SHA256SUMS"
cat "$output/SHA256SUMS"

python3 - "$PWD" "$output" <<'PYBUILD'
import hashlib,json,sys
from pathlib import Path
root,output=map(Path,sys.argv[1:])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={"format":1,"version":"0.1.0-preview.10","target":"windows-x86_64","requires_ue4ss":False,"requires_python":False,
        "sources":{p.relative_to(root).as_posix():sha(p) for p in sorted((root/'native/community').iterdir()) if p.is_file()},
        "binaries":{name:sha(output/name) for name in ['version.dll','den-community.exe']},
        "transport":"WinHTTP in owned cancellable worker process; BCrypt SHA-256; SaveGame value mailbox",
        "limits":{"total_ms":25000,"metadata_bytes":65536,"document_bytes":4194304,"parts":128},
        "scope":"Approved beta publishing: saved compositions, cached PNG, staged immutable revisions. Published imports support decimal transforms and covered mesh/material paths; availability checked by local preview. In-game connection controls with opt-in plain local remembered key and automatic reconnect.",
        "verification":"Build only; see separate native smoke and kit evidence. No shipped-game acceptance implied."}
(output/'build.json').write_text(json.dumps(report,indent=2)+'\n')
PYBUILD
