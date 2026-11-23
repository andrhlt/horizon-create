# APP-2136 frozen SDK migration

## Stage 1 case selection

Selected before implementation, from the existing evidence on current `main`
(`9a0cc9f20f98ae1de18212b634b03230837e983d`):

1. **Kinetic:** Creative Motor to shaft/cogwheel. Use `creative-motor`,
   `creative-motor-lan`, and `creative-motor-reload` from
   `tools/test-parity.py`. These cover placement and signed output, guest
   configuration, and idle plus connected save/reopen.
2. **Processing:** the original `wheat_milling` structure. Use
   `wheat-milling`, `millstone-lan`, and `milling-recipes` checks. The wheat
   case compares speed-dependent processing and inventories against the Java
   trace; the LAN case checks a guest action and converged machine state.
3. **Train/contraption:** the APP-2047 straight two-carriage replay,
   `train-multi-carriage`. It assembles four bogeys, drives all eight track
   points, saves/reopens, verifies guest convergence, and restores both cargo
   inventories on disassembly. This is the narrowest retained flow found that
   covers moving state, multiplayer, persistence, and cargo recovery.

The frozen target is Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`
(`nightly-2026-11-20`), SDK `sdk-0a875da91dbb0fdcb7ba8c42c11341aa229af51a`,
MC 26.3, and mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`. The target SDK
metadata reports package format 6, content API 0.2, and Rust 1.99.1. Artifacts
are checksum-verified in the isolated local setup; no target gameplay run has
passed yet.

## Implementation and evidence

The isolated branch starts from current remote `main`,
`9a0cc9f20f98ae1de18212b634b03230837e983d`. The pinned SDK/nightly assets
were verified by SHA-256, and the target 26.3 runtime was prepared from the
previously captured client jar and libraries. Launcher, build, and game data
are under `/private/tmp/horizon-app-2136/.sdk`; no project user's worlds were
opened.

`tools/migrate-flat-native.py` makes a temporary flat native project while
preserving the existing source files and row IDs. Its initial package selects
all 209 support modules and 301 of 329 legacy native mixins. It leaves out the
28 Elevator/nozzle mixins because they are outside these three cases and the
SDK limits one package to 511 Rust source entries. The remaining 83 legacy
hook declarations need conversion to the SDK's typed `BlockPart`,
`BlockEntityPart`, and other supported hooks.

