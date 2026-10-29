# Den Designer HoloNet bridge — 0.9.20

Use with the matching **Den Designer 0.9.20** pak. Install both with the game
closed. The bridge is a background transport for **HoloNet** (zcom.app); it has
no desktop form and never takes focus. Preserve an established Proton/Wine
`version=n,b` override.

Open **HoloNet** from the editor's menu bar. It is a centred window with these
sections on the left:

- **Browse → Compositions**: builds other captains shared. Search titles and
  creators, sort by Newest or Most imported, and page through eight cards at a time.
  **Only what I can use** hides builds that need a prop pack you don't have
  installed. A card marked **IN LIBRARY** is already in your Compositions. Pick a
  card to see its preview (rendered here from its parts; no remote images or code
  are loaded), description, revision, readiness, parts, footprint and code.
  **Add to my Compositions** saves it to your library; **Add and place now** saves
  it and starts placing it. If a prop pack is missing, **Get the prop pack on
  Nexus** opens the pack's Nexus Mods page (or a Nexus search for its title).
- **Browse → Dens**: coming soon.
- **Have a code?** (bottom of the rail): import by code or zcom.app link.
- **Share a build**: pick a saved composition. It is checked at once; the title
  defaults to its name, and if you've shared one with that title before, the
  share updates it (same code, next revision) and asks **What changed**. Choose
  **Share as a new build** for a new code instead. The requirements line says
  whether it is base game only or which prop packs it uses. Only the saved copy
  is shared, never unsaved edits. Afterwards the code is shown with **Copy code**
  and **Copy link**. **Share** on the Compositions panel opens this with the
  selected composition picked.
- **My Shares**: your shares with code, revision, imports and Public/Hidden.
  Pick one to share an update of it. Hide and show shares on zcom.app.
- **Account**: masked key entry, Connect, Disconnect, Remember on this PC and
  Forget. **Get a key at zcom.app/account** opens the browser for Steam sign-in.
  The title bar shows **Connected as <name>** or **Not connected**.

Titles, descriptions and names may use any characters (UTF-8); the game's fonts
decide which ones display.

Remember connection is opt-in **plain local storage** at
`Saved/SaveGames/ZComDen/Community/v1/connection.key`. Anyone with the file can use
that key until expiry/revocation. Off keeps the connection for this session only.
Forget stops the worker and removes the saved key; Disconnect ends this session
but keeps an opted-in saved key. Masking cannot protect clipboard history or
forced process dumps. The typed AUTH mailbox is temporary and removed after its
reply; exclude HoloNet mailbox files and process dumps from diagnostics. Keys
never enter composition/layout exports, status messages, logs, arguments or
process environment variables.

Cancel or closing HoloNet invalidates network work; closing the editor also
releases rendering work. Game exit kills owned workers. Cancel racing a committed
finalize can leave a completed publication: check your website listing before
starting a different upload. Retry the same saved composition and text to recover a
staged share. The preview image is the card's cached render (512 px when it exists,
otherwise the 128 px card); the cached-PNG padding fix still applies.

Sharing may need approval on zcom.app. This package does not approve accounts,
bypass moderation, or share whole Den layouts.
