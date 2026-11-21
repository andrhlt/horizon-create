# Fluid tank parity evidence

Verified checkpoint: November 18, 2026. Original Java Create 6.0.10 / Minecraft 1.21.1, revision `ac0c444d9828da3453ae8cc65338e8de063286fb`. Horizon remains pinned to `9f42064` / Minecraft 26.3; the integrated native build is `native-9f42064-92ef2557669b`.

**31/31 headless Horizon scenarios match all 1,430 captured Java records on this one build.** The same production connectivity/storage code also passes 19/19 fast-core scenarios (1,093 records). Integration-only scenarios exercise actual player interaction, block states, world lifecycle or lighting rather than an imitation in the core adapter.

Every record compares its logical tick and requested fields without offsets or rebasing: controller identity, capacity, fluid/amount, components, accepted fill, drained contents, held item/inventory, shape, source emission and comparator output. Exact runner artifacts, script hashes and pinned Java revision accompany the goldens. This is scoped evidence, not a claim that every tank surface is finished.

| Scenario | Java records | Shared core | Actual Horizon |
| --- | ---: | --- | --- |
| [capability-transfers](fixtures/tank-scripts/capability-transfers.json) | 21 | Pass | Pass |
| [clone-comparator](fixtures/tank-scripts/clone-comparator.json) | 31 | Integration only | Pass |
| [column-middle](fixtures/tank-scripts/column-middle.json) | 33 | Pass | Pass |
| [column-root](fixtures/tank-scripts/column-root.json) | 33 | Pass | Pass |
| [column-top](fixtures/tank-scripts/column-top.json) | 33 | Pass | Pass |
| [container-buckets](fixtures/tank-scripts/container-buckets.json) | 20 | Integration only | Pass |
| [container-variants](fixtures/tank-scripts/container-variants.json) | 30 | Integration only | Pass |
| [containers](fixtures/tank-scripts/containers.json) | 10 | Integration only | Pass |
| [creative-capability](fixtures/tank-scripts/creative-capability.json) | 11 | Pass | Pass |
| [creative-connectivity](fixtures/tank-scripts/creative-connectivity.json) | 13 | Pass | Pass |
| [creative-root-removal](fixtures/tank-scripts/creative-root-removal.json) | 10 | Pass | Pass |
| [creative-signals](fixtures/tank-scripts/creative-signals.json) | 19 | Integration only | Pass |
| [empty-anchor](fixtures/tank-scripts/empty-anchor.json) | 68 | Pass | Pass |
| [flat-split](fixtures/tank-scripts/flat-split.json) | 66 | Pass | Pass |
| [height-limit](fixtures/tank-scripts/height-limit.json) | 232 | Pass | Pass |
| [high-fill-forward](fixtures/tank-scripts/high-fill-forward.json) | 65 | Pass | Pass |
| [high-fill-reverse](fixtures/tank-scripts/high-fill-reverse.json) | 65 | Pass | Pass |
| [lifecycle-clone-capacity](fixtures/tank-scripts/lifecycle-clone-capacity.json) | 34 | Integration only | Pass |
| [lifecycle-clone](fixtures/tank-scripts/lifecycle-clone.json) | 31 | Integration only | Pass |
| [lifecycle-move](fixtures/tank-scripts/lifecycle-move.json) | 21 | Integration only | Pass |
| [light-comparator](fixtures/tank-scripts/light-comparator.json) | 19 | Integration only | Pass |
| [mixed-fluid-layers](fixtures/tank-scripts/mixed-fluid-layers.json) | 43 | Pass | Pass |
| [mixed-tank-kinds](fixtures/tank-scripts/mixed-tank-kinds.json) | 22 | Pass | Pass |
| [variants](fixtures/tank-scripts/variants.json) | 18 | Pass | Pass |
| [vertical-empty-reverse](fixtures/tank-scripts/vertical-empty-reverse.json) | 84 | Pass | Pass |
| [vertical-empty](fixtures/tank-scripts/vertical-empty.json) | 84 | Pass | Pass |
| [wide-upper-member](fixtures/tank-scripts/wide-upper-member.json) | 65 | Pass | Pass |
| [width-three](fixtures/tank-scripts/width-three.json) | 127 | Pass | Pass |
| [window-lifecycle](fixtures/tank-scripts/window-lifecycle.json) | 30 | Integration only | Pass |
| [windows-boiler](fixtures/tank-scripts/windows-boiler.json) | 8 | Integration only | Pass |
| [windows](fixtures/tank-scripts/windows.json) | 84 | Integration only | Pass |

## APP-1987 tank fluid rendering and client replication (November 20, 2026)

The bounded renderer and synchronization gate passed on integrated build
`native-9f42064-5079f533f884`. The loaded client includes the staged tank visual
module, block-entity dispatch and update-tag changes; the Create pack SHA256 is
`6e2347ac8d0a2d31c5091917565a988ad6ab138fab91c670e1eb0a7916101137`.

The diagnostic separated fixture setup from a gameplay synchronization defect.
Server `/data get` showed the intended `TankContent` after direct NBT writes,
while render-hook input on the client held `TankContent: {}`. Real bucket fills
also remained invisible: tank writes mutated saved NBT without sending a block
entity update, and the tank update-tag hook omitted its fluid and controller
data. Tank writes now mark the controller block entity updated, and the update
tag includes its NBT. This covers both fluid changes and chunk delivery on load.

