# APP-2004: Minecart Coupling, Anchor and portable cargo

## Bounded acceptance

Preserve the existing Java-derived coupling evidence in PARITY.md and the matrix.
APP-2003 (Cart Assembler and Controller Rail) is Done and supplies the integrated
assembly prerequisite. This pass covers:

- Two-cart link/unlink and survival item consumption/refunds; three-cart loop rejection.
- Representative flat bend and ascending-east travel/reversal, using existing pinned Java traces.
- Anchor assembly/disassembly and existing portable recipes and plain-block/state round trips.
- Portable loaded vanilla chest and barrel: seven copper ingots and saved block-entity inventory,
  pickup, repeated-click duplication guard, redeployment, second pickup and disassembly.
- Moving cargo save/reopen retaining cart identity, forward operation and cargo, and picked-up item save/reopen.
- Survival LAN guest pickup and redeployment of plain stone and loaded chest, with host cargo checks.

The item transition is instantaneous; picked-up inventory persistence is its meaningful
idle save case. Moving mounted cargo supplies the active case. These are Horizon
persistence checks, not claims of exact Java reload or packet-arrival parity.

## Source and implementation

Pinned Create: `ac0c444d9828da3453ae8cc65338e8de063286fb`.
Pinned Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` / Minecraft 26.3.

Reviewed `MinecartContraptionItem.wrenchCanBeUsedToPickUpMinecartContraptions`,
`create`, `useOn`, and `addContraptionToMinecart`, `Contraption.writeNBT` /
`writeBlocksCompound`, and chest/simple mounted storage unmount rules. Java carries
block-entity data and mounted inventories in the portable item and restores inventory
on unmount. Horizon previously rejected every saved block entity during pickup.

The codec now retains vanilla chest/barrel NBT in each palette entry's `Data` field,
then restores it to the existing mounted payload's `VanillaEntity` field. Horizon's
native block-entity NBT includes inventory, whereas Java also uses its separate mounted
storage codec; this does not claim byte-identical Java inventory serialization.
No entity IDs or display handles are stored in the portable block entries.
Other unsupported actors/storage/glue continue to remain mounted rather than lose data.
Review checked that pickup validates all blocks before removing cart/display entities,
and deployment validates all decoded entries before spawning or consuming the item.
The change reuses the mounted payload's current inventory, rather than an assembly-time
snapshot, and does not introduce a second inventory representation.

Source SHA-256:

- `MinecartContraptionItem.java`: `bc1a64974b164aba9ca8163a1acb0270e0eeb713e588849a86cd205057f3b626`
- `Contraption.java`: `ce7730cdd20b2b065f2b9f5deac149b5b36a3a473a79a25595191ae82170708e`

## Reproduction and environment

The pre-fix client `native-9f42064-6ce68a31b125` failed the loaded-chest pickup:
the player retained only the Wrench and received no portable item.
Raw failure: primary checkout `.local/app-2004-evidence/chest-before-unsandboxed.log`.
The first lifecycle fixture (`chest-before-lifecycle.log`) also used an invalid
zero-tick reload assumption: the client advances simulation before its control socket
can freeze the reopened world. The corrected fixture uses a longer rail, verifies
actual pre-save movement and post-reopen forward operation/identity, and records
positions without claiming a precise reload tick boundary.
An earlier sandboxed attempt failed to create its local control socket and is invalid
as gameplay evidence (`chest-before.log`).

A first build failed because the shared source was already patched with a different
digest. The successful setup copies the matching pinned patched source (digest
`664100af7e67dd9fdd01c04d91f175f7e221e39d`) into this worktree and uses a private
copy-on-write compiler cache under the primary checkout's `.local/app-2004-builder`.
No shared source/cache was modified. Builds use the compatible official launcher 0.2.67.
Worlds are temporary and clients headless or hidden offscreen; no desktop game is used.

Pack: `create.hmod`, SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Resources: `/private/tmp/duck-prepare-root/.local/horizon-client/26.3`.

## Results

Build `native-9f42064-7ed7f56ac77a` completed in 645 seconds. Script/data syntax
checks passed (487 JSON, 45 JSONL, 889 Python, 2 shell and 3 TOML files).
Client SHA-256: `a0ac417e77fbcf4c0468226e512e5b7fd82e117f2ef7aad805857db43deea5bf`.
Control tool SHA-256: `1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`.
The build includes cursor fix 16af87f via its main baseline.
Both portable checks passed: seven solo payloads (five prior plain-block/state cases,
chest and barrel) and two LAN guest payloads (stone and chest). Each loaded container
retained seven ingots; solo checks include moving and picked-up reopen and a second
pickup. Final loose-copper checks found no duplicated ground cargo.
All **16/16** selected checks passed (14 regressions plus the two portable checks).
The four curve/slope runs matched all 324 pinned Java samples. Regression runner:
422.8 seconds. Checks covered anchor, solo/LAN link/unlink, solo/LAN Wrench
restart/refunds, solo/LAN destruction/drops, solo/LAN chain/loop rejection,
solo/LAN curve, solo/LAN slope/reversal and survival recipes.

Curve and ascending-east reversal replays reuse their pinned Java CSVs, sampling
81 rows each from fixture tick 0 through 80, with position/velocity tolerance `1e-5`.
The survival inventory/slot/count and portable state assertions are exact. Reopen
checks verify identity, cargo and continuing direction, not an exact launch/reload
simulation boundary. Guest waits establish eventual agreement with the host, not
Java-equivalent packet arrival/interpolation timing.

The first new-client lifecycle run retained cart identity, forward motion and all seven
copper ingots after reopen, but an added custom-name assertion failed. The captured
payload already lacked `CustomName` before portable encoding: Horizon's vanilla
`encode_block_entity` omits the separately stored world block name. This preexisting
assembly label loss is cosmetic and is recorded as a nonblocking follow-up. The test
still starts from a named container, but requires its inventory and block state rather
than claiming preservation of that missing label. Raw result: `chest-after.log`.

## Reproduction commands and timing

From this ticket worktree, with its copied `create.hmod` in `.local`:

```sh
runtime=.local/patched-launcher/versions/native-9f42064-7ed7f56ac77a
resources=/private/tmp/duck-prepare-root/.local/horizon-client/26.3
HORIZON_NO_AUDIO=1 python3 tools/test-parity.py "$runtime/horizon-ctl" "$runtime/horizon-client" "$resources" --jobs 1 \
  --check minecart-pickup --check minecart-pickup-lan
