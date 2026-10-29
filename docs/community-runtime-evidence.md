# Community runtime investigation — 26 October 2026

## Initial investigation: decision and boundary

The existing Den Designer runtime remains content-only. A satisfactory general-purpose
pak-only transport has **not** been established for this slice's cancellation,
response-byte bounds, timeout and approved-origin requirements. This is a bounded
negative result, not a claim that Unreal has no HTTP implementation.

Do not enable an editor plugin merely because it appears in the merged kit or in
a staging manifest. Do not treat C++ facilities as Blueprint-callable facilities.

The minimum concrete alternative under investigation is an optional standalone
Windows bridge, loaded through an OS DLL proxy, with a fixed SaveGame mailbox to
the pak runtime. It would add a DLL and loader configuration but no UE4SS, engine
function hook or continuously running companion. The core offline editor must
remain usable without it. This initial proposal was **not shipped-game verification**;
subsequent implementation and user acceptance are recorded below. It relies
on a measured local SaveGame format, not a supported native Unreal plugin ABI.

## Evidence identities

The machine-readable [probe](community-runtime-probe.json) records hashes, selected
reflection rows, signatures and the exact search boundary. Absolute source paths
in that file identify the maintainer's local inputs, not player prerequisites.

* Installed executable: `SWZeroCompany/Binaries/Win64/SWZeroCompany.exe`, 64-bit PE,
  SHA-256 `aa3ff2e0759c90bae58054f2a68398e5b705fdfd05659242404d8c3602c6f36e`.
  REA `open_binary` independently identified the format and hash. It did not execute
  the game. The staged NonUFS manifest dates this executable to 13 October 2026.
* Historical reflection: reference collection v2, JMAP timestamp
  `2026-09-13T18:28:32Z`, engine 5.6, changelist 196985. Its complete object table
  has 73,481 rows, including 37,700 Function rows. This predates the installed
  executable; signatures are historical observations, not a fresh runtime dump.
* `objects.tsv` SHA-256:
  `c367c0d477d9c2b83034c77af4313920dda704136f464116749e78c5a8d8c639`.
  `properties.tsv` SHA-256:
  `a5407b83b10d129a07c3749976d0c27ad2dd896d462e803d4c21629b9807408a`.
* Supporting implementation source: the installed UE 5.6.1 engine tree, with hashes
  in the probe. Engine source explains the corresponding API's implementation;
  it is not substituted for disassembly of the game's customised binary.
* Native decompilation limit: REA `search_procedures("SendHTTPRequest")` timed out
  waiting for Hopper bridge readiness (`provider_timeout`, startup, 120 seconds).
  No native call trace or pseudocode was obtained and no successful decompilation
  is claimed. The session was closed after that failure.

A stale `Game version.txt` still mentions an August Steam build; it must not
identify the October executable. The Den Designer target build recorded elsewhere
in this repository is likewise not independent proof of this installation's ID.

## Facilities actually found

| Facility | Evidence | Use and limitation |
| --- | --- | --- |
| Movie Pipeline HTTP | Historical reflected class `/Script/MovieRenderPipelineCore.MoviePipelineExecutorBase`; protected `SendHTTPRequest` has `FUNC_BlueprintCallable`; corresponding literal remains in current executable at file offset 233213456. Class literal exists as UTF-16LE at 233212466. | A Blueprint subclass can potentially issue asynchronous HTTP. Presence is established; execution in the current shipped game has not been tested. |
| HTTP completion | Reflected `HTTPResponseRecievedDelegate`, BlueprintAssignable and protected; parameters request index, response code, response string. | Gives a completed body, not a streaming reader or native request handle. |
| Download image | Reflected `/Script/UMG.AsyncTaskDownloadImage:DownloadImage`; class literal UTF-16LE at 221985632 in current executable. | Produces `Texture2DDynamic`; no arbitrary JSON byte/string result. Fetching shared JSON through an image decoder is inappropriate. |
| JSON utilities | Historical `/Script/JsonUtilities.JsonObjectWrapper` with `JsonString`, dummy UObject; class/struct literal also in current executable. | A wrapper is not a parser or schema validator. No JSON parse Blueprint function was found in that full reflection table. |
| SaveGame | Reflected `GameplayStatics:LoadGameFromSlot` and `SaveGameToSlot`. Existing Den Designer uses them. | Suitable for locally constructed library data. Downloaded SaveGame or UObject deserialisation is excluded. |
| Game `LoadFile` | `/Script/Bruno.BrunoSaveGameSubsystem:LoadFile` takes a save filename and enters campaign loading. | It is not raw text file input; must never be used for Community responses. |
| Python | Shipped UFS manifest includes PythonScriptPlugin descriptor; local engine descriptor marks main module `UncookedOnly`. Historical reflection has no PythonScript API. Current binary contains an incidental `PythonScriptLibrary` string beside RemoteControl code. | Descriptor, Boost Python DLLs or a string do not establish in-game Python execution. No runtime scripting dependency is assumed. |
| Web browser | Historical WebBrowser module defines JS callback structs; no WebBrowserWidget class was found in that object inventory. | Does not establish a usable in-game HTTP/JSON bridge. |

