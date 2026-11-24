# APP-2172 local multiplayer runtime route

The supported managed Play route in the checkpoint evidence is single-player.
For automated local multiplayer, use the installed matching Horizon CLI pair:
`horizon-server` for a dedicated local server and `horizon-ctl launch` for
headless clients. The client binary documents `--server HOST[:PORT]` as
offline mode. This route does not use managed Play and does not change account
authentication or lease enforcement.

The repeatable smoke is:

```sh
python3 tools/test-offline-two-client-route.py \
  --server-binary /path/to/pinned/horizon-server \
  --client /path/to/the/same/build/horizon-client \
  --ctl /path/to/the/same/build/horizon-ctl \
  --resources /path/to/prepared/26.3 \
  --output /private/tmp/app-2172-route-proof
```

Use the exact same build directory for both client and server executables,
the pinned SDK toolchain recorded in the build receipt, and the content package
under review. The runner checks each executable and `native-mods.json` by
SHA-256 and retains the server log, per-client logs, UUIDs, and installed
package manifest in the output directory. Client game homes and player files
are separate. The server binds only to `127.0.0.1`, has a two-name whitelist,
and uses the runtime's explicit offline-server option. Do not expose this
server to a LAN or public interface. It uses no sign-in, copied credential,
lease change, or authentication patch.

## Production package route result

