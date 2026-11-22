# APP-2113 train passenger persistence

This bounded repair covers seated passengers across stopped and moving
save/reopen, LAN guest rejoin, carrier uniqueness, and safe dismount. Full 1:1
remains Open. APP-2010 (seats) and APP-2051 (manual controls) supply the
existing gameplay prerequisites.

## Finite cases and prior evidence

| Case | Result |
| --- | --- |
| Colored host and guest seats, travel, dismount | Existing `colored-train-seats` replay matched 123 Java ticks (246 rider samples) and both dismount poses at ticks 59 and 113. |
| Standing guest on quarter turn and gradual ascent/descent | Existing `curved-train-standing` and `train-incline-standing` gameplay support checks pass. These are not Java player traces. |
| Stopped/moving manual train reopen | Existing `manual-train-reopen` passes resumed reverse control and wheel spacing; it does not test passenger persistence. |
| Independent driver and passenger | PASS: host and guest board separate seats; passenger input does not drive; host controls and moves the train; guest dismount preserves the driver's control, then remounts the moving seat. Both rider poses converge within 0.02 blocks. |
| Idle seated host save/reopen | PASS on corrected build: host retains mount and exact seat pose; stopped train remains stopped; exactly one carrier remains. |
| Active seated host save/reopen and guest rejoin | PASS on corrected build: train resumes moving; host pose is restored; guest rejoins its seat; exactly two carriers remain for the two riders; guest safely dismounts without releasing the host. |
| Affected regressions | PASS on the same corrected build and matching pack: colored train seats, manual train reopen, curved/incline/straight standing, and moving elevator standing. |

The existing straight standing host/guest, walking off the edge, two-guest
reversal, and disassembly/reassembly evidence remains in PARITY.md. Colors are
equivalent for seat custody. Additional passenger mobs, exact pose interpolation
and network arrival timing, other mount points, and collision geometries remain
unverified.

## Build identity and reproduction

- Java: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
- Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3.
- Corrected client: `native-9f42064-8c43389a931b`; SHA-256
  `4e239c35ee34743dede4460cac93457dca7ed5f4c16af5db74ab3bfeed8dfea4`.
- Corrected Create bundle SHA-256 from `native-mods.json`:
  `bc2c64984e21749f8e746e634d8bcc0ad9108f91f8804b1a65e61698737c9370`.
- Test pack SHA-256: `6925a9a1e4c1a01acbdc6a72f3b40bcb8e88f4d75e9dce103b747591b0b7c678`.
- Prepared resources came from `native-9f42064-d6dc2ad18d3f`.

With `B` the existing client directory and `R` the prepared resource directory:

```sh
HORIZON_NO_AUDIO=1 python3 tools/test-train-passenger-lifecycle.py \
  --case idle "$B/horizon-ctl" "$B/horizon-client" "$R"
HORIZON_NO_AUDIO=1 python3 tools/test-train-passenger-lifecycle.py \
  --case active "$B/horizon-ctl" "$B/horizon-client" "$R"
```

The three checks are registered as `train-passenger-interactions`,
`train-passenger-idle-reopen` and `train-passenger-active-rejoin`. Prior
failures are regression reproductions, not results for the patch. All three
checks passed on the corrected build above. The first sandboxed attempt was
blocked before gameplay because local control socket creation was denied; its
rerun passed. A first idle run passed gameplay assertions but exited during
cleanup because its retained-save destination already existed; a fresh
destination rerun exited cleanly. Exact Java reload parity is not claimed.

The earlier isolated native build attempt stopped before compilation because
launcher-data already contained an older patch set. The corrected staged build
was reused and its metadata confirms the repaired Create bundle hash above.

## Source diagnosis and repair

Create's `native/elevator_seats.rs` uses marker armor stands as passenger
carriers. Pinned Horizon persistence serialized mobs, boats, and minecarts as
player `RootVehicle` trees, but omitted armor stands from vehicle lookup,
serialization, restoration, and removal. Armor stands are stored separately.
The patch adds them to those paths, retains rider compounds during chunk saves,
and restores rider slots when a carrier loads. This source-level repair still
needs the finite runtime checks above, including no duplicate or orphan carrier
after reconnect and safe dismount after reopen.

## Saved and loaded identity evidence

The stopped case trace shows no `RootVehicle` in the live player command output
before save; after restart, the player `RootVehicle.Attach` UUID equals the
restored armor stand UUID. The same UUID link is present after moving restore.
Preserved command traces: [stopped pre-save](app-2113-stopped-before-save.json),
[stopped post-restart](app-2113-stopped-after-restart.json),
[moving pre-restart](app-2113-moving-before-restart.json), and
[moving post-restart](app-2113-moving-after-restart.json). Runtime assertions
also verified rider position convergence and carrier counts. The corrected
build serializes and resolves the armor stand mount reference across restore.

Prior failed saves and logs remain in `/private/tmp/horizon-app-2054/.local/`
and were not overwritten. The main worktree's earlier test pack (`2dde…`)
caused one incline check to fail; rerunning with the exact APP-2113 pack
(`6925…`) passed. This pack mismatch was isolated from the patch result.
