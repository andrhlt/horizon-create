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
* tools/test-creative-motor-render.py: the first typed-Part attempt failed
  because the probe did not send a block-entity update tag; the callback ran
  with an empty client NBT. Adding `block_entity_update_tag` to the same
  `KineticPart`, reading its saved speed, and drawing the scaled shaft under
  `block_entity_submit` fixed it. The final offscreen run passed all six
  facings at both Java reference speeds, with matching axis, side, RPM, phase,
  and angle and nonzero submitted geometry.

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

The pinned SDK has a supported `BlockEntityPart::block_entity_submit` draw
callback and a separate `block_entity_update_tag` replacement hook. The prior
checkpoint incorrectly inferred a renderer gap from `BlockEntityPart`'s
surface. The bounded candidate implements both hooks on `KineticPart`, uses
`BlockEntityDrawContext::spin` and `block`, and reuses the existing direction,
phase, and `rpm * 0.3` rules. It compiles against the pinned SDK and the
offscreen fixture passes its numerical and nonempty-geometry checks. The
current probe draws a scaled `create:shaft` block; the fixture package lacks
Create's shaft-half model and textures, so exact material/mesh parity is not
verified. Replace that with the resolved shaft-half model when the selected
content package supplies it; do not import `native/visuals.rs` wholesale.

Waterlogging remains a concrete content-schema compatibility gap. In this
pin, `horizon_mod_package::content::BlockProperties` uses `deny_unknown_fields`
and has no `waterloggable` member. The probe therefore continues to omit that
property, while tracked source definitions still declare it. The passing
kinetic tests do not establish waterlogging behavior. A narrow supported
content representation or a behavior test against a waterloggable template is
still required; do not count the schema omission as equivalent behavior.

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
setter is not yet called by normal UI. The successful server and renderer
gates revise remaining motor work to about 0.5–1.5 engineer-days: about 0.5 day
to connect normal board/guest setting through APP-2164 and prove it, and 0.5–1
day for faithful shaft-half assets, waterlogging representation, integrated
package validation, and regressions. The first native renderer build took
under one second on the pinned prebuilt route; the six-facing offscreen frame
test took 19.8 seconds including client startup. This is measured slice
evidence, not end-to-end integration time.

Active work in this resumed focused cycle is approximately 14 minutes:
about 6 minutes source/API work, 1.2 seconds successful native compilation,
roughly 1 minute across the passing gear/placement/reopen fixtures, and about
1.5 minutes across the failed render and guest checks. Fixture startup includes
resource loading; these are command durations, not counted as implementation
time. No processing or train flow has been started.

## Source-matched kinetic candidate and lane checkpoints (2026-11-23)

`migration/kinetic-probe` is the tracked SDK package harness. Run
`python3 tools/prepare-kinetic-probe.py` to stage the exact tracked
`native/kinetic_slice.rs` and `native/kinetic_adapter.rs` into the isolated
launcher project, then run:

```sh
HORIZON_LAUNCHER_HOME="$PWD/.local/sdk-check/home" HORIZON_HOME="$PWD/.local/sdk-check/game" .local/toolchains/launcher-0.2.105/horizon-launcher native-build .local/sdk-check/project --instance 'APP-2136 SDK Probe' --trust-native-code --profile optimized
```

That normal optimized SDK build passed in **1 second**, producing
`native-0a875da-eb660c9fc22d`. This proves the tracked adapter code compiles;
it is still a probe package, not central-registry integration into the full
Create package.

The four existing cases rerun on that source-matched build and
`.local/create.hmod`:

* `tools/test-shaft-and-cogwheel.py`: **36/36 Java rows passed**, including
  speed propagation, signs, interruption, motor replacement, and restoration.
* `tools/test-creative-motor-placement.py`: **7/7 Java placement cases passed**.
* `tools/test-creative-motor-reload.py`: **active horizontal/vertical and idle
  motors retained settings and regenerated expected speed after reopen**.
* `tools/test-creative-motor-render.py`: **all six facings passed at both
  reference speeds** using `--offscreen`; axis, direction, RPM, phase, angle,
  and nonempty model submissions matched the Java-derived expectations.

The measured command wall times for these fixture runs were approximately 24,
8, 7, and 6 seconds (about **45 seconds total**, including isolated client
startup). The build took 1 second. This resumed source-matched cycle from the
11:52 MDT build through the final offscreen result took about **4 minutes wall
time** including iteration and tool overhead; time before that build was not
separately timed. The earlier 14-minute cycle in the prior section is a
separate report, not throughput derived from this run.

The renderer uses the supported client update-tag and submit hooks and submits
a scaled `create:shaft` model with kinetic spin speed/phase. The fixture
package lacks Create's shaft-half model and textures; its successful geometry
and angle assertions do not prove material or exact mesh parity. Waterlogging
also remains unverified: the pinned `BlockProperties` schema rejects
`waterloggable`, and the ignored test pack omits it. The source JSON still
declares waterlogging. Neither gap is presented as an SDK renderer blocker or
as equivalent waterlogging behavior.

### Processing handoff: Millstone

The bounded Millstone tick in `native/machines.rs::tick_mill` consumes these
interfaces: its existing kinetic entity `Speed`; a ten-slot saved inventory
(slot 0 input and slots 1–9 outputs); a `ModContainer` declaration for normal
player/hopper access; `create:milling` recipes and `recipe_ingredient` /
`recipe_result`; a saved `Timer`; and level RNG for chance outputs. It also
uses the existing landed-item collection path. The original wheat fixture adds
a barrel, Smart Chute, hopper, chest, motor, and shaft/cogwheel drive, so its
whole fixture closure includes item logistics and redstone controls rather
than only Millstone. The narrow machine boundary can first use a typed
Millstone Part and the API's existing block-container/capability interfaces;
APP-2163 owns the stationary inventory/recipe/item-transfer behavior and its
fixture expansion.

