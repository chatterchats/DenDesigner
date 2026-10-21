# Unreal source and generated assets

| Folder | Purpose |
|---|---|
| `DenDesignerGF/` | Runtime Game Feature plugin. Its descriptor is source; `Content/` is authored output. |
| `DenPropsExample/` | Local development sample plugin, separate from every runtime release. |
| `specs/` | Python graph generators and widget/input templates. |
| `generated/runtime/` | Reviewable JSON specifications generated from `specs/runtime.py`. |
| `data/` | Canonical catalog metadata and procedural gizmo geometry. |
| `scripts/` | Unreal Editor authoring, importing, schema export and pack verification. |

Regenerate JSON with `python3 -I unreal/specs/runtime.py` from the repository root.
Compiled Blueprint tests live in `tests/unreal/`. The creator plugins and their public guides live
under `authoring/prop-packs/`; they are separate from this runtime plugin.

See [development](../docs/development.md) for the build and generated-output boundaries.
