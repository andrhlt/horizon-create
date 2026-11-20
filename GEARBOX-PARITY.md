# Gearbox and Vertical Gearbox comparison

APP-1946 uses Create 6.0.10 at `ac0c444d9828da3453ae8cc65338e8de063286fb`
on NeoForge 21.1.219 and Minecraft 1.21.1. The Horizon engine pin is
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` on Minecraft 26.3.

| Area | Java behavior and current evidence | Remaining comparison |
| --- | --- | --- |
| Placement and support | `GearboxBlock.getStateForPlacement` fixes the regular item to Y. `VerticalGearboxItem.updateCustomBlockEntityTag` prefers the perpendicular axis to one consistent horizontal shaft axis and uses the player's horizontal facing to resolve conflicts or absent shafts. The [20-case placement matrix](fixtures/vertical-gearbox-matrix-java.json) covers all six clicked faces and all four horizontal player facings, neighboring shafts and Clutches, selected replaceable targets, and wall, floor and ceiling support removal. The LAN case uses a guest beside a powered Clutch. | Compare other kinetic neighbor types, collision boundaries, and expanded guest placement and item replication. |
| Item identity and crafting | `GearboxBlock.getDrops` and `getCloneItemStack` use the regular item for Y and the vertical item for X and Z. Existing solo checks exercise pick, mining and Wrench pickup on all three axes, both shaped recipes and both conversions. | Verify tool and inventory edge cases and LAN crafting and ownership variants. |
| Kinetic routing | `GearboxBlock.hasShaftTowards` opens the four faces perpendicular to the casing axis. `RotationPropagator.getAxisModifier` preserves the incoming side, inverts its opposite, and inverts perpendicular outputs with the same axis direction. [The render fixture](fixtures/gearbox-render-java.csv) checks shaft rates for one source on each of the twelve open input faces across three axes. The [network fixture](fixtures/gearbox-network-java.jsonl) covers adjacent Y and Z Gearboxes, compatible motor competition and handoff, blocked ports, source loss and reassembly. The [topology fixture](fixtures/gearbox-topology-java.jsonl) verifies 11 pinned Java joins, including directed axis links and compatible/incompatible tied sources. | Other layout combinations, closed loops, stress and overload remain follow-ups. |
| Wrench and transforms | `IWrenchable.getRotatedBlockState` rotates the axis around the clicked face axis. `KineticBlockEntity.switchToBlockState` detaches the old network before substituting the new orientation. `RotatedPillarKineticBlock.rotate` also swaps X and Z for quarter-turn structure rotations. [The general Wrench fixture](fixtures/wrench-java.csv) rotates one box through an ordered face sequence. [The dedicated trace](fixtures/gearbox-wrench-java.json) captures all independently started rotations and survival pickups, plus a powered Y–Z–Y transition. [The source-retaining trace](fixtures/gearbox-wrench-retained-java.jsonl) adds X→Z and Z→Y transitions and an X-axis powered no-op. | Compare the other powered axis, input and rotation combinations, competing sources during rotation, LAN pickup, and contraption and structure transforms. |
| Pistons and reassembly | `GearboxBlock` declares `PUSH_ONLY`. The [vanilla piston trace](fixtures/gearbox-piston-java.csv) covers two Gearbox orientations, two vanilla controls and shaft restart at the landing position. Java's `PistonContraption.addToInitialFrontier` separately excludes a push-only block when a sticky mechanical piston assembles for retraction. [The direction trace](fixtures/gearbox-piston-directions-java.jsonl) also checks a west push and an upward glued gearbox carried indirectly on retraction. | Compare north, south and downward motion, additional glue and pole layouts, kinetic reattachment, and reversal while the payload is still mounted. |
| Render lifecycle and sound | `GearboxRenderer` and `GearboxVisual` draw four independent half shafts using source direction and positional phase. `GearboxVisual` updates those instances when the source changes and deletes them when unloaded. `GearboxBlockEntity.isNoisy` returns false. Existing render checks compare rates, phase, angle and submitted geometry in solo and LAN. | Check source-side replacement, orientation changes, removal and placement, unload/reload, lighting, casing connected textures, and absence of kinetic noise. |
| Persistence and networking | `KineticBlockEntity.write/read` save speed, source and network state and clear that kinetic data when restoring a moved block. The [reopen trace](fixtures/gearbox-reopen-java.json) covers a powered X and blocked Z through a real world restart and source replacement. The headless guest also rotated a powered gearbox twice with exact Java host samples. | Compare reload immediately after movement, Wrench use or a live handoff, and during chunk unload and rejoin. Verify guest source and rendered motion during those transitions. |

## Vertical Gearbox placement matrix

The [Java GameTest](tools/java-vertical-gearbox-matrix-trace.patch) calls
`BlockItem.place` with a survival player and an explicit block hit. The
[20-row trace](fixtures/vertical-gearbox-matrix-java.json) covers all six
clicked faces and all four horizontal player facings across the cases.
Shaft cases include each horizontal axis, two opposite shafts on one axis,
an X/Z conflict, sneaking beside a shaft, an obstructed axis, a vertical
shaft, and a clicked shaft whose axis overrides the player fallback. The
Clutch cases cover powered X, unpowered Z, and a misaligned Clutch. The
regular item keeps its Y axis beside a connecting shaft. The final cases
replace directly clicked short grass, replace water adjacent to the clicked
support, and reject an occupied fence without consuming the item.

Each expected row records action acceptance, the remaining item count, and
the block and casing axis at the target. The wall, floor, and ceiling cases
also remove the clicked support and confirm the block and axis on the next
tick. The [headless replay](tools/test-vertical-gearbox-matrix.py) verifies
the real survival player's look direction and clicked block and face before
using the item. It checks placement from the resulting block and inventory.

Apply the patch to a disposable pinned Create checkout and run
`./gradlew --offline --no-daemon --max-workers 2 runGameTestServer` with Java 21.
Extract the JSON objects prefixed `CREATE_VERTICAL_GEARBOX_MATRIX ` in log
order. The [metadata](fixtures/vertical-gearbox-matrix-java.metadata.json)
records the pinned versions, hashes, and 16.24-second Java capture.
Run the headless Horizon replay through
`tools/test-parity.py --check vertical-gearbox-placement-matrix` with the
candidate and prepared resource paths.

Candidate `native-9f42064-79727a892648` matched all 20 cases in 33.73 seconds
with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The registered headless check passed 1/1 in 33.92 seconds.
The Java capture, direct replay and registered check logs are retained
under `.local/app-1946/*vertical-gearbox-matrix*`. The first capture and
34.19-second replay also remain there. The final capture varies the
player facing in the clicked-shaft case so the shaft and fallback rules
predict different axes. Other kinetic neighbor types, collision
boundaries, and the extended matrix on a LAN guest remain open.

## Mechanical piston endpoint replay

The [Java GameTest patch](tools/java-gearbox-mechanical-piston-trace.patch)
uses the original `ploughing` template. It pushes the X, Y and Z casing axes
with a sticky mechanical piston, pushes Y with a regular mechanical piston,
and pushes stone with a sticky piston as a pullable control. Movement mode 0
makes each rig place its payload at full extension before switching direction.
The three sticky Gearbox runs leave the block at the destination, as does the
regular control. The sticky stone run pulls the block back to its starting cell.

The [120-sample trace](fixtures/gearbox-mechanical-piston-java.jsonl) records
piston state, offset, RPM, seven block positions, and the IDs and Gearbox axis
of carried blocks. The origin is the second GameTest tick after setup. The motor
reverses before sample 10, and the capture continues through sample 23. The
[metadata](fixtures/gearbox-mechanical-piston-java.metadata.json) records the
pinned version and hashes. The [Horizon replay](tools/test-gearbox-mechanical-piston.py)
compares all fields exactly against Java on the authoritative world and checks
the guest's eventual world-block and piston-state replication at each step
in the LAN run.

To recapture, apply the patch to a disposable pinned Create checkout and run
`./gradlew --offline --no-daemon --max-workers 2 runGameTestServer` with Java 21.
Extract `CREATE_MECHANICAL_GEARBOX ` rows in case order X, Y, Z, regular and stone,
then sort each case by tick. Run the Horizon replay via `tools/test-parity.py`
with `--check 'gearbox-mechanical-piston*'`. Both checks use headless clients.

The original-template movement mode leaves the sticky rigs mounted at full
extension. The first successful GameTest execution retained the payload through
reversal, so it could not test fresh retraction assembly. That exploratory log
is retained at `.local/app-1946/java-second.log`, alongside the accepted capture
at `.local/app-1946/java-endpoint.log`.

The pre-fix `native-9f42064-a5156e57df79` replay used pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
It matched the X-axis rig through the direction change and diverged when
retraction assembled at sample 11. Horizon removed the Gearbox from the
destination and included it in the carried blocks. Java left it in place.
The 24-sample run recorded 21 field mismatches in
`.local/app-1946/horizon-before-x-retry.json`. The local command was
`python3 tools/test-gearbox-mechanical-piston.py "$runtime/horizon-ctl" "$runtime/horizon-client" "$runtime/.local/horizon-client/26.3" --case x`.

The pre-fix build also matched all 24 samples for the stone control in a
headless LAN run, including guest convergence at each step. Its successful
retry is retained in `.local/app-1946/horizon-before-lan-stone-retry.json`.

On rebuilt candidate `native-9f42064-d968dc65fa5b` with the same pack,
both headless checks passed in 247.25 seconds. The solo world and LAN host
each matched all 120 Java samples across the five rigs. The headless guest
converged on all 120 LAN steps. Candidate samples are retained as
`.local/gearbox-mechanical-piston-solo.json` and
`.local/gearbox-mechanical-piston-lan.json`. This comparison covers a fresh
retraction after endpoint placement. Guest convergence measures the received
state at each paused step, with packet timing and client interpolation open.

The same candidate passed the six existing checks selected by
`--check 'gearbox-piston*' --check 'vertical-gearbox-*'` in 68.63 seconds.
Both offscreen checks selected by `--check 'gearbox-render*'` passed in
77.66 seconds. The solo render compared all 576 samples across twelve rigs.
The LAN render compared four shaft halves on the host and guest at +64 and
−24 RPM. The run logs are under `.local/parity/`, with elapsed batch times in
`.local/app-1946/candidate-*.log`.

## Multi-Gearbox source handoff

The [Java GameTest](tools/java-gearbox-network-trace.patch) builds adjacent
Y- and Z-axis Gearboxes with four open output branches and one deliberately
blocked shaft on each casing. A +32 RPM motor initially drives both boxes
and overdrives a compatible −16 RPM motor on the second box. Removing the
primary motor hands the network to the backup on the next sample. The
first box changes input from north to east, and the second changes from
west to down. Removing the backup stops all four outputs. Reinstalling the
primary at −48 RPM reverses them, and removing and replacing the second
Gearbox stops and restarts its branches. Both blocked shafts stay at zero.

The [reference](fixtures/gearbox-network-java.jsonl) compares block ID and
effective signed RPM at ten points, plus casing axis and source face for
each Gearbox. Sampling begins on GameTest tick 8, after setup has settled.
The test applies each block or motor change after samples 3, 9, 15, 21,
and 27, then captures each following tick through sample 33. All fields
use exact equality. The [metadata](fixtures/gearbox-network-java.metadata.json)
records the versions, hashes and 34.06-second Java capture time.

Apply the patch in a disposable checkout and run
`./gradlew --offline --no-daemon --max-workers 2 runGameTestServer` with Java 21.
Extract and sort `CREATE_GEARBOX_NETWORK ` rows by tick. Run the headless
[Horizon replay](tools/test-gearbox-network.py) via
`tools/test-parity.py --check gearbox-network` with the usual prepared paths.
The direct replay on `native-9f42064-d968dc65fa5b` and the pack recorded above
matched all 34 ticks and ten points in 48.25 seconds. The registered
check passed in 48.69 seconds and produced the same trace. This source-handoff
layout required no native changes. The Horizon trace is retained in
`.local/gearbox-network-horizon.json`.

## Wrench transforms

The [Java GameTests](tools/java-gearbox-wrench-trace.patch) invoke the pinned
`WrenchItem.useOn` with a survival player model. Each of the 18 cases starts
with a fresh X-, Y- or Z-axis Gearbox and a single ordinary use on one of
the six faces. The capture records the resulting axis and the inventory
and block state after a sneak pickup from the west. On the existing
`native-9f42064-d968dc65fa5b` candidate, a headless survival player matched
all 18 transforms and recovered the exact Java item each time.

The powered rig uses a west-face wrench action to rotate a Y-axis Gearbox
with a north motor to Z, then rotates back to Y. Java removes the source
and zeros both driven shafts during the first use. After the second use,
the network remains stopped until the next tick. The 11 samples compare
axis, source face and signed RPM at the box and three neighboring shafts
with exact equality, including both immediate post-use samples. The
[reference metadata](fixtures/gearbox-wrench-java.metadata.json) records
the pins, hashes and capture duration.

The pre-fix replay on `native-9f42064-d968dc65fa5b` took 48.81 seconds.
It matched ten of the eleven powered samples. Immediately after the first
rotation, the box still reported its north source and +32 RPM, with −32
and +32 RPM on the south and east shafts. Java reported zero RPM and no
source in that same sample. The pre-fix comparison and client logs remain
under `.local/app-1946/horizon-wrench-before-fix*`.

The worktree rebuilt in 113.73 seconds with the pinned compatible launcher
through `tools/build-native.sh`. The headless `gearbox-wrench` check matched
all 18 rotation and pickup cases and all 11 powered samples on
`native-9f42064-4648fb340354` in 48.48 seconds with the same pack. The
candidate trace and logs are retained in
`.local/app-1946/horizon-wrench-candidate*`. The comparison still leaves
other powered orientation and source combinations, LAN Wrench pickup, and
structure transforms open.

Apply the patch to a disposable pinned checkout and run
`./gradlew --offline --no-daemon --max-workers 2 runGameTestServer` with Java 21.
Extract the JSON rows prefixed `CREATE_GEARBOX_WRENCH ` and
`CREATE_GEARBOX_WRENCH_POWER ` into the rotations and powered arrays.
Run the headless Horizon replay with `tools/test-parity.py --check gearbox-wrench`
and the usual candidate and prepared resources arguments.

## Rebuilt family regression

The Wrench candidate `native-9f42064-4648fb340354` used pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
All 12 distinct checks passed in their applicable modes. The
`--jobs 2 --check 'gearbox-*' --check 'vertical-gearbox-*'` sweep first
reported 11 of 12 in 397.70 seconds. A worktree-local control shim kept
non-render checks headless. The crafting fixture opened its recipe UI, then
`click-slot` reported `no renderer yet`. The standard hidden offscreen
`--jobs 1 --check vertical-gearbox-crafting` replay passed in 6.99 seconds.
Both Gearbox rendering checks used offscreen clients. All other checks
passed headlessly, including the player-driven piston, placement, pickup,
and Wrench scenarios.

The batch and launch modes are recorded in
`.local/app-1946/candidate-full-suite.log` and
`.local/app-1946/candidate-full-launches.log`. The headless crafting failure
and successful retry are preserved in
`.local/app-1946/vertical-gearbox-crafting-forced-headless.log` and
`.local/app-1946/candidate-crafting-offscreen.log`. Per-check results are
under `.local/parity/`.

## Save and reopen

The [Java server capture](tools/java-gearbox-reopen-trace.patch) runs two
distinct headless dedicated server processes against the same on-disk
world. The first stops and saves a reverse-driven X-axis Gearbox and a
stopped Z-axis Gearbox with a motor facing a blocked port. The second reads
the saved world, samples both Gearboxes, removes the X box's lower motor,
and replaces its input with an opposite-sign drive from the south.
The saved and restored Java block-entity tags retain the powered box's
source coordinates and −32 RPM. The two driven shafts stay at +32 RPM after
load, stop on source removal, then run at −24 RPM after replacement.
The blocked Z box stays stopped throughout.

The [five reference checkpoints](fixtures/gearbox-reopen-java.json) record
block ID and signed RPM at nine points, plus both casing axes and source
faces. The [metadata](fixtures/gearbox-reopen-java.metadata.json) records
the save and reopen durations, the initial server properties, and raw Java
Gearbox NBT. Set up an empty disposable checkout's `run/server` with those
properties and `eula=true`, apply the patch, then run
`CREATE_GEARBOX_REOPEN_PHASE=save ./gradlew --offline --no-daemon --max-workers 2 runServer`
followed by the same command with `CREATE_GEARBOX_REOPEN_PHASE=reopen`.
Use Java 21 and leave the saved world in place between server runs.

The [Horizon check](tools/test-gearbox-reopen.py) stops the headless
process, checks for the saved `level.dat`, and opens that same world.
All five phases matched `native-9f42064-4648fb340354` with the same pack
in 17.43 seconds. The first accessible Horizon sample followed 13 startup
world ticks. Java samples the first dedicated-server post-tick after boot,
so this comparison establishes the restored state and later changes. The
difference between those first sampling times leaves startup-tick timing open.

## LAN Wrench interaction

The `gearbox-wrench-lan` replay puts the host outside the guest's approach
and equips the guest with one Wrench in survival. Both clients run headlessly.
The guest clicks the west face for the Y→Z→Y transition. The host matches
all eleven Java authority samples, including the same-tick detachment
and next-tick attachment. The guest observes both resulting axes after
the host applies each click. This covers guest input, host kinetics and
guest block state. Guest RPM and packet timing remain open. The first
attempt put both players in the same interaction position and timed out.
That failure and both client logs are preserved under
`.local/app-1946/horizon-wrench-lan-first*`. The separated rerun passed
in 16.70 seconds on `native-9f42064-4648fb340354`.

The registered headless run of `--check gearbox-network --check 'gearbox-wrench*'
--check gearbox-reopen` passed all four checks in 69.81 seconds with
`--jobs 2`. The direct and runner logs are preserved under
`.local/app-1946/horizon-reopen-first*`,
`.local/app-1946/horizon-wrench-lan-separated*`, and
`.local/app-1946/horizon-reopen-wrench-suite.log`. Per-check logs and the
current traces are under `.local/parity/` and `.local/`, respectively.

## Remaining orientation and power cases

All twelve open casing-axis and input-face pairs in the render reference
already include both speed signs. The exercised two-box network is a
direct Y/Z pair, so Y/X, X/Z and matching-axis pairs, alternate entry
faces, competing-source directions, loops and overload remain open.
The powered Wrench traces cover closing and reopening a source port,
keeping an open source port while changing output branches, and a powered
same-axis click. Other powered combinations, including repeated rotations
with varying source direction and motor sign, remain open.

## Powered rotation with an open source port

The [pinned Java patch](tools/java-gearbox-wrench-retained-trace.patch)
captures X→Z around a −32 RPM down input and Z→Y around a +24 RPM east
input, plus a same-axis west click on the powered X box. Both rigs contain
a source motor and five shafts. The [15 samples](fixtures/gearbox-wrench-retained-java.jsonl)
record the six adjacent blocks, signed RPM, casing axis and source face
before use, immediately after use and on the following world tick.

Java keeps the motor running through rotation while it clears the old
source and all five shaft speeds during the action. On the next tick the
Gearbox reconnects through the same input and turns the newly opened
branches. The same-axis click keeps every sampled field unchanged.
Horizon matched all 105 sampled positions headlessly on
`native-9f42064-4648fb340354` in 29.96 seconds. The replay checks the actual
corner hit on each intended face so the neighboring shafts stay installed.
The original upper aim hit the approach platform, and that invalid
attempt is preserved under `.local/app-1946/horizon-wrench-retained-first*`.

The [metadata](fixtures/gearbox-wrench-retained-java.metadata.json) records
the pins, hashes and the 13.40-second Java capture. Capture with Java 21 and
`./gradlew --offline --no-daemon --max-workers 2 runGameTestServer`. Run
the headless Horizon replay with `tools/test-parity.py --check gearbox-wrench-retained`.
The registered headless check passed in 29.57 seconds. The replay logs are
under `.local/app-1946/horizon-wrench-retained-*`.

## Shaped Gearbox crafting

The pinned Java `data/create/recipe/crafting/kinetics/gearbox.json` has
SHA-256 `8a140cebfb5b51e91347ac490e146818acff8b80a816b15c60acb63f6ff9f9dc`.
It places four cogwheels at the cardinal crafting-grid positions around
an Andesite Casing. The imported pack preserves that pattern and output
with the Horizon ingredient encoding. The existing survival UI replay
crafted this regular Gearbox, the corner-pattern Vertical Gearbox and
both conversions on `native-9f42064-4648fb340354` in 7.68 seconds. It used
a hidden offscreen client because the fixture clicks crafting slots.
The runner log is `.local/app-1946/gearbox-regular-crafting-offscreen.log`.

## Mechanical piston directions and Super Glue

The [pinned Java GameTests](tools/java-gearbox-piston-directions-trace.patch)
use two one-pole sticky mechanical pistons in movement mode 0. A west-facing
piston pushes a direct Y-axis Gearbox one block and leaves it at the
destination after retraction. An up-facing piston moves a stone block with
an X-axis Gearbox glued to its east side. The stone is the pullable block
in front of the head. The glued Gearbox returns alongside the stone
during fresh retraction. Create excludes the push-only Gearbox from the
direct retraction frontier and still follows an explicit glue connection
from a pullable block.

The [48 samples](fixtures/gearbox-piston-directions-java.jsonl) record
piston state, offset, signed RPM, five line positions, two transverse
positions for the glued case, and captured block IDs with the Gearbox axis.
Both captures reverse the motor after endpoint placement at sample 10.
The [Java metadata](fixtures/gearbox-piston-directions-java.metadata.json)
records the pins and hashes. Both GameTests passed in 13.40 seconds with
Java 21 and `./gradlew --offline --no-daemon --max-workers 2 runGameTestServer`.

The headless `gearbox-mechanical-piston-directions` replay matched all
samples on `native-9f42064-4648fb340354` with the existing pack. The direct
run took 42.96 seconds and the registered run took 43.63 seconds. Logs and
the first replay are under `.local/app-1946/horizon-piston-directions-*`.
These layouts leave LAN replay, other push directions, additional pole
lengths and powered gearbox reattachment unverified.

## Quarter-turn bearing transform

The [Java GameTest](tools/java-gearbox-bearing-transform-trace.patch)
rotates two glued Gearboxes through a real +90° turn about Y. The center
Gearbox starts on X and takes −32 RPM from above. Its unpowered neighbor
starts on Z, east of the center. The bearing removes both blocks while
they are mounted. Java restores the center on Z and the relocated north
box on X. At the first restored sample the center reports zero RPM and
has no source. It reconnects to the upper motor by the settled sample.

The [four Java checkpoints](fixtures/gearbox-bearing-transform-java.json)
record the bearing angle and running state, plus block ID, casing axis,
signed RPM and input direction where a Gearbox is present. The Java
capture passed in 17.06 seconds. The headless pre-fix run on
`native-9f42064-4648fb340354` took 11.89 seconds. It matched the first two
checkpoints and restored both blocks in the correct positions, then kept
their old casing axes and immediately restored the center's stale
−32 RPM and source. The pre-fix logs and trace are preserved under
`.local/app-1946/horizon-gearbox-bearing-baseline*`.

The pinned incremental rebuild produced
`native-9f42064-79727a892648` in 104.90 seconds with the existing pack.
The first and only headless `gearbox-bearing-transform` check matched all
four Java checkpoints in 12.41 seconds. Both axes were restored correctly,
and the center resumed its upper source after the zero-RPM restored sample.
Build and replay logs are under `.local/app-1946/build-bearing-transform.log`
and `.local/app-1946/horizon-gearbox-bearing-candidate*`. Other bearing axes,
mirrors, structure template transforms, moving render geometry and LAN
presentation remain open.

## APP-1946 finite gameplay gate

The ticket's finite gates passed on the rebuilt client `native-9f42064-d8a055d1998e`, using Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and Create mod SHA-256 `3170213ffa3e13898119832b0bcf7cd42f5198d8fe5296ca5d2d240df7b53ea5`. The build used `tools/build-native.sh` with pinned launcher 0.2.67 and the standard `nightly-2026-11-13-9f42064` resources.

The recorded finite checks were: both Gearbox forms and recipes, placement and drops, three-axis render coverage, source direction and sign handoff, compatible and incompatible source ties, powered Wrench rotation and pickups, bearing transform, vanilla and mechanical piston movement, and save/reopen. Guest actions were exercised through Wrench rotation and piston operation. The active X and stopped/blocked Z setup was saved and reopened before source removal and opposite-sign replacement.

On that exact build, the registered regression set passed 16/16: `vertical-gearbox-placement`, `vertical-gearbox-placement-matrix`, `vertical-gearbox-crafting`, `gearbox-render`, `gearbox-network`, `gearbox-topology`, `gearbox-wrench`, `gearbox-wrench-lan`, `gearbox-wrench-retained`, `gearbox-reopen`, `gearbox-bearing-transform`, `gearbox-piston`, `gearbox-piston-lan`, `gearbox-mechanical-piston`, `gearbox-mechanical-piston-lan`, and `gearbox-mechanical-piston-directions`. Headless checks were run headless; the render and crafting checks used offscreen UI clients. The Java trace counts include 20 placement cases, 15 topology samples in 11 cases, 34 network ticks across 10 points, 18 Wrench transforms/pickups, 15 powered retained-source Wrench samples, 5 reopen phases across 9 points, 104 vanilla piston states, 120 mechanical piston samples in solo and LAN, 48 direction samples, and 576 rendered shaft speeds/sides.

`Full 1:1` remains Open. Remaining comparisons in the table are follow-up coverage rather than blockers for this gameplay pass.

## Combined-main build verification

After the first PR opened, `origin/main` advanced through `3345bef`, `7a6449f`, and `d3e4090`. I merged the latest `d3e4090` base, preserved the APP-1946 Gearbox matrix row and the intervening cogwheel/transmission rows, then rebuilt the combined tree. The exact tested client is `native-9f42064-af0399665b45` (Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Create mod SHA-256 `8df1356527eb1995526f73455aaf740c36beae0f8ecb991056f9f6689ddb52ee`). Build profile was performance with the recovered 0.2.67 launcher and `nightly-2026-11-13-9f42064` resources. Its target cache was isolated because other worktrees were compiling concurrently.

The combined-build runner passed 20/20 checks: all 16 Gearbox checks listed above plus `clutch-gearshift-placement`, `clutch-gearshift-timing`, `clutch-competing-input`, and `gearshift-timing-lan` for the shared kinetic-network changes. The Gearbox set included headless placement, network, topology, Wrench, piston, persistence and LAN checks, plus offscreen Gearbox rendering and Vertical Gearbox crafting. The final combined-build run confirmed the 20-case placement matrix, 15 topology samples in 11 cases, 34 network ticks over 10 points, 18 Wrench transforms/pickups, 15 retained-source samples, 5 reopen phases over 9 points, 104 vanilla piston states, 120 mechanical-piston samples in solo and LAN, 48 piston-direction samples, and 576 rendered speeds/sides. The four adjacent transmission regressions also passed.

`Full 1:1` remains Open. The implementation is ready for review; Done still requires review, merge, and affected checks on the post-merge combined build.
