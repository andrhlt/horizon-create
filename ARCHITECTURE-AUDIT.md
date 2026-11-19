# Create architecture audit and tank experiment

Decision: continue this repository, reuse Java algorithms in modules that can be
executed without Minecraft, and describe new fixtures as data. Keep the current
Horizon pin for this experiment. A current-SDK migration needs a separate live
compatibility proof before changing the rest of the port.

This is a bounded proof of a faster development loop. It does not close full
fluid-tank parity or the remaining 40 partial feature families.

## Preserved baseline

The verified pre-experiment client `native-9f42064-6f6533d3f402`, complete runtime
resources, content pack, source, tests, fixtures and documentation are preserved
under `.local/baselines/2026-11-18-pre-architecture-6f6533d3f402/`. The snapshot
is outside launcher pruning and uses independent copy-on-write files. Its
`manifest.json` records 35,320 file hashes and sizes. The copied client actually
ran and passed the four baseline headless fixtures.

The preserved pack SHA256 is
`036218cf690405199aa24e67e63433bc138cfd3272742d435f7ec602992ccc85`.
The baseline Java revision remains
`ac0c444d9828da3453ae8cc65338e8de063286fb` (Create 6.0.10, NeoForge 21.1.219,
Minecraft 1.21.1). Horizon remains `9f42064` on Minecraft 26.3. The normal Create
Parity Lab installation was not changed.

## What the audit found

The pre-experiment source inventory contains 566 Rust files / 76,543 lines,
707 Python files / 85,756 lines, and 667 Java capture patches / 65,758 lines
including patch context. These are text-line counts, not measures of correctness
or a completion percentage.

| Area | Evidence | Consequence |
| --- | --- | --- |
| Pre-experiment runtime integration | 195 inserted modules and 372 manifest injections: 300 direct Rust targets, 72 versioned named hooks; 48 cancellable entries | Direct engine signatures and state are part of the port's interface. A broad SDK upgrade is a migration, not a build flag. |
| Engine changes | 133 Horizon patches, 3,466 added and 387 removed source lines; one additional Java patch is also stored in patches/ | Some behavior depends on added engine hooks, including post-command tank updates. Preserve these semantics during migration. |
| Tank algorithms | Controller formation, queue tie order, splitting and transfer order follow Java ConnectivityHandler | Preserve and test the implementation directly instead of reconstructing it from individual fixture outcomes. |
| Tank world adapter | NBT, legacy ownership reconstruction, real block-entity ticker order, placement/removal and persistence remain engine-dependent | Pure algorithm tests need complementary real-world checks. |
| Fixture workflow | Many scenarios have separate Java patches and Python drivers | A shared script runner can add cases without adding new capture code. |
| Assets and recipes | Existing preparation imports upstream assets/data | Keep the importer; this experiment addresses logic and test iteration. |

At the initial six-case checkpoint, the experiment added one core module and
one opt-in control injection, bringing that checkpoint manifest to 196 modules / 373 injections (301 direct targets and
72 named hooks). These additions are included in the experiment cost.

### SDK finding

