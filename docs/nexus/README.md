# Nexus publication copy

This folder follows the `docs/nexus` convention used by Off Duty, Colors+, Fast Resonance and the
other projects in `ZComMods`.

- **[summary.txt](summary.txt):** paste the single paragraph into Nexus's summary field.
- **[Banner](media/den-designer-banner.png):** 1300×372 PNG matching the cyan HUD banner series.
  Generated with the built-in imagegen tool; the [prompt](media/den-designer-banner-prompt.txt)
  records the references and design specification.
- **[description.bbcode](description.bbcode):** paste into the description's BBCode/source editor.
  The headings, lists, links and closing list-item tags follow the neighboring mods' format.
- **[Full feature guide](../features.md):** detailed controls, defaults, workflow and scope.
- **[Shipped player guide](../../distribution/pak/README.md):** installation and reference material
  included in runtime packages.

The Nexus text is version-neutral apart from the target game build. It describes the features
present in `1.1.0-preview.18`; it does not promote the runtime to a stable version or publish a page.
The source URL comes from this repository's Git remote. Mod-manager, other-mod and community links
follow the existing neighboring Nexus copy.

Creator tools remain a separate preview, not an included player dependency. There is no runtime
UE4SS requirement or requirement for a separate settings manager. Compatibility claims are limited
to the documented target; the copy does not claim every mod combination was tested.

The README changes made alongside this copy must be included when the release archive is next
built. Existing versioned ZIPs and the installed test build have not been rewritten by this
writing task.
