# Den Designer Community bridge — 0.1.0-preview.10

Use with the matching **Den Designer pak 1.1.0-preview.22**. Install both with the
game closed. The bridge is a background transport; it has no desktop form and
never takes focus. Preserve an established Proton/Wine `version=n,b` override.

**Compositions** and **Community** are distinct editor toolbar destinations:

- **Compositions** is the local creation/library/placement workflow: select parts,
  save a composition, inspect cached local previews, place and delete saved copies.
- **Community → Browse → Compositions** loads actual revisioned public listings.
  Search filters titles, descriptions and codes in the service feed; six cards
  appear per page. The deployed v1 service returns its latest 24 feed entries;
  search/pagination currently operate within that bounded feed. Legacy entries
  without a published revision are excluded. Empty, loading and service-error
  messages appear inside the panel. Select a card for description, creator,
  revision, requirements and a local preview. Preview work downloads only validated
  part values and uses Den Designer’s bounded render/cache service; remote image
  URLs and downloaded code are never loaded. **Download** adds a saved snapshot
  to the local Compositions library and never places it automatically. Code/link
  import remains an additional shortcut.
- **Community → Upload → Composition** has its own selector of saved LOCAL cards.
  It is independent of public browsing and local Compositions selection. Select
  a source, Review saved snapshot, enter title/description, then Publish / retry.
  Every mesh/material dependency is reviewed; unknown coverage is explicit.
  Empty update fields create a listing; updating yours requires code and current
  revision. Form values survive recoverable errors and tab changes. Search and
  page actions cannot cancel an active upload. Success provides a public URL and
  share code with copy controls. Existing ownership, revision conflicts, staged
  immutable uploads and idempotent retries remain authoritative.
- **Community → Browse → Dens** is a labelled placeholder, with no fabricated
  cards or download actions. **Upload → Full Den** lists local layout presets and
  offers an explicit save-current-as-NEW-preset action. Its Publish button is
  disabled because Full Den backend/capture/revision support is not implemented.
- **Account** inside Community provides status/profile, masked key entry, Connect,
  Disconnect, Remember and Forget. Website account is the explicit browser action
  for Steam sign-in and generating a key; it is not an embedded website.

Remember connection is opt-in **plain local storage** at
`Saved/SaveGames/ZComDen/Community/v1/connection.key`. Anyone with the file can use
that key until expiry/revocation. Off keeps the connection for this session only.
Forget stops the worker and removes the saved key; Disconnect ends this session
but keeps an opted-in saved key. Masking cannot protect clipboard history or
forced process dumps. The typed AUTH mailbox is temporary and removed after its
reply; exclude Community mailbox files and process dumps from diagnostics. Keys
never enter composition/layout exports, status messages, logs, arguments or
process environment variables.

Cancel or closing Community invalidates network work; closing the editor also
releases rendering work. Game exit kills owned workers. Cancel racing a committed
finalize can leave a completed publication: check your website listing before
starting a different upload. Retry the same saved snapshot/metadata to recover a
staged outcome. The cached-PNG exporter padding fix remains included: validate the
PNG through IEND, omit/zero allocator slack, keep strict server validation and the
original retry identity. The image is not re-rendered for uploading.

Approved beta access is still required to publish. This package does not approve
accounts, bypass moderation, or enable Full Den sharing.
