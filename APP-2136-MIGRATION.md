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

A diagnostic retry excluded all rows reported by the initial validator and
the two obsolete module destinations. This reached SDK source validation, then
failed because remaining helpers reference the old `horizon_client::mobs`
module path from extension modules that no longer resolve in the flat project
(`E_MIXIN_SOURCE`, 57 diagnostics). This filtered package is only a diagnostic
artifact: it drops gameplay rows and is not a candidate runtime build. The
three Stage 1 flows have not passed and no behavior is claimed as migrated.

## Remaining migration inventory and assessment

Pending Stage 1 verification. The Full 1:1 migration and the other Create
families remain out of scope until the three selected cases pass and the
assessment checkpoint is presented.
