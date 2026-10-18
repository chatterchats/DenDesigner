"""Build Den Designer's kit assets from unreal/specs/<set>/*.json with ZComAuthoring (run by tools/build_plugin.sh).

The spec set comes from ZCOMDEN_SPECS (a directory); files build in name order. Prints ZCOMDEN_RESULT ok|failed.
"""
import os
from pathlib import Path

import unreal
import zcom_authoring

specs = sorted(Path(os.environ["ZCOMDEN_SPECS"]).glob("*.json"))
ok = bool(specs) and zcom_authoring.build(specs)
unreal.log(f"ZCOMDEN_RESULT {'ok' if ok else 'failed'} ({len(specs)} specs)")
