# APP-2058 Train door integration

## Bounded acceptance matrix

Preserve the existing Java captures and implementations. Prerequisites APP-2051
(manual driving/controls) and APP-2057 (Sliding Doors) are Done. This pass adds
physical passenger checks, rather than repeating the extensive material and
orientation comparisons in PARITY.md.

| Case | Evidence |
| --- | --- |
| Appropriate stopped platform and departure/arrival | Existing scheduled-train-doors and station-door-control compare 123 authority samples, ticks 23–145; Train Door platform replay checks origin closure and Terminal arrival. NORTH opens only the north side at the destination. |
| Paired supported leaves and manual choice | Existing paired-train-door compares five Java observations for all four halves, with next-tick persistence; solo and guest actions are covered. |
| Closed collision and open passenger passage | New train-door-passage checks actual Survival walking through a north-facing pair, both solo and as host/guest. |
| One obstruction | A two-block-high stone column beyond the open door stops each walker without changing the four open flags. This is physical obstruction, not an invented obstruction sensor. |
| Stopped reopen | Existing paired-train-door-reopen retains manually open and closed pairs, including guest rejoin. |
| Moving reopen | Existing moving-paired-train-door-reopen-open/closed saves a moving curved train and checks cold states/poses before ticking, then guest rejoin. |

The paired station layout, straight departure and curved moving reload represent
the required integration classes. Broader platform layouts, rotated passage,
trapdoor orientations, folding animation variants and exact guest packet timing
remain follow-ups. Full 1:1 stays Open.

## Reference and interpretation

Create 6.0.10 `ac0c444d9828da3453ae8cc65338e8de063286fb`:
`SlidingDoorMovementBehaviour.tickOpen/shouldOpen/shouldUpdate/getDoorFacing`,
`DoorMovingInteraction.handle/updateColliders`, and `SlidingDoorBlock.getShape`
with `SlidingDoorShapes`. These establish station-side selection, changed-target
updates preserving manual choice, paired interaction and collider invalidation.
Horizon already implements those paths in `elevator_doors.rs`, `train.rs` and
`elevator_collision.rs`; no ordinary passage mismatch required a native fix.

“Close before travel” follows the Java actor update timing: the captured train
starts at speed 0.0075 on tick 27, reaches 0.015 on tick 28, and closes both sides
on tick 29 at speed 0.022499999. This pass does not claim closure at zero speed
or change the Java rule to impose it. Tick origin is the existing capture's
world tick, mapped by the replay to its schedule-assignment origin.

The new passage check uses real key input, a level landing and a stopped
assembled train, with normal ticking during each walk and separate worlds for
closed, open and obstructed layouts. The open case also walks back onto the deck. Client feet height must remain within 0.05 blocks of the deck;
client/server positions must agree within 0.05 blocks. Closed doors stop at the
north panel; open doors permit crossing beyond it; the exterior stone column
stops the player before the landing exit. Four door-half flags are exact.
This is functional Horizon collision evidence, not a Java tick-by-tick movement
or network arrival comparison.

## Reproduction

Use the identified final build's `horizon-ctl`, `horizon-client`, and prepared
26.3 resources as the three positional arguments to `tools/test-parity.py`:

```sh
python3 tools/test-parity.py CTL CLIENT RESOURCES --jobs 2 \
  --check 'train-door-passage*' --check 'station-door-control*' \
  --check 'train-sliding-platform*' --check 'paired-train-door-reopen*' \
  --check 'moving-paired-train-door-reopen-open*' \
  --check 'moving-paired-train-door-reopen-closed*' --check manual-train
python3 tools/check-source.py
git diff --check
```

All worlds/guest directories are temporary and all render clients are hidden
`--offscreen`. The ticket uses a private copy of the writable compilation cache.
Normal Create Parity Lab and other workers' changes were preserved.

## Identified build and setup

Final client: `native-9f42064-76138ca65acb`, built from main `40fa2fb` plus
this test/documentation-only pass, with pinned Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and launcher 0.2.67.
Engine patch bundle Git hash: `664100af7e67dd9fdd01c04d91f175f7e221e39d`.
The downloaded pinned Horizon archive SHA-256 is
`a2549acc67393bc7e388531f59afb4a827d7427923f44b2777f05545f2495ffa`.

| Input | SHA-256 |
| --- | --- |
| horizon-client | `6d9be729b6a09ce610c08cd12ae5f03cb3a4578c8ef7a29ca1599da66e4f997a` |
| horizon-ctl | `1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8` |
| create.hmod | `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7` |