On 2026-11-24, the complete production `create.hmod` was installed and enabled
on the dedicated server and both clients. The matching native Create build was
`native-9f42064-6bdf8691aa42` (Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`,
Rust 1.99.1, mixins `5a64af938ec86b00d53d16a408aabc0038fb3e57`). Its
`native-mods.json` listed `create` with no left-out mods. This is the source
revision pinned by the current `native/horizon-mixin.toml`; it is not the
APP-2172 0a/3fa candidate.

The package was freshly built with `python3 tools/prepare.py` from Create
commit `ac0c444d9828da3453ae8cc65338e8de063286fb`. Its 9,262 archive entries
had SHA-256
`253311260017a64c37c2b1506fa6e7cd9010c280beaa0970167a15ae08b6e7be` on the
source file, server copy, host copy, and guest copy. On clean startup the
server generated Create content registrations with zero content warnings:
658 blocks, 711 items, four fluids, and three entity types. The host received
four Create shafts, placed one at `0 64 -16`, and the server reported its
`create:simple_kinetic` block entity with `Speed`, `Network.Capacity`, and
`Network.Stress`. After `/save-all flush`, both clients disconnected, and the
server stopped and reopened, that same block entity data was present. The
host inventory held all four shafts, and the guest observed the placed shaft
at the same coordinates with state `create:shaft[axis=y,waterlogged=false]`.
The reopened config retained loopback binding, whitelist enforcement,
two-player limit, view/simulation distances, world name, seed, and survival mode.

The generated package is at `/private/tmp/horizon-app-2172/.local/create.hmod`
on the validation host. The proof and exact binary, native-mod manifest, and
package hashes are in
`migration/APP-2172-route-proof.json`. The server logs and isolated world are at
`/private/tmp/app-2172-production-rebuilt` on the validation host. Reproduce
with the runner command below, substituting the matching 9f binaries and
package path:

```sh
python3 tools/test-offline-two-client-route.py \
  --server-binary /path/to/native-9f42064-6bdf8691aa42/horizon-server \
  --client /path/to/native-9f42064-6bdf8691aa42/horizon-client \
  --ctl /path/to/native-9f42064-6bdf8691aa42/horizon-ctl \
  --resources /path/to/prepared/26.3 \
  --package /path/to/create.hmod \
  --output /private/tmp/app-2172-production-route
```

This establishes production package loading, registration, item/block use,
save/reopen, configuration persistence, and the supported local two-client
route on the current compatible 9f production build. It does not prove every
legacy callback, optional integration failure behavior, or config hot-reload.

## Production package on the pinned 0a runtime

On 2026-11-24, the full native package `create` was loaded by the pinned
Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a` runtime with Rust/SDK
1.99.1 and mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`. The tested
launcher was 0.2.105. The package contains the canonical Rust root at
`migration/create`, kinetic and controls adapters, and the normalized full
Create content at the same flat package root under `assets/` and `data/`.
`native-mods.json` listed `create` with no omitted native modules. The tested
package tree SHA-256 was
`a8712458841000595e526072776df6c9d1772749804a5bcddce8edb6e8dec59d`.

A localhost-only dedicated server accepted two whitelisted headless clients
with distinct UUIDs. The server registered 658 blocks, 711 items, four fluids,
and three entity types with no registry warnings. Representative server and
two-client behavior covered motor and shaft rotation, clutch stop/restart,
gearshift reversal, rejection of opposing sources, speed ratios, controller
and sequencer UI/state, gearbox and flywheel behavior, chain signal/output,
loop conflict handling, stress overload and recovery. The shaft, ratio output,
controller, sequencer, and whitelist/world configuration survived save, clean
stop, and reopen. Full captured evidence is in
`migration/APP-2172-0a-production-proof.json`.

The tested normalized source content archive was
`/private/tmp/create-0a-content-v9.hmod` (SHA-256
`a250e64669a078792354ca91a3894f223d9e61eabe6b051338f8bf3d0a4afa83`). Its
original source was `.local/create.hmod` (SHA-256
`253311260017a64c37c2b1506fa6e7cd9010c280beaa0970167a15ae08b6e7be`). The
compatibility conversion removed 203 block fields unsupported by Horizon 0a,
translated 9 field groups, added 2 menu definitions, normalized one loot
condition array, and deduplicated 2 fluid block/item definitions. This is a
working package with known data limitations; those source-to-0a omissions are
recorded in the converter report.

A follow-up converter change now evaluates optional NeoForge recipe conditions
against tags in the pack and moves three configured worldgen features to the
0a `worldgen/feature` registry path. Its normalized archive passed structural
checks: 30 genuinely optional recipes omitted, no retained recipe contains a
NeoForge load condition, and no configured-feature paths remain. This revised
content archive has **not** yet been rebuilt into a native runtime package or
run through gameplay, so the acceptance proof above applies to the earlier
v9 package. The v2 report is retained at
`migration/APP-2172-0a-content-report.json`; the follow-up should be folded
into the next full runtime acceptance when a writable pinned build is
available.

The repeatable source preparation commands are:

```sh
python3 tools/prepare-0a-content-pack.py .local/create.hmod /path/to/create-0a-content.hmod --report /path/to/content-report.json
python3 tools/prepare-create-native.py --output /path/to/create-native --content-pack /path/to/create-0a-content.hmod
```

Build the staged native project against the exact 0a launcher SDK, then install
that one package as the `create` native module. Use
`tools/test-create-production-offline-route.py` with the matching dedicated
server/client/ctl binaries and content resources to repeat the isolated route.
The runner uses distinct player homes and UUIDs and retains logs, package/runtime
hashes, save/reopen observations, and server configuration. It binds only to
`127.0.0.1`, uses the supported offline server path, and makes no account,
credential, lease, or authentication changes.

## Fan and Nozzle package integration

The staged native package also includes `native/create_fan_nozzle_adapter.rs`
and `native/fan_airflow_math.rs`. `migration/create/src/lib.rs` declares both
modules and registers the Nozzle block-entity part; the package builder copies
both canonical source files into the package's `src/` directory. The Fan tick
callback is exposed for the kinetic part to call after graph recomputation.
The adapter source is refreshed from APP-2177 commit
`402e4489314cc64b3b0f75285565aba4d7364b9a` (SHA-1
`4bd7b95692e9e3c222b1c8b3d897840f78892354`), which stores Depot processing on
the Depot entity, splits output stacks, and tracks affected entities by UUID.
This adapter addition has not yet been exercised in the captured APP-2172
two-client proof above; its runtime behavior remains open until the combined
package is rebuilt and checked.

## Remaining acceptance notes

The production package, registrations, representative gameplay, save/reopen,
and distinct-UUID offline route now pass on the pinned 0a runtime. The 3fa
marker-query behavior has not been separately verified against this package;
small rendering/audio variants and optional integrations absent from the pack
remain follow-up coverage rather than claimed passes. The later converter
cleanup described above still needs incorporation into a fresh runtime build
and route run. PR #206 is open for review; no checks have reported yet. Keep the
issue open through review and resolve it through the agreed `/close` workflow
after the remaining acceptance notes are dispositioned.

## Historical 3fa build attempt

A source build of Horizon `3fa53d4b99ca22bba5897c6544b9515fd5521948` with Rust
1.99.1 exhausted available disk while compiling the matching SDK. Partial build
outputs were removed. That attempt is superseded for package acceptance by the
successful pinned 0a production runtime route above; it did not establish
behavior for the 3fa marker-query change.
