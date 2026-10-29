# Maintainer tools

Run commands from the repository root. Players and in-editor prop-pack creators do not need these tools.

| Folder | Commands and purpose |
|---|---|
| `build/` | `build_gf.sh`, `test_native.sh`, `package_gf.py`, build validation and catalog conversion. `lint_specs.py` checks the generated Blueprint specs offline; `simulate_specs.py` runs their logic in Python tests. |
| `prop_packs/` | `package_editor_authoring.py` for the recommended creator ZIP; optional scripted pack tools and reference export. |
| `dev/` | Local Lutris/Sandbox control, guarded input and screenshots. |

Builds/logs use `dist/build/`, ZIPs use `dist/packages/`, and local test records use
`dist/verification/`. The [development guide](../docs/development.md) covers prerequisites and commands.

Portable sharing validation and the offline Community registry live in
[`sharing/`](sharing/); see the [contract and compatibility rules](../docs/portable-sharing.md).