Pinned SDK source inspection found `BlockEntityPart` server ticking and saved
NBT, `ModBlockEntityFields.items`, `Registrar::block_container` with
side/input/output rules, the `ITEMS` capability, `Host::recipes_of_type`,
`recipe_ingredient`, `recipe_result`, and `LevelRef::with_random`. These are
concrete supported APIs for the listed boundaries. No missing engine
capability has been reproduced for this Millstone slice. No Millstone runtime
pass is claimed; APP-2163 still needs to implement and compare its first flow.

The usable kinetic interface is `kinetic_adapter::register` plus
`KineticPart::set_motor_setting` in `native/kinetic_adapter.rs`; connected
machine Parts can read synchronized saved `Speed` in their own tick NBT. The
central registry stays with APP-2136; APP-2163 owns Millstone state, recipes,
and inventory; APP-2164 owns player menu/input and guest networking. APP-2163
can start against this handoff without importing the other 22 machine modules
or waiting for the motor board work.

### Moving/train feasibility checkpoint

APP-2165 owns the moving train/contraption family. Its selected train replay
needs shared package registration, typed server block/entity hooks, saved and
synchronized moving state, guest-visible movement, and moving-payload draw
callbacks. The kinetic source can supply speed state as described above; the
train lane owns track/contraption graph, collision, payload and train
rendering. The current kinetic candidate does not compile or run any train
family, so no train API seam is declared solved and no train runtime pass is
claimed. Pinned API source exposes typed block/entity callbacks and supported
draw contexts, and inspection found no specific missing capability; the
remaining uncertainty is migration/fixture closure, not a reproduced engine
blocker. APP-2165 can prepare its owned modules against the source-matched
adapter/build recipe now. A minimal moving-flow runtime probe is still needed
before estimating the full lane from measured throughput.

Kinetic feasibility is established for the bounded server graph, placement,
reload, and submitted shaft rotation. A complete playable motor flow remains
open pending normal board/guest setting, source/registry integration, faithful
shaft-half assets, and waterlogging. The processing and moving lanes are
unblocked at their specific adapter/interface boundaries; neither lane is
represented as complete.

## FEATURE-MATRIX migration ownership (2026-11-23)

Every distinct family row and exact-ID registry inventory entry below has a primary migration owner. This assigns engine-migration ownership only; it does not reopen completed gameplay tickets or change historical verification. A primary family owner owns its gameplay adapter and focused fixtures. The listed co-owner owns only the named cross-cutting seam. APP-2136 retains shared typed-Part/package-root/registry integration and the bounded kinetic family.

