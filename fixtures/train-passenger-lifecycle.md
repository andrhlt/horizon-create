# APP-2113 train passenger persistence

This bounded repair covers seated passengers across stopped and moving
save/reopen, LAN guest rejoin, duplicate carrier prevention, dismount, and a
vanilla vehicle regression. Full 1:1 remains Open. APP-2010 (seats) and
APP-2051 (manual controls) supply the existing gameplay prerequisites.

## Finite cases and prior evidence

| Case | Prior result |
| --- | --- |
| Colored host and guest seats, travel, dismount | Existing `colored-train-seats` replay matched 123 Java ticks (246 rider samples) and both dismount poses at ticks 59 and 113. |
| Standing guest on quarter turn and gradual ascent/descent | Existing `curved-train-standing` and `train-incline-standing` gameplay support checks pass. These are not Java player traces. |
| Stopped/moving manual train reopen | Existing `manual-train-reopen` passes resumed reverse control and wheel spacing; it does not test passenger persistence. |
| Independent driver and passenger | Prior `--case interactions` pass: host and guest board separate seats, passenger input does not drive, host controls and moves the train, guest dismounts without releasing the driver, and remounts the moving seat. Rider poses converge within 0.02 blocks. |
| Idle seated host save/reopen | Prior build failed: verified mount was absent after save/restart. Reproduced with original host name and `@s`. |
| Active seated host save/reopen | Prior build failed: save/restart lost the host mount after interaction and guest disconnect. Guest rejoin assertions were not reached. |
| Patched build, guest rejoin, carrier deduplication, dismount then reopen, vanilla vehicle, static/elevator seat regression | Pending isolated integration on one identified patched build. |

The existing straight standing host/guest, walking off the edge, two-guest
reversal, and disassembly/reassembly evidence remains in PARITY.md. Colors are
equivalent for seat custody. Additional passenger mobs, exact pose interpolation
and network arrival timing, other mount points, and collision geometries remain
unverified.

## Identity and reproduction for prior failures

- Java: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
- Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3.
- Existing client: `native-9f42064-6ce68a31b125`; SHA-256
  `bdbafe5289f2c05ef76009c17070e0320a7c606e042dd5202b142e0e6d123fc9`.
- Pack SHA-256:
  `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
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
failures are regression reproductions, not results for the patch. The engine
patch has not yet been runtime-verified. Keep APP-2113 In Progress until the
pending cases and justified neighboring regressions pass on the repaired build.
Exact Java reload parity is not claimed.

The isolated native build attempt stopped before compilation: the launcher-data
source tree already contained an older patch set, so reapplying the repository
patches failed at `horizon-advancement-initial-inventory.patch`. The separate
13 GB compilation cache was copy-on-write cloned in `/private/tmp`; it was not
written by this attempt. This is a source-input/setup failure, not a result for
the APP-2113 patch.

## Source diagnosis and repair

Create's `native/elevator_seats.rs` uses marker armor stands as passenger
carriers. Pinned Horizon persistence serialized mobs, boats, and minecarts as
player `RootVehicle` trees, but omitted armor stands from vehicle lookup,
serialization, restoration, and removal. Armor stands are stored separately.
The patch adds them to those paths, retains rider compounds during chunk saves,
and restores rider slots when a carrier loads. This source-level repair still
needs the finite runtime checks above, including no duplicate or orphan carrier
after reconnect and safe dismount after reopen.

## Evidence handling

Prior captures used isolated temporary worlds and offscreen clients. No new
build or combined-main verification is claimed yet. Preserve raw logs for both
the old failing reproductions and the patched build; distinguish setup failures
from gameplay results. Record the final build and pack identity, elapsed time,
commands, per-case results, and remaining gaps here and in the PR.
