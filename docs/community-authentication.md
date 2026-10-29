# Current in-game account UI — paired bridge preview.7 / pak preview.20

Connection and publishing are entirely in the Community UMG panel. The bridge
uses an invisible message-only timer endpoint without controls or foreground
activation. Steam browser authentication opens only from the explicit website
account action. See [the current player flow](../distribution/community/README.md).

Remember connection still uses the existing opt-in plain local key. Typed AUTH
mailboxes temporarily carry the key and are removed after responding. Masking
and clearing reduce accidental exposure but cannot exclude key text from all
forced process dumps; do not collect those or Community mailbox files. No key
is put into exports, diagnostics or status messages.

The following sections document earlier stages and their superseded UI/storage
decisions. References below to native forms or memory-only behavior are historical.

---

> **Remember connection update — bridge 0.1.0-preview.6:** Connection controls
> now live in Compositions. The masked key field is cleared after Connect.
> Remember connection opts into a plain local file at
> `Saved/SaveGames/ZComDen/Community/v1/connection.key` (68 bytes). It enables
> automatic reconnect on game startup. Disconnect ends the current session;
> Forget connection stops the worker and removes that file and any staged write.
> A rejected/expired/revoked key (HTTP 401) is removed; a temporary network failure
> or beta publishing restriction preserves it for a later retry. A write failure
> leaves the connection usable for the current session and reports that it was
> not remembered. The earlier memory-only design below is historical.
>
> This choice is not encryption: copying the file grants its Community upload
> permissions until expiry/revocation. The user explicitly accepted this local
> persistence tradeoff. The connection key passes through one typed `AUTH`
> mailbox request; its response replaces the key and the worker then deletes the
> request. Credentials are excluded from composition/layout exports, campaign
> saves, logs, process arguments and environment variables. Because entry is now
> in-game, credentials can exist in game memory and crash dumps. Publishing review
> still uses the existing native review window; this update changes connection UX.

> Follow-on implementation: [composition publishing](composition-publishing.md) replaces
> the private-queue-only publishing limitation below with approved-beta staged publishing.
> The credential storage decision remains memory-only.

# Community authentication integration — 26 October 2026

ZComShare's adjacent checkout implements Steam-only website OpenID authentication,
internal UUID accounts, secure sessions, personal game upload keys and a private
beta submission queue. See `../ZComShare/docs/authentication.md` for setup,
provider evidence, endpoint contracts and the additive database migration.
The service was inspected at `../ZComShare`; the older frozen download-only
`tools/sharing/service_slice/foundation/` remains an immutable regression fixture.

## Runtime boundary and credential storage decision

**Since 0.9.20 the separate process described below is gone.** The connection
runs on a thread inside `version.dll`, so the key is in the game process's
memory (on a locked page, excluded from Windows Error Reporting where supported)
and can appear in game crash dumps. The owner accepted this: the key only limits
who can upload and lets HoloNet moderate users; it is not a high-value secret.
Keys still never enter exports, logs, status messages, command lines or the
mailbox beyond the temporary AUTH request. A caught fault in bridge code wipes
the key. See `docs/holonet-phase4-plan.md`, "Single-DLL bridge". The rest of this
section is the earlier design, kept for reference.

The actual installed integration is a Windows x64 proxy plus a private WinHTTP
worker, exchanging bounded values with Unreal through a fixed SaveGame mailbox.
It also runs under Proton. This stage adds a separate **game-owned connection
process**, using the same worker executable with a fixed `--connect` argument.
The argument never includes credentials. The existing kill-on-close Job object
owns this process, so game exit terminates it. Offline editing and public imports
remain independent of it.

Available runtime evidence: the bridge already builds against kernel32, winhttp
and bcrypt. The installed Wine SDK contains `CredWriteW` declarations in
`include/wine/windows/wincred.h` and credential/crypto import libraries; native
Windows documents Credential Manager and user-bound DPAPI. API presence in Wine
is insufficient evidence of equivalent credential protection in a Proton prefix.
No usable Blueprint secure credential vault has been established in the content-only
runtime. There is no Linux secret-service integration in this Windows bridge.

**Decision: memory-only for this stage on both platforms.** No key is saved,
including to SaveGame, preferences, campaign saves, layout/composition exports,
environment variables, command lines, logs or application crash diagnostics.
No plaintext fallback or embedded encryption key exists. Players must reconnect
after closing the connection window or restarting the game. The UI explains this
before accepting a key. Credential Manager/DPAPI persistence can be a later,
explicitly tested native-Windows feature; never silently apply its security claims
to Proton.