| FEATURE-MATRIX family | Primary migration owner | Explicit boundary |
| --- | --- | --- |
| Kinetic network propagation, speed, stress and overload | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Small and large cogwheels, encased cogwheels | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Shafts, andesite and brass encased shafts | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Gearbox and Vertical Gearbox | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Clutch and Gearshift | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Encased Chain Drive and Adjustable Chain Gearshift | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Sequenced Gearshift | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Creative Motor | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Rotation Speed Controller | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Hand Crank | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Copper Valve Handle and all dyed handles | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Water Wheels and Large Water Wheels | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Speedometer and Stressometer | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Flywheel | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Turntable | APP-2136 | Bounded kinetic graph/source/transmission/stress adapter; avoid unrelated machine modules. |
| Millstone | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Crushing Wheels and controller | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Mechanical Press | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Basin compacting and mixing | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Mechanical Crafters | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Mechanical Saw | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Mechanical Drill | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Deployer | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Encased Fan | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Nozzle | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Sequenced Assembly and unfinished ingredients | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Sandpaper and Red Sandpaper | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Fluid Pipe, Glass Fluid Pipe, Smart Fluid Pipe | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Encased Fluid Pipe | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Mechanical Pump | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Fluid Valve | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Fluid Tank and Creative Fluid Tank | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Item Drain | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Hose Pulley | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Spout | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Potion fluids and heated brewing | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Honey, chocolate and tea | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Blaze Burner, fuels and blaze cakes | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Steam Engine, boiler and Powered Shaft | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Steam Whistle and extension | APP-2163 | Stationary processing/inventory/fluid behavior; common menu/network binding remains APP-2164. |
| Super Glue and assembly selection | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Linear, Secondary Linear and Radial Chassis | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Mechanical Bearing | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Windmill Bearing and colored sails | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Clockwork Bearing | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Cuckoo Clock and Mysterious Cuckoo Clock | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Mechanical Piston, Sticky Mechanical Piston, Extension Poles | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Rope Pulley and moving payload | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Elevator Pulley, Elevator Contacts and cabin | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Gantry Shaft and Gantry Carriage | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Cart Assembler and Controller Rail | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Minecart Coupling, Anchor and portable contraption items | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Contraption Controls | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Harvester and Plough | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Mechanical Roller | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Dispensers, droppers and mounted actor behaviors | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Portable Storage and Fluid Interfaces | APP-2165 | APP-2165 owns moving target/lifecycle; APP-2163 owns inventory/fluid semantics; APP-2164 owns player interaction dispatch. |
| Seats and colored seats | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Sticker | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| General contraption rendering, collision and synchronization | APP-2165 | Moving assemblies, lifecycle, collision and moving rendering; mounted inventory contents co-owned with APP-2163; input/menu dispatch with APP-2164. |
| Mechanical Belt and Belt Connector | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Depot | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Weighted Ejector | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Chute and Smart Chute | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Andesite and Brass Funnels | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Andesite and Brass Tunnels | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Mechanical Arm | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Item Vault | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Creative Crate | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Item Hatch | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| List Filter, Attribute Filter and Package Filter | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Cardboard packages and rare variants | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Packager | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Repackager | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Stock Link | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Redstone Requester | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Stock Ticker and Stock Keeper | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Factory Gauge and Factory Panels | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Chain Conveyor | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Frogport | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Postboxes, 16 dyed blocks and items | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Table Cloths, 16 colors and 3 metal variants | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Shopping List | APP-2163 | Item logistics and inventory behavior; shared player interactions/UI with APP-2164. |
| Redstone Contact | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Redstone Link | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Linked Controller and Lectern Controller | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Analog Lever | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Powered Latch and Powered Toggle Latch | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Pulse Repeater, Extender and Timer | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Desk Bell | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Peculiar Bell and Haunted Bell | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Stockpile Switch | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Smart Observer (Content Observer) | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Display Link and Display Board | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Nixie Tubes and dyed variants | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Rose Quartz Lamp | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Controller Rail | APP-2164 | Redstone/display family and common interaction/network hooks; kinetic consumers remain APP-2136. |
| Train Track, curved spans and Railway Casing | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Fake Track | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Track Observer | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Bogeys and train assembly | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Train Station, names and dispatch | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Train Signals and occupancy | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Manual driving and Train Controls | APP-2165 | Track/train/moving state, collision and rendering; schedules/controls UI and common input/network dispatch co-owned with APP-2164. |
| Train Schedules, conductor and schedule condition editor | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Scheduled routing and arrival | APP-2165 | Track/train/moving state, collision and rendering; schedules/controls UI and common input/network dispatch co-owned with APP-2164. |
| Train passengers, seats and dismount | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Mounted train item and fluid storage | APP-2165 | APP-2165 owns moving target/lifecycle; APP-2163 owns inventory/fluid semantics; APP-2164 owns player interaction dispatch. |
| Train post routes, parcels and station buffers | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Train door integration | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Train display sources, announcements and audio | APP-2165 | APP-2165 owns moving/train behavior; APP-2164 co-owns player input, menus and common networking. |
| Zinc Ore, deeper Zinc Ore, raw/zinc blocks and Zinc processing | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Create stone world generation and Striated Ore | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Decorative stone palettes | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Rose Quartz and Polished Rose Quartz palettes | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Glass windows and panes | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Train Trapdoor and Framed Glass Trapdoor | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Copycat Panel, Step, base and Bars | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Andesite, Brass and Copper Casings | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Andesite Alloy and Industrial/Weathered Iron blocks | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Metal Bars | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Metal Ladders | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Andesite, Brass and Copper Scaffolding | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Metal Girders and encased Girder Shafts | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Wooden and Metal Brackets | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Copper Shingles and Tiles, slabs, stairs, wax/oxidation variants | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Placard | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Sliding Doors and train-side door interactions | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Shadow Steel and Refined Radiance family | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Common parts and metal intermediates | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Experience Nugget and Experience Block | APP-2164 | Content/static assets/worldgen; moving train-side door behavior co-owned with APP-2165. |
| Wrench | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Engineer's Goggles | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Clipboard | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Cardboard, Pulp, Cardboard Block and Bound Cardboard | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Cardboard armor and disguise | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Cardboard Sword | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Copper Backtank, Copper Diving Helmet and Copper Diving Boots | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Netherite Backtank and Netherite diving gear | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Toolbox, 16 colors | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Potato Cannon | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Extendo Grip | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Wand of Symmetry | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Handheld Worldshaper | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Tree Fertilizer | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Shears/deployer interactions | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Create foods and Builder's Tea | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Crafting Blueprint and Blueprint display | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Empty Schematic, Schematic and Quill, Schematic Table | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Schematicannon | APP-2164 | Tools, equipment, screens and player interactions; recipe/machine outputs co-owned with APP-2163. |
| Survival progression and advancement ownership | APP-2164 | Static presentation, UI and compatibility; machine recipe logic with APP-2163; kinetic rendering/dispatch with APP-2136; moving presentation with APP-2165. |
| Creative tabs, creative search and item attribution | APP-2164 | Static presentation, UI and compatibility; machine recipe logic with APP-2163; kinetic rendering/dispatch with APP-2136; moving presentation with APP-2165. |
| Crafting, Stonecutting, smelting, blasting, smoking and campfire recipes | APP-2164 | Static presentation, UI and compatibility; machine recipe logic with APP-2163; kinetic rendering/dispatch with APP-2136; moving presentation with APP-2165. |
| Machine recipe logic and registry integration | APP-2163 | Static presentation, UI and compatibility; machine recipe logic with APP-2163; kinetic rendering/dispatch with APP-2136; moving presentation with APP-2165. |
| Block, item and entity models, textures and animation | APP-2164 | APP-2164 owns static assets; APP-2136 owns bounded kinetic dynamic state; APP-2165 owns moving-world rendering. |
| Sounds, particles and effects | APP-2164 | APP-2164 owns shared asset/event registration; each gameplay lane owns its event triggers and state. |
| Localization and UI | APP-2164 | Static presentation, UI and compatibility; machine recipe logic with APP-2163; kinetic rendering/dispatch with APP-2136; moving presentation with APP-2165. |
| Ponder and tutorials | APP-2164 | Static presentation, UI and compatibility; machine recipe logic with APP-2163; kinetic rendering/dispatch with APP-2136; moving presentation with APP-2165. |
| Server configuration, permissions and persistence | APP-2136 (integration); each lane (family state) | APP-2136 owns shared save/runtime integration; APP-2163/2164/2165 own their family-specific data and multiplayer behavior. |
| Java integration equivalents | APP-2164 | APP-2164 owns screens/input/common networking; APP-2163 owns recipe lookup/content integration. |
| Blocks | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Items | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Recipes | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Block entity types | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Entity types | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Fluids | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Menus | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Particle types | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Recipe types | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Sound events | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| Java recipe ID | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| `create:emptying/compat/farmersdelight/milk_bottle` | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| `create:filling/compat/farmersdelight/milk_bottle` | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |
| `create:haunting/compat/farmersdelight/rotten_tomato` | APP-2136 | Central registry/package manifest integration; functional tests stay with the owning family. |