Build command:
`sh tools/build-native.sh /Users/andrewholt/dev/horizon-create/.local/toolchains/launcher-0.2.67/horizon-launcher .local/build-data`.
The private `build-data` uses APFS copies of the target/Cargo caches and a fresh
pinned source archive. The source archive's `CLAUDE.md` symlink was materialized
as a regular file to satisfy the mixin tool's staged-input rule. No gameplay
source was altered by that setup step. Existing cursor handling is included in
the current patch bundle. Prepared 26.3 resources were reused from
`/Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/.local/horizon-client/26.3`.

Local logs live under
`/Users/andrewholt/dev/horizon-create/.worktrees/app-2058/.local/`.
`build.log` and `build-v2.log` record invalid attempts to reuse an already-patched
source cache; `build-v3.log` records sandbox DNS denial; `build-v4.log` records
the archive symlink rejection. `build-v5.log` is the successful 595-second build.
`passage-solo.log` records sandbox socket denial; `passage-solo-unsandboxed.log`,
`passage-solo-v2.log` and `passage-solo-v3.log` record harness tick-step/no-chat
errors. These attempts do not establish gameplay failures. The corrected
preliminary solo (`passage-solo-v4.log`) and host/guest (`passage-lan-v1.log`)
checks passed on the retained APP-2057 client before the fresh build.

## Final-build verification

The grouped run completed 12/13 checks on the first attempt. Platform and
station-control checks passed in solo/LAN; station control matched 123 Java
samples per run. Stopped paired open/closed reopen and all four moving
open/closed solo/LAN cold-reopen checks passed. Manual driving matched all
125 Java ticks. The solo passenger check passed with closed stop Z=-7.7,
open crossing Z=-11.7941 and obstruction stop Z=-8.7 (door block Z=-9).

The first LAN passage attempt failed in shared `test-simple-train.setup` at
“connected carriage did not assemble”, before guest creation or any door
assertion. The failure log, client log and screenshot are preserved as
`.local/passage-final-first-failure.log`, `-client.log` and `.png`.
The grouped result is preserved in `.local/final-regressions.log`; each case
has its own `.local/parity/NAME.log`. The isolated retry uses the identical
client, pack and fixture, with `--jobs 1` and only `train-door-passage-lan`.

Main advanced from `40fa2fb` to `cd18c0f` during verification with signal tests
and documentation only. `git diff 40fa2fb..cd18c0f -- native patches` is empty:
the final combined gameplay build inputs are unchanged.

### Corrected physical layouts and retained diagnostic gap

The serial retry passed closed/open passage for both players, but the host fell
below deck when `/tp` returned it after an occupied landing was edited. Two
additional diagnostics reproduced a below-deck **starting** pose (also with
normal ticking); the train and captured floor/door collision data still existed.
These failed sequences are preserved in `passage-final-second-failure.log`,
`passage-diagnostic.log`, `passage-diagnostic-v2.log` and
`passage-live-diagnostic.log`, with client logs alongside them. The root cause
of this command-teleport-after-live-edit combination is unresolved. It is not
claimed fixed or proven equivalent to Java. It remains a nonblocking command/
teleport follow-up outside this pass's ordinary boarding and platform layouts.

The final runner isolates closed, open and obstructed physical layouts in
fresh worlds, uses normal ticking for movement, checks that each walker starts
on deck, and adds **real walking back onto the carriage** after crossing the
open doors. This directly tests ordinary reboarding without that artificial
teleport sequence. No collision assertion or tolerance was relaxed.

Both final `train-door-passage` checks passed (`final-passage-isolated.log`,
2/2). In LAN, host and guest each stopped at Z=-7.7 while closed, crossed to
Z=-11.7314 while open, reboarded to Z=-7.4604, and stopped at Z=-8.7 with the
obstruction. Feet remained at Y=115 and server agreement stayed within 0.05.
That is eight actual walks across three independent layouts for host/guest,
plus four solo walks. All four half flags matched each layout's expected state.
Together with the eleven unchanged regression checks, all **13 selected checks**
have passing final evidence. This is not a claim that the initial grouped run
was clean or that the retained teleport diagnostic is resolved.

Source syntax checks passed for 487 JSON, 45 JSONL, 890 Python, two shell and
three TOML files, and whitespace checks passed. No Rust code changed, so no new
Rust unit/Clippy run was needed. No new Java capture was made; existing pinned
references were reused. The fresh build took 595 seconds; grouped integration
took 352 seconds. Setup/source review and fixture coding took approximately
15 minutes with overlap; physical-fixture debugging and reruns approximately
8 minutes; source checks approximately 2 seconds per run. Raw logs remain in
the isolated worktree rather than being copied over another worker's evidence.
