# Den Designer Migration

Convert existing Lua-edition JSON layouts into the pak edition's own save slots.
This optional, one-time utility uses **Python 3.10 or newer** and its standard library.
The game and the pak mod do not need Python afterward.

Close the game and stop editing before taking the snapshot. Keep the original
`%LOCALAPPDATA%\SWZeroCompany\Saved\ZComDen` directory and your normal backups.

## 1. Stage the conversion

Extract this utility to a separate folder. Open a command prompt in that folder.
On Windows, with Python installed:

```bat
py -3 migrate_layouts.py --source "%LOCALAPPDATA%\SWZeroCompany\Saved\ZComDen" --output "%USERPROFILE%\Desktop\DenDesigner-import"
```

The output directory must be new and outside the source directory. Choose another name if it
already exists. On Linux/Wine, use `python3` and the game's prefix paths:

```sh
python3 migrate_layouts.py --source "/path/to/prefix/drive_c/users/steamuser/AppData/Local/SWZeroCompany/Saved/ZComDen" --output "/path/to/new-import"
```

This step does not install anything. The new folder contains:

- `originals/`: byte-for-byte copies of the source files, including backups and drafts.
- `SaveGames/ZComDen/Native/v1/`: converted layout, draft and preset banks.
- `migration.json`: file hashes, source-to-output mapping and conversion warnings.

Read any warnings. An invalid active layout stops conversion instead of silently dropping edits.
An invalid old backup is preserved and reported, but is not converted into a native bank.
Thumbnail caches are left in place rather than copied into the migration archive.

## 2. Preview installation

```bat
py -3 install_migration.py --migration "%USERPROFILE%\Desktop\DenDesigner-import"
```

Windows defaults to `%LOCALAPPDATA%\SWZeroCompany\Saved`. To choose another installation or
a Wine prefix, supply `--saved "/path/to/SWZeroCompany/Saved"`.

The preview validates every original and converted file, reconstructs each payload from its
preserved JSON, and lists exactly which files it would install. It writes no game files.

If a different native layout or draft already exists for an imported scope, installation stops.
Other campaign scopes and native settings are left alone. There is no automatic merge or
overwrite option. Keep both versions; do not delete your native work to get past a conflict.

## 3. Install with the game closed

Repeat the preview command with `--apply`:

```bat
py -3 install_migration.py --migration "%USERPROFILE%\Desktop\DenDesigner-import" --apply
```

The installer checks that the game is closed and publishes each complete file without overwriting
an existing path. It uses hard links within the Saved volume, so that filesystem must support
them (NTFS on Windows, or a compatible Linux filesystem). An unsupported filesystem produces
an error rather than a less safe overwrite. Ordinary write failures roll back this invocation's
new files. After an abrupt interruption, rerunning the same command accepts identical files and
completes the remaining files. A different or newly edited native file stops the retry.

Keep the entire staging folder as your migration backup. The installer never changes the source
JSON files, the staged originals, the game INIs, another mod's settings, or campaign saves.

## 4. Open the pak edition

Follow the pak download's installation instructions to disable only the Lua edition of Den
Designer and install the three native containers. Load a campaign, enter the Den, and press
Ctrl+Home. Home applies to campaigns without their own imported layout; imported campaign copies
are selected by their campaign IDs. Presets appear in Layouts.

Imported drafts never apply automatically. Their old format has no baseline identity, so review
the recovery prompt and its mismatch confirmation before adopting a draft. The saved layout and
all original files remain available.

Settings/key bindings are configured in the pak edition's Settings panel; this utility converts
layouts and presets, not MXM settings. Returning to the Lua edition uses the untouched original
JSON. There is no reverse conversion for new edits made in the pak edition.