Repeated identical family labels within one matrix section are intentionally mapped once. Cross-cutting static content does not transfer ownership of the underlying machine algorithm. APP-2163 owns stationary processing/logistics; APP-2164 owns common player interaction and static content; APP-2165 owns moving assemblies/trains; APP-2136 owns residual kinetic behavior plus shared integration.

## Central integration progress (2026-11-23)

Reviewed APP-2163 PR #193 commits `3534d45` and `6360a23`: the existing
Millstone tick path now calls the extracted pure `native/millstone_processing.rs`
transition. Its focused Rust checks and GitHub quick checks passed. This owner
integrated both commits into the PR #192 working branch and added the module to
`native/horizon-mixin.toml` plus the kinetic probe crate/stager so the source is
available to the typed package without pulling in `machines.rs`'s sibling
machine closure. At this earlier checkpoint the pinned SDK validation was
pending; the result below supersedes that status.

APP-2164 PR #194's signed-speed zero-detent fix (`signed_speed`) is also
integrated. It repairs the legacy board conversion. The later typed board Part
and setter compile, but normal screen opening and host/guest configuration
remain unverified. APP-2165's draft PR #195 is stacked on PR #192 and includes
a typed mechanical-bearing feasibility probe. The later section records its
pinned compile and bounded world-runtime results. Neither lane checkpoint
establishes full processing or train migration.

## Frozen-SDK kinetic and follow-on probe (2026-11-23)

### Compiled dependency closure

The bounded probe staged typed sources rather than trimming siblings out of
`machines.rs`. Its closure was `kinetic_slice` + `kinetic_adapter` + the
APP-2164 `motor_board` Part; Millstone Part/container + pure
`millstone_processing` + the `create:milling` raw recipe serializer; and the
APP-2165 bearing payload Part. It registered only Creative Motor, shaft,
cogwheel, large cogwheel, Millstone and mechanical-bearing blocks. The other
22 machinery modules were not included, and their omitted diagnostics are not
migration defects.

The normal pinned `native-build` passed with launcher 0.2.105, Rust 1.99.1,
Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, MC 26.3 and mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`. Lane source heads were APP-2164
`915b4b6`, APP-2163 `39e6c28` and APP-2165 `476f5b2`; central integration is
source commit `b15a2ca`, and final artifact is
`native-0a875da-a61b632c7d2d`.

### Runtime evidence on that artifact

- Creative Motor placement: 7/7 Java cases.
- Shaft/cogwheel graph: 36/36 Java trace ticks.
- Connected and idle Motor save/reopen preserved `ScrollValue`, Motor speed
  and driven shaft speed.
- Supported offscreen Motor rendering: all six facings at both signed speeds
  matched Java axis, half-shaft side, RPM, phase and angle assertions.
- Typed Millstone probe: a synthetic `create:milling` wheat recipe completed
  at 16 RPM; zero-speed input and existing output remained through save/reopen.
- Typed bearing probe: a chest carrying seven iron ingots moved through the
  payload path, retained inventory across active save/reopen, carried the host
  player and reached the safe dismount state.

The Millstone test exposed two closure/adaptation needs. The typed package
must register the mod-owned `create:milling` recipe type and raw serializer.
Create writes ingredients as `{item: ...}` / `{tag: ...}`, while the pinned
`Host::recipe_ingredient` accepts a bare id, `#tag` or a string list; the
adapter now normalizes those forms. This is a small supported-API adaptation,
not an engine rewrite. The synthetic fixture does not prove the production
wheat/flour recipe, output backpressure, automation or LAN behavior.

### Remaining concrete gates

The kinetic calculation and typed world adapter are viable without the
monolithic machine closure. The complete user flow is not: the typed board
Part and shared setter compile, but `PlayerRef::open_mod_menu` needs opaque
`MenuKey`. The pinned public API exposes `menu_keys()` and `menu_key_id(key)`,
but no supported content-id-to-key lookup or registrar resolver. The empty-hand
board hook therefore remains non-opening; normal host/guest setting changes
are unverified. No opaque-key indexing was used. This specific API seam is not
evidence that the kinetic graph requires a broad rewrite.

The bearing is a minimal typed feasibility probe, not a full bearing port: its
runtime check covers block movement, inventory conservation, save/reopen, a
host rider and safe terminal dismount. Legacy controls, arbitrary glued
payloads, collision parity, guest riders, rendering and train behavior remain
open. The typed Millstone uses a synthetic recipe; production recipe and
inventory automation checks remain open.

The broader `tools/test-kinetic-network-sources.py` does not pass on this
adapter: it stops at the first assertion because the typed path publishes
`Speed` / `MotorGeneratedSpeed` but does not publish legacy `Capacity` and
`Stress` fields. That suite also exercises multiple-source conflicts and
network merge/split behavior beyond the one-motor gear-train slice. Keep those
as explicit kinetic follow-ups; do not infer their correctness from the 36-row
single-source trace.

The probe stager omits `BlockProperties.waterloggable` because the pinned
content schema rejects it. The probe is not waterlogging-equivalent; production
`.hmod` content was not stripped. Offscreen rendering currently validates the
existing Motor rotation only.

### Time and next steps

The final `native-build` command reported 1 second (earlier iterations were
0–1 seconds) and selected `native-0a875da-a61b632c7d2d`. The six final runtime
suites accumulated about 69 seconds by the tool-reported wall times. The
elapsed implementation cycle from resume to this report was 45 minutes 11
seconds, including inspection, code changes, builds and
runtime checks; uninterrupted coding time was not instrumented.