The native key field uses ES_PASSWORD with no reveal control, a strict size limit,
and immediate clearing after Connect. It holds the key and Authorization header
in locked memory in a separate process, clears them on disconnect/auth failure,
requests WER memory exclusion where supported, suppresses its own crash reporting,
and requests capture exclusion where supported. The ordinary game process never
receives the key, which keeps it out of game crash bundles. This is not protection
against a compromised computer, privileged debugger, OS-enforced full memory dumps,
or clipboard history. WinHTTP and the OS can make transient internal copies;
we cannot guarantee protection from externally forced process diagnostics. Do not
attach connection-process memory dumps to support reports. Clear clipboard history
after pasting. Capture exclusion is best-effort under Wine; password masking is
always applied and no plaintext reveal control is provided.

## Game UX and operations

Compositions has Connect uploads…, Disconnect, and Submit selected parts for beta
review. Connect opens the separate native window with masked key entry, Connect,
Disconnect, and status/linked Community profile. Async WinHTTP validates the key
at the approved fixed origin. Closing the window or Disconnect clears credentials
by terminating this owned process. The window remains available while editing;
the game controls cannot view or export its secret. A 25-second task deadline
ends an unresponsive connection process, leaving the editor usable.

The Blueprint export captures currently selected editable parts and serializes
only reviewed monitor meshes, transforms and collision mode. Material overrides are explicitly omitted in this beta stage and the UI states this limitation. It provides no client author ID, credential, URL or
media. Publishing is a separate `PUBLISH` value message. The connection process
sends it only to `https://share.zcom.app/api/v1/game/submissions`, with credentials
in an HTTPS Authorization header. Cookies, HTTP authentication and redirects are
disabled. Generic failures and revoked/expired keys have no offline editing effect.
Server attribution and permissions are authoritative. Website account keys remain
valid across ordinary website sign-ins; disconnecting locally does not revoke one.

Public share-code input rejects `zcu_` credential-shaped input before writing a
mailbox, reducing accidental paste exposure. Actual secrets are never entered in
Unreal widgets. Responses contain only profile/operation status, never credentials.
The native bridge never follows response URLs. The upload API stores beta
submissions privately; it cannot turn them into published public gallery records.

## Verification and release boundary

Service security tests exercise forged provider/identity/callback/signed-field
assertions, missing browser state, replayed login state and nonces, invalid provider
signatures, CSRF, server-only attribution, cross-account PUT/DELETE, expiry,
revocation, independent sign-in/key lifetime, URL origin, rate limits and secret
non-disclosure in stored rows/account responses. Existing import/parser/installer
regressions also run. Windows cross-compilation checks both proxy and worker.

This change does not deploy remotely, apply production migrations, approve beta
users, enable paid services, install into the game or claim shipped-game acceptance.
Live Steam sign-in and native UI/deployed upload acceptance remain release checks.
Current upload validation is deliberately a narrow queue; full moderation and
portable publishing validation remain incomplete and public publishing stays closed.

Official sources checked:

- [Valve OpenID website authentication and separate ownership checks](https://partner.steamgames.com/doc/features/auth)
- [OpenID 2.0 assertion verification](https://openid.net/specs/openid-authentication-2_0.html#verification)
- [Microsoft Credential Manager CredWriteW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew)
- [Microsoft user-bound DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [Microsoft password edit controls](https://learn.microsoft.com/en-us/windows/win32/controls/edit-control-styles)
- [Microsoft WER memory exclusion](https://learn.microsoft.com/en-us/windows/win32/api/werapi/nf-werapi-werregisterexcludedmemoryblock)
- [Microsoft display-affinity capture limitations](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)

Completed local verification for this stage:

- ZComShare: 12 Node tests passed, including four security suites using SQLite.
- Den Designer: 35 Community Python/parser/installer tests passed.
- Unreal kit: 1,400 VM checks passed; the new cases execute numeric serialization,
  real engine outgoing mailbox persistence, and credential-shaped input refusal.
- Windows x64 proxy/worker cross-compilation passed. The separate native connection
  smoke executable passed under Wine/Xvfb with an injected fake transport (exit 0):
  ES_PASSWORD, invalid-key refusal, async profile success, field clearing, revoked-key
  failure, and credential-buffer clearing. It uses only a synthetic dummy key.
- Cloudflare production deployment dry run passed; additive migration applied
  successfully to the **local** development D1 database (14 SQL commands).

No real provider login or real authenticated upload is claimed by these tests.