The [offscreen render fixture](tools/test-tank-render.py) uses real bucket
interactions and checks authoritative host values plus client-submitted fluid
geometry for a 1x1 ordinary tank (3,000/8,000 after a drain), a full 1x1
creative lava tank (8,000/8,000), and a half-full joined 2x2 tank
(16,000/32,000). It observes the ordinary tank at 4,000 and 3,000 mB on the
live host, then verifies the persisted final levels after a cold reopen and on
a joining LAN guest. Host and guest screenshots show visible water and lava in
their tank windows. These representative cases establish functional geometry
and replication, not pixel-exact Java rendering or interpolation parity.

The new renderer fixture and the affected tank, bucket, pump, fluid-pipe,
encased-pipe guest and lifecycle checks passed (38/38 checks across the grouped
run and the separately rerun cached core gate). The grouped run initially
could not compile its offline core runner because the isolated Cargo cache was
missing locked `serde_json`; after fetching the locked crate, `tank-script-core`
passed. Formatting and whitespace checks also passed.

## Closed gaps and regressions

- Tall-column and wider-group removal share the production split algorithm. The reproduced middle-column bug retained 24,000 mB in an 8,000 mB survivor; Java's 8,000 mB behavior now matches.
- Fluid-component identity, simulation, compatible/rejected transfers and creative configuration/drain semantics match Java. Creative stack amount remains distinct from capacity and effective fill level, including Java's retained oversized split stack.
- Copy/move preserves separate saved controller identity, cached capability and inventory capacity. Immediate, first-tick, next-tick and retained-capacity fill/drain observations match. Comparator output uses that same actual controller/capacity semantics.
- Window shapes match immediate formation, member updates, wrench toggling and immediate split/reset for widths 1/2/3. Wrench state survives a cold reopen. Active boiler windows reject toggling, and the boiler's separate 10,000 mB water-only sink capability matches Java.
- Actual player container interactions preserve potion components and Java held/returned inventory behavior. Tea extraction, milk buckets, honey/chocolate buckets and their survival creative-tank prediction defects are corrected. Water, splash and lingering variants are covered.
- Source emission and comparator output match Java, including creative effective fill and immediate/first-tick transitions. Physical Horizon neighbor light changes 0→11, survives a cold reopen at 11 with source emission 12, then returns to 0 on drain. Existing and late-joining offscreen guests observe the light updates. Survival guests also match the captured honey/chocolate tank contents, held buckets and returned items.
- The original steam-engine fixture matches all 13 Java ticks on the integrated build. The temporary six-tick regression was fixed by placing moved-tank reconnection at its source-equivalent phase; goldens and sample offsets were not changed.

Additional physical guards pass: imported Java `Controller` and `LastKnownPos` compounds through restart, asserted controller-only chunk unload, full unload and reload; solo and LAN bucket interactions; and chest/barrel/hopper inventory copy/move after the engine clone-ordering correction. These lifecycle guards establish Horizon behavior; actual Java unload timing remains a separate gap.

Muted real-player sound tests compare 24 successful/rejected water/lava/potion/bottle interactions plus a survival silence control with Java event IDs/counts. Category BLOCKS, volume 0.5 and amount-dependent randomized pitch follow Java source; those additional audio fields are not claimed as independently verified by event counters.

## Remaining full-parity work

| Surface | Status |
| --- | --- |
| Tank fluid interpolation, gauges, occlusion and exact client presentation | Open; representative visible-fluid geometry and host/guest replication now pass, but exact Java rendering and interpolation remain unverified |
| Java client light propagation and particle feedback | Open; Java's headless server reports propagated light 0 even after 40 ticks despite source emission 12, and particles are client-side |
| Audio category/volume and seeded pitch verification | Source implementation present; independent runtime comparison open |
| Actual Java partial chunk unload/reload timing | Horizon regression passes; paired Java trace open |
| Mounted/contraption tank storage, goggles/tooltips, remaining transform/collision consumers | Separate source-derived acceptance checks still required |
| Nondefault tank capacity/height configuration and external container compatibility | Current fixtures establish pinned default configuration and original built-in items |

The feature family's Full 1:1 status remains **Open**. Normal Create Parity Lab was not rolled forward. The complete verified client, resources, pack, source, fixture runners and receipts are independently preserved at `.local/baselines/2026-11-18-fluid-tanks-92ef2557669b/`; the copied build itself passed a fresh headless creative-signal Java comparison. Its `manifest.json` records file hashes and sizes. The pre-experiment runnable baseline remains independently preserved under `.local/baselines/2026-11-18-pre-architecture-6f6533d3f402/`.

## Fast workflow

Add scenarios as data, capture original Java in a fresh world, compare the shared production core where applicable, then validate the actual world adapter. Each capture archives its exact runner under `fixtures/tank-scripts/java/runners/`, avoiding forced recaptures of unchanged scripts when optional observers are added. The native suite supports `--jobs 2` and reports every failed case rather than stopping at the first one. See [the architecture audit](ARCHITECTURE-AUDIT.md) and [runner instructions](fixtures/tank-scripts/README.md).