Runtime traces/logs are retained under `.local/candidate-a61b632c7d2d-*`. The
older working build and reference fixtures remain. PR #192 remains draft; the
engine and shared pin are unchanged.

1. Resolve the public `MenuKey` seam, then wire the existing board action and
   verify host/guest setting changes plus shaft convergence.
2. Run the typed Millstone against the production wheat/flour recipe, then
   verify conservation, idle/active reopen, full outputs, hopper insertion and
   extraction, and host/guest inventory authority. Reuse its current
   Part/container/timer and recipe normalization.
3. Bridge the bearing probe to actual legacy assembly/control, collision and
   guest-rider semantics before measuring a train slice; the current proof does
   not justify a train-monolith migration.

The bounded proof shows typed adapters compile and run on the frozen SDK, with
one known public menu-resolution gap before the normal kinetic user flow is
complete. Re-estimate remaining effort from these scoped results; the broad
full-mod estimate was not measured by this checkpoint.

## Capacity, stress and source-transition checkpoint (2026-11-23)

This supersedes the earlier source-network and MenuKey gate notes above. I
extended the same bounded graph rather than importing `machines.rs` or any of
the 22 omitted families. `kinetic_slice` now resolves motor source capacity,
network RPM, Millstone impact and opposing-source conflict; `kinetic_adapter`
publishes `Network.Capacity` and `Network.Stress` while preserving sibling
network tags. It uses the retained constants and rules: a Creative Motor yields
16,384 capacity per generated RPM; Millstone contributes 4 stress units per
RPM adjusted by its graph ratio; sources sum capacity, greatest absolute
supplied RPM wins, and the network overload boundary is strictly
`stress > capacity`. The Millstone adapter uses effective speed at that same
boundary, so overloaded motion does not continue processing.

A supported `LevelRef::destroy_block(host, pos, drop, tool, collect)` call now
removes a newly joined kinetic bridge when opposing nonzero source directions
conflict, retaining normal drops. The existing Java transition fixture verifies
equal, weaker and stronger conflicting joins; equal and unequal source merges;
separation; motor-setting changes; and idle/active reopen. The adapter stages
all retained network state and updates connected members from the graph.

### Verified on the latest normal SDK candidate

Pinned optimized `native-build` passed on launcher 0.2.105 / Rust 1.99.1 with
Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, MC 26.3 and the unchanged
mixins pin. Candidate: `native-0a875da-bd31d83d5ff9`. The probe-content SHA-256
remains `b185423f64c75cfae3c24a31cfc17de72257447eb43998520fcef89b8bc9775a`.

All eight headless/offscreen suites passed on that artifact:

- `test-shaft-and-cogwheel.py`: 36/36 Java trace ticks.
- `test-creative-motor-placement.py`: 7/7 placement cases.
- `test-creative-motor-reload.py`: driven and idle persistence after reopen.
- `test-creative-motor-render.py`: six facings at both signed settings through
  the supported offscreen render path.
- `test-kinetic-network-sources.py`: source conflict, merge/split and reopen
  trace.
- `test-typed-kinetic-stress.py`: motor capacity 262,144 and Millstone stress
  64 at 16 RPM.
- `test-typed-millstone-probe.py`: synthetic recipe, idle input and reopen.
- `test-typed-bearing-probe.py`: seven-item payload, host rider and reopen.

The standalone pinned Rust test harness for `native/kinetic_slice.rs` passed
4/4, including exact-capacity operation, overload above capacity, capacity
summing, and opposing source detection. The runtime stress fixture exercises
real graph publication at its measured motor/Millstone values; an actually
overloaded motor-to-Millstone world is not claimed because the bounded fixture
load is far below Creative Motor capacity. Runtime command wall times summed
across the eight concurrently run fixtures were about 84 seconds; their total
batch wall time was about 16 seconds. The final SDK build reported 0 seconds
(launcher rounded subsecond elapsed time). The retained artifacts are
`.local/candidate-bd31d83d5ff9-horizon-ctl` (SHA-256
`61ab9be5b1f232446f1d6d5be4b296b954d538986bbac38dc5f54ba8c7e11372`) and
`.local/candidate-bd31d83d5ff9-horizon-client` (SHA-256
`012bf6dbfecb095bfb27f9b84452105639501cc5444aca15517360cd90547935`). The fixture and pure-test loop after
the previous checkpoint took about 17 minutes wall-clock; uninterrupted coding
time was not instrumented.

### Remaining kinetic and lane boundaries

The earlier statement that the pinned API lacks a menu identifier resolver is
incorrect. `KeysHost::menu_keys()` and `KeysHost::menu_key_id(MenuKey) -> String`
provide a supported canonical-ID scan, and APP-2164 pushed it in PR #194
(commit `c243446`). The resolver compiles, and the diagnostic use trace now confirms the server
path runs: `USE` reached the motor, the canonical resolver returned
`key=true`, and `open_mod_menu` returned `Some(1)` / `Some(2)`. The focused
`tools/test-creative-motor.py` still fails because after those server opens the
client reports `screen=playing`, `menu=None`, and no screen buttons. The
remaining gate is client-side screen presentation/widgets. No guest setting
change through the typed board has yet passed runtime acceptance. Earlier
click-hook failures came from cached prebuilt metadata; source provenance now
shows this is not a proven frozen-engine capability gap (see below).

Waterlogging remains a content-compatibility gap: the isolated probe stager
omits the pinned-schema-unsupported `BlockProperties.waterloggable`, and emits
that warning each time it stages. Production source content was not stripped.
The Millstone recipe is synthetic; production wheat/flour recipe, output
backpressure and guest inventory authority remain unverified. The bearing result
is feasibility evidence only; it is not complete legacy bearing, contraption or
train behavior. Processing and moving-lane ownership/assessment remain separate
from this bounded kinetic result.