HORIZON_NO_AUDIO=1 python3 tools/test-parity.py "$runtime/horizon-ctl" "$runtime/horizon-client" "$resources" --jobs 1 \
  --check minecart-anchor --check minecart-coupling --check minecart-coupling-lan \
  --check minecart-coupling-wrench-restart --check minecart-coupling-wrench-restart-lan \
  --check minecart-coupling-chain-destroy --check minecart-coupling-chain-destroy-lan \
  --check minecart-coupling-chain --check minecart-coupling-chain-lan \
  --check minecart-coupling-curve --check minecart-coupling-curve-lan \
  --check minecart-coupling-slope --check minecart-coupling-slope-lan \
  --check minecart-contraption-items
python3 tools/check-source.py
```

The two gameplay runners ran concurrently with one worker each. Portable runner:
228.8 seconds. Regression elapsed time is recorded in Results above.
Setup/source discovery and initial reproduction were approximately 21:45–21:50 UTC;
coding and fixture preparation overlapped compilation at 21:49–21:55. Lifecycle
fixture debugging ran approximately 22:01–22:03. Build: 645.7 seconds; initial
syntax check: 2.3 seconds. No new Java capture was needed; pinned existing coupling
fixtures were retained. These phase intervals overlap and are not additive CPU time.
Raw results remain under the primary checkout's `.local/app-2004-evidence/` and
this worktree's `.local/parity/`; failed/invalid results are retained as described above.

## Follow-ups

Full 1:1 remains Open. Container display-name preservation during assembly is a known
cosmetic follow-up. Other portable actors/inventories, glue, furnace/chest cart
carriers, cargo rotations and broader chains/off-rail/unloaded lifecycle geometries
remain outside this bounded pass. Existing matrix evidence and its detailed limits
continue to apply. Exact Java storage bytes, save/reload timing, network arrival,
render interpolation, pixels and sounds are not established by these checks.