The first target build (`native-build` with launcher 0.2.105, pinned nightly
`nightly-2026-11-20-0a875da`, SDK `sdk-0a875da91dbb0fdcb7ba8c42c11341aa229af51a`,
and mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`) failed before Rust
compilation. It produced 120 diagnostics: 106 target-resolution diagnostics
(some report multiple mixin rows), 12 functions that are not replaceable, and
two invalid module destinations. The recorded log is at
`.sdk/launcher-data/native/build.log`. The missing targets are mostly old
`native_hooks` extension
slots; the SDK now exposes typed parts and hooks for many of those behaviors.
The two invalid module destinations are the wheel fluid helper in
`horizon-world` and schematic capture in a file no longer present at the old
path. No gameplay case has run on the migrated build yet.

The source package build also confirmed an important scope boundary: the old
manifest's 412 rows are not all native mixins. It contains 83 old hook rows
plus 329 source mixins. The SDK package limit and the disappeared old engine
extension points make a broad row-for-row manifest conversion unsuitable for
Stage 1.

The diagnostic retry excluded 245 mixin IDs reported by the first validator,
the two obsolete module destinations, and the previously out-of-scope
Elevator/nozzle rows. The resulting package has 207 modules and 58 mixins. It
then failed SDK source validation with 57 `E_MIXIN_SOURCE` diagnostics. They
are one root-cause group: every message says `no module horizon_client::mobs`.
The 57 lines name 39 distinct target functions and 57 distinct mixin IDs (121
ID mentions because some lines combine several rows). The reported functions
span world ticks, block entities, interaction, persistence, and vehicle paths.
The pinned source puts `mobs` in `horizon-client-lib`'s `client_lib.rs` and
re-exports that crate from `horizon-client/src/lib.rs`; the mod API generator's
source resolver does not follow that re-export while validating the full
support-module graph. The same `check_transmission_reconnections` mixin no
longer reports this diagnostic when paired with `machines` alone.

This filtering is a diagnostic scope reduction, not a gameplay fix: it removes
rows from the candidate, and therefore does not validate their behavior. A
one-row `check_transmission_reconnections` package with only the `machines`
module no longer produces `E_MIXIN_SOURCE`, but compilation then fails on the
module's broad dependencies and outdated internal `Game` API calls (471 Rust
errors). With the full support-module set and that same row, the SDK reports
`E_MIXIN_SOURCE` again. So the source diagnostic is avoidable in a narrow
package, while the motor implementation itself still needs a scoped port or a
reproduced engine/API blocker. No kinetic flow has compiled or passed runtime
verification. The filtered package is not a candidate runtime build.

`tools/migrate-flat-native.py` now supports explicit module/mixin inclusion so
follow-up attempts can build small candidates rather than starting from every
Create family. The three Stage 1 flows have not passed and no behavior is
claimed as migrated.

## Remaining migration inventory and assessment

Pending Stage 1 verification. The Full 1:1 migration and the other Create
families remain out of scope until the three selected cases pass and the
assessment checkpoint is presented.

## Kinetic-only feasibility checkpoint (2026-11-22)

The isolated `machines.rs` compile is not a representative kinetic build: at
4,356 lines, the module imports and matches many unrelated machine families.
The intentionally narrowed build omitted its sibling modules. Its Rust output
had 475 primary diagnostics: 306 are artifacts of that isolation (33 missing
sibling imports, 233 references to omitted siblings, and 40 pattern bindings
that cease to be constants when those imports are absent). The other 169 are
real migration diagnostics in this whole module: one NBT path moved from
`horizon_world::nbt` to `horizon_core::nbt`, 160 missing legacy `Game` methods,
two missing fields, two changed call arities, and four type mismatches. The
launcher footer summarized these as 471 previous errors. This count mixes
whole-module failures; it is not a count for a motor-only extraction.

The old motor path shares 1,276 lines of `machines.rs` source spans with the
general kinetic enum, graph traversal, source arbitration, motor initialization,
and network publication. Those spans refer to 22 sibling `create_*` modules
because the enum also handles other kinetic blocks: `backtank`, `bearing`,
`belt`, `chain_conveyor_connect`, `chain_gearshift`, `display_board`, `drill`,
`elevator`, `fan`, `fluids`, `flywheel`, `gantry`, `hand_crank`, `hose`,
`mechanical_piston`, `saw`, `sequencer`, `shaft`, `speed_controller`, `steam`,
`turntable`, and `valve`. That is the broad source closure, not the selected
fixture's closure.

The selected fixture's observed production call graph is narrower. `motor`
has BE id `create:motor`; `shaft`, `cogwheel`, and `large_cogwheel` have BE id
`create:simple_kinetic`. Current code enters that graph through the common
`block_entity`, `block_entity_ticks`, and `block_entity_tick` helpers; motor
setting changes route through `speed_controller`, world changes through
`prepare_sequencers`/`windmill_data_loaded`, disconnection through
`flush_clutch_signals`, and visual speed reads through `visuals`. The
test-specific algorithm needs only motor, shaft, and cogwheel connection
rules, signed RPM propagation, saved BE data/sync, the guest setting action,
and shaft/cogwheel draw state. Gearboxes, other source/consumer types, and the
other 22 helpers are not dependencies of the selected structure. The exact
post-extraction file list remains to be confirmed by the next build; the
current monolith does not expose that closure as separate Rust modules. A full
1,276-line copy would retain unrelated branches and is not an acceptable
isolation fix.

A typed-Part probe was built with launcher 0.2.105, the pinned Nov 20 nightly,
SDK `sdk-0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, and the isolated launcher
and game homes. It attached `BlockEntityPart` to `create:motor`, enabled ticking,
read the level through `ServerHost`, and changed the saved NBT through the
tick event. The SDK's normal `native-build` validation and compilation passed
(`prebuilt-api` route; Rust compile 966 ms; build completed). This is a compile
probe only: it has no migrated content, network algorithm, guest interaction,
or parity/runtime evidence. It establishes that the supported typed-Part
surface can express the required server boundary; no missing engine capability
has been reproduced.

**Recommendation:** continue only the bounded motor/shaft/cogwheel port using
typed `BlockPart`/`BlockEntityPart` callbacks and `ServerHost` block/entity
reads, saved-data writes, and sync. Keep the graph limited to the three selected
block kinds and retain the existing signed RPM and persistence observations.
The probe makes this approach technically plausible, but the actual flow is
not yet viable: there is no compiled production slice or passing parity run.

Estimated remaining kinetic work is **5–10 engineer-days**: extract and adapt
the motor graph plus guest configuration and visual state (3–6 days), adapt
the fixture's required content for SDK content API 0.2 (1–2 days), then run
host/guest and save/reopen checks and repair failures (1–2 days). The estimate
is based on the observed call graph and compile probe, not a completed
extraction; it may exceed 10 days if the callback or content closure is wider
than it appears. The largest uncertainties are guest action routing, motor
reinitialization after reload, and the exact draw/content closure. Do not use
the broad `machines.rs` compiler count as a kinetic estimate. Processing and
train work has not started.

Time record: **24 minutes wall-clock** from the first timestamped APP-2136
diagnostic commit at 09:26 MDT to this checkpoint at 09:50 MDT. This is an
upper bound on hands-on time because it includes pauses between requests.

## Kinetic slice implementation checkpoint (2026-11-23)

The requested slice is the motor, straight shaft, and the small/large cogwheel
train already covered by `fixtures/shaft_and_cogwheel-java.csv`. The actual
fixture closure is therefore three block-entity roles (`create:motor` and
`create:simple_kinetic` for shaft/cogwheel), their orientation/state properties,
the existing graph walk's shaft and gear connection rules, signed speed
propagation, the motor board's setting action, block-entity persistence and
sync, plus the client pose path for those shaft and cogwheel entities. The
Java-backed checks already present are `creative-motor`, `creative-motor-lan`,
`creative-motor-reload`, and `shaft-and-cogwheel`. The first three cover setting
and reload paths; the last supplies the actual small/large gear train, ratios,
opposite direction, and interruption/restoration. The selected gear-train
fixture must be included alongside the motor fixture for the requested
motor→shaft→cogwheel result.

The former 22 `create_*` references are not the selected feature's dependency
closure. They came from generic matches and helpers in the monolithic
`Kinetic` enum and describe other cases that the enum supports. Leaving those
siblings out of an extracted candidate would create unresolved names, not
prove API incompatibility. The slice still has real cross-cutting seams in
`machines.rs` (network rebuilding and event ordering), `speed_controller.rs`
(motor input), `visuals.rs` (pose production), and the migrated block/content
registrations. None of the 22 unrelated machine modules is needed to represent
the selected fixture's entity types or gear edges.

I did not complete the production extraction in this pass. The SDK's typed-Part
compile probe recorded in the prior checkpoint demonstrates that a Part can
attach to `create:motor` and request server ticks. In this resumed checkout, I
attempted normal pinned `native-build` validation in `.local/sdk-check` using
Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, its Nov 20 SDK metadata,
and its matching mixin pin. The launcher stopped before Rust diagnostics with
an empty `error:` and `The build failed:` in its private build log. The
isolated launcher home has the pinned version, source and prebuilt artifacts;
the precise launcher prerequisite producing this blank failure remains
unresolved. This is an environment/build-route failure, not evidence that the
typed Part API lacks a required capability. No gameplay stage was run in this
pass, and no stage is claimed as passing. The earlier probe also was compile
only; it does not count as block creation or ticking gameplay evidence.

### Remaining work and revised estimate

The API surface observed so far does not establish a missing engine capability:
typed block/entity Parts, server tick callbacks, and host world/entity access
are present. Concrete unverified API seams for a full slice are: supported
guest screen input and motor-setting persistence; server-side graph mutation
and block-entity sync at the old tick order; persistent `Speed` and
`ScrollValue` behavior after reopening; and client-facing rotation state for
the selected shaft/cogwheel parts. They need compile probes or runtime results
before any of them can be called an API gap. The normal validation route must
also be made reproducible in the isolated home before the production slice can
be trusted.

Based on the fixture closure and existing Java evidence, the implementation
estimate is revised from **5–10 to 6–9 engineer-days**: 2–3 days to extract the
three-kind topology and isolate its supported host adapter while preserving
the current `ratio_to`/signed-speed rules; 1–2 days for guest configuration,
sync, and save/reopen; 1–2 days for content registration and offscreen rotation;
and 1–2 days for repair and final pinned validation. This is an estimate, not
measured delivery: this pass produced no production code or passing check. It
assumes the blank launcher failure is local setup and the old Java fixture
content can be retained; failure of either assumption could increase the
estimate. Processing and trains have not been started.

Time record for the resumed pass: **4 minutes 51 seconds** from 13:59:26 to
14:04:17 UTC (06:59:26–07:04:17 MDT), spent checking the dependency closure and
attempting isolated SDK validation. Production implementation time: **0**;
compiler time is not available because the launcher stopped before compilation;
gameplay/test time: **0**. The earlier 24-minute diagnostic/checkpoint record
remains separate and is not counted as implementation time.

## Kinetic adapter runtime evidence (2026-11-23)

The frozen launcher route is now reproducible in the isolated `.local/sdk-check`
homes. `launcher@0.2.105 native-build --instance 'APP-2136 SDK Probe'
--trust-native-code --profile optimized` compiled the selected typed-Part adapter
against the pinned Nov 20 SDK in **1 second** (`native-0a875da-128150ca3ffb`).
This is the normal SDK compile path and does not change the shared SDK/mixin pin.
Two pure kinetic calculation tests also pass (2/2) with managed Rust 1.99.1.

The existing offscreen `shaft-and-cogwheel` fixture now starts with the staged
motor/shaft/cogwheel Part set and exercises server ticking. The first comparison
exposed a speed conversion bug in the adapter: it multiplied the relative gear
ratio where the old graph walk divides by it. After correction, measured speeds
for ticks 1–10 match the Java trace, including the small/large gear ratio and
rotation sign. Breaking power at tick 10 clears that train as expected. The
fixture still fails its restoration phase: after replacing the motor at tick 24,
ticks 25–35 retain zero speed in that train (11 mismatching rows). A short
headless reproduction reads motor and shaft data around removal and re-placement:
the original motor ticks and writes speed 16, but the recreated motor remains at
`Speed: 0.0f` and its shaft remains zero through four more ticks. The second
independent train remains powered. This isolates a runtime lifecycle defect in
the selected candidate, not a proven SDK limitation. The probe package omits the
existing `create_machines` placement/event hooks. The normal player-placement
fixture was run offscreen and failed six orientation cases, consistent with that
omission; it cannot attribute a placement defect to the SDK. An offscreen
screenshot was captured, but rotation animation was not asserted. The full 36-row
fixture therefore does not pass. Rerun the replacement lifecycle with the old
placement/event hooks integrated before declaring a pinned-SDK/API blocker.

The harness required a local Unix control socket; its first sandboxed attempt
was denied. Running the same isolated offscreen command with filesystem/socket
access succeeded. It uses the existing Java fixture and trace copied from the
original checkout's ignored evidence directory. For the temporary content pack,
the selected four block definitions had `waterloggable` removed because the
pinned content schema rejects that property. This is a demonstrated content API
compatibility gap; waterlogging is not verified and the workaround is only in
ignored test artifacts, not source content.

Stages: typed block/entity registration and initial server tick **compile and
runtime-observed**; initial signed speed propagation **partially verified**;
full interruption/restoration **failed**; motor setting interaction, guest
configuration, save/reopen and rotation animation **not implemented or tested**.
The adapter currently reads `minecraft:overworld` directly, so other dimensions
are also unverified. No missing engine capability has been established. The exact
restore path must be debugged before this can be called viable as a complete motor
slice.

Measured work in this resumed implementation: the focused edit/build/fixture
and replacement reproduction took about **8 minutes wall-clock** by the local run
timestamps; the
successful mod compile itself took **1 second**; the two offscreen fixture runs
took about **18 and 28 seconds** from command start through comparison. The
pure Rust tests passed **2/2**. These figures cover only the bounded work above,
not the earlier 24-minute and 4-minute-51-second diagnostic checkpoints.

Estimate from evidence: reserve **1–2 days** to make the bounded graph lifecycle
(including motor removal/replacement and reconnection) match the Java trace and
integrate it reproducibly into the source generator; **1–2 days** for motor
setting input, guest sync and save/reopen; and **1–2 days** for content schema
compatibility, selected client rotation and final normal validation. Total
remaining kinetic slice estimate is **4–7 engineer-days**, assuming the pinned
SDK's existing typed Part event and persistence APIs suffice. The motor board's
guest action path and persistent speed state remain uncertain. If they cannot be
implemented with existing Part APIs, stop at a minimal reproduction and reassess

## Kinetic adapter acceptance checkpoint (2026-11-23)

### Usable adapter and measured dependency closure

native/kinetic_slice.rs retains the three-kind kinetic topology and speed
rules, without Horizon access. native/kinetic_adapter.rs owns typed
BlockPart/BlockEntityPart registration and host IO for only the Creative
Motor, shaft, and small/large cogwheel entities. Its concrete slice closure is
their block/entity registrations and state properties, initial placement and
load callbacks, server tick/network traversal, saved NBT/sync, and the selected
gear edge calculations. The adapter no longer reads the current tick entity
back from the world while the SDK temporarily removes it for its callback; it
uses that callback's current NBT for the source. On-load stores the actual
dimension supplied by the event and ticking resolves that level, with a
state-based fallback for older saves. This removes the hardcoded Overworld path.

The 22 machinery siblings remain out of this dependency closure. machines.rs
and visuals.rs are monolithic legacy modules; importing either wholesale
would pull unrelated machine behavior into this slice. The source code is
bounded to the two adapter modules, but it is not yet integrated into the
complete Create package generator/central content registry.

### Verified source and commands

Source base before this checkpoint: 36cfe1cb017aac83ecf11defb6ca6b82f2e2f680.
The current candidate adds the described server-side adapter changes on that
base. SDK build: Horizon 0a875da91dbb0fdcb7ba8c42c11341aa229af51a, matching
Nov 20 SDK and mixin pin, launcher 0.2.105, Rust 1.99.1, optimized native
profile. The first normal native-build succeeded in 1.15 seconds, producing
native-0a875da-cf76fc2f4db2. After shaping the lane handoff as the free
set_motor_setting(host, level, pos, setting) entry point and exposing the
adapter module to sibling code in the probe crate root, the normal native-build
succeeded again in 1 second, producing native-0a875da-a3e0d9e82002. The full
package generator still needs its central module registration integrated.

Using the source-matched probe package and .local/create.hmod, the existing
fixture commands reported:

* tools/test-shaft-and-cogwheel.py: all 36/36 Java trace rows passed,
  including gear ratio/sign propagation and motor break/replacement restore.
* tools/test-creative-motor-placement.py: all 7/7 facing and item-use
  rows passed.
* tools/test-creative-motor-reload.py: connected horizontal/vertical motors
  and a disconnected idle motor retained ScrollValue and regenerated speed
  after save/reopen.
* tools/test-multiplayer-creative-motor.py: failed at the existing normal
  board action; the typed-Part probe has not migrated the motor menu/input
  route, so this does not test the new setting method or guest replication.
* tools/test-creative-motor-render.py: failed at the frame assertion.
  The offscreen client loaded and rendered, but emitted no
  CREATE_MOTOR_FRAME record.

Tests used horizon-ctl and horizon-client from the built pinned runtime,
prepared 26.3 resources from the installed matching-pinned client, unique
fixture worlds under /private/tmp/hc-fixtures, and the existing Java CSVs.
Behavioral clients were headless; the placement, gear-trace, and visual checks
used the supported --offscreen path. The source content/data still declares
waterlogging. The ignored test pack omits the schema-rejected
properties.waterloggable field to load this selected content under SDK 0.2;
the omission is not represented as equivalent behavior and waterlogging is
unverified in the migrated package.

The exact existing placement, propagation, and reload fixtures pass on the
compiled candidate. The new public set_motor_setting(host, level, pos, setting)
entry point persists a clamped setting and recomputes/syncs its connected
graph, but it is compile-verified only: the existing board and guest action do
not call it yet. Therefore the kinetic flow is partially viable, not a
complete playable/guest-verified slice.

After adding the free entry point and probe crate's sibling-visible module
export for the lane handoff, the exact 36-row, seven-case placement, and
save/reopen fixtures were rerun on native-0a875da-a3e0d9e82002 and all passed
again. Their measured command
durations were 29.4, 7.8, and 8.1 seconds respectively.

### Concrete remaining SDK/API seams

The SDK Part surface supports the server work verified above. Its
BlockEntityPart API has no client block-entity draw callback. The minimal
reproduction is this typed motor entity build plus the existing
test-creative-motor-render.py: with CREATE_MOTOR_RENDER=1, the pinned
offscreen runtime loads the pack and draws frames, but no Part receives the
motor render event and no motor frame trace appears. The old motor draw is in
the broad native/visuals.rs dispatcher alongside many unrelated renderers.
This establishes a missing typed-Part renderer entry point for a behavior-
preserving bounded migration; it does not show that the Horizon renderer
cannot render or that a broad engine rewrite is required. Preserve the old
render path as the reference and resolve through a narrow rendering adapter or
leave this acceptance gate open; do not port the monolithic visuals module.

The normal board, its setting gesture, and its client-to-server guest path are
also not part of this adapter. APP-2164 owns those interactions and common
networking. The tested setter is the shared server operation to wire once that
lane adapts the board. No guest configuration pass is claimed. The old SDK
content schema's rejection of properties.waterloggable is a separate,
reproduced content compatibility gap. No broad engine rewrite, SDK pin update,
or upstream change is warranted by these findings.

### Interface handoff and estimate

For APP-2164, the usable shared source is this checkpoint commit on top of
36cfe1cb017aac83ecf11defb6ca6b82f2e2f680; shared files are
native/kinetic_adapter.rs and native/kinetic_slice.rs. Add the lane's
settings interaction around the registered KineticPart and call
KineticPart::set_motor_setting on the authoritative ServerHost, passing
the typed LevelRef, motor position, and selected signed RPM. The operation
persists the clamped ScrollValue, records the dimension, recomputes the graph,
and syncs speeds. Keep all board/input/network files in APP-2164; send any
shared lib.rs/manifest registration as a small integration patch. Reuse
tools/test-creative-motor.py, tools/test-multiplayer-creative-motor.py,
tools/test-creative-motor-reload.py, and the existing Java evidence. Build
with the pinned launcher command recorded in the Linear handoff; test headless
and use --offscreen only for visual frames.

Implementation has not been integrated into the full package, and the setting
setter is not yet called by normal UI. The successful build and three
server-side fixture gates revise the remaining motor work to 1–3 engineer-
days: about 0.5–1 day to wire normal board/guest setting through APP-2164 and
prove it, 0.5–1 day to preserve/render rotation through a bounded client
adapter, and 0.5–1 day for content waterlogging compatibility, integrated
package validation, and regressions. This range assumes a narrow supported
rendering path or a deliberately open visual gate; inability to add custom
block-entity rendering within the pinned API raises that scope and requires a
decision before an engine-side adapter. It is evidence-based from the passing
server slice, not measured throughput.

Active work in this resumed focused cycle is approximately 14 minutes:
about 6 minutes source/API work, 1.2 seconds successful native compilation,
roughly 1 minute across the passing gear/placement/reopen fixtures, and about
1.5 minutes across the failed render and guest checks. Fixture startup includes
resource loading; these are command durations, not counted as implementation
time. No processing or train flow has been started.