The complete historical object table was also searched for `VaRest`,
`HttpBlueprint`, `JsonBlueprint`, `PythonScript`, `FileHelper` and
`LoadFileToString`; all returned zero matching paths. This is complete within that
particular table and does not prove absence from all future builds or nonreflected
native code. Literal searches in the current executable similarly cannot prove
availability or absence of callable code.

## Why the found HTTP node does not satisfy this task

In `MoviePipelineExecutor.cpp:203`, `SendHTTPRequest` creates an `IHttpRequest`,
sets URL/verb/headers/body, binds completion and starts it. It returns an integer
index. The actual request is held in a private `OutstandingRequests` array.
Completion at line 226 obtains the complete response as a string, then broadcasts
index/code/string; failure broadcasts code -1 and an empty string.

The reflected surface exposes no cancellation of that request, per-request
connect/read/overall deadline, streaming byte limit, final URL, response headers or
redirect veto. `CancelCurrentJob` and `CancelAllJobs` control render jobs; they are
not HTTP cancellation functions. Ignoring a late callback can prevent stale UI
mutation, but cannot bound the underlying network transfer or cancel it. Checking
string length after completion also cannot bound downloaded bytes or peak body
allocation. The corresponding source completion path does not remove finished
requests from its private array, another reason not to use it as a general client.

A Blueprint JSON parser could be authored, but that would not repair transport
cancellation or redirect-origin controls. The node is therefore a real candidate
that fails this slice's requirements, rather than an assumed unavailable feature.

## Smallest standalone alternative and installation implications

A narrow Windows x64 bridge can own HTTPS, strict JSON and payload validation,
request generations, cancellation, and bounded response buffers on its own worker.
Blueprint uses the shipped SaveGame APIs and a timer to exchange data with fixed
request/response slots under `ZComDen/Community/v1`. Only validated primitive values
reach Blueprint staging; commit constructs a fresh local composition and uses the
existing library, thumbnail and placement workflow. Remote responses must never
select functions, load executable modules, supply serialized objects, or become
console commands.

A single FString `Wire` field in a dedicated mailbox SaveGame class is the smallest
encoding candidate: its bounded text contains request generation and data records.
The bridge validates the locally generated request class and exact string property
tag, then emits the same measured local schema with a new bounded string. Header,
class paths and property names must come exclusively from an allowlisted local
template; none may come from the service. Fixed filenames, atomic response rename,
reparse-point refusal, private size limits and generation matching prevent path
selection, partial-response reads and stale completion. Import still constructs
a fresh layout through local Blueprint logic.

This is supported by an actual kit save (`NativeLayoutRoundtrip.sav`, 4,946 bytes,
SHA-256 `f990c92f36583786b986ea4ae0b8037d6b35aaaa8691adbe65b179a8db4e057b`):
GVAS version 3, UE4 package version 522, UE5 package version 1017; class FString
length at byte 1842 and `/DenDesignerGF/Runtime/BP_DenLayoutSave.BP_DenLayoutSave_C`
starts at 1846, followed by tagged properties. `GameplayStatics.cpp:2364` writes
`FSaveGameHeader`, then `FObjectAndNameAsStringProxyArchive`; its load path at 2460
reads the local class and constructs/serializes a new instance. A dedicated
mailbox fixture and fresh-process readback remain required; this existing layout
file proves the format family, not the new mailbox encoder. Do not adapt campaign
saves or arbitrary player files.