The [current Horizon guide](https://playhorizon.dev/docs/make-a-mod) describes
native mods compiled against a prebuilt game. Its modding book documents
[Parts](https://github.com/horizon-rust/horizon/blob/main/docs/modding/src/concepts/parts.md),
[capability providers](https://github.com/horizon-rust/horizon/blob/main/docs/modding/src/concepts/capabilities.md)
and a [native route](https://github.com/horizon-rust/horizon/blob/main/docs/modding/src/concepts/native-route.md).

The cached `9f42064` toolchain uses the older game-linked mixin route. No current
`.horizon/sdk`, SDK metadata or `cargo-horizon-mod` executable was found in the
Create workspace or available launcher cache. Current documentation therefore
cannot establish an offline SDK compile against this installed build.

A future isolated SDK proof must exercise a real tank's storage, both placement
and command mutations, pre-removal contents, ticker ordering, saving/reopening,
and synchronization. Documented fluid providers alone do not establish those
ordering guarantees. Install an exact matching SDK/runtime and measure it before
committing to a migration; no SDK performance improvement is claimed here.

## Implemented tank seam

[The shared core](native/tank_connectivity.rs) contains the existing formation,
priority queue and wider split-distribution implementation. Both
[tank reconnection](native/tank_reconnect.rs) and the wider removal path in
[the world adapter](native/fluid_tank.rs) call it. The old duplicate algorithm was
removed from the adapter. No intentional gameplay change was made.

The concrete seam is `Part<F>` plus `reconnect` and `split_removed`. A small fluid
interface preserves amount changes and variant equality. The game adapter uses
the existing fluid type with NBT components; the fixture adapter uses registry identities and component values. These are two real adapters, not separate copies of the algorithm.

The interface still exposes controller identity, dimensions, dirty/touched flags
and an ordering requirement. This extraction improves locality and testability;
it is not yet a complete game-independent implementation of tank lifecycle.

[Action scripts](fixtures/tank-scripts) contain ordered placement, removal, capability transfer,
configuration, ticking and probe operations (plus real-world clone/move integration). One [Java patch](tools/java-tank-script.patch) and
[capture tool](tools/capture-tank-script-java.py) run original Create. The same
scripts run through the [core and Horizon adapters](tools/run-tank-script.py).
The Horizon observer reads actual production storage; its opt-in fill command
sets up storage, not a player bucket interaction. Existing physical guards remain.

Every record is compared exactly, including logical tick, controller position,
capacity, fluid, amount and fill acceptance. Script and Java-patch hashes prevent
silently using stale captures. Same-tick Java actions execute in a single ordered
callback; separate callbacks were observed to reorder placements.

Six cases passed both adapters against Java: both vertical bridge orders, flat
controller/member removal, an empty mixed-fluid anchor, and forward/reverse
high-fill removal. That is 416 probe observations and 16 fill results per adapter.
The last two scenarios were added as JSON data without changing the Java runner
or adding scenario-specific Python/Rust code. Their 128 legacy observations also
matched the prior Java references.

The core negative control changed its actual production split constant from
8,000 to 8,001. The Java comparison failed on the changed survivor amount. The
source was restored in a finally block, rebuilt, and all six core checks passed.
A separate mock implementation would not provide this link to production code.

## Measured development loop

Measurements are local, single-machine samples. The repeated core benchmark
reuses six scenarios; it is not 6,000 distinct fixtures or new coverage.

| Measurement | Time |
| --- | ---: |
| Four original headless fixtures on preserved build | 29.90 s |
| Same four shared-script Horizon fixtures | 31.67 s |
| All six shared-script Horizon fixtures | 46.32 s |
| Complete six-scenario core check command, warm median of three runs | 0.45 s |
| Six core scenarios, each repeated 1,000 times | 0.30 s inside the process |
| Isolated core build with cached dependencies | 2.38 s |
| Incremental core mutation / restoration builds | 0.42 / 0.39 s |
| Game-linked native build for this refactor | 110.61 s |

The measured benefit is checking changes to the shared algorithm without
rebuilding or launching Minecraft for each iteration. End-to-end checks still
cost roughly the same and remain necessary. No overall mod-delivery speedup or
completion date is inferred from these samples.

Raw timings, mutation failure, native build output and all adapter outputs live
under `.local/tank-architecture-proof/`. The experiment's native build is
`native-9f42064-7e4344e38662`. The content pack is unchanged from the baseline.

The focused regression batch passed 15/15 checks, including the shared runner,
wide storage, high-fill 3×3, pair split, mixed columns, same-fluid merge, flat
player mining and empty-anchor physical ports. This was a tank-focused batch,
not a run of the full Create suite. A separate actual-player check also passed
when reopening and extending both fluid orders from a pre-ownership a8f build.

## Coverage limits and next work

The fast adapter supplies creation-order ticks in an always-loaded fixture.
Horizon instead supplies live block-entity tickers, ticking-area eligibility,
sleep state and border checks. Legacy/imported world reconstruction, chunk
lifecycle, unusual re-placement order, NBT fluid components, bucket inventories,
side-dependent access, rendering and networking require real integration tests.
Width-one removal is explicitly unsupported by the fast adapter; the original
runtime pair path remains outside the extracted wider split function.

Five existing default storage comparisons now use the shared runner. The
original scripts remain for baseline comparison and physical variants; new tank
scenarios should use the shared script format. This is an incremental migration,
not a wholesale test rewrite.

Next, use this loop against the remaining explicit tank behavior checklist
without declaring the entire family complete. Then validate the pattern on one
other deterministic subsystem with repeated failures, such as kinetic network
calculations or train graph routing. Extract
the production algorithm, use original Java as the oracle, measure the loop and
retain a small set of real-world tests for the adapter. Keep physics, rendering
and persistence checks at their actual engine interface. Expand only after that
second subsystem confirms the benefit.
