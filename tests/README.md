# Tests

| Folder | Purpose |
|---|---|
| `python/` | Standard-library tests for migration, packaging, catalog data and creator tooling. |
| `unreal/` | Compiled Blueprint execution tests and public-kit creator integration checks. |
| `fixtures/` | Fixed independent regression data. |
| `integration/native_travel/` | Disposable mission-return QA plugin; never installed automatically. |

From the repository root:

```sh
python3 -m unittest discover -s tests/python -p '*_test.py'
bash tools/build/test_native.sh --existing
```

The second command requires the authored runtime in the private maintainer kit. Public-kit creator
checks are documented separately in the [development guide](../docs/development.md#prop-pack-editor).
Game checks and preservation requirements are in [verification](../docs/verification.md).
