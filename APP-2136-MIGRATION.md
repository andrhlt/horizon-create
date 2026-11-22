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