The motor/shaft/cogwheel adapter is viable without broad architecture changes.
Reuse its `KineticPart` graph traversal, signed motor source, persistence/sync,
source handling and gear ratios for the next integration step. Keep PR #192
Draft and preserve the shared SDK pin. Continue from the board lane's supported
menu resolver, then rerun host/guest input and save/reopen on the combined
candidate before claiming the ordinary user flow complete.


### Board-open integration follow-up (2026-11-23)

Integrated APP-2164 resolver source `c243446` into the probe’s tracked
`native/motor_board.rs`. Pinned `native-build` passed and selected
`native-0a875da-614736877ab7`. Headless source-transition, capacity/stress and
motor-reload checks pass on that candidate. The focused offscreen
`tools/test-creative-motor.py` remains failed: it reports no board/buttons after
seven input ticks; a direct state sample shows `menu=None` and `screen=playing`.
This does not yet isolate whether the typed Part interaction hook fired or the
menu open was refused. Adding a separate `Registrar::block_part` registration
was tested and immediately refused at startup with duplicate `KineticPart` and
`MotorBoard` attachments; those lines were reverted. On this SDK path,
`block_entity_part` already attaches a dual-trait Part's BlockPart implementation.

The fixture's reported state also included `pointer_grabbed=true` under its
offscreen interaction path. No visible window was opened, but I stopped further
interactive offscreen trials pending confirmation that this is only the virtual
client state and not OS pointer capture. Headless server and persistence tests
continued.

Measured since the capacity checkpoint: approximately 12 minutes additional
wall-clock for resolver integration, build, focused test and hook registration
investigation; active coding time was not instrumented. A test call on this
candidate takes about 10 seconds; the normal optimized mod build rounded to
1 second. The source-transition, stress and reload headless tests passed again.


### Motor board server-open trace (2026-11-23)

The diagnostic candidate `native-0a875da-e4a376e468b3` compiled with
APP-2164's env-gated trace and the production resource
`content/data/create/horizon/menu/creative_motor.json`. The same offscreen
interaction fixture reached the server callback twice. Logs show the expected
motor block/position, `CREATE_MOTOR_BOARD_MENU key=true`, and
`CREATE_MOTOR_BOARD_OPEN result=Some(1)` / `Some(2)`; no `OpenMenuError`
was returned. The client nevertheless stayed at `screen=playing`,
`menu=None`, with an empty buttons list. This isolates server callback dispatch,
menu-key resolution and server open success; it does not pass client menu
presentation or button interaction. The stager now sources the menu JSON from
production `content/` so subsequent probes use the real resource.

The frozen SDK source documents scoped `screen`, `screen_draw`, and
`screen_click` hooks for block menus, plus a separate mod-owned widget screen.
`MotorBoard` currently implements only the server `menu_button` callback; it
does not provide a `screen` layout/draw implementation. The client screen path
is still unverified, not an established API absence. Older builds reported
`Hooks::screen_click` E0407 and an immutable/mutable ClientHost mismatch, but
those builds used stale cached prebuilt metadata. The source checkout
`e9e32af90a` has merge-base exactly
`0a875da91dbb0fdcb7ba8c42c11341aa229af51a`; its generated
`mod_api_generated.rs` exposes `Hooks::screen`, `screen_draw`, and `screen_click`
(SHA-256 `78cb448493be7c4f0a868592c66d429c5ba6420a478de17cd1507b4b7bd6fed2`).
The launcher 0.2.105 prebuilt `libmod_api.rmeta` used here has SHA-256
`b2b76c563ba4495697a8fdd357331573651884992000892e435498fa27906c21` and lacks
`screen_click`; its build log says it reused mod tools kept from the Nov 20
update. This is an SDK artifact provenance mismatch. Do not label it an engine
blocker or use regenerated API metadata with the old runtime until a
source-matched build path is demonstrated. Separate Horizon PR #1
(`e9e32af90a`) makes `MenuRef::click_button` use the immutable host and its
focused test emits exactly one `ContainerButtonClick(container=5, button=3)`;
that patch is not in this candidate. APP-2164 still owns proving the matching
typed client screen/input route. The legacy NativeScreen helpers are excluded
from this typed probe. Ordinary host/guest settings remain unverified until a
matching client screen, visible controls and shared server setter pass
together.

### Typed adapter source-path validation (2026-11-23)

The typed adapter now imports sibling `create_kinetic_slice` / `kinetic_adapter`
modules through `super`, and the probe stager maps those production names back
to its standalone crate's short module names. This is path adaptation only; the
kinetic rules are unchanged. The normal optimized build command used the
existing instance ID `app-2136-sdk-probe` (the old display-name alias no longer
resolves) and selected `native-0a875da-d219d9ba5254` on Horizon
`0a875da91dbb0fdcb7ba8c42c11341aa229af51a` / MC 26.3, launcher 0.2.105,
Rust 1.99.1, unchanged mixins and unchanged `.local/create.hmod` SHA-256
`b185423f64c75cfae3c24a31cfc17de72257447eb43998520fcef89b8bc9775a`.

On that exact candidate, headless checks passed:

* `tools/test-creative-motor-reload.py`: connected signed settings and idle
  motor settings/speeds survive reopen (9.5 s).
* `tools/test-kinetic-network-sources.py`: source conflicts, equal/unequal
  merges, split, idle reopen and active reopen pass (21.9 s).
* `tools/test-typed-kinetic-stress.py`: connected 16 RPM motor/Millstone
  reports capacity 262144, stress 64 and speed 16 (4.6 s).

All three harnesses first hit sandbox `Operation not permitted` while creating
their local control socket; rerunning through the approved scoped filesystem
escalation reached the headless world and passed. I did not rerun the offscreen
placement/click fixtures because the earlier offscreen snapshot reported
`pointer_grabbed=true`; their previous passing results remain attached to the
earlier candidates, not this final source hash. Active time for this follow-up
is about 18 minutes wall-clock; the successful optimized compile took 1.2 s,
and the three passing harnesses took 25.7 s as a parallel batch (35.9 s summed
process time). The board's client layout and visible controls remain open; the
kinetic normal-setting flow is incomplete.

