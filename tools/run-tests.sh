#!/bin/sh
# Offline tests (LuaJIT, no game needed).
cd "$(dirname "$0")/.." || exit 1
status=0
for t in tests/*_test.lua; do luajit "$t" src/ZComDen || status=1; done
exit $status
