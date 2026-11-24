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

## Pinned 0a route result

On 2026-11-23, runtime `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, SDK
`1.99.1`, and launcher build `native-0a875da-4388e6fde41d`, one local
dedicated server accepted both headless clients. The server log records both
join events. Its whitelist assigned `Create2172Host` UUID
`799b198e-b7b6-3d66-a793-3cf3375643a2` and `Create2172Guest` UUID
`eb0e20a5-f85d-3404-84a7-e4b4f64ae0ae`. Both clients disconnected cleanly and
the server saved and stopped. The captured build contains only the kinetic
probe package; this verifies the supported runtime route, not the production
Create package or APP-2165's marker-query fix.

## Remaining package and provenance gates

The full package gameplay route above passed, but the issue's pinned 0a
production build and selected `3fa53d4b99ca22bba5897c6544b9515fd5521948`
marker-query fix are still unverified. The available 0a runtime contains only
`create_kinetic_probe`; it is not the production Create native module. The
0a/3fa build must produce and load the full package on both client and server,
then repeat the focused fixed-runtime behavior with matching receipts before
APP-2172 can meet its pinned build contract or declare companion provenance.
At this checkpoint, the GitHub PR-authentication status had not yet been
rechecked; the current connector state is recorded below.

## 3fa source build attempt (2026-11-24)

The selected public Horizon source commit
`3fa53d4b99ca22bba5897c6544b9515fd5521948` was checked out in a task-local
clone and built with Rust 1.99.1 using the `fast` profile. The resulting
`horizon-client`, `horizon-server`, and `horizon-ctl` binaries had SHA-256
`9e97d48a98020df11cbaa4b5c662c1e2a75c2b6b508dcbd8d8236081f0e8a5dc`,
`08956bdf64181fef1f82e09c942ee8bd9824f925657589566e82fc8e405ef883`, and
`f9e771f81e545375a6d04885ece82352603dab188e8e359b36f5af0939573202`
respectively. This is a source-built
local runtime cohort, not an indexed 3fa SDK cohort.

The source's `tools/prebuilt_game.py build` route stages the 3fa API, then
exhausts the host filesystem while compiling the SDK's `horizon-client`
library, both with its published `release` profile and with a temporary
`fast`-profile attempt matching the runtime binaries. Both builds were stopped
before producing a complete SDK. The failed outputs were removed; the source
checkout and three game binaries remain under task-local `.local/` storage.
Consequently, no native Create module was built for the 3fa binaries and the
full production package route was not run on 3fa.

The completed production package gameplay proof remains the 9f cohort above.
The earlier 0a two-client proof remains probe-only. Do not treat either as
fixed-runtime 3fa acceptance. The configured GitHub connector currently has
push permission, and the branch is pushed; the missing PR is waiting on this
runtime/package acceptance, not a credential reconnection.
