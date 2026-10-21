#!/usr/bin/env python3
"""Validate reviewed release evidence against the exact build and shipped files.

This is an integrity/completeness gate, not an automated judge of screenshots.
A reviewer must inspect the evidence and populate every required result. Missing,
failed, stale or changed evidence stops release packaging; preview packaging does
not imply acceptance. Reports/evidence remain development artifacts.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

from gf_build_info import require, sha

# Keep these aligned with the full migration objective, not whichever tests pass.
REQUIREMENTS = {
    'startup': 'Automatic Den-only lifecycle, open/close, view restoration, cold restart',
    'controls': 'Camera flight/look, modifiers, surface/height drag, independent floor/wall/structure safeguards and selection range',
    'selection': 'Placed and vanilla selection, missing-collision fallback, highlights',
    'transforms': 'Numeric transforms and all 16 move/rotate/scale gizmo handles',
    'history': 'Duplicate, reset, undo and redo without unrelated changes',
    'catalog': 'Full catalog, search/collections, async placement and repeated placement',
    'compositions': 'Capture, save, replace, restart, group placement/history and composition thumbnails',
    'prop_packs': 'Independent pack discovery, textured meshes, thumbnails, persistence and missing-pack recovery',
    'thumbnails': 'Fresh generation and cache reuse in catalog and Storeroom',
    'storeroom': 'Store/restore both placed and vanilla props; unavailable entries',
    'layouts': 'Home/campaign switching, named presets, save/restart and rotating backups',
    'preferences': 'Own settings, physical rebinding, persistence and no MXM dependency',
    'drafts': 'Autosave, abrupt exit, explicit recovery, save and restart',
    'migration': 'JSON layouts/backups/presets/drafts convert and load, originals preserved',
    'travel': 'Mission success return, restored layout, working editor and no stale hosts',
    'preservation': 'Separate mod slots, original data preserved, temporary setup restored',
    'documentation': 'Install/update/uninstall/rollback, controls, persistence and migration instructions',
}
# In-game acceptance must exercise the standalone runtime, not merely invoke its
# functions through UE4SS. Engine tests/source review can supplement these rows.
STANDALONE = set(REQUIREMENTS) - {'preservation', 'documentation'}
SHIPPED_INPUTS = (
    'distribution/pak/README.md', 'distribution/pak/CREDITS.md',
    'distribution/migration/README.md', 'LICENSE',
    'tools/migration/migrate_layouts.py', 'tools/migration/install_migration.py',
    'tools/migration/den_save.py', 'tools/migration/den_save_schema.json',
    'tools/build/package_gf.py', 'tools/build/gf_acceptance.py',
)


def payload_inputs(root):
    return {p: sha(root / p) for p in SHIPPED_INPUTS}


def evidence_path(root, name):
    require(isinstance(name, str) and name, 'Missing evidence path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '\\' not in name and ':' not in name
            and all(part not in ('', '.', '..') for part in name.split('/')),
            'Invalid evidence path: ' + name)
    target = root / name
    require(target.resolve().is_relative_to(root.resolve()), 'Evidence escapes repository: ' + name)
    require(not any(parent.is_symlink() for parent in [target, *target.parents] if parent != root.parent),
            'Evidence must not use symlinks: ' + name)
    return target


def verify_acceptance(root, build, path):
    root = Path(root).resolve()
    data = Path(path).read_bytes()
    report = json.loads(data)
    require(report.get('format') == 1, 'Unsupported acceptance format')
    require(report.get('build') == build, 'Acceptance does not match the exact verified build')
    require(report.get('payload_inputs') == payload_inputs(root), 'Shipped files changed after acceptance')
    require(report.get('remaining') == [], 'Acceptance has missing or outstanding work')
    require(isinstance(report.get('reviewed_by'), str) and report['reviewed_by'].strip(), 'Missing evidence reviewer')
    rows = report.get('requirements')
    require(isinstance(rows, dict) and set(rows) == set(REQUIREMENTS), 'Acceptance requirement inventory differs')
    evidence = report.get('evidence')
    require(isinstance(evidence, dict) and evidence, 'Missing evidence inventory')
    used = set()
    for ident, row in rows.items():
        require(isinstance(row, dict) and row.get('passed') is True, 'Acceptance not passed: ' + ident)
        require(isinstance(row.get('summary'), str) and row['summary'].strip(), 'Missing review summary: ' + ident)
        refs = row.get('evidence')
        require(isinstance(refs, list) and refs and all(isinstance(p, str) and p in evidence for p in refs),
                'Missing evidence references: ' + ident)
        used.update(refs)
        if ident in STANDALONE:
            require(row.get('standalone') is True, 'Standalone runtime not verified: ' + ident)
            process = row.get('process_evidence')
            require(isinstance(process, str) and process in refs, 'Missing loader-free process evidence: ' + ident)
            process_data = json.loads(evidence_path(root, process).read_bytes())
            require(process_data.get('ue4ss_loaded') is False and type(process_data.get('pid')) is int
                    and process_data['pid'] > 0, 'Process record must prove UE4SS absent: ' + ident)
    require(used == set(evidence), 'Acceptance contains unreferenced evidence')
    for name, expected in evidence.items():
        require(isinstance(expected, str) and len(expected) == 64 and sha(evidence_path(root, name)) == expected,
                'Acceptance evidence changed: ' + name)
    # Ship only a small certificate, never the local evidence paths, screenshots,
    # campaign dumps, or user data which the reviewer inspected.
    return {'format': 1, 'version': build['version'], 'acceptance_sha256': hashlib.sha256(data).hexdigest(),
            'containers': build['containers'], 'requirements': dict(REQUIREMENTS),
            'full_regression_complete': True}