### Powered bearing feasibility checkpoint (2026-11-23)

The latest APP-2165 probe was tested as a bounded moving feasibility slice on
the same frozen pin, without claiming full contraption or train migration. The
actual compile dependency closure was the existing kinetic-probe module set
(motor registration and `ScrollValue`, kinetic adapters/content, menu and
Millstone registration) plus the APP-2165 moving-bearing Part and the production
`mechanical_bearing.json` block definition. A motion-only mod did not have the
motor block-entity registration; its first launch correctly followed the idle
path. The combined probe reuses the existing kinetic modules instead of pulling
in unrelated machinery families. This launcher build compiles one combined
probe mod, not the final whole Create pack.

Normal optimized SDK validation passed on launcher 0.2.105 / Rust 1.99.1 / MC
26.3 / Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a` / unchanged mixins.
It reused the Nov 20 prebuilt API route and selected
`native-0a875da-cc05729f9304`; launcher reported one second. The artifact's
`native-mods.json` SHA-256 is
`5c4473beeb89a702bcf306af13f8baebce4926fedadeee695a6b820bc3b4f249`, and
`libmod_create_kinetic_probe.dylib` SHA-256 is
`bb06d4bce80803cb638646d1295089c45cd8fcc2934e9a3844fbfa6040da17bd`. It used
the unchanged Create pack SHA-256
`b185423f64c75cfae3c24a31cfc17de72257447eb43998520fcef89b8bc9775a`. The
staged root registration was based on `migration/kinetic-probe/src/lib.rs`
(staged SHA-256
`ba7ece5eb3d61fce535134dbe4ff1c525999eac2bb53ee7977669ad44e2bac24`). The
moving Part implementation came from APP-2165 PR #195 head `4fdeb64`, source
`migration/motion-probe/src/lib.rs` (SHA-256
`1412d6b57f9b28e52e74dca957c0bfd571ac42ce161d6d23228288c60ea1f6cb`); for the
combined crate, only its package-level Hooks tail was replaced with a
`register` function. The compiled staged `moving_probe.rs` SHA-256 is
`a67b67f5eb7b1398feea4750e8f2764e4a195e4aa87bc178dbe57e7efcb4e03f`.

The headless command was
`TMPDIR=/private/tmp/hc-fixtures PYTHONPATH=tools python3
.local/sdk-check/app2165-83d2e97/tools/test-typed-bearing-rotation.py
.local/sdk-check/home/versions/native-0a875da-cc05729f9304/horizon-ctl
.local/sdk-check/home/versions/native-0a875da-cc05729f9304/horizon-client
'<26.3 resource directory>' --pack .local/create.hmod`; the test source hash is
`18923242721ead7b7fbb5f3929b39baae3107ce7c5590733c25c4c0f073ab58f`. It
passed both powered and blocked worlds: a 20 RPM motor advanced angle to about
90° in 15 controlled ticks; the chest rotated to `(0,101,-1)`; the rider
followed within fixture tolerance; seven iron ingots were conserved; active
save/reopen retained the payload and angle progression; zero power and an
occupied target both ended motion with safe dismount. The initial rider run
exposed a real defect: rounded angular steps with no block-coordinate movement
were treated as a dismount and teleported the rider to `(0,0,0)`. APP-2165
fixed this by distinguishing no positional delta from an explicit dismount.
The passing reopen check measures `MotionOffset` delta and checks six degrees
per actual Part tick; world startup clock ticks differ from bearing Part ticks.
The fixture used headless clients and the approved local-socket filesystem
escalation; no visible client was opened.

On the same artifact, three kinetic regressions also passed in about 20 seconds
batch wall time: motor settings/speeds persisted through reopen; equal/weaker/
stronger sources, merge/split and active/idle reopen passed; and the motor/
Millstone graph published capacity `262144`, stress `64`, and speed `16` at 16
RPM. Their scripts were `test-creative-motor-reload.py`,
`test-kinetic-network-sources.py`, and `test-typed-kinetic-stress.py`.

This is feasibility evidence for one up-facing bearing, an adjacent creative
motor and one immediately adjacent chest. Server payload relocation is discrete
block movement; continuous client pose is a separate rendering path. It does
not prove arbitrary glue/BFS payload capture, multiple blocks or entities,
complete item restoration, general collision restoration, LAN guest rider
safety, or trains. Those limitations and the typed screen artifact provenance
mismatch remain open. The source-matched typed motor board screen has not yet
passed; APP-2164's latest candidate must stage `native/motor_board.rs` and
match generated SDK metadata to its runtime.

Measured since the previous kinetic checkpoint: three optimized launcher build
attempts completed in about one second each after staging corrections; the
successful powered fixture and three kinetic regressions together used roughly
35 seconds of headless test runtime. Wall-clock implementation time was not
instrumented; this investigation/integration cycle took about 25 minutes by
elapsed work. The earlier 4–7 engineer-day estimate is not a measured rate and
should be replaced with scoped estimates after board source/runtime provenance
is resolved. No processing or train expansion was performed in this cycle.

### Screen source port and production Millstone recipe (2026-11-23)

The central `native/motor_board.rs` now contains the typed `screen`,
`screen_draw`, and `screen_click` handlers from APP-2164's source-generated API
candidate, using the shared adapter setter for the authoritative server action.
Formatting and diff checks pass. Source-generated API compilation was verified
on APP-2164's isolated candidate, but this central combined source has not been
built against a matching client/runtime. The Nov 20 cached `libmod_api.rmeta`
remains ABI-stale for those hooks, and the exact source-matched developer
version is not prepared in the isolated launcher home. The supported launcher
`prepare --download` path returned the Java Edition account-entitlement gate.
No account files, managed resources, or cache leases were copied or bypassed.
Host/guest board opening, rendering, clicks, and motor changes remain
unverified; this is a runtime provisioning blocker, not evidence that Horizon's
frozen source lacks those hooks.

APP-2163 supplied a separate Java-backed wheat milling recipe: wheat flour ×1
at 100%, flour ×2 at 25%, seeds ×1 at 25%, `processing_time: 150` (fixture
`fixtures/typed-millstone-production`, source commit `1569bbb`). It must not be
mixed with the synthetic probe wheat-to-bread override. I built an isolated
temporary test pack containing the existing test pack plus only this recipe;
pack SHA-256 is
`43e3eac075c7c60172ddae1013576d45cf8770d777774d8d8f9432c321fc212e`, and the
synthetic recipe is absent. The production fixture needs 152 ticks at 16 RPM
to account for the start tick and 150 timer decrements. Its run was blocked
before world startup: direct `horizon-ctl` launch returned exit 78 for
unregistered managed cache leases; the registered-version route said the
candidate was not prepared in the selected home. No processing, persistence,
or backpressure result is claimed from that attempt. The tracked `content/`
tree is an override set; `tools/prepare.py` imports generated Java milling
recipes into a full production pack. The minimal `.local/create.hmod` used for
this probe is not that full pack. This temporary recipe is test input and is
not a product resource change.

### Isolated source compile and moving-probe correction (2026-11-23)

I integrated APP-2165's bounded adjacent-block bearing source (PR #195
`f0d05fe`) into the central probe and fixed its actual pinned API usage. The
probe snapshots canonical state strings and block-entity NBT for the five
immediate blocks around the bearing, rotates/restores those states, and
preserves their inventories. It is not a glue/BFS contraption traversal; the
client draw path still submits one chest model, and only server payload state
is covered by the current fixture. The fixture's barrel was moved from two
blocks east (outside the probe closure) to the immediate south neighbor; it
now checks two actual captured inventories without claiming glue behavior.

A private target-directory `cargo check --offline` compiled the complete
central probe (kinetic adapter/slice, typed motor board, Millstone matcher and
processing logic, and moving bearing) against Horizon source-generated API from
`e9e32af90a8661c61a65be3e5ecb05a3dd9aabab`. Relevant API source differs from
frozen `0a875da91dbb0fdcb7ba8c42c11341aa229af51a` only in
`horizon-mod-vocab/src/host/menus.rs`; screen-hook declarations are unchanged.
The build first identified `block_state_id`/`block_state_string` as direct
`ServerHost` methods rather than `BlockStates` methods, plus the lossless NBT
`JavaString` conversions. The corrected code passes; only the existing unused
`Network::speed` warning remains. Initial dependency compilation took about
21 seconds; the incremental check took 0.36 seconds. This is a source compile,
not launcher `native-build` or client/runtime validation. The isolated
`native-build --server-output` route separately refused this macOS host because
Horizon has no game package for its system.

The exact source hashes are: moving Part
`e0853afb7cbccf271f59b2174011e6cd8c2d5b374b62d265db236cc5e22969a8`, rotation
fixture `35e341f0f0df29faeed7b489bdfa06c42d467e2b4daf70f2371df8d5428bad00`,
Millstone fixture `9593fbce2c3caa4c33c11a84c9bcdae5a80f4b68bc9fa65efd14ea0b0d46af30`,
and Java-backed recipe
`c90d2e53533cc896d76f76054dc4eea3506406b905feccada49d8d8cde8ca1dc47`.
The matching runtime fixtures remain blocked before world start by managed
launcher preparation/lease requirements; no runtime result is claimed for the
new multi-block source or the production Millstone recipe.

The integrated movement fixture was corrected after checking the capture closure:
the chest and barrel now occupy two immediate neighbors of the bearing, rather
than placing the barrel two blocks out. It verifies two inventories and rider
position but does not claim glue detection; the probe snapshots the five
immediate positions only. The bearing draw hook currently renders one chest,
so multi-block visible rendering is still open. The Millstone assertion now
accepts the guaranteed flour regardless of the optional 25% extra-flour roll.
Its repeatable pack builder removes the synthetic bread recipe, retains a
production wheat-milling recipe when present, and otherwise injects the
Java-backed fixture recipe. Pure pack assertions passed with `.local/create.hmod`:
synthetic recipe absent, fixture recipe present; generated test pack SHA-256
`6acac7cf0c44399d74fd9af240a8ba3d21b88ca4b6db69481ec42b23d6b590f4`.
Updated fixture hashes: bearing
`35e341f0f0df29faeed7b489bdfa06c42d467e2b4daf70f2371df8d5428bad00` and
Millstone `15696ea4ecfe9e3d76020d7d9c1c4320d9e0d9ef0f2cca98d170100fad0a3fa1`.
The pack-builder check is not a Horizon gameplay result; both runtime fixtures
still await a runnable matching registered candidate.

### Remaining migration inventory size

The ownership table contains 174 entries: 163 FEATURE-MATRIX gameplay-family
rows and 11 exact-ID registry/inventory rows. Primary ownership is APP-2136 29
entries, APP-2163 49, APP-2164 61, and APP-2165 34, plus one shared registry
state row. These are assignments, not 174 uniformly missing or unverified
families: the feature matrix currently has 119 `Yes` and 44 `Partial` gameplay
rows, with Full 1:1 still tracked separately. This APP-2136 probe is feasibility
coverage for a bounded kinetic/motor/shaft/cogwheel path, one Millstone matcher,
and an immediate-neighbor bearing path. It does not complete any broad family
row or justify declaring the remaining ownership table migrated.
