# APP-2054 passenger lifecycle pass

This is a **partial, blocked gameplay pass**, not baseline completion. The
existing travel evidence remains valid; Full 1:1 stays Open. APP-2010 (seats)
and APP-2051 (manual controls) are Done and supply the prerequisites.

## Finite cases and results

| Case | Result |
| --- | --- |
| Colored host and guest seats, travel, dismount | PASS: existing `colored-train-seats` replay matched all 123 Java ticks (246 rider samples) and both dismount poses at ticks 59 and 113. |
| Standing guest on quarter turn | PASS: `curved-train-standing`. Retains the existing gameplay support check, not a Java player trace. |
| Standing guest on gradual ascent/descent | PASS: `train-incline-standing`. Route comes from Java; player support is Horizon gameplay evidence. |
| Stopped/moving manual train reopen | PASS: `manual-train-reopen`, including resumed reverse control and wheel spacing. This does not test passenger persistence. |
| Independent driver and passenger | PASS: `--case interactions`. Survival host and guest board separate seats. Six passenger W-input ticks leave train speed/distance/wheels unchanged. Seated host takes controls and drives 12 ticks. Guest Sneak dismounts, preserves Driver, then boards the moving seat again. Both rider poses converge within 0.02 blocks. |
| Idle seated host save/reopen | FAIL: after verified mount and save/restart, current host has no authoritative vehicle. Reproduced with original host name and with `@s`. |
| Active seated host save/reopen | FAIL: following the passing interaction sequence and guest disconnect, save/restart loses the host mount. Guest rejoin assertions after that failure were **not reached**. |

Existing straight standing host/guest, walking off the edge, two-guest reversal,
and disassembly/reassembly evidence is retained in PARITY.md. It was not
recaptured. Colors are equivalent for seat custody; straight, quarter-turn and
gradual up/down routes are representative collision geometries, not every slope.
Additional passenger mobs, exact pose interpolation/network arrival timing,
other mount points and collision geometries remain unverified.

## Identity and reproduction

- Java: Create `ac0c444d9828da3453ae8cc65338e8de063286fb` (verified local checkout).
- Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3.
- Existing client: `native-9f42064-6ce68a31b125`.
- Client SHA-256: `bdbafe5289f2c05ef76009c17070e0320a7c606e042dd5202b142e0e6d123fc9`.
- Pack SHA-256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
- Java seat capture patch SHA-256:
  `1b7a4bef643b1f5a87a9b61a024bca6c72255809e866bd8e69a811276880a244`.
- The prepared 26.3 resources were reused from sibling build
  `native-9f42064-d6dc2ad18d3f`; ctl and client both came from `6ce68a31b125`.
  No new client build or combined-main verification is claimed.

With `B` the existing client directory and `R` the prepared resource directory:

```sh
TMPDIR=/private/tmp HORIZON_NO_AUDIO=1 python3 tools/test-parity.py \
  "$B/horizon-ctl" "$B/horizon-client" "$R" --jobs 2 \
  --check colored-train-seats --check manual-train-reopen \
  --check curved-train-standing --check train-incline-standing

HORIZON_NO_AUDIO=1 python3 tools/test-train-passenger-lifecycle.py \
  --case interactions "$B/horizon-ctl" "$B/horizon-client" "$R"
# Known failing reproductions (idle and active fail at the host mount check):
HORIZON_NO_AUDIO=1 python3 tools/test-train-passenger-lifecycle.py \
  --case idle "$B/horizon-ctl" "$B/horizon-client" "$R"
HORIZON_NO_AUDIO=1 python3 tools/test-train-passenger-lifecycle.py \
  --case active "$B/horizon-ctl" "$B/horizon-client" "$R"
```

The three cases are registered as `train-passenger-interactions`,
`train-passenger-idle-reopen` and `train-passenger-active-rejoin`. The last
two intentionally expose unresolved blockers; this PR is not ready to merge.
Syntax compilation and `git diff --check` pass. No Rust changed, so no new Rust
build/Clippy results are claimed. Integration used isolated temporary worlds
and offscreen clients without desktop interaction or shared compilation writes.

## Source diagnosis and required shared repair

Reviewed Java `AbstractContraptionEntity` passenger interaction, seat mapping,
positionRider and dismount callbacks, `SeatBlock` state/interaction behavior,
and `CarriageContraptionEntity` passenger handling. Existing native attachment
and dismount offsets correspond to those rules. No new Java capture was needed
for ordinary save/reopen gameplay; exact Java reload parity is not claimed.

Create's `native/elevator_seats.rs` uses marker armor stands as passenger
carriers. In pinned Horizon `crates/horizon-client/src/game/persist.rs`,
`vehicle_tree_nbt` serializes mobs/boats/minecarts, `vehicle_by_uuid` recognizes
the same classes, and `restore_saved_vehicle` rejects other root kinds. Armor
stands are held separately. This supports a shared vehicle-persistence diagnosis;
it is not proof that adding a serializer branch alone fixes the lifecycle.
The shared owner must also check restoration ordering, seat pruning, unload and
deduplication before a verified fix. No shared persistence patch is bundled here.

Required follow-up is bounded: idle and moving host passenger restoration;
guest disconnect/rejoin without duplicate/orphan carriers; dismount then reopen
without resurrecting a ride; one vanilla vehicle and affected static/elevator
seat regression. Keep APP-2054 In Progress until these pass on the repaired build.

## Raw evidence and invalid attempts

Raw logs are retained in the ticket worktree's `.local/`: `parity/*.log`,
`passenger-lifecycle-first.log`, `passenger-lifecycle-second.log`,
`passenger-lifecycle-third.log`, `passenger-interactions-first.log`,
`passenger-interactions-second.log`, and `passenger-active-first.log`.
The first lifecycle run failed in setup (host name queried before LAN opened).
The first interaction run failed in setup (duplicate LAN open). Both were
corrected; neither is counted as gameplay evidence. The initial sandboxed
regression attempt could not open control sockets and was rerun outside the
sandbox. Final four-check logs report 4/4 PASS; the later lifecycle logs retain
the genuine mount failures. Artifacts are local, not attached to an issue.

Time accounting was not separately instrumented: source/setup and harness
development were interleaved with roughly 15 minutes of offscreen integration
and debugging. New capture/build time: none. No exhaustive parity or completed
save/rejoin gate is claimed.
