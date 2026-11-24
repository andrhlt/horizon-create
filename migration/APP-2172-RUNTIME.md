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

## Recorded route result

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

APP-2172 is not complete from this runtime smoke. Build and load the migrated
production Create package on both client and server, compare package/content
identities, and exercise the bounded host/guest action that depends on the
selected engine fix. Record a native build receipt whose source revision
contains the selected fork fix and hash the actual client, server, mod and
content artifacts. SDK metadata or a matching version string alone does not
establish that the binaries include the fix. Until those artifacts and the
focused behavioral result match, do not claim companion provenance or mark
the production package verified.