A proxy `version.dll` is an available bootstrap candidate because the actual PE
import table directly imports `VERSION.dll` with `VerQueryValueW`,
`GetFileVersionInfoW` and `GetFileVersionInfoSizeW`. A proxy must forward those
functions to the OS library using an absolute system path, initialise outside
loader lock, preserve existing proxies, and fail disabled if build validation
fails. `WINHTTP.dll` is also imported by the executable, although that alone says
nothing about Blueprint exposure. A private WinHTTP implementation avoids an
engine HTTP ABI dependency.

The implemented slice adds a proxy DLL and a bundled short-lived native request
worker next to the game's Win64 executable, plus the pak update. (Since 0.9.20
the worker is gone: requests run on guarded threads inside the DLL; see
`docs/holonet-phase4-plan.md`, "Single-DLL bridge".) The proxy owns
the worker process so cancellation and a total deadline also cover DNS/TLS hangs;
a kill-on-close Job object prevents it surviving the game. No separately started
service or Python runtime is installed. Proton
needs a `version=n,b` override; Windows loads the local proxy through normal DLL
search. Installation must refuse a running game and an unknown existing
`version.dll`; it must never overwrite another loader. Uninstallation removes only
the bridge's own verified files and restores only its own configuration changes.
The bridge must log an unsupported mailbox schema instead of guessing property
encodings after an update. It does not require game function offsets.

The executable's exports inspected with `objdump -p` include ImGui/ImPlot symbols
but did not expose `UObject::ProcessEvent`, `StaticFindObject`, `GUObjectArray` or
`FModuleManager`. No supported general native Unreal mod-plugin loading route has
been established. Editor SDK module binaries cannot be copied into this monolithic
Windows game. A proxy plus a build-specific reflection/tick boundary would add update and
crash risks. The fixed SaveGame mailbox avoids that boundary and should be tried
first. Native hooking is not part of the minimum proposal.

Offline tools found locally: Clang/clang-cl, lld-link, llvm-pdbutil and llvm-readobj
under `/usr/lib64/rocm/llvm/bin`; Windows headers and import libraries in the
installed Lutris Wine runner. Their presence makes a small freestanding Windows
DLL build plausible without installing a full UE Windows SDK, but is not a build
or runtime test. The shipped PDB is present; llvm-pdbutil reports GUID
`{28FDBAB2-F3FD-10A9-20AC-B2EF0623B9F0}`, age 1, with publics, globals and types.
The PE CodeView record matches that PDB GUID and age. Public symbols were located
for ProcessEvent, StaticFindObject and Tick, but the mailbox proposal needs none
of their addresses. They must not be used merely because they are available.

## Original proof obligations (status recorded below)

1. Generate a dedicated mailbox SaveGame in the kit; verify bounded native encoding
   and fresh-process Blueprint readback. Keep all game calls on the pak timer thread;
   the DLL must not dereference Unreal objects or call game functions.
2. Build and test the transport separately, then test the value boundary in the kit.
3. Fetch a genuinely published immutable composition from the deployed versioned
   service. Local registry fixtures and mocked API responses are not this proof.
4. In the shipped game, resolve/download, show dependencies, import persistently,
   generate a local thumbnail, and place through normal composition UI. Record
   offline, cancelled, oversized, malformed, unknown-code and schema failures.
5. Package exact verified bytes and install only with the game closed.

Until these are observed, describe the result as an investigated implementation
candidate or kit slice, never a proved shipped-game Community integration.

## Subsequent implementation results

The standalone DLL and worker now build with Clang/lld against Windows system
imports. Native Wine smoke checks cover the live published test, forwarding,
cancellation, the total deadline and parent-exit cleanup. A fresh Unreal process
deserialized the exact live worker response, imported its monitor into the local
library, staged the existing thumbnail system, and placed/undid it through the
composition workflow. The packages were installed with the game closed.

The user subsequently confirmed successful fetch/import, rendered thumbnails,
placement and persistence after restarting the shipped game with preview.3.
That establishes user-reported happy-path acceptance for the published test;
manual shipped-game failure-path tests remain separate from the automated checks.
The complete scope, limits, test counts and installation evidence are recorded in
[Community verification](community-verification.md).
