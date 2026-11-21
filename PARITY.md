# Create parity

The reference is Create 6.0.10 for NeoForge on Minecraft 1.21.1,
commit `ac0c444d9828da3453ae8cc65338e8de063286fb`. The 64 upstream
GameTests are the existing simulation baseline. A family is complete when
its player-visible behaviors have Java references and repeatable Horizon
checks for the applicable simulation, rendering, interaction, multiplayer
and world-reload paths.
The [feature matrix](FEATURE-MATRIX.md) tracks availability and verification by family.

## November 18 parallel replay

The original parallel run finished 1,022 named checks on
`native-9f42064-7f3945f841a4` with 1,003 passed and 19 failed. The build,
pack and check names were fixed. Fixture files in the working tree were
still being developed during the run. The original outputs, SHA-256
inputs, preserved original pack and rerun evidence are in
`.local/parity-full-7f3945f841a4-overnight/`.

All 19 original failures subsequently passed on
`native-9f42064-4cc56f444117` with a frozen working-fixture snapshot and
the original creative-tab pack. The repeat ran in two parallel workers.
It preserved the original results and stored its own selected cases,
build and pack hashes, and per-check logs in the overnight dossier
under `original-19-failures-4cc/`.

A separate 1,103-check run finished with 1,089 passes and 14 failures
on `native-9f42064-d542a1892c07` and the projectile pack. Its four
workers each had a snapshot of the test code, fixtures and their
diagnostic directory. Inputs and raw outcomes are preserved in
`.local/parity-full-d542a1892c07-frozen/`. The water failure uses
the earlier reference from before the correction below.
The verified Create Parity Lab uses its separately recorded build.

A later frozen follow-up on `native-9f42064-2daa71b5b44b` and the
creative-tab pack finished with 105 of 108 passes. Both live package
placement checks hit extra throws. The enchanted golden apple LAN
client reported an early inventory sample. Subsequent direct package
collisions and the corrected live blocked-tap replay passed under the
separately recorded conditions below.
Later owner and guest authority cannon probes observed the correct
100-tick interval. The original outcomes remain in
`.local/parity-delta-2daa71b5b44b-frozen/`.

The next frozen delta on `native-9f42064-06ad48ac67bb` and the
creative-tab pack passed all 64 cases in two isolated workers. It
covered 60 additional checks and four earlier train setup replays.
The separate replay of the 14 d542 failures passed 13 with current
fixtures on the same candidate. The remaining live LAN package
repeat charged long enough to throw. Raw evidence is in
`.local/parity-delta-06ad48ac67bb-frozen/` and the overnight dossier.

A fourth frozen delta on `native-9f42064-f2fcebd19cb9` and the
creative-tab pack passed all 49 checks in two isolated workers. It
covered curved pairs, folding panels, cold-start states and the single
LAN package packet cases. Raw results are in
`.local/parity-delta-f2fcebd19cb9-frozen/`.

A frozen replay of the original 14 d542 failures then passed all 14 on
`native-9f42064-3ec911595d40` and the creative-tab pack using the
corrected fixtures. Both live package matrices passed all 36 cases.
Those releases lasted zero to two authority ticks. The separately
induced charged cases remain recorded below. Inputs, traces and raw
results are in the overnight dossier under `d542-failures-3ec/`.

A frozen integration delta passed all 31 checks on
`native-9f42064-fe2a9995b89b` and the exact-shape pack. It
included all 20 previous mounted and platform door checks, all eight
curved door animations, wheat milling, the loaded stressometer and
multiplayer elevator. Inputs and outputs are in
`.local/parity-delta-fe2a9995b89b-frozen/`. A separate frozen
priority delta on `native-9f42064-fe00c2f5ddec` passed all 28
selected cannon, minecart, and freestanding authority/outline checks
with the exact-shape pack. It is archived under
`fe00-priority-regression/` in the overnight dossier.

Curved and branched signal occupancy lost the driver during their shared
manual-control fixture. Live player movement continued between the
fixture's repositioning calls despite the frozen world clock. The
[updated replay](tools/test-curved-train.py) positions the driver before
each driven step. On the frozen build and pack, both occupancy checks,
ordinary curved travel and right steering matched all 160 Java speed
and wheel samples in each replay. Four curved and six branched signal
lamp states also matched.

The [pinned water-bottle authority probe](tools/java-water-filling-bottle-authority.patch)
confirmed the potion reaches the smart chute at tick 52 and the barrel
at tick 57. The prior reference had both events two ticks later.
After correcting [rows 52–58](fixtures/water_filling_bottle-java.csv), the
[factory replay](tools/test-water-filling-bottle.py) matched all 60 ticks
on the original 7f build with the archived original pack and on d542
with the new pack. The pinned Java probe also passed the upstream
barrel assertion. The original run’s failure remains in its raw log.

## APP-1990 Spout source audit

The pinned source checkout at `ac0c444d9828da3453ae8cc65338e8de063286fb`
was reviewed read-only. `SpoutBlockEntity.onItemReceived` and
`whenItemHeld` define the empty-tank, incompatible-input, and fluid-shortage
decisions; the held-item callback starts a 20-tick cycle and fills at remaining
tick 5. `SpoutBlockEntity.tick` advances that timer independently of kinetic
speed, while belt `whenItemHeld`/held-item processing is what delivers the
completed bottle after movement resumes. The Horizon paths in
`native/spout.rs`, `native/belt.rs`, `native/depot.rs`, and `native/ejector.rs`
were checked against those rules.
No runtime logic change was needed: Spout timing and belt-held item processing
are separate callbacks, and the belt pauses its held item at zero speed.

The existing bottle, potion-crafting, nine-lane spouting, and Blaze Cake
fixtures passed on isolated build `native-9f42064-6a3da367a9bb`; potion crafting,
nine-lane spouting, and Blaze Cake are the full archived replay checks, while
the bottle check passed its factory assertion. New isolated harnesses are
registered as `spout-lan-feed-collect`, `spout-output-backpressure`,
`spout-input-timing-boundaries`, and `spout-reopen` in `tools/test-parity.py`.
The boundary case checks a 249 mB shortage against a 250 mB water-bottle
requirement and passes cobblestone through. It then removes belt RPM after a
valid bottle is held: the independent Spout timer reaches -1 while the bottle
stays centered and 250 mB remains; restoring RPM invokes the held-item callback
and produces exactly one output while consuming 250 mB. The test follows that
output to the Depot, confirms the route is clear, the timer is idle, and there
is no duplicate. These are source-aligned checks, not Java tick traces. LAN
feed/collection, output backpressure, and idle/partway save/reopen cover the
remaining ticket gates.

On the merged tree, all 12 APP-1990 and affected belt checks passed against
gameplay build `native-9f42064-6a3da367a9bb`, with pack SHA-256
`8921cd3502ce28d0bf6662e9d46eb33e81ca3cb9d914a6abd9c2aa4ee9047d1c`:
`water-filling-bottle`, `spout-crafting`, `spouting`, `heated-fluid-food`,
`spout-lan-feed-collect`, `spout-output-backpressure`,
`spout-input-timing-boundaries`, `spout-reopen`, `horizontal-belt`,
`belt-output-backpressure`, `belt-reopen`, and
`horizontal-belt-lan-guest-placement`. The changed Spout, belt, Depot, and
ejector runtime sources match the verified build; the follow-up changes only
correct harness setup and assert delivery through the Depot.

Run the new cases together with the existing Java replays using:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 \
  --check water-filling-bottle --check spout-crafting --check spouting --check heated-fluid-food \
  --check spout-lan-feed-collect --check spout-output-backpressure \
  --check spout-input-timing-boundaries --check spout-reopen
```

The zero-RPM timing gate intentionally distinguishes the Spout machine tick
from belt-held-item processing: timer completion alone does not fill the bottle
until belt movement resumes.

## APP-1991 Potion fluids and heated brewing

The finite acceptance set is: (1) the original water → Healing potion recipe
with Nether Wart and Glistering Melon Slice, including basin tank identity and
amounts, mixer state, filtered pipe, Spout timer and final bottle; (2) a
no-heat rejection control; (3) potion fill/empty and container remainder; (4)
guest insertion/result convergence; and (5) idle and active save/reopen of the
basin and Spout path. The original replay at
[`tools/test-potion-brewing.py`](tools/test-potion-brewing.py) compares all 394
Java observations in [`fixtures/potion_brewing-java.csv`](fixtures/potion_brewing-java.csv),
including both basin tank pairs and the Spout tank, through delivery of Healing
potion to the chest. Its reference is the pinned Create 6.0.10 GameTest and
`tools/java-potion-brewing-trace.patch`.

The pinned source audit covered `PotionMixingRecipes.createRecipe` and
`PotionFluidHandler`: vanilla potion recipes preserve bottle type and potion
contents, consume 1,000 mB, and require heat; emptying an ordinary water potion
uses water while other potion contents retain the `create:potion` identity;
filling consumes the matching amount and returns the appropriate container.
The existing [Basin lifecycle](tools/test-basin-lifecycle.py) covers real guest
insertion/collection and active/idle reopen. APP-1990's [Spout baseline](tools/test-spout-gameplay.py)
covers guest feed/collection and idle/partway reopen. These neighboring gates
apply to the same authoritative basin inventory and Spout transfer paths; they
do not claim packet-timing parity for a guest-triggered potion brew.

The replay was rerun from the isolated ticket worktree on client build
`native-9f42064-6bdf8691aa42` with pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`; all 394
Java rows matched exactly. Horizon output is in the worktree's
`.local/potion_brewing-horizon.csv`, and the runner log is
`.local/horizon-potion-brewing.log`. The no-heat rule is source-aligned in both
Java (`PotionMixingRecipes.createRecipe` requires `HEATED`) and Horizon
(`native/mixer.rs::recipe` blocks heat-required recipes and `brew` requires
heat). The new `potion-brewing-no-heat` control clears every burner in the
isolated fixture, runs 120 ticks, and confirms the mixer stays idle while all
five fluid amounts, both ingredients, and the empty output remain conserved.
The neighboring Basin lifecycle and Spout checks provide the potion-path
guest insertion/result convergence and idle/active reopen gates: on the same
build, `basin-lifecycle`, `spout-lan-feed-collect`, and `spout-reopen` all pass.
These checks establish guest convergence and persistence, not Java packet
arrival timing. Remaining potion variants, splash/lingering handling and
exhaustive fluid component combinations stay follow-ups.

Reproduce the Java trace comparison with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 \
  --check potion-brewing --check potion-brewing-no-heat \
  --check basin-lifecycle --check spout-lan-feed-collect --check spout-reopen
```

## Freestanding paired doors

The [pinned GameTest](tools/java-world-paired-doors.patch) recorded 24
samples each for andesite and copper pairs. A lower-left click opens
all four halves and clears visibility on tick 3. The second click
closes all four halves on tick 13. Both leaves restore visibility
after block entities tick on tick 20. The original before-block-entity
probe first observed that state on tick 21. The [offscreen replay](tools/test-world-paired-doors.py)
reproduced the missing pair interaction and visibility change on both
materials on `native-9f42064-f49095b31d17`. On
`native-9f42064-3ce180589241`, all 48 post-tick state samples and six
[sound cues](fixtures/world-paired-doors-sound-java.csv) matched in solo
and LAN. A single opening cue came from the mate on tick 3. Both lower
halves played one closing cue on tick 20. Volume, position, source,
opening pitch range and fixed closing pitch matched. The host and guest
both heard the LAN cues. Panel animation and broader placement, collision
and redstone paths remain open.
A separate 20-check mounted and platform regression run passed on the
same build and pack. On `native-9f42064-4cc56f444117` and the isolated
door-render pack, the actual offscreen render submissions matched
[68 Java previous/current animation samples](fixtures/world-paired-doors-progress-java.csv)
per viewer in solo and in LAN with both viewers. The fixture waits for
the frame after the click inside the same frozen tick. The render pack
passed 30 mounted and freestanding regression checks.
When the Java doors have begun closing, the open outline persists until
the closed model returns. The previous Horizon pack switched to the
closed outline immediately. The [Java ray capture](fixtures/world-paired-doors-outline-java.csv)
and the same offscreen replay with the exact-shape pack matched all 16
upper-panel rays in solo and LAN. The sampled depth was 0.4375 blocks
at the hinge while open or still closing, and 0.8125 after settling.
The exact-shape pack is now the working test pack. The earlier
creative-tab pack is archived in the overnight dossier alongside
the render-only pack. The verified Lab uses its separately recorded
build and pack.
The earlier candidate briefly drew a closed pose when a state update
arrived before its animation tag. On `native-9f42064-352d59d17c49`, the
client starts the same motion from its retained pose when the block
state arrives. The offscreen replay matched 136 submitted folding
panel transforms per viewer across the two materials in solo and LAN,
including both panel parts, actual interpolation fractions and nonempty
textured geometry. Other ray directions and pixel comparisons remain open.

The [Java redstone probe](tools/java-world-paired-door-power.patch)
powered one leaf at a time on freestanding brass and copper pairs.
Both leaves opened when the first source appeared, stayed open while
either source remained, and closed when the last source disappeared.
Removing the left support did not remove either leaf. On
`native-9f42064-27315d94ff35` and the exact-shape pack, the [replay](tools/test-world-paired-doors-power.py)
matched all 64 state samples and eight cues in solo and with a LAN
guest applying the power sources. Both clients heard the LAN cues.
The direct synchronous neighbor implementation on
`native-9f42064-352d59d17c49` repeated all 64 state samples and eight
cues in both modes with the same pack.

The [rapid post-tick action probe](tools/java-world-door-rapid-post.patch)
caught an early closing cue during a rapid reopen. Java considers the
motion settled only once its previous sample, current sample and target
agree. On `native-9f42064-fe2a9995b89b`, the
[rapid](tools/test-world-door-rapid-post.py) and
[mixed-power](tools/test-world-door-power-post.py) replays each matched
all 64 same-phase states and eight cues in solo and LAN. Rapid reopening
plays no closing cue at tick 9. The final rapid close settles at tick 26
and the mixed-power close at tick 29. The earlier pre-block-entity
action traces remain recorded under their candidate builds.

The [manual GameTest](tools/java-world-paired-doors.patch) captures
the server-authority phase with `CREATE_WORLD_DOOR_POST=1`. Its default
captures the pre-block-entity action for the renderer reference.
In the authority-aligned replay on `native-9f42064-fe2a9995b89b`,
andesite, copper, brass, train and framed-glass pairs matched all
120 Java state samples, 15 sound cues and 40 outline rays in solo
and LAN. They open at tick 3, close at tick 13 and settle at tick 21.
The sampled outline stays displaced through the closing interval.

On `native-9f42064-272b79adfbbc`, the [offscreen render replay](tools/test-world-paired-doors.py)
matched all 340 synchronized panel samples per viewer across these
five materials, in solo and with both LAN viewers. It samples each
integer tick after the viewer has received the expected state and
animation values, then compares the submitted pane geometry at the
actual frame interpolation fraction. Earlier strict captures also
showed occasional frames with the prior pose while the next
snapshot arrived. The replay exposes those separately with
`--strict-frames`. The paired local prediction experiment did
not resolve them and was removed. Continuous transition frames
remain open.

The [fresh Java block-entity capture](fixtures/world-door-fresh-animation-java.csv)
starts fully open when the saved door state is open. In the previous
candidate, a world saved during opening could briefly resume its
old interpolation after a cold reopen. On
`native-9f42064-d75472298edb`, the [real save-and-reopen replay](tools/test-world-door-cold-open.py)
matched the fully open first rendered pose for brass and copper pairs
in solo and LAN, including a guest rejoining. The fixture reads the
first samples before the previous motion could have finished. A
cold reopen while closing remains outside this comparison.

The first final-candidate smoke ran nine of ten cases green. Its LAN
folding replay sampled one of the host’s four halves before the client
finished receiving the closing model at tick 21. Both authority
closing cues were already recorded at that tick. The fixture now
checks all four states on the authority and waits for both viewers
within the same frozen tick. The affected replay then passed on the
same executable and pack. Both logs remain under `d754-smoke/`.
A second frozen smoke caught the same viewer-side timing in solo. Its
authority also recorded both closures on tick 21. The identical
fixed-tick observation now applies in either mode. Both isolated
replays passed all their synchronized panel, state and cue samples.

## APP-2057 Sliding Doors gameplay baseline

The bounded acceptance matrix reuses the Java comparisons above for manual
open/close, paired leaves, material coverage, redstone source handoff, sound,
and solo/LAN interaction. The elevator walkthrough also verifies that the
physical doors block the players while closed and allow both host and guest to
cross after opening. Mounted train-platform scheduling and controls remain in
their Train Doors issue and are not counted as new APP-2057 coverage.

The new [survival placement check](tools/test-sliding-door-placement.py)
performs real player clicks in Survival for Andesite folding doors facing
north/east and Brass sliding doors facing south/west. All four placements
created the expected Java lower/upper block states, consumed one item, and
matched at the same frozen tick. Its reopen extension retained both halves of
an open Andesite pair and a closed Brass pair. The existing cold-open replay
also saved Brass and Copper pairs during active opening, then matched Java's
fully open first pose after host reopen and guest rejoin. This is Horizon
save/reopen evidence, not a Java reload-parity claim.

The placement and static-reopen cases passed with the pinned Horizon Nightly
9f42064 client build `native-9f42064-d6dc2ad18d3f` and prepared Minecraft 26.3
resources. The client SHA-256 was
`006bfe15a198b29d6af7633d353dcadaa07039121ae66c2081927299835a8811`, the
control client SHA-256 was
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`, and the
Create pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The comparison reference is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`.

Run the new cases with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client \
  /path/to/prepared/26.3 --check sliding-door-placement
```

The gameplay baseline is bounded to the four placement cases plus the existing
five-material manual state/cue checks, representative two-material redstone
handoff, paired host/guest interaction, closed-door obstruction and open-door
passage, and idle/active save/reopen. Other placement/property cross-products,
moving assemblies outside the existing Train Doors evidence, frame-level
network arrival, and cosmetic equivalence remain open follow-ups. Full 1:1
parity remains Open.

## Creative search gear attribution

Pinned Java registers Gearbox, Gearshift and Sequenced Gearshift in
the Create namespace. An offscreen `gea` search on
`native-9f42064-846e2873d256` with the prepared projectile pack
returned all three, plus the Adjustable Chain Gearshift and Vertical
Gearbox. The three captured tooltips showed the blue Create tab label
and textured icons. Screenshots and widget IDs are archived in
`.local/parity-full-7f3945f841a4-overnight/creative-gears/`.

The [pinned Java tab inventory](tools/java-creative-tabs-inventory.patch)
captured [203 Base and 377 Palettes display entries](fixtures/creative-tabs-java.csv).
The prepared pack uses those display memberships and the Java Palettes
order. The [offscreen replay](tools/test-create-creative-tabs.py) checked
both memberships, Palettes order, and both first live pages on
`native-9f42064-89e551a852ca`. The 16-color seat search also passed.
Base keeps the port’s existing relative order pending a Java client
capture of its 3D-first sort. The APP-2095 replay below compares
representative search-only entries and attribution.

## Inventory

Apply `tools/java-parity-inventory.patch` in a disposable checkout of the
reference commit and run the GameTest server with Java 21.

```sh
./gradlew runGameTestServer > /path/to/java-registry.log 2>&1
```

From the Horizon port root, compare that run with the prepared pack.

```sh
python3 tools/parity-inventory.py /path/to/Create /path/to/java-registry.log \
  --horizon /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

The script writes `.local/parity-inventory/registries.csv`,
`resources.csv` and `summary.json`. The optional Horizon arguments probe
blocks, items and recipes inside an isolated world with the selected pack.
The Java recipe list reflects the mods loaded by the reference run.
The registry comparison uses exact IDs. Review entries that use another
native representation or ID before counting them as missing. A loaded
entry still needs the applicable gameplay checks. The resource report
compares files by path and bytes, including generated Java resources.

| Audited Horizon build | Matching block IDs | Matching item IDs | Matching recipe IDs |
| --- | ---: | ---: | ---: |
| `native-9f42064-352d59d17c49` | 642 / 642 | 699 / 699 | 1,526 / 1,529 |
| `native-9f42064-c218e039de3c` | 642 / 642 | 699 / 699 | 1,526 / 1,529 |
| `native-9f42064-0c674427b610` | 642 / 642 | 699 / 699 | 1,526 / 1,529 |
| `native-9f42064-a63b614bb300` | 642 / 642 | 699 / 699 | 1,526 / 1,529 |
| `native-9f42064-f88edc65213a` | 641 / 642 | 699 / 699 | 1,526 / 1,529 |
| `native-9f42064-24deca5c6180` | 640 / 642 | 697 / 699 | 1,523 / 1,529 |
| `native-9f42064-fac0f278b640` | 640 / 642 | 695 / 699 | 1,522 / 1,529 |
| `native-9f42064-18472b3bb96b` | 639 / 642 | 690 / 699 | 1,518 / 1,529 |
| `native-9f42064-5add64cfcfc1` | 638 / 642 | 689 / 699 | 1,517 / 1,529 |
| `native-9f42064-17fce985eb74` | 637 / 642 | 687 / 699 | 1,516 / 1,529 |
| `native-9f42064-0159058dd907` | 636 / 642 | 685 / 699 | 1,515 / 1,529 |
| `native-9f42064-673f99e57bfa` | 635 / 642 | 680 / 699 | 1,514 / 1,529 |
| `native-9f42064-008abfc9ea02` | 633 / 642 | 678 / 699 | 1,512 / 1,529 |
| `native-9f42064-a55af2b6a899` | 630 / 642 | 665 / 699 | 1,508 / 1,529 |
| `native-9f42064-b72bb1a821ed` | 625 / 642 | 660 / 699 | 1,501 / 1,529 |
| `native-9f42064-d21a99bf48d2` | 623 / 642 | 659 / 699 | 1,472 / 1,529 |
| `native-9f42064-7f0b3254fd60` | 622 / 642 | 653 / 699 | 1,445 / 1,529 |
| `native-9f42064-0e486313d59d` | 600 / 642 | 631 / 699 | 1,400 / 1,529 |
| `native-9f42064-18338e7d2169` | 600 / 642 | 631 / 699 | 1,228 / 1,529 |
| `native-9f42064-72c3825b41bc` | 598 / 642 | 627 / 699 | 1,225 / 1,529 |
| `native-9f42064-340be4107ec4` | 597 / 642 | 623 / 699 | 1,044 / 1,529 |
| `native-9f42064-70205eb8ade6` | 596 / 642 | 621 / 699 | 1,021 / 1,529 |
| `native-9f42064-83f9aa22ed27` | 594 / 642 | 619 / 699 | 1,019 / 1,529 |
| `native-9f42064-1dd8e27e9a29` | 576 / 642 | 601 / 699 | 1,015 / 1,529 |
| `native-9f42064-f25b37d50376` | 560 / 642 | 585 / 699 | 983 / 1,529 |
| `native-9f42064-ca95edd27742` | 538 / 642 | 578 / 699 | 973 / 1,529 |

The refreshed registry audit used `native-9f42064-352d59d17c49`
with the exact-shape development pack, SHA-256
`d939d324ab57110d6392e3a4b75d9b829809e92a6d3fb7e10ea6212f05332414`.
Raw reports are in the overnight dossier under `inventory-352-exact-shape-pack/`.
It verified all 642 original block IDs, all 699 item IDs and 1,526 of
1,529 recipe IDs. The three missing recipes require Farmer’s Delight.
The audit also confirmed the original texture and sound bytes and
the two converted models. The reports are archived in
`.local/parity-full-7f3945f841a4-overnight/inventory-c218-current-pack/`.
The development archive `create-full-java-media-locales.hmod` contains
all 1,307 original texture resources, 38 original sound files, and the
79-entry Java sound event table with identical bytes. It contains every original model file, with 2,760
identical and two Horizon model conversions (Copper Casing and the
flat Encased Fluid Pipe). The archive SHA-256 is
`e55a99d8f01c5ea3c321e3d43191e772761f34b46221794bff91c6409cfcd14f`.
The complete texture archive passed the original pointer visual and
19-tick Fluid Valve replay on host and guest. The full media archive
passed the 18-sample mounted train door animation and muted playback
replay in LAN on `native-9f42064-f4b621608334`. The full sound table
passed the LAN Frogport catch and deposit replay at Java ticks 24 and 37
on `native-9f42064-c601610833ba`. The current archive also preserves all
133,980 original values across 59 locale files. The two Minecart variants
now use their specific upstream names where supplied, and Horizon aliases
fill absent item keys. The original station UI and Minecart recipe replays
passed on `native-9f42064-1f2743f4b4c4` with this archive. The
[feature matrix](FEATURE-MATRIX.md) records remaining runtime behavior.

## Survival machine recipes

### Probabilistic mixer outputs

The pinned [Create 6.0.10 `ProcessingOutput`](https://github.com/Creators-of-Create/Create/blob/ac0c444d9828da3453ae8cc65338e8de063286fb/src/main/java/com/simibubi/create/content/processing/recipe/ProcessingOutput.java)
rolls once per output item when `chance < 1`, retaining that item when the
random float is at most the chance. Guaranteed outputs consume no random value.
Horizon's Mixer had treated every item output as guaranteed. It now preserves
the recipe's output order and resolves chance rolls when applying the recipe,
not during repeated recipe lookups. This keeps lookup and tick validation from
rerolling an output. Fluid outputs are unaffected.

The Rust helper test supplies three fixed rolls and checks the count and order
of interleaved guaranteed and probabilistic outputs. The [runtime replay](tools/test-mixer-chance.py)
loads a world datapack with one diamond input, 64 gold nugget rolls at 50% each
and two guaranteed items. It closes the host while the mixer is running with
at least 20 processing ticks left. On reopening, the same recipe still has its
diamond and a positive countdown. After 80 more stepped ticks, the diamond is
gone and the mixer is idle. The survival guest picks up the rolled stack from
the depot and checks its exact count against the host. After an idle reopen,
the depot still holds the iron nugget and the basin still holds the queued
copper ingot. This checks output order, custody and persistence.

The combined client `native-9f42064-12f8cd8053b7` produced 30 gold nuggets in
the first completed replay. The game uses the level RNG, so the count varies
between runs. The pinned 26.3 resources used `create.hmod` SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The client SHA-256 is
`0d8c15ef73ed7f31847b91f961a3ac9423887292b1275e8347aa7c54c270374c`.

The combined build and the earlier `native-9f42064-ffe4b00e329a` both passed
the following 11 neighboring checks:
`wheat-milling`, `milling-recipes`, `depot-pressing`, `pressing-category`,
`basin-dry-alloy`, `basin-wet-materials`, `heated-fluid-food`,
`water-filling-bottle`, `spouting`, `mixing-lookup` and `recipe-navigation`.
These cover accepted and rejected inputs, basin routing, fluid processing,
spouting and guest recipe/tag synchronization on reload. Run the same named
checks and `mixer-chance` with `tools/test-parity.py` on the combined build.
Exact RNG stream alignment with Java and guest packet timing remain unverified.

The [Java crafting probe](tools/java-machine-crafting-trace.patch) resolves
24 original recipe IDs through the game's recipe manager and records the
grid, result stack and crafting remainders. The
[Horizon survival replay](tools/test-machine-crafting.py) takes each result
at a crafting table and compares the final inventory with that
[Java trace](fixtures/machine-crafting-java.csv). It includes both pipe
orientations, the Zinc Alloy variant, the Speedometer conversion, moving
assembly and logistics parts, and the empty bucket returned after making
dough. The recipe ingredients still use their original tags. The fixtures
exercise the concrete input shown in each row.

The [reset probe](tools/java-crafting-reset-trace.patch) covers an original
Filter configured with a Diamond and a Train Schedule with saved data.
Each returns one default stack and clears the Create component, custom
name and custom data. The [Horizon replay](tools/test-crafting-reset.py)
checks the authoritative inventory before crafting and after taking the
result in survival.

## Vanilla recipe save and reopen

The `vanilla-recipe-reopen` check in [the parity runner](tools/test-parity.py)
saves two White Wool stacks in separate hotbar slots, reopens the same world and
confirms both persisted. It puts one wool in the player's 2×2 crafting grid
and verifies the incomplete recipe has no result, then adds the second wool
and crafts three White Carpet. This is a bounded gameplay persistence check
for one ordinary vanilla crafting recipe; it does not establish full catalog,
recipe-book unlock, stonecutting or cooking parity.

The surrounding recipe evidence remains sampled: `survival-crafting` covers
starter Create parts, `machine-crafting` compares 24 Java recipes including
remainders, `cooking-materials --cooking-only` compares 609 Java samples for
smelting bread, smoking bread and smelting Scoria, and
`test-extra-material-recipes.py` has a campfire Dough-to-Bread case.
`test-zinc-progression.py --heating` compares the
existing smelting and blasting recipes. `vanilla-stone-palettes-lan` passed
seven guest Stonecutter cases on retry; its first run transiently missed an
output before the successful retry. Full catalog equivalence remains open.

## Zinc mining and processing

The [original Java probe](tools/java-zinc-progression-trace.patch) records
12 mining outcomes using Stone, Iron, and Silk Touch pickaxes. The
[Horizon replay](tools/test-zinc-progression.py) mines each block in
survival and checks the dropped stack. The pinned blockstate, model,
and texture assets match the original bytes.

Zinc Ore, Deepslate Zinc Ore, Raw Zinc, and Crushed Raw Zinc finish at 200
in an ordinary furnace and 100 in a blast furnace. The importer accounts
for Horizon's built-in blast speed multiplier. The replay checks cook
progress and the first output tick for all eight inputs.
The [five original crafting traces](fixtures/zinc-crafting-java.csv)
exercise both directions of Raw Zinc and Zinc Ingot storage and the
Zinc Chain recipe.

The [Fortune check](tools/test-zinc-progression.py) runs twelve survival
mining outcomes with Fortune III: six Zinc Ore and six Deepslate Zinc Ore.
Each produced Raw Zinc within the pinned Java `ore_drops` bounds (1–4), and
seven trials yielded a bonus. This is a representative case, not an exhaustive
Fortune distribution. The [LAN persistence check](tools/test-multiplayer-zinc.py)
mined and picked up one Raw Zinc as a survival guest. On build
`native-9f42064-b2e225daec86`, the host and guest inventories agreed, and the
inventory remained after the host world was reopened and the guest rejoined.
The ore stayed mined. Furnace experience payout and grinding output remain
follow-ups.

The focused regression batch passed on build
`native-9f42064-b2e225daec86` with pack SHA-256
`6ac5f2d01e229ca8df2104fbe0ec105c7c5310da21f32d3db3b251f4fe81a4b4`:
`python3 tools/test-parity.py BUILD/horizon-ctl BUILD/horizon-client BUILD/.local/horizon-client/26.3 --jobs 2 --check zinc-mining --check zinc-fortune --check zinc-mining-lan --check zinc-heating --check zinc-crafting --check crushed-materials-heating`.
All six checks passed: 12 Java-referenced mining cases; 12 Fortune III trials;
one LAN mine/pickup, host world reopen, and guest rejoin; eight Zinc cooking
cases; five storage/chain recipes; and six crushed-material cooking cases.

The [natural generation probe](tools/capture-java-zinc-worldgen.py)
records ore coordinates across four chunks at seed 810102. Java with
Create world generation disabled and the installed Horizon pack have
the same 100 Gold positions. Java with Create enabled has 262 Zinc
positions and 82 Gold positions in those chunks. The natural generation
prototype remains in a disposable pack for the seeded world comparison.

The [Striated Ore replay](tools/test-striated-ore.py) runs the Rust feature
through Horizon's worldgen decoder and placement interface at the absolute
origins captured by the Java GameTest. Two Overworld cases and one Nether
case matched all 21,305 position and material changes. The fixture uses
controlled stone, deepslate and netherrack volumes. A separate native
build matched all 344 Zinc and Gold positions in the four-chunk seeded
world, including original Striated Ore scheduling and the 1.21 Tuff rule.
The [matched force-load replay](tools/test-zinc-worldgen.py) waits for the
same chunk rectangle in both games before sampling. At seed 810102, all
4,157 Overworld and 4,787 Nether positions matched and survived saving
and reopening. The Nether sample includes ten Create Scoria positions
and the [disabled reference](fixtures/layered-nether-36-forced-disabled-java.csv)
matched all 4,777 vanilla ore positions. Natural generation in this
tested configuration is now enabled in Create Parity Lab.

The earlier scans requested or sampled chunks at different points in
generation. Those runs included one Zinc variant discrepancy and a
vanilla Quartz vein difference. Original Java also changed two Veridium
positions when the surrounding chunks were generated before a sequential
scan. Further seeds and load sequences remain open. Build with `prepare.py
--disable-worldgen` to omit the ore features. The original runtime setting
still needs a Horizon equivalent.

### APP-2060 bounded gameplay baseline

On Horizon build `native-9f42064-6bdf8691aa42` with pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`, the
bounded acceptance cases passed against Java Create
`ac0c444d9828da3453ae8cc65338e8de063286fb`:

- Seed `810102`, 4×4 Overworld chunks, forced before view and fully generated:
  all 4,157 positions/materials matched the Java reference and remained the
  same after save/reopen. This includes 2,676 Striated blocks across Asurine
  (2,391) and Veridium (285), alongside Zinc and vanilla Gold.
- Seed `810102`, 6×6 Nether chunks with a two-chunk halo:
  all 4,787 positions/materials matched and remained the same after
  save/reopen, including ten Scoria blocks. The disabled Java reference
  contains the same 4,777 vanilla ore positions.
- Disabled Create worldgen pack, seed `810102`, 4×4 Overworld chunks:
  all 422 vanilla Gold positions matched Java and remained unchanged after
  save/reopen. The pack omitted the nine Create worldgen/biome-modifier data
  entries, matching the supported `prepare.py --disable-worldgen` mode.
- A LAN guest mined each of the seven Java-defined Striated stone blocks with
  an iron pickaxe. Every drop matched its Java block loot table (one matching
  block item); host and guest agreed on the mined state, and all seven guest
  drops and mined positions persisted after host reopen and guest rejoin.

The LAN check is registered as `striated-ore-mining-lan` in
`tools/test-parity.py` and uses the portable Java loot reference
`fixtures/striated-ore-drops-java.csv`. The headless worldgen replays used
`tools/test-zinc-worldgen.py` with `--force-before-view --reopen`; Overworld
and Nether used `fixtures/zinc-worldgen-16-enabled-java.csv` and
`fixtures/layered-nether-36-forced-java.csv`, respectively. The disabled
worldgen run used `fixtures/zinc-worldgen-16-disabled-java.csv`.

The nine-entry omission is a pack-build control. Horizon still has no
in-game/runtime equivalent for Java's `create-common.toml` setting
`worldgen.disableWorldGen`; that config UI/runtime behavior and further seed
and load-order sweeps remain open follow-ups. Exact runtime-setting parity is
not claimed here.

## Metal bars

The [original Java probe](tools/java-metal-bars-trace.patch) captures
Andesite, Brass, and Copper Bars' Stonecutter recipes and 24 connection
states. Each ingredient yields four bars. The [Horizon replay](tools/test-metal-bars.py)
places the bars in survival, compares their connections to stone, iron
bars, glass panes and oak fences, then waterlogs them. The host and a live
LAN guest matched all 24 states. The same focused replay now also checks an
unsupported oak-leaf neighbor, survival placement and pickup after mining,
and the three variants' saved connection/waterlogged states after reopen.
The block declarations all inherit `minecraft:iron_bars`, which supplies the
vanilla collision shape and neighbor behavior. The models and textures use
the original Create assets. Neighbor arrangements beyond the recorded
equivalence classes and pixel-level rendering remain open.

The bounded APP-2066 replay passed both registered checks, solo and LAN, on
`native-9f42064-d6dc2ad18d3f` with pack SHA-256
`4b974e9e8a5ebe8ff97975148ee5670dd10a500c0ca03d6af59f946457a5f584`.
The Java capture at Create
`ac0c444d9828da3453ae8cc65338e8de063286fb` contributes three Stonecutter
recipes (four bars per input) and 24 exact discrete state samples at ticks
1–8 for three materials. The replay adds one unsupported-leaf control per
material, and survival placement/mining returns the placed bar. LAN guest
placement, state convergence, mining pickup, and host save/reopen passed; all
three configured states remained equal to the Java tick-8 state. Collision
behavior is source-aligned through the `minecraft:iron_bars` template, not an
independent voxel-box measurement. Since bars are static, an active-operation
save case does not apply. The run exposed that metal-decoration loot tables
were not converting Java's legacy condition field; `prepare.py` now converts
the full decoration family, including bars and ladders. Raw run logs are in
`.local/parity/metal-bars.log`
and `.local/parity/metal-bars-lan.log`. The related Metal Ladder solo and
LAN checks also passed after the shared loot conversion, with logs in
`.local/parity/metal-ladders.log` and `.local/parity/metal-ladders-lan.log`.
Full 1:1 remains Open for other neighbor combinations and pixel-level
rendering.

## Metal Ladders

The [Java Metal Ladder probe](tools/java-metal-ladder-trace.patch) records
Andesite, Brass and Copper Ladder Stonecutter recipes and 84 block and
inventory samples. The [survival replay](tools/test-metal-ladders.py)
matches all samples with both a host and a live LAN guest. It covers
vertical placement assist, hanging support, waterlogging and cascade
removal when the last backing block is removed.

The [controls GameTest](tools/java-metal-ladder-controls.patch) captures
15 [Wrench cases](fixtures/metal-ladder-wrench-java.csv) and
39 [climb samples](fixtures/metal-ladder-climb-java.csv). A turn requires
support in its new orientation. Sneak-clicking returns one ladder to the
player. The [player replay](tools/test-metal-ladder-wrench.py) matched
the sampled block states and inventory counts in solo and live LAN.
Each player also matched the Java climb height and vertical velocity on
every sampled player tick, including the grounded starting state.

### APP-2067 bounded gameplay baseline — November 21, 2026

The seven registered `metal-ladder*` checks passed (7/7) on Horizon
`native-9f42064-6bdf8691aa42`, pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, using the prepared 26.3 resources
and Create pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The build metadata reports mixin hash
`5a64af938ec86b00d53d16a408aabc0038fb3e57` and Create mod hash
`4e77322220d09ddbeedcbc87fccdf409833d07367e4b943423494e3f4871526b`.
Command: `python3 tools/test-parity.py <horizon-ctl> <horizon-client> <prepared/26.3> --jobs 2 --check 'metal-ladder*'`.
Logs are in `.local/parity/metal-ladder*.log`.

This reuses Java Create `ac0c444d9828da3453ae8cc65338e8de063286fb` and the
bounded cases: each metal's Stonecutter recipe, vertical placement assist,
backing and hanging support, waterlogging, support loss, Wrench rotation/reject
and pickup, climb movement, and idle cold reopen. The existing Java fixture
contains 84 placement/support/water samples, 15 Wrench cases and 39 climb
samples across the three materials. Capture patch SHA-256 values are
`370911f983d578c2192e892bac9a99527da804b9804ab2cf9ed2701f65e2c93a`
(`java-metal-ladder-trace.patch`) and
`9a7ae1085f18c52206a738a8cf41c56e5448a3b3d47a80c0d91a57cb51246681`
(`java-metal-ladder-controls.patch`). Existing placement, Wrench and climb
replays passed in solo and LAN, including guest inventory/state convergence.
The new cold-reopen replay retained all three variants, north/east/south
facings, the matching-ladder support chain, waterlogging and each player's
inventory stack. Removing the copper column's only wall support removed its
upper ladder, restored water in the lower cell and preserved item counts.
Metal ladders are static, so active-operation reopen is not applicable.

A fresh native rebuild was attempted with a private copy of the launcher
cache. It stopped before compilation because that cache's Horizon source
already contains part of the repository patch set and rejects
`horizon-advancement-initial-inventory.patch`. No native code changed in this
ticket; the focused checks above used the identified existing pinned client.
Exact rendering and remaining collision/neighbor combinations remain open.

## Andesite and Brass Tunnel gameplay baseline (APP-2013)

APP-2013 reuses the pinned Create GameTests and fixtures at
`ac0c444d9828da3453ae8cc65338e8de063286fb`. The bounded routing comparison
covers 552 Java ticks: andesite split (30); brass filtering (82), split (61),
round robin (111), prefer nearest (99), and synchronized input (169). The
existing [runner](tools/test-parity.py) checks every sampled inventory count;
andesite also compares belt stack and position. All seven routing checks passed.
The separate [settings replay](tools/test-brass-tunnel-settings.py) checks all
seven mode buttons, group propagation, and East-side filter set/clear without
consuming the held stack.

The APP-2013 [lifecycle replay](tools/test-brass-tunnel-lifecycle.py) adds the
finite boundary cases. It saves/reopens an idle connected group and checks its
mode; naturally loads ten brass casings into the connected tunnel group; stops
the belt at the lever-controlled clutch; saves/reopens with all ten buffered;
then restarts the belt and checks all ten arrive in the three depots. The
[LAN settings replay](tools/test-brass-tunnel-settings.py) performs all seven
mode changes and East-filter set/clear as a guest, checking the host's
authoritative group and filter state and the guest's unchanged item count.
Guest convergence is checked; Java packet arrival timing is not claimed.

The belt/funnel prerequisites are complete in [APP-1968](https://linear.app/appstu/issue/APP-1968/create-gameplay-baseline-mechanical-belt-and-belt-connector)
and [APP-1970](https://linear.app/appstu/issue/APP-1970/create-gameplay-baseline-andesite-and-brass-funnels).

All nine registered cases passed on `native-9f42064-6bdf8691aa42`, Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, with the matching Create pack
SHA-256 `a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
This available main-synchronized build is from source commit `781c0ef`; the
tunnel and belt implementation files match the ticket checkout. It was reused
instead of compiling a new client because this worktree has no private launcher
compilation cache. Exact Java reload behavior, every routing mode/layout
cross-product, animation curves, and pixel-level presentation remain open.

## Behavior audit

| Family | Evidence already available | Next behavior to compare |
| --- | --- | --- |
| Elevator | Redstone trips, linked pulleys, restart and disassembly, named floors, seated riders, standing riders, per-floor doors, animated floor display and sounds | Client pose timing outside the elevator fixture, more layouts and camera comparisons |
| Moving assemblies | Bearing controls, both Linear Chassis variants, Radial Chassis, wrench range controls and previews, Windmill Bearing controls and load, Gantry actors, press and piston traces, mounted storage, rope payload, and cart crop harvesting | Chassis group preview transitions, additional windmill configurations and clockwork bearings, the remaining actors, collision and player transport |
| Trains | Track placement, assembly, manual and scheduled travel, live train seating and dismount, train state reload, branched signal occupancy, cross-signal reservations, station dispatch and Schedule editor | Multi-carriage layouts, alternative routes to one station, remaining wait conditions and Java standing-player parity around trains |
| Kinetic power | Water wheels, chain drive and adjustable chain gearshift, basic gear trains, loaded stressometer, Creative Motor and Rotation Speed Controller settings, hand-crank actuation and coast, and Copper Valve Handle angles and mounting | More power sources and transitions between networks |
| Factory processing | Milling, crushing, mixing, sawing, drilling, compacting (four Java traces), crafting, spouting, and sequenced assembly | Belt and entity pressing, remaining recipes and conditions |
| Item logistics | Belts, funnels, vaults, arms, chutes, tunnel routing, filters, and redstone-controlled Packager transfers | Factory gauges, stock links and ordering, other Packager inventory paths, train and contraption interactions |
| Fluids and steam | Pump timing, branched pipes, hose pulley, Item Drain transport and emptying, boiler operation and potion brewing | Registry fluids, remaining Item Drain interfaces and visuals, tank and valve variants, remaining effects and recipes |
| Building, equipment and schematics | Survival crafting, shearing, sandpaper, backtank damage traces, Goggles crafting, right-click equipping and Java-matched gauge text, Schematicannon flight, 14 decorative stone palettes (259 blocks), and 36 windows and panes with connected textures on 34 of them | Decorative stone world generation, remaining connected textures, further palettes, diving and refilling, Goggles targets beyond the lever and gauges, exact pixel comparisons, and advancement triggers, Schematic Table and entity printing |
| Redstone and displays | Contacts, Redstone Links, the Analog Lever’s power and removal, Smart Observers, stockpile switches and Display Links | Remaining display sources and targets, tuning screens, and moving contraption interactions |
| Presentation and progression | Original models and textures used by tested Horizon machines | Ponder scenes, advancements, translations, sounds, particles and configuration workflows |

The table is the initial feature-family audit. Add individual Java actions
and evidence as each family is inspected.

## Hose Pulley baseline (APP-1989)

The original Java GameTest `TestFluids.hosePulleyTransfer` uses a finite
3×3×3 source of 27 water blocks and expects all 27 destination blocks filled,
all 27 source blocks emptied, and the pulley tank empty. `tools/test-hose-pulley.py`
compares 301 ticks, including both buffers and all 54 reservoir cells; the
recorded run matched every Java sample. Idle save/reopen preserved the complete
observable state and 27,000 mB. Active pump save/reopen retained 27,000 mB,
resumed pumping, and matched the later Java trace state reached after restart.

The pinned Java config defaults to a 10,000-block infinite-source threshold
and `ALLOW_BY_TAG`; its generated `create:bottomless/allow` tag contains water
and lava. `native/hose.rs` previously promoted only water. It now promotes both
tagged vanilla fluids at the existing body limit. Isolated source bodies passed
at 9,999 water blocks (finite), 10,000 water blocks (infinite), and 10,000 lava
blocks (infinite). Powered lowering and raising passed, and active saves at both
positions retained the pulley offset. In an integrated LAN world, a guest
operated the pulley lever, the host received the action and started the pump,
and the guest converged on the lever's resulting state. This checks guest
interaction and state convergence, not Java packet timing or interpolation.

The neighboring `fluid-pipe-gameplay` check also passed. The final checks used
Horizon build `native-9f42064-52335bcc9361`, source baseline
`47dcb5118e3a1b60dd4a80d02b6102eef68a9ba2`, and Create pack SHA-256
`ff689b6512cec7eafee14305728047fa4aedaf1a8fccefb1ed963c57723c1d98`.
Command: `python3 tools/test-parity.py <build horizon-ctl> <build horizon-client>
<build .local/horizon-client/26.3> --jobs 1 --check 'hose-pulley' --check
'fluid-pipe-gameplay'` (2/2 checks passed). Dynamic/nondefault
`hosePulleyBlockThreshold` configuration, additional fluids/dimensions, and
fluid effects remain outside this baseline. Early invalid fixtures and their
diagnostics remain in `.local/parity/hose-pulley-bottomless-step-origin.log`,
`.local/horizon-hose-lava-verify.log`, and `.local/horizon-hose-pulley-movement.log`;
the final harness force-loads its threshold body and clears the movement column.
Full 1:1 remains Open.

## Decorative stone cut from vanilla materials

The [Java GameTest](tools/java-vanilla-stone-trace.patch) records
[126 blocks](fixtures/vanilla-stone-palette-blocks-java.csv) across Andesite,
Calcite, Deepslate, Diorite, Dripstone, Granite and Tuff. The Horizon replay
matched all 126 registry IDs and default states. The archive includes 588
byte-identical models, textures and blockstates, all 126 loot tables, and
all 238 recipes with Horizon's ingredient format.

Solo and live LAN survival players matched the
[Java action trace](fixtures/vanilla-stone-palette-actions-java.csv) for the
seven Stonecutter results, merging slabs, placing horizontal pillars and
joining walls. The prior seven Create-material palettes also passed their
registry, asset and survival regression.

## Palette mining and metal construction

The [Java mining probe](tools/java-palette-mining-trace.patch) records
40 [drop cases](fixtures/palette-mining-java.csv). The Horizon replay
matched all 40 with a host and a live LAN guest using a wooden pickaxe
and an empty hand. It covers every stone family, full blocks, walls,
stairs, pillars, single and double slabs, and three metal blocks.
Double slabs return two items. The pack translates the original loot
conditions and modifiers to Horizon's format.

The [metal construction probe](tools/java-metal-construction-trace.patch)
captures both Andesite Alloy crafting directions and both iron Stonecutter
recipes. Horizon survival matched the recipe outputs and actual placement.
Host and guest matched the Java Wrench pickup results for all three
blocks. Industrial Iron washing matched [all 175 Java ticks](fixtures/fan_metal-java.csv)
through a fan power interruption. The per-block placement sounds from the
Java construction reference still need an in-game Horizon comparison.

## Colored Seats

The [original Java GameTest](tools/java-colored-seats-trace.patch) measures
16 [seat colors](fixtures/colored-seats-java.csv). All 32 original recipes,
including both wool-and-slab crafting and dye recoloring, passed in Horizon
survival. The pack uses 82 byte-identical Java models, blockstates and textures,
and all 16 colors appear in the live creative search. Red is in Create's
Palettes tab.

A host and live LAN guest each recolored all 16 waterlogged seats, keeping
the waterlogged state and the original dye count. Each player boarded and
dismounted with normal input. The existing white-seat elevator and train
replays passed on the same build.

Changing the Java train's three seats to red, blue and green reproduced
all [246 rider samples](fixtures/scheduled_player_seats-java.csv) and both
[dismount poses](fixtures/scheduled_player_dismounts-java.csv). The live
Horizon host and guest matched the same 123 ticks in the colored train.
The [Java dropped-item replay](fixtures/seat-item-fall-java.csv) records
30 ticks of an ingot falling onto a Seat. Horizon matched its position,
velocity and ground contact every tick in solo and with a live LAN guest
on `c28568a5b862`. On the same build, both roles matched 28 ticks each
of the [Java player fall trace](fixtures/seat-fall-ticks-java.csv) onto
stone, a Seat, and a Seat while crouching. Position, velocity and ground
contact are compared each tick. The host and guest each end with Java's
health in all three cases. The host's client health update can arrive
after the matching physics tick.

The [live Java pig replay](fixtures/seat-mob-landing-java.csv) matched
all 32 ticks in solo and LAN on `a3cc418aff88`, including the actual
passenger link on the guest, the last riding tick after block removal,
and the resumed fall. A [second pig fixture](fixtures/seat-mob-rival-java.csv)
matched 42 ticks, the reduction from ten health to eight on touchdown,
and the second pig rebounding off the occupied Seat. The 67-tick cow
elevator and 92-tick host-and-guest elevator ran on the same build.

## Rose Quartz palettes

Nine [placement cases](fixtures/rose-quartz-states-java.csv) matched
Java in solo and with a live LAN guest. The original Block of Rose
Quartz follows the clicked face axis. Both tile sizes place as full
blocks. The three [Stonecutter checks](fixtures/rose-quartz-cutting-java.csv)
matched the original ingredient and two-block output in survival.

### APP-2062 gameplay baseline

The finite cases are survival acquisition of Rose Quartz from quartz and
redstone, Sand Paper polishing to Polished Rose Quartz, both original
reciprocal 1:1 shapeless tile conversions; all three full-block palette items
and their Java placement axes; all three pickaxe drops; survival Stonecutter
outputs; and solo/LAN save behavior. Existing Java-captured
[intermediate crafts](fixtures/intermediate-crafting-java.csv) and the
[Sand Paper checks](tools/test-sandpaper.py) cover material acquisition and
polishing, with a guest polishing and retaining inventory through rejoin in
[LAN](tools/test-sandpaper-lan.py). The solo lifecycle replay converted both
tile sizes, placed the three palette shapes, mined one of each with a wooden
pickaxe, then reopened the world with all placed block states and two polished
Rose Quartz retained. The LAN replay placed all three shapes as a guest,
retained the guest's two polished Rose Quartz, reopened the host world, and
confirmed the guest inventory and all three block states after rejoin. The
existing placement and Stonecutter Java traces also passed in solo and LAN.
The Java classes are full blocks, so slab merging and wall joining do not
apply to these three items.

The checks ran on the pinned Horizon 9f42064 engine client
`native-9f42064-6bdf8691aa42` (client SHA-256
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`, built
from main baseline `781c0ef`) with pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b` and
prepared Minecraft 26.3 resources. Commands:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check 'intermediate-crafting' --check 'sandpaper-lan' --check 'rose-quartz-palettes*' --check 'rose-quartz-lifecycle*'
```

All six selected checks passed. The standalone `sandpaper` check was also
attempted, but this cached client was built from `781c0ef`, before the
Sand Paper runtime hooks present on current main; that run reached the old
seven-use boundary and did not complete its eight-use durability case. It is
preserved in `.local/parity/sandpaper.log` and is not treated as evidence
against the already-Done APP-1964 prerequisite. The Java reference remains
`ac0c444d9828da3453ae8cc65338e8de063286fb`; palette definitions, reciprocal
recipes and block loot tables were reviewed at that revision. This is a
gameplay baseline, not exhaustive visual or full 1:1 parity. Exact appearance,
additional placement combinations, and other tool tiers remain open.

The [three-lamp Java fixture](fixtures/rose-quartz-lamp-java.csv) matched
39 ticks in solo and LAN on `a52e5e190a8d`. It covers a rising pulse on
each lamp, the one-tick activation, held latching after power is removed,
both comparator directions, and two survival Wrench actions. Verified
emission is 15 when lit and zero when off. Placement beside an existing
power source sets the input state while leaving the lamp off. The
survival recipe and six byte-identical blockstate, model and texture
files are included.

### APP-2043 Rose Quartz Lamp gameplay baseline

The bounded cases are survival crafting and placement; a rising and falling
input on each of three connected lamps; one-tick activation and held latching;
both comparator directions and redstone wire output; placement beside an
existing source; two survival Wrench actions; LAN guest interaction; and idle
and active save/reopen. Java source review covered
`RoseQuartzLampBlock` defaults, placement, `neighborChanged`, cluster traversal,
signal output, tick scheduling and Wrench behavior at
`ac0c444d9828da3453ae8cc65338e8de063286fb`.

`tools/test-rose-quartz-lamp.py` matched all 39 fixture ticks in solo and LAN.
The solo check crafted the lamp from the original recipe and exercised the
source, comparator, wire and Wrench paths. In LAN the guest performed the
representative Wrench actions and converged on the host's resulting lamp state.
`tools/test-rose-quartz-lamp-persistence.py` cold-reopened idle and latched
states and observed the same three block properties afterward. Connected
output and source removal are covered by the Java-matched gameplay trace; the
persistence fixture deliberately omits adjacent output wire to avoid feeding
the lamp's output back into its input. This is a scoped gameplay baseline, not
full 1:1 verification. Exact renderer behavior and other neighbor/power
combinations remain open.

The selected Horizon checks passed on the compatible
`native-9f42064-6bdf8691aa42` client, built from main `781c0ef`; the affected
Rose Quartz lamp code and fixture are unchanged through the current main base
`11654d5`. Prepared Minecraft 26.3 resources came from the
same build. The content pack SHA-256 was
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
The Java fixture SHA-256 is
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`; the
capture patch SHA-256 is
`6c2df799cf53b61c099831299b1083b181d7b8788f0166bc31e49c255091e033`.
Commands selected `rose-quartz-lamp`, `rose-quartz-lamp-lan` and
`rose-quartz-lamp-persistence` through `tools/test-parity.py` with `--jobs 1`.
Each passed. The first sandboxed launch attempt was blocked from creating its
local control socket; rerunning with local socket access completed the checks.
No gameplay implementation or Java recapture was needed. Time log: source and
runtime setup 15 minutes; harness coding 10 minutes; native build 0 minutes
(reused); focused integration and debugging 8 minutes.

## Window palettes

### APP-2063 glass windows and panes

The bounded gameplay baseline reuses the existing 36-state Java palette and
eight-neighbor traces, placement/waterlogging/crafting/Stonecutter replay,
eight-recipe recycling trace and six live loot cases. The LAN replay covers
host and guest survival placement, shared pane connections and guest
waterlogging. The family is static, so active-operation persistence does not
apply; `window-reopen` saves and cold-reopens a connected pane beside a
waterlogged pane and confirms both complete block states are retained.
The source review covered `ConnectedGlassBlock`, `WindowBlock`,
`GlassPaneBlock` and `WindowGen`: windows inherit glass behavior and disable
spawn, redstone-conductor, suffocation and view-blocking checks; panes inherit
vanilla iron-bar behavior. The original asset audit retains alpha, and the
272-case directed face-visibility replay matched Java for full blocks and
stacked/connected panes. Representative oak windows and birch panes were
rendered with the original assets. On Horizon build
`native-9f42064-6bdf8691aa42` with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`, the
five targeted checks passed; the separate window face-visibility check also
passed. Full 1:1 remains open for remaining shape and connected-texture
combinations and exhaustive pixel comparisons.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 --check 'window-palettes' --check 'window-palettes-lan' --check 'window-recycling' --check 'window-silk-touch' --check 'window-reopen'
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --window-culling --check 'window-culling'
```

The pinned [Java GameTest](tools/java-window-palettes-trace.patch) records
[36 default window and pane states](fixtures/window-palettes-java.csv)
with material values, eight pane joins and source-water placement. Horizon
matched all 36 blocks placed by a survival player, the eight joins,
and bucket waterlogging. In LAN, the host and guest each placed a pane.
Both clients saw the panes join and the guest waterlog one pane. A player
also crafted oak windows and panes and used both original glass inputs in
the Stonecutter. The pack audit checks
216 original model, state and texture files, 36 loot tables, and 48
crafting, stonecutting and recycling recipes. Representative oak windows
and birch panes rendered using the original assets.

Run `tools/test-window-palettes.py --visual --java-source /path/to/Create`
with the standard Horizon arguments to repeat the asset and gameplay
checks.

The 11 wooden windows and Ornate Iron Window use Horizon's built-in
vertical connected textures for full blocks and panes. Pack generation
extracts the 48 tiles directly from Java's sheets and preserves their
alpha. The [Java texture-context GameTest](tools/java-window-ctm-trace.patch)
records [192 tile selections](fixtures/window-ctm-java.csv) over both
block shapes, including same-family front blockers, stone blockers,
mixed families and waterlogged pane neighbors. The visual replay checks
tile selection and the pane models' mirrored texture coordinates.

```sh
python3 tools/test-window-ctm.py --java-source /path/to/Create /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

The Industrial Iron Window and its pane use the original 16-tile
rectangular pattern. Horizon matched 168 rendered Java selections on all
four horizontal faces, including front blockers, diagonal neighbors,
and mirrored pane faces. All 16 tiles retained the original decoded RGBA
pixels. [Java GameTest](tools/java-industrial-window-ctm-trace.patch) and
[recorded contexts](fixtures/industrial-window-ctm-java.csv).

```sh
python3 tools/test-industrial-window-ctm.py --java-source /path/to/Create /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

Framed Glass, Horizontal Framed Glass, and Vertical Framed Glass
match 304 rendered Java contexts. The tests cover pane connections and
mirroring, ordinary diagonal joins, and the different top and bottom
treatments. The pack retains 55 original tile crops and mirrors those
same pixels on the pane faces that require it. [Java GameTest](tools/java-framed-glass-ctm-trace.patch) and
[recorded contexts](fixtures/framed-glass-ctm-java.csv).

```sh
python3 tools/test-framed-glass-ctm.py --java-source /path/to/Create /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

Weathered Iron Window uses four connected atlases and four weighted
end models. The pinned Java client probe reads the actual baked quads.
The Horizon replay matches 364 rendered samples across 12 positions,
including the distinct atlas choices on one pane face and the weighted
end models. All 64 original atlas tiles retain their RGBA pixels. The
native renderer opts these two block IDs into Java 1.21.1's model random
sequence through their connected texture rules. [Java client probe](tools/java-weathered-window-client-probe.patch)
and [sampled quads](fixtures/weathered-window-java.csv).

```sh
python3 tools/test-weathered-window-ctm.py --java-source /path/to/Create /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

Horizon build `68c7ab9c0826` matched all 272 directed face checks,
including mixed full blocks and stacked panes with different arms or
water states. The same checks found 55 differences before the correction.
The original Java client recorded 2,394 decisions, including the
unrendered faces and vanilla controls.
[Java client probe](tools/java-window-culling-client-probe.patch) and
[sampled faces](fixtures/window-culling-java.csv).

```sh
python3 tools/test-window-culling.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

The standalone visual replays use FFmpeg. Add `--window-culling`
to `tools/test-parity.py` to include the face check in the full suite.
Tiled Glass uses fixed tiles in Java. The Copycat section below records
which painted window joins and shared faces were verified.

The [recycling trace](fixtures/window-furnaces-java.csv) compares 53
samples per recipe across eight furnaces. Horizon matched all 424 rows,
including fuel, lit state, cook progress and completion on tick 50.
The six [live loot cases](fixtures/window-loot-java.csv) compare survival
mining of Framed Glass, Oak Window Pane and Weathered Iron Window Pane.
A plain pickaxe drops nothing. Silk Touch drops one of the original block
or pane. The pack translates the Java loot condition to Horizon's
current format for all 36 windows and panes.

## Machine waterlogging

The [dispenser fixture](fixtures/waterlogged-blocks-java.csv) switches from
a water bucket to an empty bucket while sampling the target block, its
waterlogged state, and the dispenser inventory. Horizon build
`ed3075daa96c` matched all 338 Java samples across 26 blocks over 13 ticks.
The previous pack differed in 234 samples across the same cases. The
[Java GameTest patch](tools/java-waterlogged-blocks.patch) reproduces the trace.

Build `75389a9bfde4` matched the original 338 samples again and all 78
[dispenser samples on supported blocks](fixtures/waterlogged-supported-java.csv).
The six targets are Hand Crank, Copper Valve Handle, Mechanical Harvester,
Mechanical Plough, Steam Engine, and Powered Shaft. The
[Java GameTest patch](tools/java-waterlogged-supported.patch) places the
required supports for that second replay.

Build `bfc003939702` also matched all 39
[connected belt samples](fixtures/waterlogged-belts-java.csv) for Belt,
Andesite Belt Funnel, and Brass Belt Funnel. Both clients use connected
shafts to form the belt under test and the belts supporting the funnels.
The prior pack differed in 27 samples. The
[Java GameTest patch](tools/java-waterlogged-belts.patch) reproduces the trace.

Build `0bfdfbf3d971` matched 12 [Weighted Ejector placements](fixtures/weighted-ejector-placement-java.csv)
covering all four facings in air, source water, and flowing water. Its
[13 dispenser samples](fixtures/weighted-ejector-buckets-java.csv) also
check the adjacent space. Water first reaches it at tick 9 and the
dispenser removes the embedded source at tick 10. The previous runtime
kept the adjacent space dry through tick 12.
The [Java GameTest patch](tools/java-weighted-ejector-water.patch) captures both replays.

The same build matched [all 45 sticky-piston ticks](fixtures/waterlogged-piston-java.csv)
in the place-at-either-stop mode. The wet sticky head lands at tick 9, its
retraction reveals the source again at tick 25, and the returning plough
retains that water at tick 33. The
[Java GameTest patch](tools/java-waterlogged-piston.patch) reproduces the
round trip. All 455 previous machine dispenser samples and eight Copycat
bucket cases passed again with the same build.

## Cart Assembler

Build `0a1a3bb56ec0` matched eight [survival placements](fixtures/cart-assembler-placement-java.csv)
over straight regular, powered, detector, and activator rails. The
placement preserves the original rail kind and axis, stores the player's
direction, and consumes one assembler. The
[13-tick dispenser replay](fixtures/cart-assembler-drain-java.csv) fills
the placed assembler at tick 4 and breaks it at tick 10 when the bucket
removes its water. It drops one assembler and the stored rail on that
tick. The [Java GameTest patch](tools/java-cart-assembler-rails.patch)
reproduces both traces.

### APP-2003 Cart Assembler and Controller Rail gameplay baseline

The finite case list follows APP-2003: ordinary and powered/control rail
acquisition and placement; valid assembly and disassembly; supported cart axes
and speed control; a moving cargo/harvester case; guest interaction; and idle
and active reopen. Coupling-chain solving remains with the coupling feature.

All 12 selected checks passed serially on
`native-9f42064-6bdf8691aa42` using the prepared Minecraft 26.3 resources and
Create pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

| Check | Result |
| --- | --- |
| `cart-assembler-rails` | Pass: 8 Java survival placements and 13 Java fill, drain, and drop samples |
| `minecart-anchor` | Pass: both cart axes assemble and disassemble; the assembler rail remains in place |
| `crop-farming` | Pass: all 72 Java ticks; moving harvester crops and cart output match, immature crops remain untouched, mature crops are harvested, and output survives save/reopen |
| `minecart-pickup-lan` | Pass: LAN guest picks up and redeploys a stone payload; host retains anchor/orientation and the payload disassembles at the destination assembler |
| `controller-rail` | Pass: 12 Java placements, rejected unsupported placement, and 221 power samples |
| `controller-rail-gradient` | Pass: 490 rail and comparator samples |
| `controller-rail-motion` | Pass: 52 Java minecart samples for full/partial speed, centering, and braking |
| `controller-rail-craft` | Pass: survival recipe crafts six rails and consumes all eight inputs |
| `controller-rail-wrench` | Pass: 12 rotations and two dry/wet pickup cases |
| `controller-rail-assembler` | Pass: six rail exchanges and 18 directed departure samples |
| `controller-rail-persistence` | Pass: idle/powered rail states survive reopen and a moving cart resumes |
| `controller-rail-lan` | Pass: guest converges on host's powered rail state |

The Java-derived comparisons use the pinned fixtures described above; the
additional reopen, negative placement, and LAN cases are Horizon gameplay
checks. The guest check proves resulting-state convergence, not Java-equivalent
packet arrival. Existing source/matrix evidence establishes the APP-1978
Super Glue/assembly-selection and APP-1979 contraption rendering/collision/
synchronization prerequisites. No Cart Assembler production mismatch was
reproduced, so this baseline adds finite acceptance evidence only. Full 1:1
remains Open for the matrix's remaining carriers, crossings, and entity
persistence.

Reproduce with the matching checks registered in `tools/test-parity.py`:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check cart-assembler-rails --check minecart-anchor --check crop-farming --check minecart-pickup-lan --check controller-rail --check controller-rail-gradient --check controller-rail-motion --check controller-rail-craft --check controller-rail-wrench --check controller-rail-assembler --check controller-rail-persistence --check controller-rail-lan
```

Approximate effort: source review and existing Java-fixture selection 10
minutes; isolated runtime/output setup 10 minutes; focused integration about
three minutes. No Java recapture or production repair was needed.

## Controller Rail

Build `df42bb0aa2f2` matched [12 Java placements](fixtures/controller-rail-placement-java.csv)
across four player headings, including source water and an ascending
neighbor. It matched [221 power samples](fixtures/controller-rail-power-java.csv)
for one-ended and two-ended redstone and
[490 rail and comparator samples](fixtures/controller-rail-gradient-java.csv)
when an Analog Lever supplies power 7 at the opposite end. The comparator
follows the rail midpoint after two ticks. An earlier Horizon candidate
published the Analog Lever change one tick late.

The [52-row minecart replay](fixtures/controller-rail-motion-java.csv)
covers full speed, partial speed, centering at zero power, and braking
against the configured direction. Position and horizontal velocity
matched within 0.000001 blocks or blocks per tick on every sampled tick.
The original six-rail recipe works at a survival crafting table. Nine
original blockstate, model, and texture files match byte-for-byte, and
Horizon renders the idle and powered tints. The
[Java GameTest patch](tools/java-controller-rail.patch) captures the
placement, signal, and movement references.

Build `3d6e2316bfbe` matched [12 Wrench rotations](fixtures/controller-rail-wrench-java.csv)
and [two crouch-pickup cases](fixtures/controller-rail-pickup-java.csv).
The wet pickup returns one rail and leaves source water behind. Six
[Cart Assembler actions](fixtures/controller-rail-reuse-java.csv) preserve
the original shape and direction while exchanging the installed rail and
returning the replaced item. The [18-sample departure replay](fixtures/controller-rail-cart-direction-java.csv)
matches both directions every tick. The assembler takes the payload on
tick 1 and launches the minecart in the stored direction at 0.4 blocks
per tick. The [Java GameTest patch](tools/java-controller-rail-tools.patch)
recaptures the Wrench and Assembler traces.

### APP-2044 finite gameplay baseline

The [placement reference](fixtures/controller-rail-placement-java.csv) has 12
Java rows across four headings, including straight, waterlogged and supported
ascending placement. The `controller-rail` replay also rejects a south-side
placement with no supporting block and confirms the rail stays in hand. The
[signal reference](fixtures/controller-rail-power-java.csv) has 221 samples;
the [gradient reference](fixtures/controller-rail-gradient-java.csv) has 490
rail/comparator samples, including a two-tick comparator response. The
[minecart reference](fixtures/controller-rail-motion-java.csv) checks 52
samples for full/partial speed, zero-power centering and braking, with
position and horizontal velocity within 0.000001 blocks or blocks per tick.
The assembler regression retains six rail exchange actions and 18 departure
samples from its existing Java fixtures.

All eight selected checks passed serially on `native-9f42064-fb8446effe86`,
built from the Controller Rail source at `781c0ef` with Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and the prepared Minecraft 26.3
resources. The installed Create pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

| Check | Result |
| --- | --- |
| `controller-rail` | Pass: 12 Java placements, rejected placement, 221 power samples |
| `controller-rail-gradient` | Pass: 490 rail and comparator samples |
| `controller-rail-motion` | Pass: 52 Java minecart samples |
| `controller-rail-craft` | Pass: survival recipe crafts six rails and consumes all eight inputs |
| `controller-rail-wrench` | Pass: 12 rotations and two dry/wet crouch-pickup cases |
| `controller-rail-assembler` | Pass: six rail exchanges and 18 departure samples |
| `controller-rail-persistence` | Pass: idle rail and powered rail state survive save/reopen; a moving cart remains on the powered line and advances after reopen |
| `controller-rail-lan` | Pass: guest observes the host's powered rail state on a dedicated LAN server |

The new rejection, persistence and LAN cases are Horizon behavior checks, not
new Java timing captures. The existing Java fixtures remain the comparison
evidence for power, direction and cart motion. The guest check establishes
state convergence, not Java-equivalent packet arrival. During harness repair,
the negative placement aim was moved away from an occluding fixture rail, and
the Controller Rail pickup check stopped using a Wrench helper hard-coded to a
different block position. No production Controller Rail mismatch was
reproduced; this pass changes checks and evidence only.

Reproduce the bounded final set with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check controller-rail --check controller-rail-gradient --check controller-rail-motion --check controller-rail-craft --check controller-rail-wrench --check controller-rail-assembler --check controller-rail-persistence --check controller-rail-lan
```

Time (approximate): setup and private runtime/cache provisioning 15 minutes;
source review and fixture implementation/repair 25 minutes; Java recapture 0
minutes (existing captures reused); native builds 20:32 for the first build,
8:32 for the first rebased build and 5:01 for the final incremental build;
static checks under one minute; final eight-check integration run about five
minutes. Full 1:1 remains Open for remaining slopes, crossings and powered
combinations.

## Copycat Panel and Step

Horizon build `613a2d8c9600` matched 90 Java material and Wrench
observations on the action tick. The replay checks the placed block
state, the copied material and its properties, the stored item count,
and the survival inventory after successful interactions. Eight
lifecycle observations cover off-hand application and survival and
Creative break drops. The actual Stonecutter returns four Panels or
Steps per Zinc Ingot. [Java GameTests](tools/java-copycat-material.patch),
[material trace](fixtures/copycat-material-java.csv), and
[lifecycle trace](fixtures/copycat-lifecycle-java.csv).

The standalone FFmpeg replays check applied materials on both original
shapes and the host and guest framebuffers during material application
and removal. The LAN replay observes both changes on the action tick.

```sh
python3 tools/test-copycat-render.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-copycat-lan.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

Horizon candidate `3e9daba8359d` matched all 12 Java placement-assist
outcomes on the action tick, including floor and wall Panel extension,
a blocked Panel, Step alignment and half preservation, and source
versus flowing water. A real host and guest matched three of those
cases on the action tick. The 90 material and eight lifecycle checks
also passed on this candidate. [Java placement test](tools/java-copycat-assist.patch)
and [trace](fixtures/copycat-assist-java.csv).

Horizon candidate `217c11b195b6` matched all eight Java bucket
interactions on the action tick. Water fills and drains both shapes,
lava uses the adjacent cell, and each action preserves the applied
material and stored item. [Java bucket test](tools/java-copycat-buckets.patch)
and [trace](fixtures/copycat-buckets-java.csv).

A standalone window on native `539abfaeee59` selects all 48 tiles
expected by the [Java Copycat neighbor probe](tools/java-copycat-window-joins.patch).
The cases include Panel and Step orientation and a front-facing neighbor
that stays disconnected. In the [LAN replay](tools/test-copycat-window-lan.py),
both players see the join appear when the guest applies material and disappear
when the guest resets it on the action tick. The [standalone replay](tools/test-copycat-window-joins.py)
also checks that saving and reopening preserves the join and that replacing
the Panel clears it.

Build `0b725c3de704` matched [56 Java tile selections](fixtures/copycat-wrapped-window-java.csv)
on the faces of painted Panels, including aligned and opposed Panels and
ordinary windows. In the [painted Panel LAN replay](tools/test-copycat-wrapped-window-lan.py),
both players see the surface join and separate on the same world tick
as its neighbor is added and removed. The Panel keeps its copied material
throughout. The [Java client probe](tools/java-copycat-wrapped-window.patch)
and [Horizon framebuffer replay](tools/test-copycat-wrapped-window.py)
cover the selected textures and require FFmpeg for Horizon screenshots.
The repackaged atlas also passed the previous 48 standalone join and
192 vertical window and pane cases. All 48 vertical texture tiles retain
the original Java pixels and alpha.

Build `b4b2c9b204c4` matched [56 Java tile selections](fixtures/copycat-step-window-java.csv)
on painted top and bottom Steps. That includes matching opposite halves,
opposite facings, and mismatched material. The 56 painted Panel cases
passed again on the same build. The [Java Step probe](tools/java-copycat-step-window.patch)
recaptures those selections. Pass `--steps` to the painted Copycat
framebuffer replay.

Build `0df22c12788d` matched [72 more Java tile selections](fixtures/copycat-framed-window-java.csv)
for painted Framed Glass, Horizontal and Vertical Framed Glass, and
Industrial Iron Window Panels. The [Java client probe](tools/java-copycat-framed-window.patch)
and [Horizon replay](tools/test-copycat-framed-window.py) cover ordinary
and painted neighbors on both sides and above and below. The relocated
PNG files retain all 126 established source or mirrored tiles. The
304 original Framed Glass and 168 Industrial Iron window and pane
cases passed again, as did both 56-case painted Panel and Step replays.

Build `359451469bec` matched [60 Java Weathered Iron side selections and 12 cap variants](fixtures/copycat-weathered-window-java.csv)
on painted Panels. The [Java probe](tools/java-copycat-weathered-window.patch)
and [Horizon replay](tools/test-copycat-weathered-window.py) cover all
four seeded texture variations across 12 positions. The previous 364
Weathered Iron terrain and pane selections and all 64 source RGBA tiles
passed again, along with the focused painted Panel cases.

The original Java client captured [28 standalone window faces](fixtures/copycat-window-culling-java.csv)
against painted Panels and Steps and [56 painted faces](fixtures/copycat-painted-culling-java.csv)
against windows and other painted Copycats. Horizon build `586c579cd9cc`
matched both captures and six earlier painted-window connected-texture
checks. A matching painted face disappears where the adjacent geometry
covers it. A differing material or partial overlap follows the original
visibility decision. The [visual replay](tools/test-copycat-window-culling.py)
uses FFmpeg and runs both captures under the suite's `--window-culling` option.

## Wrench

The pinned [Java Wrench fixture](tools/java-wrench-trace.patch) records
[42 uses](fixtures/wrench-java.csv) on the shaft, cogwheel, gearbox, Creative
Motor, Encased Fan and Item Drain. Horizon matched the block identity,
orientation and survival inventory on all 42 player actions, including
held crouch pickup. The original two model parts and recipe are packaged.
The shared survival recipe test also verifies crafting the Wrench.

The [tagged pickup fixture](fixtures/wrench-tagged-java.csv) matches
survival crouch-use on rail (via the vanilla rail tag), repeater, a
redstone wall torch, and a hopper. It verifies the exact pickup item,
including the standing redstone torch, and checks that plain stone stays
in place. Run `tools/test-wrench.py --tagged` with the standard Horizon
arguments. Broader Create block overrides, tagged inventory contents,
sound playback timing, and the animated Wrench gear remain open.

The APP-2076 bounded pass ran on `native-9f42064-558283db0c26` with pack
SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
It passed the base and tagged fixtures, a new survival Wrench recipe test,
18 gearbox rotation/pickup cases plus 11 powered Java samples, guest gearbox
rotation, guest shaft/cogwheel wrench operations, and shaft save/reopen.
The focused final suite comprises `wrench`, `wrench-tagged`,
`wrench-crafting`, `gearbox-wrench`, `gearbox-wrench-lan`,
`gearbox-wrench-retained`, `shaft-casing-lan`, `shaft-reopen`, and
`brass-cogwheel-casing-lan`. A first aggregate gearbox run reported three
missed pickup rows; the complete standalone Java comparison and later focused
checks passed on the same build. The initial observation and its limits are
preserved in `.local/parity/APP-2076-first-gearbox-observation.md`: the rows
were initial X/south to Y, X/west to X, and Y/east to Z, each leaving the
gearbox in place without a refund. The first aggregate's raw log was replaced
by the rerun; this summary records the captured mismatch. An instrumented sweep
hit the target but missed one pickup in 18 actions; 12 repetitions of the
south-face case then succeeded with the player crouching.

To investigate those three cases without retrying a failed interaction,
`tools/test-wrench-pickup-probe.py` made three fresh-world repetitions of each
original setup on the same build and pack. All nine attempts, including the
original three setup/action combinations, recorded a block ray at `[8, 180,
23]` on the west face, `sneaking=true`, successful rotation interaction with
the expected axis, click input accepted (`ok=true`), post-click block `air`,
and exactly one expected gearbox item returned while retaining the Wrench.
The rotation interaction reports its before/after state; the mouse result only
acknowledges input, so removal and inventory are the semantic pickup evidence.
All nine passed with zero explicit frames between aiming and ray inspection;
the fixture also passed nine repetitions with a one-frame settle. No gameplay
defect reproduced, and the ray target was reliable in this focused check. The
original cause remains uncertain: the original raw log was overwritten, and
the ray inspection itself adds a control round trip before the click. The
Wrench fixture now waits one frame after aiming and refuses to click unless the
ray hits the intended block, so a future targeting miss is reported rather
than retried or hidden.

Reproduction command from the worktree root:

```sh
python3 tools/test-parity.py \
  .local/patched-launcher/versions/native-9f42064-558283db0c26/horizon-ctl \
  .local/patched-launcher/versions/native-9f42064-558283db0c26/horizon-client \
  .local/patched-launcher/versions/native-9f42064-558283db0c26/.local/horizon-client/26.3 \
  --jobs 2 --check 'wrench*' --check 'gearbox-wrench*' \
  --check 'shaft-casing-lan' --check 'shaft-reopen' \
  --check 'brass-cogwheel-casing-lan'
```

## Item Drain

The pinned [Java fixture](tools/java-item-drain-trace.patch) exercises honey
bottles, a water bucket, and an ordinary iron stack entering from the west.
The [105 samples](fixtures/item-drain-java.csv) record progress, item and
fluid identities and amounts. Horizon reproduces the four-tick approach to
the center, the conversion at tick 19, and the subsequent approach to a
blocked exit. A west hopper also transfers one bottle while retaining two.
Run `tools/test-item-drain.py --fluid-visual --plumbing` with the standard
Horizon arguments. The fluid comparison checks 105 liquid height and
stream radius samples across three frame fractions on the honey rig. The
survival interaction pours a held bottle, returns a glass bottle, and
pumps all 250 mB into a separate tank. The independent LAN fixture checks
both players' inventory and the shared 500 mB fill after their pours.

Exact item and camera transforms, more fluid containers, belt funnels,
comparator timing, and multiplayer visual timing still need comparison.

## Hand crank

`tools/java-hand-crank-trace.patch` runs the original crank in a disposable
Create checkout and records 56 observations in `fixtures/hand-crank-java.csv`.
The Horizon replay checks both directions, renewal during a turn, same-tick
shutdown of the rear shaft and stressometer, isolated front shaft, stress
capacity, survival exhaustion, handle coast, and both models at three
interpolated frames. It also checks shaft-preferred placement, dropping the
crank when its supporting shaft breaks, and waterlogging. A separate LAN replay
turns the crank on the host and reverses it from a guest in survival.
The faster-motor replay matches 24 successive Java ticks. Turning with a
64 RPM motor adds 256 SU. Reversing the crank against that motor breaks the
crank and leaves the shaft running at 64 RPM with the motor's own capacity.

```sh
python3 tools/test-hand-crank.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-hand-crank.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-hand-crank-motor.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

The [Java GameTest capture](tools/java-hand-crank-edges-trace.patch) ran on
Create `ac0c444d9828da3453ae8cc65338e8de063286fb` with Java 21. Applying the
patch to a clean checkout and running `./gradlew --offline runGameTestServer`
passes all 21 required tests (five edge tests and 16 matrix cases). The patch
SHA-256 is `fd64c9c045cd6244ae49240735cf94b516589144bcd18f37d38346083887a8d2`.
The capture verifies the empty-food interaction, although the GameTest mock
player does not report the advancement through its tracker; delivery remains
source-verified rather than claimed as a Java runtime check. Copy the CSV
fields from the `CREATE_HAND_CRANK_EDGE_PLACEMENT`,
`CREATE_HAND_CRANK_EDGE_GRIP`, `CREATE_HAND_CRANK_EDGE_MOTOR`, and
`CREATE_HAND_CRANK_MATRIX` records into their respective fixtures.

- [Eight placement cases](fixtures/hand-crank-placement-java.csv) cover both
  axial ends of a Brass Encased Cogwheel, active and perpendicular stressometer
  axes, sneaking, and a second shaft on a conflicting axis. The Horizon baseline
  missed both exposed cog ends and the active gauge axis, and aligned with the
  regular shaft in the conflicting-axis case.
- [Three survival uses](fixtures/hand-crank-grip-java.csv) record the active
  timer, RPM, exhaustion change, and grip damage. The main-hand Extendo Grip
  prevents 0.32 exhaustion and uses zero durability. The empty and offhand-only
  cases charge 0.32. The Horizon baseline charged all three.
- [Two motor rigs](fixtures/hand-crank-edges-motor-java.csv) record ticks 0–28,
  with strokes after samples 4, 9, and 16. The replay compares ticks 1–28 after
  kinetic initialization. When reversed against a 32 RPM motor, Java breaks
  the crank and drops one item at tick 17. The Horizon baseline instead ran the
  intact crank at −32 RPM. With a 16 RPM motor, both engines accepted the
  reversal. Java returned to +16 RPM and 262144 SU at tick 26, one tick ahead of
  the Horizon baseline shaft.

### Measured Hand Crank motor matrix, November 19 2026

The expanded [Java capture](fixtures/hand-crank-matrix-java.csv) adds 16
deduplicated rigs: stopped, 31/32/33/64 RPM, opposing 32 RPM, speed and sign
changes before and during use, Wrench-held normal and sneaking use, and all six
crank facings.
Each capture includes ticks 0–28; Horizon is compared at ticks 1–28 after
kinetic initialization (448 tick comparisons). Fields include motor setting
and existence, crank existence/timer/direction/RPM, shaft and network RPM,
capacity, stress, overload, and crank/motor drops. Strokes occur at ticks 4, 9,
and 16; speed and sign changes occur at tick 2 (before use) or tick 7 (during
use). The Wrench is neither an `IWrenchable` crank nor in Create's
`wrench_pickup` tag, so both normal and sneaking Wrench uses continue to crank
the block instead of rotating or removing it. The Java captures show two
distinct source-conflict paths: an idle crank
trying to join an oppositely rotating network breaks even against a slower
source, while a crank already driving the network can reverse against a slower
31 RPM motor. Changing the attached weaker motor from +16 to −16 during crank
use instead breaks and drops the motor; when the crank expires, the shaft stops.

The first captures exposed three gameplay gaps: opposing-generator behavior on
first crank use, motor sign changes against an active crank, and Creative Motor
loot-table normalization. All three now follow the captured Java behavior.
An initial overbroad fix also broke the valid reversal against a slower motor;
the capture distinguished an idle crank joining a network from an active crank
reversing its own network. The refined rule passed all 448 final observations.
The Java capture patch is
[`tools/java-hand-crank-edges-trace.patch`](tools/java-hand-crank-edges-trace.patch)
(SHA-256 `fd64c9c045cd6244ae49240735cf94b516589144bcd18f37d38346083887a8d2`);
the matrix CSV SHA-256 is
`63b534639ddabc6b3265ef63ae258f85b5caa21542679dd7d4d80a6d2a9af342`.
Java revision remains `ac0c444d9828da3453ae8cc65338e8de063286fb`; all 21
required Java GameTests passed. The final rebuilt Horizon verification used build
`native-9f42064-7f4d88c9778e`, client SHA-256
`bdc37f62b0eba075233a3db5ba80695d34a257156708361430ed514edc8435df`,
ctl SHA-256 `1cca267a26d8e85ed00e7fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`,
and prepared pack SHA-256
`d907f9a6dc2129d83bad5eab4ef80e713ad4d8308841ca1f9946198fbb50bd04`.
The fresh rebuild's bounded batch passed 11/12 checks on its parallel first
run; its sole gauge-facing placement mismatch passed when rerun in isolation on
the same build. Thus each of the 12 selected checks passed, including crank,
equal/slower/faster motor behavior, multiplayer, persistence, grip, placement,
and neighboring shaft/cogwheel/valve placement. The bounded LAN rerun passed: the
host drove +32 RPM and a survival guest reversed the authoritative shaft to
−32 RPM; guest convergence is checked, not Java packet-arrival timing. The
expanded persistence rerun passed both idle and active setups: idle crank state
and zero-speed network survived reopen; the active save retained its attached
16 RPM motor and, after the crank stroke naturally ended during cold startup, the
connected shaft resumed at +16 RPM. Exact Java active-timer reload parity remains
unverified. Nonvisual matrix, placement, motor, LAN and persistence runs use
`--headless`; only the motor-setting UI and rendered animation comparison use
isolated offscreen clients. Shared code touched here includes `native/machines.rs`
and motor loot/settings support used by [APP-1943](https://linear.app/appstu/issue/APP-1943/create-full-parity-kinetic-network-propagation-speed-stress-and)
and [APP-1950](https://linear.app/appstu/issue/APP-1950/create-full-parity-creative-motor); this PR records the crank-facing source conflict coverage and the focused checks run.

The final source comment clarifying the stopped-versus-active conflict rule
forced a fresh incremental build with `tools/build-native.sh`: 97 seconds, build
`native-9f42064-7f4d88c9778e`. The bounded crank/regression batch took about
three minutes plus the isolated placement rerun.

Measured workflow elapsed about 135 minutes from the workflow comment to the
latest Wrench-case regression run: Java/source inspection and capture setup
about 9 minutes; implementation and repair about 63 minutes; native builds
about 16 minutes;
pack preparation under a minute; fast standalone logic comparisons 0 minutes
(the matrix runs production Horizon to include its engine/network path); Horizon
solo matrix and focused comparisons about 27 minutes; host/guest integration
and focused regressions about 6 minutes; harness/environment debugging about
10 minutes. Durations are rounded from recorded command runs and wall clock.
Full-family parity stays open: exact animation/sound timing and remaining
applicable placement, generator-layout, manual-break/drop, and action/presentation
combinations still need evidence. Wrench behavior is covered: Java does not mark the
Hand Crank as wrenchable, so ordinary and sneaking wrench use cranks it.

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-7f4d88c9778e/horizon-ctl .local/patched-launcher/versions/native-9f42064-7f4d88c9778e/horizon-client /Users/andrewholt/dev/horizon-create/.local/baselines/2026-11-19-pre-mechanical-piston-b2405826c686/build/.local/horizon-client/26.3 --jobs 2 --check hand-crank --check 'hand-crank-*' --check cogwheel-placement --check shaft-placement --check copper-valve-handle-placement
```

These cases use exact comparison for placement,
mounted state, countdown, and item counts, with an absolute tolerance of
0.00002 for floating-point fields.
The persistence check compares an idle reopen and an active connected setup. The
active crank’s ten-tick stroke may finish during cold launcher startup; the
reopened motor setting and resumed connected shaft operation are verified, while
exact active-timer reload parity remains unverified.

Sound timing remains open. Java requests the layers from each client's crank
block-entity tick before decrementing its active timer, using the local animation
clock. Horizon requests them from the server's world clock. A client-side timing
comparison and additional shaft types and generator layouts remain open.

## Flywheel

The stationary Flywheel transmits rotation through its axle and contributes
zero stress and capacity. The Java GameTest and Horizon replay sample 96 ticks
across startup, reversal, power loss and restart. They compare both shaft
speeds, an isolated adjacent cogwheel, network stress and capacity, rotor speed,
and rotor angle. The Horizon client also checks four survival placements,
including looking steeply downward, alignment to a shaft, and crouching to
override that shaft. The original model and texture files match byte for byte.

`tools/java-flywheel-trace.patch` adds this reference to the pinned Java
checkout. Its output is recorded in `fixtures/flywheel-java.csv` and
`fixtures/flywheel-placement-java.csv`.

```sh
python3 tools/test-flywheel.py --visual --java-source /path/to/java/create /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

A separate host and guest replay matches all 96 Java network and rotor
samples. The guest breaks the motor on tick 51, and the shaft stops on
tick 52 while the rotor continues coasting. Host and guest captures of the
brass rotor had 99.98% minimum overlap, rounded, at 12 frozen server ticks. The
replay uses ffmpeg to read the screenshots and saves its frames and timing
table under `.local/flywheel-lan/`. Java screenshot comparison remains open.

```sh
python3 tools/test-multiplayer-flywheel.py --java-source /path/to/java/create /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

APP-1976 adds removal/reconnection and idle/active save/reopen of a powered
Flywheel/shaft/cogwheel assembly. The packaged survival recipe is checked
against Create's 3×3 brass-ingot and shaft pattern, and the player placement
replay consumes four Flywheels in survival. Interactive crafting-table output
is exercised by `flywheel-crafting`: eight brass ingots surround one shaft,
producing exactly one usable Flywheel with no ingredient loss or duplication
before survival placement. The Flywheel
transmits axial rotation and does not generate power. The lifecycle check
verifies that the powered source drives the shaft at +64 RPM while the adjacent
cogwheel remains stopped, removal stops the assembly, and a reconnected -32 RPM
source and its driven shaft survive active world reopen.

```sh
python3 tools/test-flywheel-reopen.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

Verification used build `native-9f42064-d6dc2ad18d3f` and pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`. The
pinned Java checkout is `ac0c444d9828da3453ae8cc65338e8de063286fb`; capture
patch `tools/java-flywheel-trace.patch` SHA-256 is
`6ea13e7bed95335e68327439f72711447e44f6563da7644bae32ce7b40c31570`.
References `fixtures/flywheel-java.csv` and
`fixtures/flywheel-placement-java.csv` have SHA-256 values
`c224b1482dc58c3bb88109db00f45eb9890dc35fae5a6962c1af8efd5bd7384c` and
`246074d4db1610ce71543f1e5f960062978ce5742966b6829b650b942b928a8f`.
Solo replay matched 96 Java ticks and four placements; LAN replay matched 96
Java network/rotor samples with at least 99.94% host/guest rotor-mask overlap
at 12 frozen checkpoints. Lifecycle replay passed idle +64 RPM, stopped, and
reconnected -32 RPM before and after active reopen. Exact Java screenshot,
packet arrival, interactive crafting and other assembly layouts remain open.

## Adjustable Chain Gearshift

The 75-tick replay compares the original Java gearshift in both drive
directions at analog strengths 0, 7, 15, 12, and 0 after lever removal.
It checks the powered model state, the delayed redstone notification,
the periodic signal check, and the two output speeds. It also places an
adjustable gearshift and an encased chain drive by hand, then breaks one
to verify the remaining drive disconnects. A LAN smoke check raises the
server output from 24 to 27 RPM using a separate survival guest. Both
original chain recipes pass the survival crafting fixture.

```sh
python3 tools/test-adjustable-chain-gearshift.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-adjustable-chain.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

The mixed-cog speed-limit replay uses 64 and 96 RPM motors, each driving
a large cog, a small cog, and an adjustable gearshift linked to an encased
chain drive. A weaker motor joins each output side before full redstone
power is applied. Java transmits −256 RPM in the 64 RPM case. In the 96 RPM
case it breaks the gearshift when the chain would transmit −384 RPM, leaving
the output at −32 RPM from the backup motor. Removing the primary motors
tests reverse drive through the surviving gearshift, then removing the
signal restores its 1:1 ratio.

The two rigs are sampled at Java GameTest ticks 0–19 and compared from
tick 1, after Horizon publishes its first RPM. The comparison uses exact
values for block survival, ratio and signed RPM at both cogs, the
gearshift, and the output shaft. Capture from Create revision
`ac0c444d9828da3453ae8cc65338e8de063286fb` with Java 21 by applying
`tools/java-adjustable-chain-speed-limit.patch` in a disposable checkout,
running `./gradlew --offline runGameTestServer`, and taking the
`CREATE_CHAIN_SPEED_LIMIT` rows in order.

The capture patch SHA-256 is
`f4e2b95520ac9d1c50209043cc6d9f64364fdb49e04ed0149ed5b4e87b47ff6f`.
The Java capture passed its GameTest in 13 seconds and produced 40 rows.
The pre-fix Horizon build `native-9f42064-a5156e57df79` differed on all 13
samples of the 96 RPM case starting at tick 7. It retained the gearshift
and reported −384 RPM at the output through tick 11.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --check adjustable-chain-speed-limit
```

The chain placement replay covers each shaft axis and both perpendicular
chain axes. Each arrangement records three positions through nine stages,
starting with an unlinked placement and adding both ends. It checks removal
and restoration of an end and the middle, a neighbor with a different
perpendicular shaft axis, and a neighbor whose shaft points along the
chain and prevents a link. It compares the block type, shaft axis,
`axis_along_first`, `part`, and the gearshift's unpowered state. Both
blocks start with `axis_along_first=true` when placed unlinked. Linked
blocks calculate the value from their connection direction.

Capture the 54 `CREATE_CHAIN_PLACEMENT` rows by applying
`tools/java-chain-drive-placement.patch` to the pinned Java revision in
a disposable checkout and running `./gradlew --offline runGameTestServer`
with Java 21. The Horizon replay uses an offscreen client to place both
items through the normal input path and reads their block states after
each action.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --check chain-drive-placement
```

On rebuilt `native-9f42064-75906adc2576` with pack SHA-256
`1f6abc604c1840a87dd662eb616580b056d0cb3a4b3bbaf7fe8821e7ddb2be79`,
the mixed-cog speed-limit check passed all 38 Java samples in headless
mode. The adjustable gearshift replay passed 75 simulated ticks in both
directions offscreen. Placement matched all 54 snapshots offscreen; the
split snapshot advances one game tick after removing the middle link to
sample the settled neighbor state. The same offscreen replay submitted
chain-drive shaft geometry on all three axes in 5,253 frames; each frame's
rotation and shaft phase matched the renderer calculation.

The bounded save/reopen replay configures both gearshifts to analog signal 3.
It saves a connected but idle network and confirms signal, connection state,
and zero RPM after reopen. It then reconnects both motors, records each
gearshift/output speed and sign, saves while transmitting, and verifies the
same state across three post-reopen ticks. This follows Create's
`ChainGearshiftBlockEntity.write/read` persistence of `Signal`; it is a
Horizon gameplay save/reopen check, not an exact Java reload comparison.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --check adjustable-chain-persistence
```

The persistence check passed on `native-9f42064-75906adc2576` with the
`1f6abc60…` pack. The same final build passed the 75-tick gearshift replay,
the survival guest action, all 38 mixed-cog samples, all 54 placement
snapshots and the idle/active persistence replay. The issue shares
`native/machines.rs` kinetic-network
behavior with APP-1943; its existing Linear relation is retained. The
focused gearshift, LAN, mixed-size, placement/render, and persistence checks
all pass. Other layouts, lifecycle combinations, and exact cosmetic
animation parity remain outside this bounded delivery.

## Cogwheel placement

The ten-case Java reference compares normal small and large cog placement
with the clicked face, shaft preference, crouching, and small-cog alignment.
It checks two invalid gear contacts and verifies that the client still holds
both items when the server refuses placement. A large cog keeps source water,
while flowing water stays out of the placed block.

Eight additional cases exercise Java’s cog item placement assistance.
Rim clicks put equal small cogs beside each other, mixed sizes diagonally,
and an equal large pair on perpendicular axes. The replay covers an
obstructed closer diagonal, both diagonals blocked, shaft-end clicks,
and crouched placement. A live host and guest place the mixed and
perpendicular pairs, with matching inventory and final block positions.
The Java capture patch is `tools/java-cogwheel-rim-assist-trace.patch`
and its reference is `fixtures/cogwheel-rim-assist-java.csv`.

Five further cases use a Brass Encased Cogwheel as the clicked gear and
cover adjacent small gears, mixed diagonals, blocked or invalid nearer
diagonals, and axial fallback. The capture is
`tools/java-encased-cogwheel-rim-assist-trace.patch` and the reference is
`fixtures/encased-cogwheel-rim-assist-java.csv`.

`tools/java-cogwheel-placement-trace.patch` captures the comparison in
`fixtures/cogwheel-placement-java.csv`.

The pinned Create 6.0.10 axe and pickaxe block tags both include the small
and large cogs and all four encased variants. The headless mining-tag check
places each variant and queries both tags. Tool-specific break timing and
drop behavior need separate gameplay comparisons.

The bounded gameplay pass also checks a zero-speed idle large-to-small gear
train, a powered train at +24/-48 RPM, and save/reopen retention followed by
resumed operation. The existing gear-train fixture covers the -2 and +0.5
ratios and source removal/reconnection. Its 36 observations span ticks 0–35:
tick 0 is the frozen setup baseline, then each row samples one controlled server
tick. Each row compares the exact integer `Speed` values of ten shafts and
cogs. The motor is removed after sampling tick 10 and restored after tick 24;
disconnection is observed at ticks 11–24 and motion resumes at tick 25. The
competing-source fixture also checks a negative motor setting. The existing
encased-cogwheel LAN check covers guest shaft toggling and uncasing while the
host observes the resulting gear speed. Separate source-conflict coverage
remains linked to
[APP-1943](https://linear.app/appstu/issue/APP-1943/create-full-parity-kinetic-network-propagation-speed-stress-and).
Initial persistence fixture attempts were invalid: the helper steps one tick
per call, and the first rig omitted the motor's input shaft. After correcting
the harness and matching the existing Java gear layout, the persistence check
passed.

```sh
python3 tools/test-cogwheel-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --check cogwheel-mining-tags
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --check cogwheel-reopen
python3 tools/test-cogwheel-rim-assist.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-cogwheel-rim-assist.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --encased
python3 tools/test-multiplayer-cogwheel-rim-assist.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Shaft placement

Ten survival cases match Java’s aim and connected-shaft orientation,
crouching, and source-water placement. They also check extending an existing
shaft line in either direction, falling back when the nearer end is blocked,
extending with a cog, and switching ends when the nearer run reaches Java’s
default 12-block assist range.

`tools/java-shaft-placement-trace.patch` captures the reference in
`fixtures/shaft-placement-java.csv`.

```sh
python3 tools/test-shaft-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Shaft casing

A 12-tick replay applies Andesite and Brass Casings by hand to powered
shaft lines, then sneak-wrenches them back to plain shafts. Both lines retain
their axes, their 24 and 40 RPM output, and both items in the player’s casing
stack. The Andesite transition also removes source water from the shaft.
A separate host and guest repeat the two casing materials and guest wrench
removal on the server’s active network.

`tools/java-shaft-casing-trace.patch` records the Java comparison in
`fixtures/shaft-casing-java.csv`.

```sh
python3 tools/test-shaft-casing.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-shaft-casing.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Copper Valve Handle

The [Java angle trace](fixtures/copper-valve-handle-angle-java.csv) contains
93 samples at +95°, −137° and +1°. The replay checks the 180° settings board
with 45° milestones, opening on the sixth held input tick and committing the
selected angle on release. A shorter tap activates the handle on release
and sneaking reverses rotation. The tick trace compares hold duration,
cooldown, target angle, and the signed RPM at the handle and attached shaft.
A live survival guest set −137° and produced the same pulse on the host.

The [placement trace](fixtures/copper-valve-handle-placement-java.csv)
covers six mount faces, retaining source water, orienting away from a
preferred neighboring shaft and overriding that preference while sneaking.
Player picks hit the original center plane of all six directional plates.
The [Java GameTest patch](tools/java-copper-valve-handle-trace.patch)
reproduces both traces.

All 16 colors retain the selected angle, facing, source water and dye stack
when applied in-world. A survival guest recolored a wet handle and then used
it to power the attached shaft. Survival crafting verified all 16 shapeless
recolors and converting a dyed handle back to copper. All 48 item models,
block models and textures match the original asset bytes.

The [dyed valve replay](tools/test-dyed-valve-handle.py) compares 252
speed, capacity and use-duration samples across three control setups. When
recolored during use, the mounted handle resets its speed on the color
change tick. With a spinning rear shaft, the two become each other's source
and keep turning at zero stress capacity after the handle's timer expires.
A handle mounted on stone stops delivering power at recolor. The unchanged
shaft-mounted control stops when its timer expires. The rendered angle and
sub-tick interpolation match 17 active samples from the
[Java GameTest patch](tools/java-dyed-valve-handle-trace.patch).

The [release-action trace](fixtures/valve-action-ticks-java.csv) checks 48
samples with both directions and an attached large and small cogwheel.
The shaft and large cog receive ±32 RPM at release, and the small cog
gets the opposite direction at 64 RPM. All four pieces settle with the
original cooldown and stop timing.

The [support-removal fixture](fixtures/valve-support-removal-java.csv)
compares dry copper, wet copper, and a wet dyed handle. Changing a front
neighbor leaves the handle intact. Breaking the rear support drops one
handle immediately and restores source water for both wet cases. The
[Java GameTest patch](tools/java-valve-action-trace.patch) captures both
fixtures.

## Sequenced Gearshift

Players can scroll an instruction, its parameter, and the speed direction
for each row in the original five-row editor. Its atlas matches Java's
asset bytes. The [editor replay](tools/test-sequenced-gearshift-editor.py)
writes a 45° turn at double speed, a four-tick delay, a redstone wait, a
one-meter reverse move at double speed, and End. The program matches
Java's saved instructions and all 44 [runtime samples](fixtures/sequenced-gearshift-editor-java.csv).
The shaft receives +64 and −64 RPM at the matching points in the program.
A live survival guest saved the same program and started it on the host.

A shaft held against a horizontal or vertical shaft end places onto the
original axis without opening the editor. The kinetic placement bypass
uses the items identified by Java's registry. The
[Java GameTest patch](tools/java-sequenced-gearshift-trace.patch) captures
the program, runtime, and placement references.

A physical comparator follows each displayed instruction after two ticks.
Saving while the sequencer runs stops its output shaft on the save tick.
The powered step stays visible until the redstone input goes low. An
independent survival guest repeated the active save and both clients
saw the same delayed step and comparator output. The
[44-sample replay](fixtures/sequenced-gearshift-comparator-java.csv) and
[Java GameTest patch](tools/java-sequenced-gearshift-comparator-trace.patch)
cover the powered turn, delay, redstone wait, distance step and active save.

The [reload replay](tools/test-sequenced-gearshift-reload.py) saves an idle
configured program and an active turn, closes and reopens the same world, then
checks the persisted Java fields and continuation from tick 5 to tick 6. The
[metadata](fixtures/sequenced-gearshift-reload-java.metadata.json) records the
pinned Java BlockEntity read/write fields and links the active checkpoint to
the existing Java GameTest trace. Other instruction types and persistence
boundaries remain open.

On rebased `origin/main` (`1f2f317`),
`sh tools/build-native.sh /Applications/Horizon.app/Contents/MacOS/horizon-launcher
'/private/tmp/horizon-create-app1949-build'` produced build
`native-9f42064-f1e8907217b7`. The sequenced-gearshift parity group passed all
11 checks using that build's `horizon-ctl` and `horizon-client` binaries:
editor, render, LAN editing, comparator, stop, reload, gantry distance limit,
orientation and Wrench. The reopened active sequencer
matched Java's tick-6 state on its first resumed tick. On the same build, the
sequenced pulley consumer trace passed, as did 13 affected piston, gantry,
roller and bearing regressions (including piston modes, moving actors and
reload, both mounted dispenser cases, both roller tracks, and the 105-tick
contraption-controls trace). Checks that did not need rendering used the
headless client.

The [sequenced gantry replay](tools/test-sequenced-gearshift-gantry.py) uses
the existing roller-filling fixture's live motor, gearbox, pinion and carriage.
It verifies that a 1-block sequence at 128 RPM stops the downstream 32 RPM
gantry at 0.25 blocks, following Java's relative distance context through the
gearbox, then restores the carriage. This headless check passed on
`native-9f42064-f1e8907217b7`. The
[sequenced piston replay](tools/test-sequenced-gearshift-piston.py) checks
during-motion offset plus remaining distance, then verifies the piston settles
at the 1-block endpoint after the sequence finishes. It also passed on that
exact build. Full 1:1 remains open.

## Gantry gameplay baseline (APP-2002)

The bounded baseline reuses the live roller-filling fixture and covers idle
assembly rejection, an idle save/reopen, a survival LAN guest switching the
drive lever, host and guest convergence on the powered state, carriage
movement, and a moving save/reopen that resumes along the shaft. The reload
case exposed that loaded gantry shafts have no kinetic ticker to rebuild their
network after the saved kinetic cache is empty. `power_shafts` now refreshes
those loaded shaft networks once, when their kinetic data is empty.

The [LAN and reload check](tools/test-multiplayer-gantry.py) passed on build
`native-9f42064-b9c58fb2733d` with pack SHA256
`b0b0640e75dc76ad6ba61dc8a83c868cf98f1ed0c668fdc0b87acba5504b60`. The
same build passed the selected regression batch 9/9: gantry LAN reload,
sequenced gantry distance, dispenser source/neighbor behavior, roller filling
and paving/clearing, redstone contacts, observer belt funnel, and contraption
controls. This supplements the existing sequenced gantry check, which compares
the 0.25-block limit with the pinned Java sequencer and gantry sources. The
guest check verifies state convergence; it does not measure Java packet or
interpolation timing. Additional loads, actors and layout transitions remain
untested, and Full 1:1 remains open.

When the original threshold-switch pulley finishes its rotation while the
lever remains powered, the downstream pulley stops and the gearshift retains
64 RPM. The [original fixture](fixtures/threshold_switch_pulley-java.csv)
matches all 56 Java ticks, including the pulley settling and switch output.

Normal hand placement matches [eight Java cases](fixtures/sequenced-gearshift-orientation-java.csv)
with horizontal and vertical aim, adjacent shafts, conflicting axes and
sneaking. The [Wrench replay](fixtures/sequenced-gearshift-wrench-java.csv)
covers every face for each of the four stored orientations. A survival guest
rotated the host's gearshift and picked it up with one crouched click. Both
players saw the new orientation and the removal. The
[Java GameTest patch](tools/java-sequenced-gearshift-orientation-trace.patch)
captures placement, Wrench rotation and pickup.

Both original shaft halves animate through the sequential program.
[88 Java samples](fixtures/sequenced-gearshift-render-java.csv) cover a
horizontal program with both directions, a vertical gearshift's default
turn, pauses and an active save. The submitted native corners turn at
Java's signed rates and positional phase. Both live clients saw the guest
start the +64 RPM output and stop the insert again on the save tick. The
[Java GameTest patch](tools/java-sequenced-gearshift-render-trace.patch)
captures the per-side reference.

## Clutch and Gearshift

[Fourteen hand placements](fixtures/clutch-gearshift-placement-java.csv)
match Java for horizontal and vertical aim, preferred and competing adjacent
shaft axes, sneaking, and existing redstone power. The
[Wrench replay](fixtures/clutch-gearshift-wrench-java.csv) covers every face
for each axis on both blocks. Crouched clicks return one item of each type
in survival. A survival guest placed a powered Clutch and picked it back up,
with both clients seeing the same powered state and removal. The
[Java GameTest patch](tools/java-clutch-gearshift-trace.patch) captures these
cases and the redstone traces.

The [54 state and RPM observations](fixtures/clutch-gearshift-timing-java.csv)
cover each lever action and the following ticks. Both blocks keep their input
speed on the action tick, while the output stops immediately. A closing
Clutch and a newly reversed Gearshift reconnect on the following tick. The
Clutch keeps its original input when a faster motor starts across the open
side, loses rotation when the old input is removed, and takes the other
source when reconnected, matching all [19 observations](fixtures/clutch-competing-java.csv).
A host and guest operated the same Gearshift lever and saw the power changes.
On the host the shaft dropped to zero on each actor's click and switched to
−32 or +32 RPM on the following tick.

The casings and half-shafts use byte-identical Java models. Both inserts
match Java's phase, speeds and angle at the submitted sub-tick fractions
in [54 horizontal render samples](fixtures/clutch-gearshift-render-java.csv).
Gearshift's output insert reverses on the lever action, and Clutch's stops
while the input insert keeps turning. Both actual LAN renderers submitted
the same Gearshift motion on the host's and guest's lever actions.
The solo client and LAN guest each matched another 84 offscreen samples
on `native-9f42064-5feaea81a3da`. The checks cover source face, RPM,
phase, angle and both shaft-half draws for both blocks on all three axes
and from both source directions at the submitted frame fraction 1.0.
[Java axis samples](fixtures/transmission-render-axes-java.csv) ·
[Java capture metadata](fixtures/transmission-render-axes-java.metadata.json)

The headless replay for a Clutch closing into a second drive through a
Gearshift matched all 26 Java samples on `native-9f42064-fa80052f1dec`.
Both horizontal Clutches closed on tick 8 and kept +32 RPM. On tick 9,
the Clutch facing an opposing drive broke and dropped one item. The
powered Gearshift reversed the other drive and let its Clutch take
+64 RPM. The unchanged `native-9f42064-a5156e57df79` kept the opposing
Clutch at −64 RPM through all four samples on ticks 9–12. The Java tick
origin is the first sample after the left motors were set to +32 RPM.
Each sample records block state, theoretical RPM and dropped item count
after the scheduled or lever action for that tick.
[Java reconnect samples](fixtures/clutch-gearshift-reconnect-java.csv)

Breaking the two Gearshifts after the last reconnect sample dropped
one item in both power states. Horizon sampled the outcome one tick after
the break command. Pack preparation now translates the Java explosion
survival condition for both blocks. The two loot tables were the only
changes among 9,258 entries. The rebuilt pack SHA-256 is
`5b4d4ee88226ae8b55dacb341e14c8906e13b9ff028e6f079994a1e548cd4cc0`.
The pinned Java GameTest took 22 seconds with JDK 21. The same Horizon
build and pack passed the five existing timing, competing-input, and
solo and LAN render checks. The six Horizon checks took 65 seconds.
[Java Gearshift drop outcomes](fixtures/clutch-gearshift-drop-java.csv) ·
[GameTest patch](tools/java-clutch-gearshift-reconnect.patch) ·
[Reference revisions and hashes](fixtures/clutch-gearshift-reconnect-java.metadata.json)

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --check clutch-gearshift-reconnect
```

On `native-9f42064-f8f56d21ecc8` with the same pack, Clutch and Gearshift
matched all 84 samples on X, Y and Z when an adjacent redstone block was
placed or removed on four consecutive ticks. Each block held +32 RPM
at the gate. The output stopped on each power change and resumed or
reversed on the following tick when the block state allowed transmission.
[Consecutive redstone replay](fixtures/clutch-gearshift-consecutive-java.csv)

A new Gearshift between two independently rotating drives held zero RPM
on the placement tick, then broke and dropped one item on the following
tick when the drives opposed the new ratio. The compatible Gearshifts
acquired the positive-axis source and −64 RPM. Both activating redstone
after the block was placed and placing the item against an existing
redstone block matched Java on X, Y and Z. The updated build matched
108 state, RPM and drop samples and all 54 block entity presence, source
and RPM samples from the hand placements. The preceding
`native-9f42064-bc1b4f4d38cf` differed in 18 of 54 samples for each route.
The five headless gearing replays took 91 seconds.
[Java direct redstone](fixtures/gearshift-two-sources-java.csv) ·
[Java powered placement](fixtures/gearshift-powered-placement-java.csv) ·
[Java block entities](fixtures/gearshift-powered-placement-entities-java.csv) ·
[Java patch and capture metadata](fixtures/transmission-transition-java.metadata.json)

The updated build passed three offscreen render replays. The host and
guest drew both Clutch inserts with +32 RPM input and zero output while
powered, then +32 RPM on both halves after the guest closed the Clutch.
Gearshift and Clutch both matched the sampled shaft angles. These
comparisons use eventual guest render samples.
[Split-shaft render checks](tools/test-clutch-gearshift-render.py)

The headless vanilla Crafter accepted both original shapeless recipes,
consumed all three ingredients, and placed one block into the output chest.
Without redstone it kept the other two ingredients and produced no output.
The survival menu driver required a renderer for slot clicks.
[Original Java recipes](fixtures/clutch-gearshift-recipes-java.json)

A headless cold reopen matched 54 Java records from separate save and
reopen processes. Four driven X-axis rigs kept the west input at +32 RPM.
Their outputs remained +32 RPM when unpowered, zero through the powered
Clutch, and −32 RPM through the powered Gearshift. One undriven Clutch and
one undriven Gearshift kept their block entities and output shafts at zero
RPM with no source. The test samples the stable state before shutdown and
eight ticks after startup.
[Cold reopen samples](fixtures/clutch-gearshift-cold-reopen-java.csv) ·
[Java capture setup](fixtures/clutch-gearshift-cold-reopen-java.metadata.json)

The mixed Clutch and Gearshift chain matched all 60 headless samples on
the updated build. Each X-axis device order was tested with the upstream
redstone change first and with the downstream change first. The test
sampled each callback on the same tick, the intervening shaft's RPM, and
the scheduled reconnection on the following tick.
[Mixed callback samples](fixtures/clutch-gearshift-mixed-callbacks-java.csv) ·
[Java capture metadata](fixtures/clutch-gearshift-mixed-callbacks-java.metadata.json)

Another 60 headless samples matched Java when a Z-axis Gearbox carried
the drive from an X-axis transmission into a Y-axis transmission. The
four rigs exercised both device orders and both redstone callback orders.
[Java Gearbox bend samples](fixtures/clutch-gearshift-mixed-bend-java.csv) ·
[Java capture metadata](fixtures/clutch-gearshift-mixed-bend-java.metadata.json)

On `native-9f42064-d8c0290a2281`, two Mechanical Presses on a Hand Crank
matched all 34 Java overload samples. A Clutch placed already powered
kept driving the input at −32 RPM while the presses were isolated.
Closing it overloaded the shared drive. Reopening it stopped the
presses immediately and restored the input speed after the next stress
update. The Gearshift reversed the theoretical press RPM while the
effective speed stayed at zero. The earlier build differed in six
samples across crank actuation, powered isolation and recovery.
[Overload trace](fixtures/clutch-gearshift-overload-java.csv) ·
[Java capture metadata](fixtures/clutch-gearshift-overload-java.metadata.json)

On `native-9f42064-65c9b559787b`, initialized Gearshifts with adjacent
Creative Motors matched 90 Java samples across all three axes. The
64-RPM motor took over from the 32-RPM motor before two redstone changes.
The weaker motor stopped on each action tick and resumed at the conveyed
speed on the next tick. The previous build continued publishing +32 RPM
for the weaker motor in all 12 action samples.
[Initialized Gearshift samples](fixtures/initialized-gearshift-java.csv) ·
[Java capture metadata](fixtures/initialized-gearshift-java.metadata.json)

The headless Wrench replay matched Java event IDs and counts on all 38
actions. Rotating either block played one cue, clicking along its axis
was silent, and each survival pickup played both removal cues.
[Wrench sound events](fixtures/clutch-gearshift-wrench-audio-java.csv) ·
[Java capture metadata](fixtures/clutch-gearshift-wrench-audio-java.metadata.json)

Both hidden LAN clients matched the Java Clutch break boundary and the
single dropped item. Both drew the Clutch and Gearshift before reconnection.
The Gearshift continued drawing after the scheduled break and neither
client submitted the removed Clutch's shaft halves.

The scheduled Clutch break played Java's stone break cue once on tick 9
in headless solo and on both hidden LAN clients. Both Gearshift conflict
replays matched three stone break cues on tick 5, one per axis. The
direct Horizon destroy-command replay omitted the two Gearshift break
cues emitted by Java's `level.destroyBlock`.
[Java break effects](fixtures/transmission-break-effects-java.csv) ·
[Java capture metadata](fixtures/transmission-break-effects-java.metadata.json)

On `native-9f42064-5feaea81a3da`, two X-axis Clutches closed on the save
tick between adjacent Creative Motors. After cold reopen, the opposing
motor broke and its Clutch retained +32 RPM. The compatible rig kept both
motors at +64 RPM. Two initialized Gearshifts reversed on their save tick.
On reopen each kept its ±64 RPM input, and each formerly subordinate
motor broke. The four headless replays matched all 32 saved and settled
observations with block drops enabled and disabled. Earlier builds kept
the opposing motors across three Clutch and six Gearshift post-reopen
observations.
[Java pending Clutch samples](fixtures/clutch-pending-reopen-java.csv) ·
[Clutch capture metadata](fixtures/clutch-pending-reopen-java.metadata.json) ·
[Java pending Gearshift samples](fixtures/gearshift-pending-reopen-java.csv) ·
[Gearshift capture metadata](fixtures/gearshift-pending-reopen-java.metadata.json)

The headless command harness sampled the saved game time and the first
two explicit simulation ticks on `native-9f42064-01ed5c97c72e`. All 24
Java state, RPM and motor-presence observations matched across the
original and mirrored adjacent-motor layouts. Java checks the dependent
Gearshift motor's configured speed against its conveyed speed as signed
values. The +32 motor driven at −64 broke on the first restored tick.
The mirrored −32 motor driven at +64 remained in the network. The previous
native build reached the first block-entity tick before its pending check
could see the restored entities. The new check runs before motor startup
also when the entity ticker table is still being built.
[Mirrored Clutch startup](fixtures/clutch-pending-reopen-mirrored-java.csv) ·
[Clutch capture metadata](fixtures/clutch-pending-reopen-mirrored-java.metadata.json) ·
[Mirrored Gearshift startup](fixtures/gearshift-pending-reopen-mirrored-java.csv) ·
[Gearshift capture metadata](fixtures/gearshift-pending-reopen-mirrored-java.metadata.json)

The loaded opposing-motor break uses the regular native loot result first.
If it returns no stacks with block drops enabled, the captured break path
emits one motor item. The shipped pack remains byte-identical. An explicitly
empty custom motor loot result also triggers this scoped fallback.

Final focused verification used the client reinstalled by
`tools/build-native.sh` as `native-9f42064-01ed5c97c72e`. Its content-addressed
ID is unchanged because the native inputs match the previously validated
source; the previous version directory was archived before rebuilding. The
eight headless gates passed: cold reopen, mixed callbacks, mixed Gearbox bend,
overload, both pending first-tick directions, recipes and host/guest actions.
Four hidden offscreen checks passed: guest axis rendering, Clutch break
rendering, and both settings cursor-warp cases. Client SHA-256 is
`e5ddb923ca11ae2a28e71da91e967dc84c7161f8600cc0abe45f81f871ba0da3`,
controller SHA-256 is
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`, and
the prepared pack SHA-256 remains
`5b4d4ee88226ae8b55dacb341e14c8906e13b9ff028e6f079994a1e548cd4cc0`.

Other mixed networks, initialized transitions with other load and source
combinations and pending reload layouts still need direct comparisons.
The exact queued callback lifetime and wider startup ordering remain
open. Measuring break gain, pitch and debris requires event-specific
client telemetry. Shared kinetic ambience remains open.

## Vertical Gearbox

The Vertical Gearbox is a separate inventory item with the original model
and recipes. [Nine Java placement cases](fixtures/vertical-gearbox-java.csv)
cover ordinary Gearbox, facing, adjacent shafts, conflicting axes, sneaking
and a powered Clutch. Creative pick, mining with the proper tool and
survival Wrench pickup each return the correct item for all three axes.
Both one-to-one conversions and the shaped four-cog recipe craft in
survival. A real guest placed and recovered the Vertical Gearbox beside
a powered Clutch, and the two clients agreed on its orientation and item.
The [Java GameTest patch](tools/java-vertical-gearbox-trace.patch) captures
the placement and tool reference.

The four original shaft inserts rotate around the Gearbox's open faces.
[576 Java samples](fixtures/gearbox-render-java.csv) exercise all twelve
combinations of casing axis and incoming face, including forward and
reverse rates. The driven shafts and the submitted render geometry match
the rates, positional phase and angle. The host and guest configured the
same motor to +64 and −24 RPM and both rendered all four matching sides.
The [Java GameTest patch](tools/java-gearbox-render-trace.patch) captures
the original per-side reference.

A regular or sticky piston can push the Gearbox without changing its axis.
A sticky piston leaves it in place when retracting. The [104 Java observations](fixtures/gearbox-piston-java.csv)
include both Gearbox item orientations and two vanilla piston controls.
The restored Gearbox and connected shaft first spin on the tick after it
lands. A live guest operated the piston with its lever and both clients
observed the Gearbox in its new position. The [Java GameTest patch](tools/java-gearbox-piston-trace.patch)
records the piston and kinetic states.

The [family comparison](GEARBOX-PARITY.md) records the mechanical piston
endpoint replay, multi-Gearbox source handoff, Wrench transforms in solo and LAN,
and save/reopen coverage.

## Stockpile Switch editor

The editor uses Java’s original atlas and exposes both thresholds, the
Items/Stacks selector, and signal inversion. Host and guest opened it with
a normal click and matched [42 initialized Java ticks](fixtures/stockpile-switch-editor-java.csv)
while they changed the settings of a switch attached to a barrel.
Inversion affected the output on the action tick, and changes in stock
took effect after Java’s two-tick redstone delay.
The [Java GameTest patch](tools/java-stockpile-switch-editor-trace.patch)
uses Create’s original configuration packet handler.

A Fluid Tank reports bucket thresholds in steps of 1,000 millibuckets.
A Rope Pulley reports absolute Y levels, including negative values.
[84 Java observations](fixtures/stockpile-switch-targets-java.csv) match both
targets’ readings, edited settings and output on each initialized tick.
The host and a live guest each configured both targets through the editor.
The [Java GameTest patch](tools/java-stockpile-switch-targets-trace.patch)
captures the fluid and negative-height cases.

[12 Java hand-placement cases](fixtures/stockpile-switch-placement-java.csv)
cover all six faces, a fluid target, competing inventories and the fallback
when sneaking or when no inventory is present. A guest installed the switch
against a barrel, and the host measured its 32 items on the first tick.
The [Java GameTest patch](tools/java-stockpile-switch-placement-trace.patch)
uses stock item placement.

The Wrench matches [36 Java face rotations](fixtures/stockpile-switch-wrench-poses-java.csv).
[25 initialized ticks](fixtures/stockpile-switch-wrench-ticks-java.csv) cover
turning a stocked switch, the temporary difference between its displayed
mount and sampled target, the resulting redstone and survival pickup.
Both a host and a live guest performed those actions. The
[Java GameTest patch](tools/java-stockpile-switch-wrench-trace.patch)
exercises the original rotate and pickup methods.

A click inside the original filter slot selects or clears its sample.
A click beside it opens the editor. [72 Java cases](fixtures/stockpile-switch-filter-poses-java.csv)
cover each mount, face and pointer position. The host and guest each
matched [40 action and follow-through samples](fixtures/stockpile-switch-filter-ticks-java.csv)
for item and bucket filters while keeping the ordinary samples in hand.
The [Java GameTest patch](tools/java-stockpile-switch-filter-trace.patch)
calls the original input event handler.

The selected sample renders on the original slot faces. A flat bucket and a
stone block each matched [18 Java slot transforms](fixtures/stockpile-switch-filter-transform-java.csv)
and submitted item geometry. When a guest selects a sample, both players see
it on all three active faces of the tested wall-mounted switch.

## Smart Observer filter

The [72 original slot cases](fixtures/smart-observer-filter-poses-java.csv)
exercise all mounts, block faces and pointer positions. Real host and guest
clicks each matched [56 Java observations](fixtures/smart-observer-filter-ticks-java.csv)
of the selected sample, countdown and redstone output for a solid block and
an inventory. Both peers rendered the guest's sample on the two original
faces of the tested wall-mounted observer. The [Java GameTest patch](tools/java-smart-observer-filter-trace.patch)
uses Create's original input event and behavior.

[15 Java placements](fixtures/smart-observer-placement-java.csv) cover six
inventory mounts, competing neighbors, free placement, a tank, a depot,
a pipe and a funnel. A guest placed an observer that detected its barrel on
the first tick. [36 Wrench rotations](fixtures/smart-observer-wrench-java.csv)
retain the mounted sample and the current redstone countdown. The host and
live guest each matched [six recovery cases](fixtures/smart-observer-recovery-java.csv),
including the Observer's centered List Filter drop with zero pickup delay,
ordinary block loot, and immediate Wrench inventory pickup. The Java
reference keeps the stored List Filter absent from Stockpile Switch drops.
The [mounting GameTest patch](tools/java-smart-observer-mounting-trace.patch)
captures the original placement, Wrench, and loot behavior.

A configured List Filter uses its saved whitelist or blacklist for detector
items and fluids. Each host and live guest matched [125 Java readings](fixtures/detector-list-filter-java.csv)
while changing or clearing the list against a solid block, barrel and water
or lava tanks, including the Stockpile Switch's immediate water reading and
delayed redstone. The [List Filter GameTest patch](tools/java-detector-list-filter-trace.patch)
drives the original filter interaction and world ticks.

A Smart Observer reads the Depot's held item once it reaches the transport
slot's detection range. The host and guest each matched
[78 Java observations](fixtures/observer-depot-java.csv) of placement,
removal, item filtering, the redstone countdown, and the separate processing
buffer. The [Depot GameTest patch](tools/java-observer-depot-trace.patch)
uses the original placement and retrieval interaction.

Attribute Filter, Package Filter and Brass Nugget appear in the Create
creative tab with the original models and English names. Both host and guest
matched [six Java survival recipes](fixtures/filter-recipes-java.csv), including
Brass Ingot and Nugget conversions, each wool filter recipe and the reset of
configured filter data. The [Java recipe patch](tools/java-filter-recipes-trace.patch)
samples the original crafting grid and its remainders.

The Package Filter address screen now opens from its main-hand item. A host
and a live guest each matched [seven original address saves](fixtures/package-filter-editor-java.csv)
across confirm, reopen, blank text, and reset. The same replay checks the
25-character input limit and moves a real player stack with the cursor while
preserving the selected filter. The [Java GameTest patch](tools/java-package-filter-editor-trace.patch)
uses the original menu, packet, and save-on-close behavior.

Four cardboard and ten rare package forms use their original item models, and
each forms a separate stack. Host and live guest matched
[40 Java Package Filter cases](fixtures/package-address-java.csv) in detector
inventories with 120 item, exact-component, and fluid readings each. The cases
include empty and configured filters, bidirectional wildcard matching, character
sets, alternatives, negation and Unicode. The players also set and applied a
filter through the address editor and detector. The
[Java GameTest patch](tools/java-package-address-matching-trace.patch) records
the original filter decisions and item registrations.

All 14 package forms follow Java’s nesting rule in Bundles and Shulker Boxes.
A host and a live LAN guest each matched 48 original Java actions through
the inventory cursor and placed Shulker menu, including Stone and Shulker
control stacks. The [Java GameTest patch](tools/java-package-nesting-trace.patch)
captures the original Bundle insertion and Shulker slot decisions.

Crouch-clicking opens a held package on a Stone face or in the air. A host and
a live LAN guest each matched seven original Java actions on the same world
tick, including both hands, survival and creative, named cargo, full inventory
overflow, and spawning a pig. Every connected client played both original
sound layers at the captured positions, gains, and pitches.
The [Java GameTest patch](tools/java-package-open-trace.patch) records the
inventory, overflow, spawn, and actual server sound events.

Right-clicking a block with a package places a physical entity with the
original model, box dimensions, and exact cargo. A host and a live LAN guest
each matched 36 original Java cases across all six faces, three package
forms, and survival and creative modes. The replay checks the original
offset from the actual hit, refusal when another package overlaps, and
empty-hand recovery with nested cargo intact. A supported rare package also
retained its UUID, position, yaw, address, and cargo after a save and reopen.
The [Java GameTest patch](tools/java-package-world-trace.patch) captures the
placement and overlap decisions. Frozen builds reproduced an extra
throw after some placements. Horizon now marks a clear package click
as consumed on the LAN client using the same fit check as the server.
On `native-9f42064-3dd37c693802` with the creative-tab pack, the
[original input replay](tools/test-package-placement.py) matched all
36 cases in solo and LAN, and the authority traces contained exactly
36 spawns per run. The blocked click still falls through to normal
charge handling, as it does in Java. On
`native-9f42064-69fd2b989c04` both full real-click runs hit a blocked
repeat whose input lasted long enough to trigger a charge throw. A
direct collision test and the duration of the real click are separate
observations. A [direct single-packet authority replay](tools/test-package-placement-authority.py)
on `native-9f42064-69fd2b989c04` with the creative-tab pack matched
the six Java top-face cases across three styles and both game modes.
It compared exact position, dimensions, stored item and count, then
confirmed that the rejected repeat retained the stack and left one
package. On `native-9f42064-f2fcebd19cb9` with the creative-tab
pack, the [guest single-packet replay](tools/test-package-placement.py)
matched all 36 Java cases through a real LAN connection. It covered six
faces, three styles, both game modes, exact cargo, blocked repeats
and empty-hand pickup using the normal mouse path. The host logged
36 spawns and zero charge records. The live replay now measures the
release interval on the authority and checks the appropriate Java
outcome. A blocked click released before three authority ticks retains
the stack and original package. A longer charge may throw one
additional package. The replay checks its complete stack, dimensions,
owner, and Java-derived launch speed, as well as the original pickup.
All 36 corrected live cases passed in each of solo and LAN on the same
candidate. Separate delayed survival and creative inputs both released at
eight ticks and matched their throws and inventory outcomes. The fixture
correction changed no runtime behavior. Logs and authority traces are
in the overnight dossier under `package-live-tap-evidence/final-corrected/`.

The [charged throw replay](tools/test-package-throw.py) matched all 12
nonzero [Java charge cases](fixtures/package-throw-java.csv) in solo and
with a real LAN guest on `14bca3ad3dc0`. It compares consumption,
initial position and velocity, the complete addressed item, and its
thrower UUID. A two-tick hold leaves the Package in hand. A three-tick
hold throws it, and the speed caps at twenty ticks. The throw leaves
the creative player's stack intact. The two zero-charge capture rows
are verified by the charge calculation. The live input replay starts
at two ticks.

A full throw matched all [13 Java unlanded frames](fixtures/package-flight-java.csv)
in both modes. Actual playback matched the [original cues](fixtures/package-throw-sound-java.csv)
on the acting client and the observing LAN host, including source,
position, volume, pitch and the silent short holds. The [pinned Java
probe](tools/java-package-world-trace.patch) captures all three traces.
Thrown-entity client interpolation beyond the sampled authoritative
flight and the remaining collision paths are still open.

The [world drop replay](tools/test-package-drop.py) verified that the
regular and Creeper Packages become live packages when dropped with
the drop key in both solo and LAN on `e081986d3c71`. Both clients saw
the replacement without an ordinary item entity. The component payload
and spawn position are preserved, and motion scales by the original
factor of 1.5. A powered Dropper sent the Package into a Chute with
the original right-angle yaw in both modes. The [Java drop reference](fixtures/package-drop-java.csv)
also records the simulated give effect discarding on its first tick.
The live drop checks cover the drop key and the Dropper path.

The [physical Package damage replay](tools/test-package-destruction.py)
matched nine [Java damage cases](fixtures/package-destruction-java.csv)
and the equivalent kill command in solo and with a real LAN guest on
`29a89691b39a`. Bare-hand attacks, generic damage, explosions, and contact
with water or waterlogged blocks destroyed the package, spilled the original
cargo, hatched a pig, and played both original pop layers on each connected
client. Packages survived fall damage. Void damage and kill removed the
package with its contents. The
[Java GameTest patch](tools/java-package-destruction-trace.patch) records
removal, cargo, and server sound events.

The [Package fire replay](tools/test-package-fire.py) matched all
[278 original frames](fixtures/package-fire-java.csv) in solo and with a
live LAN guest on `3cfeefd69f2e`. The cases cover an isolated ignition,
repeated fire damage, campfire, open flame, lava, and a fire-resistant
package. The host's fire timer and health matched Java, and both clients
observed the original destruction tick and cargo. The
[Java GameTest patch](tools/java-package-fire-trace.patch) captures the
contact and damage sequence.

The [Package arrow replay](tools/test-package-arrow.py) matched 25 original
frames in solo and with a live LAN guest on `e3b18cf882bb`. Ordinary and
flaming arrows broke the package and rebounded on the original tick. A
Piercing I arrow broke the package and hit the pig behind it in the same
tick. An Adventurer's shot and a shot at an invulnerable package left the
cargo sealed. The [Java GameTest patch](tools/java-package-arrow-trace.patch)
records the arrow's position and velocity, package removal, and the two
targets. Other projectile types still need parity checks.

The [Package Chute replay](tools/test-package-chute.py) matched
[92 Java frames](fixtures/package-chute-java.csv) in solo and with a live
LAN guest on `9dcc69c69319`. A physical Package began centering on the
first contact tick and entered either an open Chute or an open Smart
Chute at tick 20 with its complete addressed cargo. An occupied Chute
and a powered Smart Chute kept the Package outside while it continued
centering. The [Java GameTest patch](tools/java-package-chute-trace.patch)
records the positions, yaw, motion, removal tick, and receiving stack.

The [Package Depot replay](tools/test-package-depot.py) matched
[46 Java frames](fixtures/package-depot-java.csv) in solo and with a live
LAN guest on `afa0344ee71f`. The empty Depot caught the physical Package at
tick 20, held the complete addressed contents at its center, and played
the original plop on both clients. An occupied Depot kept its stack while
the Package continued centering and played no cue. The
[Java GameTest patch](tools/java-package-depot-trace.patch) records the
contact, insertion, and sound timing.

The [Package Weighted Ejector replay](tools/test-package-depot.py) matched
[96 Java frames](fixtures/package-ejector-java.csv) in solo and with a live
LAN guest on `cb2395e1ea93`. A charged empty pad caught the addressed Package
at tick 20 without a Depot plop. An occupied or retracting pad continued
centering the Package outside it. When a launch started while a loose
Package was on the pad, the lid advanced through launching and retracting
without sending the Package into flight. The
[Java GameTest patch](tools/java-package-ejector-trace.patch) records the
pad phases, pose, velocity and receiving stack.

The [horizontal Belt Package replay](tools/test-package-belt.py) matched
[108 Java frames](fixtures/package-belt-java.csv) in solo and with a live
LAN guest on `1462263813c0`. Each contacting tick centered the loose
Package twice. The Belt accepted it on tick 11 with its address and
nested contents, then transported it in the chosen direction. A stopped
Belt still accepted the Package, retaining the insertion offset from its
last direction. The [Java GameTest patch](tools/java-package-belt-trace.patch)
records both travel directions and the matching stopped cases. Sloped
Belts and carried Package graphics need separate checks.

The [stationary Funnel Package replay](tools/test-package-funnel.py) matched
all [182 Java frames](fixtures/package-funnel-java.csv) in each of solo and
live LAN on `6b7378daea93`. Wall-mounted Brass and Andesite Funnels accepted
the physical Package on tick 15. The floor case accepted it on tick 19.
Full storage continued centering the Package. A mismatched filter, powered
Funnel and extracting Funnel left its path unchanged. The replay compares
position, velocity and the receiving contents. Both ordinary stationary flap
directions also matched their 21 rendered samples and sounds per LAN client.

The [physical Package stacking replay](tools/test-package-stack.py) matched
all [125 Java frames](fixtures/package-stack-java.csv) in solo and with a live
LAN guest on `daabfba12364`. A falling Package rested on the 12×12 lower
Package at tick 6 and the 10×8 lower Package at tick 7. An x offset of
0.68 blocks still produced a stack. An x offset of 0.70 blocks and the
pig control both reached the floor on tick 8. The guest saw each settled
Package position. After the wide stack’s world reopened, both Packages
kept their settled positions over ten more authoritative ticks.

The [Package vertical contact replay](tools/test-package-vertical-contact.py)
matched all [48 Java authority samples](fixtures/package-vertical-contact-java.csv)
in solo and LAN on `9c577a1439d3`. An ordinary mob overlapping from above
leaves the Package’s own push impulse intact. Level and lower contact
apply both original impulses, and the separated control stays still.
Live guests observed the displacement where it occurred. A fresh guest
received the final authoritative Package position in each frozen scene.
The moving guest’s original interpolation timing still needs its own replay.

The [throw owner replay](tools/test-package-contact-owner.py) matched
[32 Java samples](fixtures/package-contact-owner-java.csv) in solo and
live LAN on `8fd28a1355c0`. An ordinary mob cleared the owner on contact,
including from above when the Package’s own impulse stayed active. A
separate Package and clear space preserved the owner.

The [survival player contact replay](tools/test-package-player-contact.py)
matched [24 Java samples](fixtures/package-player-contact-java.csv)
in each headless role on `34f0b58f5120`. A touching player cleared the
throw owner. Level contact also moved the Package before its travel step.
The separated control kept its owner and pose. Multiple simultaneous
contacts and player-side interpolation still need checks.

## APP-2020: Cardboard packages and rare variants

The bounded gameplay baseline reuses the package captures above and the
independent Cardboard prerequisite completed by APP-2019. The finite cases
and outcomes are:

| Case | Evidence and result |
| --- | --- |
| Normal and representative rare opening; exact item contents | [`package-open`](tools/test-package-open.py) and [`package-open-lan`](tools/test-package-open.py) match seven Java openings in host and guest roles. Java row 3 opens a `rare_creeper_package` containing four apples; the suite compares exact inventory and overflow, package consumption, and pig spawning. |
| Rare form survival and world conversion | [`package-placement`](tools/test-package-placement.py) covers rare Creeper and Vector forms with six-face placement and pickup. [`package-drop-rare`](tools/test-package-drop.py) and its LAN case verify rare Creeper drop conversion and cargo preservation. The supported rare entity also retains UUID, pose, address and contents through the captured save/reopen case above. |
| Address assignment/edit and matching | [`package-filter-editor`](tools/test-package-filter-editor.py) matches seven Java saves, reopen, blank/reset behavior and the 25-character limit for host and guest. [`package-address-matching`](tools/test-package-address-matching.py) matches 40 Java cases across all 14 package forms, with 120 inventory/component/fluid readings per role. |
| Throw and pickup | [`package-charge`](tools/test-package-throw.py) matches 12 Java charge cases in solo and LAN; [`package-flight`](tools/test-package-throw.py) matches 13 unlanded frames. Placement checks include blocked overlaps and empty-hand pickup. |
| Collision and damage control | [`package-damage`](tools/test-package-destruction.py) matches nine Java damage cases and kill behavior in solo and LAN. The selected vertical-contact, player-contact and stack cases cover representative collision boundaries. |
| Guest custody and persistence | Opening, damage, placement and drop checks run with a live guest. The extended [`package-stack-reopen`](tools/test-package-stack.py) check saves two stacked packages with distinct addresses and cargo, then verifies both exact item components, entity count, positions and absence of duplicate loose items after cold reopen. |

The Packager's rare selection rule is source-aligned: Java chooses the rare
pool on one `nextInt(7500) == 0` result, and `native/packager.rs` uses the
same 1-in-7,500 branch with all ten rare IDs. The bounded captures exercise a
rare package's opening, placement and drop paths; they do not claim a sampled
end-to-end Packager rare roll. Exact rare presentation and wider collision
geometry remain follow-ups. The extended reopen check passed 25 Java-aligned
stacking frames plus ten post-reopen ticks on
`native-9f42064-daabfba12364`; controller SHA-256 is
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`, client
SHA-256 is `ee0d1744b4d6817e5087ccac64fea054127f28c38a7d9c4b4c70d2561d6dff84`,
and the matching pack SHA-256 is
`7ea5f1ceb3e9fe8fca602aa24b64877f0b8e3da9f043caa04fbf45353483f7f5`.
The command was `python3 tools/test-package-stack.py <horizon-ctl> <horizon-client>
<prepared-26.3> --reopen --pack .local/exact-builds/stack-disguise-train.4eMBqP/create.hmod`.
These representative results do not close Full 1:1.

The [Packager replay](tools/test-packager-redstone.py) matched all
[67 Java ticks](fixtures/packager-redstone-java.csv) in solo and with a live
LAN operator on `15dc7ec61901`. The first pulse packs from an attached
Barrel at tick 4, assigns the two-line sign address and raises the wire at
tick 6. It preserves named cargo while combining ordinary stacks. A click
during animation leaves the box in place. The player retrieves it at tick
25 and unpacks it at tick 31. A second pulse packs the restored cargo.
The actual rendered hatch, tray and package matched
[11 original animation samples](fixtures/packager-poses-java.csv) per
observer. The Packager also matched the original [survival recipe](fixtures/packager-crafting-java.csv),
including the original Block of Cardboard ingredient and an empty grid after
crafting. The same survival replay matched both original Cardboard conversion
recipes, packing four sheets into a block and unpacking four sheets. The
[Java GameTest patch](tools/java-packager-redstone.patch) records the state,
poses and crafting results. Further Packager cases include other inventories,
Stock Links and order fulfilment, reload timing, and sound playback.

The [original Cardboard block material](fixtures/cardboard-material-java.csv)
has hardness and blast resistance 0.2, map color 26 and fire spread 100 with
flammability 20. The [Cardboard placement replay](tools/test-cardboard-placement.py)
compares [two original survival placements](fixtures/cardboard-placement-java.csv).
Both placements matched Java's axis and item consumption in solo and
with a live LAN guest on `35a2a36db0b1`. The block now uses the original
0.2 hardness and blast resistance with only its horizontal axis in the
state. The [ignition fixture](tools/test-cardboard-fire.py) matched both
[Java flint-and-steel actions](fixtures/cardboard-fire-java.csv) on
`cb2395e1ea93` in solo and with a live LAN guest. The flint lit Cardboard
and lost one durability, while the stone control stayed unlit. Lava and
longer fire spread remain open. The [production fixture](tools/test-cardboard-production.py)
matched 364 [Pulp mixing samples](fixtures/cardboard-pulp-java.csv) and 91
[Cardboard pressing samples](fixtures/cardboard-press-java.csv) in solo and with
a live LAN guest. Bamboo, sugar cane and oak saplings start processing and
produce Pulp on the same Java ticks. The 249 mB water control stays idle.
The LAN guest collected the finished Cardboard from the Depot after the trace.

The [Bound Cardboard replay](tools/test-bound-cardboard.py) matched
[Java placements, normal and Silk Touch drops, and ignition](fixtures/bound-cardboard-java.txt)
in headless solo and LAN on `34f0b58f5120`. Both roles bound a block with
String and started both original 4,000-tick furnace budgets in the survival
menus. Full fuel expiration and explosions remain open.

APP-2019's bounded recipe pass extends the survival menu replay to cover the
original cardboard recipes and shortage behavior: a plain Cardboard Block
returns four Cardboard; three sheets expose no Block recipe result, and the
fourth crafts one Block; a Cardboard Block without String still converts to
four sheets, while adding String produces one Bound Block; a Bound Block also
returns four Cardboard. Each successful craft consumes its inputs and leaves
no remainder. This follows the pinned `CreateStandardRecipeGen` and
`CreateItemApplicationRecipeGen` rules. Solo and LAN guest menu runs passed.

The new `cardboard-production-reopen` check saves while the three 250 mB Pulp
mixers and the Cardboard press are active, reopens the world, and verifies the
eligible batches and press complete once; the 249 mB control stays idle. A
second idle save/reopen retained the finished machine outputs and the X/Z axis
states of both Cardboard block forms. The game advanced during client startup
before the fixture could freeze it, so this proves operation and inventory
survival across reopen, not exact Java timer restoration or reload tick parity.
It reuses the existing Java trace cases; no new Java capture was needed.

For this pass, the pinned Horizon revision built as
`native-9f42064-f7d9ba41e662`; the installed `create.hmod` SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Ten existing placement, fire, production, Bound Cardboard, fuel and LAN checks
passed on that build. The new menu cases and active/idle reopen case also
passed. Reproduce with the exact build's `horizon-ctl`, `horizon-client` and
prepared `26.3` resources using `tools/test-parity.py --jobs 2` and these
checks: `cardboard-placement`, `cardboard-placement-lan`, `bound-cardboard`,
`bound-cardboard-lan`, `bound-cardboard-menus`, `bound-cardboard-menus-lan`,
`cardboard-fire`, `cardboard-fire-lan`, `cardboard-production`,
`cardboard-production-lan`, and `cardboard-production-reopen`. Logs are in the
worktree's `.local/parity/`. Full fuel expiration, explosions, lava spread,
other Pulpifiable tag members and exact reload timing remain follow-ups.

The four [original Cardboard armor recipes](fixtures/cardboard-armor-java.csv)
matched shaped survival crafting, consumption, right-click equip slots and one
point of defense per piece in solo and with an actual LAN guest. The pack
uses the original item sprites and underlying worn armor textures. This
fixture exercises untrimmed armor. The [disguise replay](tools/test-cardboard-disguise.py)
matches six settled [Java states](fixtures/cardboard-disguise-java.csv) in
solo and real LAN. A crouching player with the complete set has a 0.6 by
0.8 block body, 0.6 block eye height, and zero visibility for target
acquisition. The host and guest both observe the original body changes when
the boots are added, removed, and restored. Transition tick timing, mob
target loss, the disguise model, the HUD overlay, and armor trims still need
verification.

Using the pieces as furnace fuel matched all 824
[Java samples](fixtures/cardboard-armor-fuel-java.csv) solo and with a LAN
guest. Each piece burns for 1,000 ticks and produces the first iron ingot
on tick 200. The LAN guest took the ingot from the furnace.

## APP-2079: Cardboard armor and disguise

The bounded acceptance cases reuse the four original shaped recipes, host and
guest equipment interactions, the four furnace-fuel traces, and the six
settled disguise phases recorded above. `tools/test-cardboard-armor.py` now
also compares each equipped piece's maximum and remaining durability with the
Java values in `fixtures/cardboard-armor-java.csv` (44 helmet, 64 chestplate,
60 leggings, 52 boots); all four recipes, equipment slots, defense, and
durability values passed in solo and LAN.

The new [`cardboard-armor-reopen`](tools/test-cardboard-armor-reopen.py) case
equips the full set, activates the crouching disguise, cold-reopens the world,
and checks the four worn item IDs, reactivated 0.6 × 0.8 body, and zero mob
visibility. It passed on cached build `native-9f42064-6bdf8691aa42` from main
`781c0ef`, using client SHA-256
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`,
controller SHA-256
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`,
prepared Horizon 26.3 resources, and Create pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
The prior disguise replay's six settled Java phases passed solo and LAN on
`native-9f42064-daabfba12364` with pack SHA-256
`7ea5f1ceb3e9fe8fca602aa24b64877f0b8e3da9f043caa04fbf45353483f7f5`.
That earlier runtime has since been pruned; its captured results remain in
`.local/exact-builds/stack-disguise-train.4eMBqP/`.

The case list is: shaped survival craft/equip for each of four slots and
defense/durability; four fuel types; full-set crouching disguise activation,
removal and visibility; host/guest observation; and equipped full-set cold
reopen followed by disguise reactivation. Create 6.0.10 source at
`ac0c444d9828da3453ae8cc65338e8de063286fb` defines zero visibility for a
crouching player wearing all four pieces, except while flying. Exact overlay,
trims, every hostile target-loss transition, damage/repair combinations, and
all mob types remain follow-ups; Full 1:1 stays Open.

The [Cardboard Sword replay](tools/test-cardboard-sword.py) matched 88
[original mob samples](fixtures/cardboard-sword-targets-java.csv) in solo
and with a real LAN guest. It checks health, Slowness X, and knockback
through fully charged and early swings, sprinting, and Knockback II.
Both roles played the original bonk on mob hits and the start of a block
hit, including the sound category, volume, and pitch. Both roles crafted
the sword in survival, applied a supported Knockback book, rejected a
mixed book, and used the sword as 1,000-tick furnace fuel. The
[nonzero knockback control](tools/test-cardboard-sword-base-knockback.py)
also matched the Java pig impulse in both roles.

The finite APP-2080 pass reuses those mob and PvP results and adds a
[save/reopen check](tools/test-cardboard-sword-reopen.py): a survival player's
Cardboard Sword retains Knockback I and damage 3 after a real non-damaging pig
hit; the pig retains 10 health and Slowness after the world reopens. This is a
meaningful active-after-hit persistence state; an ongoing active-equipment
state does not apply to this instant-use weapon. Armor stands, the Ender
Dragon, held-item rendering, other enchantment variants, and packet arrival
timing remain follow-ups.

The reopen check passed on 2026-11-20 against Horizon source `9f42064`, client
directory `native-9f42064-558283db0c26`, and Create pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The client SHA-256 was
`37358d394a10d7758fbf1651f7432696b41f37036ff08f1bd2b18883a80ba99a`; the
controller SHA-256 was
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`.
It used the prepared 26.3 bundle from the retained Cardboard Sword test build.
Reproduce with `python3 tools/test-cardboard-sword-reopen.py <horizon-ctl>
<horizon-client> <prepared-26.3> --pack <create.hmod> --artifacts <output>`.
The control log is retained under `.local/parity/horizon-cardboardswordreopen.log`
in the isolated APP-2080 checkout. Pinned Java source is
`ac0c444d9828da3453ae8cc65338e8de063286fb`; the retained mob and PvP fixtures
have SHA-256 values `a9513fd58ec50bd6d4e25b78301c5407e18453c1c80e4f9c69d2ae017ecc8aed`
and `a01b12d85c6691db5ee75de24f0f90ec65fed707ab93788914dcb70cafab056c`.

The [Sword PvP replay](tools/test-cardboard-sword-pvp.py) matched seven
[original Java impact cases](fixtures/cardboard-sword-pvp-java.csv) in
each direction between a host and guest on `8fd28a1355c0`. The Sword
pushes players without taking health or applying Slowness, including
creative players and when PvP is disabled. Both clients played the
original bonk and the receiving player moved. Mounted targets dismounted.
The Java trace ends at impact. Armor stands, the Ender Dragon, and
held-item rendering remain open.

The List Filter opens its original 18 ghost slots, allow/deny controls, and
respect/ignore data choices from the held item. A host and a live guest
matched [nine Java menu states](fixtures/list-filter-editor-java.csv), including
shift-copying a sample, preventing duplicate insertion through shift-click,
copying the cursor stack, protecting the held filter, clearing the sample,
and saving and reopening the selected options. The
[Java GameTest patch](tools/java-list-filter-editor-trace.patch) exercises
the original menu and option packets.

The Attribute Filter opens its reference slot and the allow-any, allow-all,
and deny controls from the held item. Both a host and a live guest matched
[six original editor states](fixtures/attribute-filter-editor-java.csv) while
copying an Apple reference, selecting an ordinary and inverted attribute,
changing modes, saving, and reopening. They also matched
[53 Java filter reads](fixtures/attribute-filter-kinds-java.csv) covering
placeable items, enchantments, damage, stackability, creator, fluids, shulker
contents, and written books, plus [11 name cases](fixtures/attribute-filter-names-java.csv).
The same fixture applies a named-item filter to a Stockpile Switch through
ordinary inventory and block interaction. The [menu](tools/java-attribute-filter-editor-trace.patch)
and [predicate](tools/java-attribute-filter-kinds-trace.patch) patches record
the original Java behavior.

The color attribute matched [42 Java results](fixtures/attribute-filter-color-java.csv)
on both a host and a live guest. The samples cover dyed items, a blue Create
Seat, rocket explosion and fade colors, and unchanged colors for the named
control items. Both players applied the blue filter to a Stockpile Switch.
The [color GameTest patch](tools/java-attribute-filter-color-trace.patch)
records the original filter decisions.

### APP-2018 filter gameplay baseline

The [Smart Chute GameTest](tools/java-item-filter-chute.patch) ran with Create
`ac0c444d9828da3453ae8cc65338e8de063286fb`, Minecraft 1.21.1, NeoForge
21.1.219 and JDK 21. It installs each filter through Java's
`FilteringBehaviour.setFilter` and starts with one item in the source barrel.
The [captured source and destination counts](fixtures/item-filter-chute-java.csv)
are exact at GameTest tick 16 after setup. The 20 cases cover positive and
negative ordinary, deny, nested List, item-tag Attribute, and Package address
matches, a mixed nested list and the cleared-filter control. An initial
capture used the Java block's powered default state and transferred
nothing. The recorded capture explicitly places unpowered Chutes, matching
player placement.

Build `native-9f42064-558283db0c26` was preserved for `32fb542`, whose native
and patch trees match the `c1255a0` baseline. It left blank List Filters in
the source barrel in both the direct and nested sample cases. The fix follows Java's
`FilterItemStack.of` distinction between a fresh List Filter, which matches
by item ID under ignore-data matching, and a configured List Filter, which
tests its contents.

The replay also composes a List Filter from a configured Attribute Filter and
Package Filter using the held-item editor. It loads the resulting stack data
into two Smart Chutes. A cold reopen checks that the editor stack, both mounted
filters, and the idle rejected Apple survive. The active rig holds a Package
under redstone during startup, then delivers it when unpowered. A new tag
match verifies operation after reopen. The LAN run uses a survival guest for
the edit and rejoin. The existing detector replay covers player clicks to
install and clear filters. The Chute replay seeds its installed filter and
checks transfer outcomes. Exact packet timing, Java reload behavior, all
attribute types, deeper nesting, direct Chute and Funnel filter-slot
interaction, and other consumer combinations remain open.

To recapture Java in a disposable checkout of the pin, apply
`tools/java-item-filter-chute.patch` and run
`./gradlew --offline --no-daemon --max-workers=2 runGameTestServer` with an
isolated Gradle cache. Add the header `case,source,destination` before the
rows following the `ITEM_FILTER_CHUTE,` prefix in the output.

The patch SHA-256 is
`fade1de4bc03dcbff852d4bb676644bb3eff4f9a34a37c7d7af4af9732b57275`.
The exported CSV SHA-256 is
`c93a92b730c4e4fcb85c85b368b53a7111776d18595232f63b6be5e8e2a930b8`.
The corrected Java capture took 88 seconds using cached artifacts.

Build with the compatible launcher and private launcher/cache data as described
in [the worker guide](PARITY-WORKER.md). The Horizon Nightly pin is
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and the `create.hmod` SHA-256
is `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

The private launcher 0.2.67 build produced `native-9f42064-cd04d5a80e1c` in
841 seconds. Both Smart Chute runs matched all 20 Java snapshots and completed
the cold-reopen checks. All 19 selected regressions passed on that build.
The first two-worker batch took 12 minutes and passed 16 checks. The solo
Attribute Kinds check and LAN Color check passed serial retries after
control timeouts. The LAN Attribute Kinds check passed in 61 seconds with
a headless host and an offscreen guest after offscreen-host control timeouts.
The host only issues commands in that test. The guest still applies the
selected filter through player input.

After rebasing onto `origin/main` at `f62a9b97ebe14c4320f5e0ac84583ff43e835edd`,
the current tree rebuilt as `native-9f42064-92c206b2a1f2` in 10 minutes 52
seconds using the private launcher cache. The same 19 selected checks all
passed on that exact build, including both new Smart Chute runs. An initial
rerun inside the filesystem sandbox exited before gameplay because Horizon's
local control socket was denied; the successful rerun had local socket access.

While the PR waited for auto-merge, `main` advanced again. The branch was
rebased onto `f9ee5a75d0efbe2c9e81b535c0d41a5e6f994481` and rebuilt as
`native-9f42064-f11c2d5d72fd` in 4 minutes 8 seconds. The same 19 selected
checks passed on this latest tree.

`main` advanced once more while auto-merge was pending. On the current
`576fe85f6aa470bc6f78b3f5682d7c5e8242c681` base, build
`native-9f42064-5dce121d26bb` completed in 4 minutes 22 seconds and the same
19 selected checks passed again, including both Smart Chute traces and
cold-reopen cases.

```sh
sh tools/build-native.sh /path/to/launcher-0.2.67 /path/to/private-launcher-data
HORIZON_NO_AUDIO=1 HORIZON_NO_DISCORD=1 python3 tools/test-parity.py \
  /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 \
  --check 'filter-recipes*' --check 'list-filter-editor*' \
  --check 'attribute-filter-editor*' --check 'package-filter-editor*' \
  --check 'attribute-filter-kinds*' --check 'attribute-filter-color*' \
  --check 'package-address-matching*' --check 'detector-list-filter*' \
  --check 'attribute-filters' --check 'item-filter-chute*'
```





## Metal Girders

Five placement cases match Java over 40 sampled rows. They cover a
vertical post, both horizontal beam axes, and placement into source or
flowing water. Source water is retained. Eight raycasts exercise the post,
both beams, and the cross using Java’s shape dimensions. A survival guest
also placed a Z-axis beam into source water, with the host and guest seeing
the same block state and the guest using one item. The original survival
recipe crafts eight girders from three iron sheets and three andesite alloy.
Dry and waterlogged plain girders each drop one girder when broken.
The placement capture is
`tools/java-metal-girder-placement-trace.patch` and the reference is
`fixtures/metal-girder-placement-java.csv`.

Line-extension assistance adds five cases across 35 Java rows. It extends
horizontal beams and vertical posts past existing segments, picks the
opposite end when the preferred direction is blocked or reaches Create’s
12-block range, and retains source water. A live guest extended the host’s
wet line using a single girder and left the ordinary clicked face empty.
The capture is `tools/java-metal-girder-assist-trace.patch` and the reference
is `fixtures/metal-girder-assist-java.csv`.

Dynamic connections match 42 Java rows. A plain beam adds its perpendicular
arm when a plain or encased neighbor arrives and retains the arm while
one neighbor still connects. On a wet encased shaft, posts above and below
control their respective caps. A guest placed a post and both clients saw
the cap attach, then detach after the host removed the post. The capture
is `tools/java-metal-girder-connections-trace.patch` and the reference
is `fixtures/metal-girder-connections-java.csv`.

Manual wrenching matches 36 Java rows across an isolated beam, a stacked
pair, a cross, and axis changes. High and low clicks toggle their respective
caps, stacked beams change together, and opening a cap on a Y-axis beam
restores its horizontal axis. A survival guest disconnected and
reconnected both caps of a stacked pair. The capture is
`tools/java-metal-girder-wrench-trace.patch` and the reference is
`fixtures/metal-girder-wrench-java.csv`.

The wrench outline submits the original box bounds for a single upper cap,
a single lower cap, and a stacked pair. The frame check compares the bounds,
line width, and gray tint from Java’s selection rule and records the
Horizon scene while holding the wrench. The outline stays hidden over a
cross, while crouching, and while the wrench is stowed. The reference is
`fixtures/metal-girder-wrench-preview-java.csv`.


Over 12 simulated ticks each, a wet X-axis beam and a dry Z-axis beam
accept a shaft as a real player input. The new shaft turns perpendicular
to the beam and delivers 32 RPM. A normal wrench click returns the shaft
and stops the output. The trace also checks waterlogging, upper and lower
connections, and the inventory count at every tick. In LAN play, the host
inserts the shaft and the guest removes and reinserts it, taking one shaft
into their own inventory before returning it to the girder.

The Java capture is `tools/java-metal-girder-shaft-trace.patch` and its
reference is `fixtures/metal-girder-shaft-java.csv`.

Dry and waterlogged crouch-wrench pickup and ordinary break drops match
a further 24 Java observations. The wrench gives one girder and one shaft
to the player. Breaking the girder drops both. A crouch-wrenched wet girder
leaves a water source and stops transmission. A live guest received both
items while the host saw the water and zero output. The pickup reference is
`fixtures/metal-girder-pickup-java.csv` and its capture is
`tools/java-metal-girder-pickup-trace.patch`.

### APP-2069 Metal Girders and encased Girder Shafts — November 20, 2026

The bounded acceptance set passed on the available pinned Minecraft 26.3
runtime, build `native-9f42064-6bdf8691aa42` (APP-2017 evidence build, source
main commit `781c0ef`) and pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`. The
available build predates current `origin/main` at `ef13693`; a source diff
confirmed no changes to `native/shaft.rs`, girder helper modules, girder Java
traces, fixtures or girder gameplay checks between those revisions. The only
intervening `native/wrench.rs` changes add Deployer behavior and do not alter
the girder branch. Rebuild and rerun on the combined current build before
integration.

The case set covers the original girder recipe; five placement cases and
eight shape raycasts; five extension cases; dynamic beam arms and encased
shaft caps; wrench cap and axis changes; shaft insertion/removal across X/Z
configurations with wet/dry states and 32 RPM transmission; dry/wet drops and
crouch pickup; a guest placing, extending, wrenching, connecting, inserting,
removing and picking up; and persistence. Existing Java references are from
Create `ac0c444d9828da3453ae8cc65338e8de063286fb`. Sample counts are 40
placement rows, 35 assist rows, 42 connection rows, 36 wrench rows, 4 wrench
preview cases, 24 shaft rows and 24 pickup rows. All 15 existing registered
girder replay and LAN checks passed, including every Java trace row; the new
reopen check passed too. The `electronics-crafting` survival recipe check
also passed.

The blocking prerequisite, APP-1944 (Shafts, andesite and brass encased
shafts), is Done. Its integrated shaft casing/persistence work is in
[PR #7](https://github.com/andrhlt/horizon-create/pull/7).

Capture patch SHA-256 values:

| Capture | SHA-256 |
| --- | --- |
| `java-metal-girder-placement-trace.patch` | `58da5dbb1dc1d6936d99ff06f3b914ccf829aea2d72d51d3c258bfce1ad8db57` |
| `java-metal-girder-assist-trace.patch` | `6c7439f10681a01b18b4d9742adeb74d9e487e93944769c165555af61ed19df2` |
| `java-metal-girder-connections-trace.patch` | `8bb2ead99d086f5c1606ab1377071ef99e34d66da28db9d92f46375e219def90` |
| `java-metal-girder-wrench-trace.patch` | `977459b9e71195bbb0fe48862b10cf4807c6e6d84750ddc5257459e76ef0caf2` |
| `java-girder-wrench-preview-trace.patch` | `cb2d8b3ef89d48cf198c7cc2297838a02f2e8413238774ba4d1fd90e998ec87c` |
| `java-metal-girder-shaft-trace.patch` | `773901b1d40b4483efcbc7173f441688441918ae627b04a6913b22758934d606` |
| `java-metal-girder-pickup-trace.patch` | `5ec64331a11863b75ea79a089fc6fadfb2d4f8ca553cf05f90aaee497b5ff375` |

Reference CSV SHA-256 values in the same order are: `3027e120bddc7842398a3745256f252fdac36bb15c49139cd98b9f52ce033ddf`, `10920d8c8a0b28e173005ba5ef460cf84413a4d8b6503754806852d25b948eae`, `df1b8ea827783c71d5c219e492298aa7a5253e5ea1642b67dc884fc2f5053b1e`, `4bc66d9657d99e2a72f77c0e3bde25b7082118eace567b4ba2ad8fc23e383f01`, `ac922e8a41e75409703b7c5a94ec00f0b0168728e6ec57d442fc2ed0396ce4a6`, `4b89d634db7e39627e62f9bfec8404f1e0f01fec89ddc478fd6b4009f8a35918` and `8e54d5f0cf2fb369f4b83d84f7e2a049309e9439330ea3078f127ffd292b34eb`.

`tools/test-metal-girder-persistence.py` passed an idle wet girder save/reopen
and an active waterlogged encased shaft save/reopen. The block state remained
encased and output resumed at 32 RPM. Since the fixture freezes time, the
active state was sampled after one explicit tick following insertion.
Persistence is a source-aligned Horizon save/reopen check, not a Java reload
parity claim. The fixture is registered as `metal-girder-reopen` in
`tools/test-parity.py`.

The reproduction commands are:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 --check 'metal-girder-*'
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check 'electronics-crafting'
```

Broader support combinations, additional shaft-network layouts and visual
variants remain follow-ups. These scoped checks do not establish exhaustive
Full 1:1 parity.

```sh
python3 tools/test-metal-girder-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --shapes
python3 tools/test-multiplayer-metal-girder-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-assist.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-metal-girder-assist.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-connections.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-metal-girder-connections.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-wrench.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-metal-girder-wrench.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-wrench-preview.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-shaft.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-metal-girder-shaft.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-loot.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-metal-girder-pickup.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-metal-girder-pickup.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Encased Cogwheels

The 18-tick Java replay applies reusable Brass Casing to a powered small
cog, switches its east shaft end off and on, turns the casing from X to Y
while swapping its shaft ends, and sneak-wrenches it back to a bare cog.
It checks both shaft-end states, casing stack count, cog speed, and output
speed on every simulated tick. In LAN play, the host encases the 24 RPM cog
and the guest closes its output, then uncases it to restore 24 RPM.

The render fixture compares four sampled ticks with Java's shaftless cog
angle and open shaft selection. It can check the five corresponding assets
against the original Create checkout and save the sampled Horizon frames.
The Java capture is `tools/java-brass-cogwheel-casing-trace.patch` and
the reference is `fixtures/brass-cogwheel-casing-java.csv`.

The same casing and shaft-end interactions are covered across a further 14
simulated ticks each for the Andesite small, Andesite large, and Brass
large gears. All three hold 24 RPM while the wrench closes the axial
output, and retain a meshed −24 RPM for small gears or −48 RPM for large
gears. A host and guest repeat the Andesite small and Brass large
interactions. All four rendered variants match the Java angle and open
end geometry at four sampled ticks each, including the 11.25° phase
between the large gear and its shafts in the sampled position.
The family capture is `tools/java-encased-cogwheel-family-trace.patch`
and its reference is `fixtures/encased-cogwheel-family-java.csv`.

```sh
python3 tools/test-brass-cogwheel-casing.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-brass-cogwheel-casing.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-brass-cogwheel-render.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-encased-cogwheel-family.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-encased-cogwheel-family.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Wooden and Metal Brackets

A 13-tick comparison attaches a Wooden Bracket to a shaft, repeats the
same placement, replaces wood with metal, and returns the metal when
the player uses a Wrench. It also checks that a bracket cannot be applied
to ordinary stone and drops when the bracketed cog breaks. The fixture
compares the bracket’s model state, both held stacks, and the number of
dropped brackets. Both original recipes craft four brackets in survival.

A live host places wood. The guest replaces it with metal, receives the
wood, and removes and receives the metal with a Wrench. The guest’s frames
show the mounted bracket and the shaft after removal. The port uses the
original block and item models and textures. The bounded APP-2070 extension
adds wooden attachment to a straight standard pipe and metal attachment to a
straight glass pipe, checks Java orientation, rejects a bent pipe, and saves
and reopens both attached states. A LAN guest also attached a metal bracket to
a straight glass pipe; the host observed the expected state and the guest used
one item. Other pipe families and presentations remain follow-ups.

`tools/java-kinetic-brackets-trace.patch` records
`fixtures/kinetic-brackets-java.csv`.

```sh
python3 tools/test-kinetic-brackets.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-kinetic-brackets.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --craft
python3 tools/test-multiplayer-kinetic-brackets.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

The bracket fixture's shaft/cog trace remains the Java-captured comparison.
Its additional pipe cases run after the trace and check persisted block-entity
state directly; they do not claim Java tick-by-tick pipe parity.

### APP-2070 bounded gameplay pass (November 20, 2026)

Built from Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` with engine patch
digest `664100af7e67dd9fdd01c04d91f175f7e221e39d`, producing
`native-9f42064-672cc8e442cb`. The installed pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Java trace patch SHA-256 was
`719a8212c002c375dd6cc5756fe1aaf2c5d0db3c93c36074690237dca507ba69`.
The existing Java reference was reused; no new capture was needed. Approximate
worker time: source/setup 5 min, coding/repair 8 min, private cache/build 8 min,
fast checks and integration 4 min, debugging 2 min.

- `tools/test-kinetic-brackets.py ... --pack <pack>`: all 13 shaft/cog samples
  matched `fixtures/kinetic-brackets-java.csv`; wooden/standard-pipe and
  metal/glass-pipe attachments had the expected state, a bent pipe was
  rejected, and both bracket states survived world save/reopen. Brackets are
  static decoration, so active-operation persistence does not apply.
- `tools/test-multiplayer-kinetic-brackets.py ... --pack <pack>`: host wood
  placement, guest metal replacement and wrench return, then guest metal
  attachment to the glass pipe all converged to the expected server state and
  inventory counts.
- `tools/test-kinetic-brackets.py ... --craft --pack <pack>`: both original
  survival recipes passed.
- `python3 -m py_compile` on both bracket test scripts, `rustfmt --edition
  2024 --check native/bracket.rs`, and `git diff --check` passed.

The first pipe test attempt used direction names that the fixture helper did
not implement, so the click hit the top face; it was corrected to the helper's
supported `up` target and passed. The first guest-pipe attempt tried to
teleport from the guest, which lacks command permission; the host now moves the
guest before the click, and the LAN check passed. The recipe runner also needed
the existing `wheat_milling.nbt` copied into this isolated worktree. No Java
pipe tick trace was added; axis rules were translated from the pinned
`BracketBlock.getSuitableBracket` and `FluidPropagator.getStraightPipeAxis`.

## Creative Motor

A 41-tick replay presses Java’s signed settings through the original
value-settings packet and uses Horizon’s actual board on south-facing and
upward-facing motors. It compares both motor speeds and both shaft outputs
at +64, −24, the limits of +1 and +256, and −11 RPM. It checks that holding
Use Item opens the board on the sixth client tick, a three-tick press leaves
it closed, and the inactive end face stays inactive. A live host sets +64
and a guest reverses the authoritative shaft to −24 RPM.

`tools/java-creative-motor-trace.patch` captures the speed trace and the
board’s two rows, 256 RPM limit, 32 RPM milestones, and value-box positions
for both motor directions. The three references are
`fixtures/creative-motor-java.csv`, `fixtures/creative-motor-board-java.csv`,
and `fixtures/creative-motor-hit-java.csv`.

The seven survival placement cases compare sideways and steep aim, adjacent
shaft preference, a crouched override, conflicting axes, and two shafts on
one axis. Java captures are in `fixtures/creative-motor-placement-java.csv`
from `tools/java-creative-motor-placement-trace.patch`.

Java’s `CreativeMotorRenderer` draws one `SHAFT_HALF` partial on the motor’s
`facing` side. It rotates about that axis with a position-dependent phase of
0° or 22.5°. The [render replay](tools/test-creative-motor-render.py) samples
all six facings in solo and the south-facing motor on both LAN clients. The
replay places motors with +32 and −48 RPM settings and checks the rendered
axis, half-shaft side, signed speed, phase and angle after each placement.
It compares speed and axis to `fixtures/creative-motor-render-java.csv`
([capture](tools/capture-creative-motor-java.py) with
`tools/java-creative-motor-family-trace.patch`) and evaluates Java’s phase and
angle rules at Horizon’s frame position and time. The independent LAN settings
check verifies the server shaft response to the host and guest board actions.
A [save/reopen replay](tools/test-creative-motor-reload.py) keeps `ScrollValue`
and regenerates speed for two motors each connected to its own shaft at −24 RPM
and one disconnected motor at +40 RPM.

The direct two-motor replay checks the presence and signed speed of the two
motors and their shaft in each lane. The original combined Java capture
`fixtures/creative-motor-competition-java.csv` placed both GameTests in the
same batch. At competition tick 5 the render GameTest placed its five-block
wide template over the first lane, removing those blocks before the settings
callback. The original capture is preserved for diagnosis. Capture the
competition GameTest in isolation with
`python3 tools/capture-creative-motor-java.py --competition-only` to regenerate
`fixtures/creative-motor-competition-isolated-java.csv` at the pinned revision.
The replay compares all 144 samples over ticks 0–23, with settings, removal and
re-add applied after sampling ticks 5, 12 and 18 respectively.

In Java, the first initialized motor drives the default-speed lane at +16 RPM
through tick 12, even though its attached motor initially has an opposing
setting. After the source is removed, the attached motor drives at +16 RPM.
That lane accepts a same-direction re-add. The other lane already has a source
because its initial setting invokes the callback during setup. Its reversal
moves all three blocks to −16 RPM at tick 6. Removing its driven motor leaves
the shaft and source at −16 RPM. Re-adding the opposed motor destroys the new
motor while preserving the running shaft and source. The fixture measures
presence and speed. Stress and capacity remain outside this comparison.

The [corrected competition replay](tools/test-creative-motor-competition.py)
matches all 144 isolated Java samples on final build
`native-9f42064-1e629580d78f`. The fixture uses the isolated Java reference
and samples before each corresponding action; the original combined capture
and prior 70/144 comparison remain available for audit. The six registered
motor family checks also pass on this build, including the competition check.
The source-transition regression passes on the same build and still covers
the bridge, split and reopen cases from
[APP-1943](https://linear.app/appstu/issue/APP-1943). This competition fixture
only measures block presence and speed; stress and capacity remain unverified
by this fixture.

```sh
python3 tools/test-creative-motor.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-creative-motor-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-creative-motor-render.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-creative-motor-render.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --lan
python3 tools/test-creative-motor-reload.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-creative-motor.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-creative-motor-competition.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Rotation Speed Controller

Two 51-tick Java comparisons cover both drive directions, ordinary shaft
passthrough, signed settings and limits, source RPM changes, and stress and
capacity with fans on both sides. Both verify that holding Use Item on the
settings box opens the board on the sixth client tick, and releasing it
confirms the selected value. A three-tick press stays in the world and a
left-click on the board leaves the setting pending.

The overload replay uses an 8 RPM water wheel supplying 256 SU through a
gearbox and controller. One fan on the cog side applies 254, 256 or 258 SU
at targets 127, 128 and 129 RPM. The fan runs at equality and stalls at
258 SU. The replay recovers first at +128 and then at −127 after another
overload at −129. Java records the fan's effective RPM directly. The Horizon
replay computes it from the fan's saved speed, capacity and stress, and
independently samples the speedometer target, which drops to zero during
overload. Build
`native-9f42064-4ce381fec622` matched all 17 samples after the 70-tick
water-wheel warmup. Horizon sets the target with the server NBT command.
The tested pack SHA-256 is
`d6361c9f73eee47726e1b26463b463670e7be1e6b5e42a47019a14318d37c7df`.
[Java trace](fixtures/rotation-speed-controller-overload-java.csv)

Apply the overload patch to the pinned Java checkout and run
`./gradlew --offline runGameTestServer` with Java 21. Extract the CSV fields
after `CREATE_CONTROLLER_OVERLOAD `. The patch SHA-256 is
`f5fd02e889371390358e0766d782927bb0369297f7c5c2c797a21f7dc8efd6d8`.
[Capture patch](tools/java-rotation-speed-controller-overload.patch)

The boundary replay compares both drive directions on ticks 1–23 after
setup. The negative row's zero column selects −1 RPM. The board also sets
−73, −256, +256 and +23 RPM. A true zero target after ticks 9 and 18 stops
the regulated side while the input stays at 24 RPM. Java invokes
`SpeedControllerPeripheral.setTargetSpeed(0)`. The Horizon replay injects
`ScrollValue:0` with the server's `/data merge block` command. The comparison
covers the resulting settings and all seven speeds at four decimal places.
[Java trace](fixtures/rotation-speed-controller-boundaries-java.csv) ·
[Capture patch](tools/java-rotation-speed-controller-boundaries.patch)

Apply the boundary patch to Create 6.0.10 at `ac0c444d9828da3453ae8cc65338e8de063286fb`
and run `./gradlew --offline runGameTestServer` on Java 21. Extract the CSV
fields after `CREATE_SPEED_CONTROLLER_BOUNDS `. The patch SHA-256 is
`142a5e1dcb914680c5d953b5d4ad0a996aeb5c53435e509376af19ec9e4348ee`.
Existing build `native-9f42064-711c7991bebd` matched all 23 ticks with
prepared pack SHA-256 `d6361c9f73eee47726e1b26463b463670e7be1e6b5e42a47019a14318d37c7df`.

A cold reopen replay saves four powered rigs at signed targets −73 and +83,
plus a zero target in each drive direction. A fresh Java server process
loads the same world. The trace records the target and five block RPM
readings before save, at the first loaded pre-tick, and for six more ticks.
Horizon closes and relaunches its world process and takes the first sample
before stepping the reopened world. Build `native-9f42064-711c7991bebd`
matched all 32 rows using prepared pack SHA-256
`d6361c9f73eee47726e1b26463b463670e7be1e6b5e42a47019a14318d37c7df`.
[Java trace](fixtures/rotation-speed-controller-reopen-java.csv)

Apply the reopen patch to the pinned Create 6.0.10 checkout. With Java 21,
run `python3 tools/capture-java-rotation-speed-controller-reopen.py /path/to/checkout --output /path/to/empty-capture-dir --offline`.
The patch SHA-256 is
`14af0eca9f174c4e1f475ddf576dd16f3c180acdc03b6ac7f548d6dea912845d`.
[Capture patch](tools/java-rotation-speed-controller-reopen.patch)

The 40-tick cascade replay loads two regulators with fans in all three
sections. It compares six rotational speeds and both controllers’ stress and
capacity while changing signed settings, removing the first motor, then
powering the network from the opposite end. Capture comes from
`tools/java-rotation-speed-controller-cascade.patch` and is recorded in
`fixtures/rotation-speed-controller-cascade-java.csv`.

The 24-tick competing-motor fixture compares two separate networks. Both
begin with 24 RPM below the controller. Java accepts a same-direction
40 RPM motor above the large cog while retaining 24 RPM below, and breaks a
new opposing −40 RPM motor before the next sample in the other network. The
original 16 RPM output resumes after removal in both cases. The capture
uses `tools/java-rotation-speed-controller-competing.patch` and is recorded in
`fixtures/rotation-speed-controller-competing-java.csv`.

The six-case survival placement reference uses
`tools/java-rotation-speed-controller-placement.patch` and
`fixtures/rotation-speed-controller-placement-java.csv`. It covers both
controller axes, side placement when the top is blocked, placement beneath
an existing cog, and horizontal shaft preference in the presence of a vertical
shaft. A live host sets 64 RPM, and a guest reverses the server output to
−32 RPM, then attaches a large cog to a second controller and spends one item.
The original recipe passes the survival crafting fixture.

An integrated hidden Java host and guest also opened the survival settings
board and sent real `ValueSettingsPacket` edits through the LAN server. At
frozen world tick 283 the host's +64 and guest's −32 edits were both accepted
by the server and appeared on both clients' controller block entities at that
tick. This verifies authority and replication for those edits. The frozen
world reports effective RPM zero, so this capture does not establish the
unfrozen shaft or rendered replication delay; LAN timing remains open.

The survival Wrench replay starts with 24 RPM through a bare controller
set to −73. A top click rotates the axis to X and stops the downstream
shaft. The side click leaves the axis at X, and a bottom click restores the
Z axis and 24 RPM. The setting survives both turns. Sneak-clicking picks up
one controller and stops its former output shaft. The original motor
keeps running. Baseline `native-9f42064-711c7991bebd` differed in six rows.
Candidate `native-9f42064-4ce381fec622` matched all eleven samples from
ticks 1–11 using the same prepared pack.
[Java trace](fixtures/rotation-speed-controller-wrench-java.csv)

Apply the Wrench patch to the pinned Java checkout and run
`./gradlew --offline runGameTestServer`, then extract the fields after
`CREATE_CONTROLLER_WRENCH `. The patch SHA-256 is
`0d9c40a415a15cf22afcef6a832446f0d9b83da33d60a269cfd1d4aa0f82dcae`.
[Capture patch](tools/java-rotation-speed-controller-wrench.patch)

The render replay checks the X and Z controller shafts at +16 and −16 RPM.
Both clients submit shaft and bracket geometry in an enclosed fixture with
distinct block light at the controller and cog. The hidden Java client uses
the fallback renderer with Flywheel disabled. The six stages cover an empty
top, vertical large cogs, Brass and Andesite Encased Large Cogwheels, bare
horizontal cogs, their removal, and reinstallation. Each stage contributes
two actual frame submissions per axis after the Java bracket has settled.

The comparison measures emitted vertex counts and light exactly. Local
bounds have a tolerance of 0.0001 blocks and shaft angles have a tolerance
of 0.003 degrees. Shaft bounds use the pose before spin, and angle
comparisons align the clients' reported render times and fractions.
Baseline `native-9f42064-c717808ff817` used block light 12 from the controller
for all eight bracket submissions. Java used light 13 from the cog cell.
Build `native-9f42064-2ffe2a07cde0` matched all 24 submissions using prepared
pack SHA-256 `d6361c9f73eee47726e1b26463b463670e7be1e6b5e42a47019a14318d37c7df`.
[Java trace](fixtures/rotation-speed-controller-render-java.csv)

Apply the render patch to the pinned Create checkout, then use Java 21 and
run `python3 tools/capture-java-rotation-speed-controller-render.py /path/to/checkout --output /path/to/empty-capture-dir --offline`.
The patch SHA-256 is
`0006d6ed092875363bb9376f300202b02e7f7fd2524ac50fdb1df49ddd5fc2b9`.
[Capture patch](tools/java-rotation-speed-controller-render.patch)

Six more rigs check survival placement under Brass and Andesite Encased Large
Cogwheels, both regulation directions, and isolation for parallel, vertical
and small cogs. The shaft-driven andesite rig has both casing shaft ends
closed. A pre-oriented brass rig tests transmission independently of
placement. Java removes each 24 RPM motor after tick 4 and reinstalls it at
32 RPM after tick 8. Horizon compares all 72 rows from ticks 1–12, measuring
controller, cog and output shaft RPM to four decimal places, controller axis
and remaining item count. Tick 0 records the Java setup state.
[Java trace](fixtures/rotation-speed-controller-encased-java.csv) ·
[Capture patch](tools/java-rotation-speed-controller-placement.patch)

The encased capture uses Create 6.0.10 at `ac0c444d9828da3453ae8cc65338e8de063286fb`
with Java 21. Apply the capture patch in a disposable checkout and run
`./gradlew --offline runGameTestServer`, then extract the comma-separated
fields after `CREATE_SPEED_CONTROLLER_ENCASED,`. The patch SHA-256 is
`63dfba533978470a8864971de85229f1300e18aac6bd8a039f9d82ac847540ce`.
Baseline `native-9f42064-a5156e57df79` differed in 32 rows.
Build `native-9f42064-3bf392fcd9c8` matched all 72 rows with prepared
pack SHA-256 `d6361c9f73eee47726e1b26463b463670e7be1e6b5e42a47019a14318d37c7df`.

Four additional rigs use the controller's settings board to check which block
breaks at the default kinetic limit. A shaft-driven large cog turns a small
cog at 256 RPM with a setting of ±128. At ±129 the large cog breaks before the
next sample, leaving the controller, small cog and motor in place. After
setting ±48, replacing the large cog restores both gear speeds. All blocks
survive the same edits with the motor missing or driving from the large-cog
side. The replay compares exact block presence and setting plus RPM to four
decimal places from ticks 1–18. Tick 0 records the Java setup state.
[Java trace](fixtures/rotation-speed-controller-break-java.csv) ·
[Capture patch](tools/java-rotation-speed-controller-break.patch)

Apply the break-order patch to the pinned Java checkout and run the same
GameTest command, then extract the fields after
`CREATE_SPEED_CONTROLLER_BREAK `. The patch SHA-256 is
`5728675450d454a0fad2a505b331105c16412e97288d8dc0ec24faa1d91d1bd4`.
Baseline `native-9f42064-3bf392fcd9c8` differed in 12 rows.
Build `native-9f42064-711c7991bebd` matched all 72 rows using the same
prepared pack and passed all 13 selected regressions.

```sh
python3 tools/test-rotation-speed-controller.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --loaded
python3 tools/test-rotation-speed-controller-overload.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --boundaries
python3 tools/test-rotation-speed-controller-reopen.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-cascade.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-competing.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-encased.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-break.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-wrench.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-render.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-rotation-speed-controller.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-rotation-speed-controller-timing.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-clipboard.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-rotation-speed-controller-clipboard.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --lan
```

A diagnostic four-gearbox bypass confirmed a loop conflict at initial motor
attachment. The Java loop at a +24 RPM target breaks the controller and
first gearbox. The Horizon baseline keeps the loop in place and publishes
different gear speeds. In Java, the loop with a −24 RPM target runs until a
setting edit to −48 breaks the controller, large cog and first gearbox.
Installing the missing gearbox while the +24 RPM loop is already powered
breaks the newly placed gearbox in Java by the next sample. Horizon keeps
the gearbox and reverses the large cog from +24 to −24 RPM.

The [LAN replay](tools/test-multiplayer-rotation-speed-controller.py)
checks host and guest settings, shaft RPM after a server step, and guest
cog placement. The [timing replay](tools/test-multiplayer-rotation-speed-controller-timing.py)
uses the real settings screen on an offscreen host and guest. It freezes the
world between packet acceptance and the next server tick. Java 6.0.10's
settings callback immediately updates theoretical output RPM to +64 for the
host and −32 for the guest. The host and guest block entities both receive
each setting on that tick. Effective kinetic RPM is zero while Java is frozen.
The four [captured Java observations](fixtures/rotation-speed-controller-lan-timing-java.csv)
cover both actors and both recipients.

The Horizon settings callback now refreshes every connected kinetic member
after the target changes, matching Java's remove-and-reattach path. The
headless client cannot expose the controller settings screen to the test
driver, so the two-client settings interaction uses offscreen rendering. In
the fresh build after cherry-picking `16af87f`, the Horizon timing replay
matched Java: host +64 and guest −32 were visible on the output shaft at
acceptance, before another server step. The targeted parity selection passed
17/17 checks, including the LAN timing replay.

The Java reference uses a disposable offline-profile setup and explicit IPv4
loopback binding. On the pinned Create checkout, apply the render patch first
and then the LAN timing patch; run
`python3 tools/capture-java-rotation-speed-controller-lan.py /path/to/checkout /path/to/empty-capture-dir`
with Java 21. The LAN patch SHA-256 is
`830572544d2ac0733dcac1770da2d0cf02a6f603c81562add49ef78fd84a1427`.
[Capture patch](tools/java-rotation-speed-controller-lan-timing.patch)

The [Clipboard replay](tools/test-rotation-speed-controller-clipboard.py)
copies the controller's signed setting using Create's `Speed` key and
`Row`/`Value` payload, then pastes −64 and +96 RPM into a second controller.
Solo and LAN guest replays check that Clipboard interactions leave the
simulation tick unchanged. The LAN host is headless; only the interacting
client renders offscreen.

### APP-1951 bounded gameplay pass

The finite matrix for this delivery retains the existing Java comparisons and
adds the signed Clipboard actions above:

* Six survival placement cases cover both controller axes, blocked-top fallback,
  large-cog placement and shaft-preferred orientation. Encased cog checks cover
  horizontal valid layouts and parallel, vertical and small-cog controls.
* Settings checks cover −256, −73, −1, zero, +23, +83, +128, +256 and the
  overload boundary at ±129, plus positive/negative reversal and passthrough.
  The 23-tick boundary fixture compares seven connected speeds per sample.
* The 40-tick loaded cascade changes both controller targets, removes the first
  source and powers from the opposite end. The 24-tick competing-motor fixture
  covers a stronger same-direction source and an opposing source that breaks.
  Both compare connected speed/sign; the cascade also compares stress/capacity.
* Persistence saves four connected rigs: active −73 and +83 RPM outputs, plus
  zero-target outputs in both drive directions while their inputs remain active.
  It samples the saved state, the first reopened tick and six resumed ticks;
  all 32 Java rows matched.
* LAN coverage includes a host setting +64 RPM, a guest editing it to −32 RPM,
  guest large-cog placement and guest Clipboard copy/paste. Resulting host state
  matches; settings/clipboard delivery checks do not claim Java packet-arrival
  or interpolation timing.
* The powered four-gearbox/controller loop-close replay matches the saved Java
  outcome: the newly inserted gearbox loses its block entity by tick 8 and is
  air by tick 9, while the original network retains +24 RPM.
* On the fresh combined build `native-9f42064-5a0a0aaed520` (Horizon source
  `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, prepared pack SHA-256
  `d6361c9f73eee47726e1b26463b463670e7be1e6b5e42a47019a14318d37c7df`), the
  bounded controller suite, APP-1943 source-conflict check and selected neighbor
  regressions passed 21/21. This build includes the APP-1943 merge and the
  shared Wrench changes from main through `716e57e`; checks used this build's
  `horizon-client` and resource directory. The compatible-launcher rebuild
  took 8m00s (incremental). Test outputs are retained in `.local/parity/`.

The formerly blocking shared-network mismatch from
[APP-1943](https://linear.app/appstu/issue/APP-1943/create-full-parity-kinetic-network-propagation-speed-stress-and)
is resolved and checked on the combined build. Full 1:1 parity remains open.

Nonblocking follow-ups are exact bracket-transition timing, Flywheel
instancing, overload tint/particles, cosmetic feedback-sound timing, other
Clipboard settings families and unfrozen LAN frame-arrival timing.

## Analog Lever

`tools/java-analog-lever-trace.patch` adds two GameTests to the pinned Create
checkout. The first records 105 ticks in `fixtures/analog-lever-java.csv`.
The Horizon replay uses real right clicks and crouch input, including bursts
of successive clicks and attempts beyond both ends of the 0–15 range. All
105 observations of the lever value, its debounce timer, the neighboring
wire, and the wire powered through its support match Java. The second
reference records nine ticks around powered removal. Both destruction and
block replacement match the two wires, including the transition to zero on
the removal tick. Survival crafting and placement verify the original stick
and andesite casing recipe and axe and pickaxe mining tags. A separate LAN
run checks the host raising the lever and the guest lowering it while holding
a block, with both circuits synchronized and both inventories intact.

The fixtures use the original base, handle and indicator models and block
texture. The visual run captures the low and raised handle in Horizon.
The [save/reopen replay](tools/test-analog-lever.py) raises the lever to State 7,
saves after the 15-tick debounce has settled, reopens the same world, and checks
State 7, ChangeTimer 0, and both connected redstone wires before lowering it and
checking State 6 and both outputs. This is source-aligned gameplay persistence
evidence; it does not claim Java restart-timing parity. Wall and ceiling power,
visual tick timing, audio playback, and ambient particles remain follow-ups. The
pinned Java Analog Lever is not `IWrenchable`; Horizon likewise leaves a
Wrench-held interaction unchanged, so Wrench behavior is source-aligned and no
separate gameplay fix is required.

The isolated replay passed on `native-9f42064-d6dc2ad18d3f` with pack
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

```sh
python3 tools/test-analog-lever.py --visual /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --removal --destroy /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --removal /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --craft /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --reopen /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-analog-lever.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Survival progression baseline (APP-2094)

The bounded progression path passed on the isolated build
`native-9f42064-b2e225daec86`, built from Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, with the pack prepared from the
pinned Create checkout. All 12 focused checks passed: the six-recipe survival
craft replay includes Andesite Alloy; brass Basin mixing matched 186 Java
ticks; and brass Depot pressing matched 71 Java ticks and four impact cues.

Advancement checks matched the original 14-tick Alloy and casing traces in solo
and LAN. The placer alone earned casing progress. Small Water Wheel score and
ownership matched 32 Java ticks in solo, LAN, and after reopening the placed
wheel; a LAN guest could earn the award while the host remained a bystander.
Press ownership matched 33 Java ticks in both LAN role directions, with only
the placer earning the award. The first advancement check also retained earned
progress after a solo reopen. This covers the recorded host/guest ownership
cases and representative persistence; other advancement criteria, rewards and
progression combinations remain follow-ups. Full 1:1 remains Open.

## First Create advancements

The [Java advancement probe](tools/java-first-advancements-trace.patch)
records the root and Andesite Alloy criteria before and after inventory
acquisition. Holding a stick first unlocks the root on sample 5.
Acquiring an Andesite Alloy unlocks its advancement on sample 9. Native
`0df22c12788d` matches all 14 [Java ticks](fixtures/first-advancements-java.csv)
for both the solo player and a real LAN guest. The host keeps separate
progress and earned advances survive a solo world reopen.
The pack carries both original JSON files, the original background,
and matching localized labels. The [Horizon replay](tools/test-first-advancements.py)
checks the criteria themselves. The advancement screen and toast frames
remain under comparison.

The [manual casing probe](tools/java-casing-advancement-trace.patch)
extends that fixture with a survival player applying alloy to stripped
oak. The original award occurs on the action tick, alongside the block
replacement and alloy consumption. With `--casing`, the Horizon replay
matches all 14 observations and the immediate award for a real host and
guest on native `4d8eb3a09003`. It also checks solo reopen and separate
progress for the LAN host. Deployer-awarded casing progress remains open.

The [original small Water Wheel probe](tools/java-waterwheel-advancement-trace.patch)
assigns the wheel to a real server player and samples a second player's progress.
Both opposing streams leave both criteria incomplete. On tick 31 the effective
flow becomes 2 and only the placer earns the advancement.
On native `542458f07b38`, the [Horizon replay](tools/test-waterwheel-advancement.py)
matches all 32 ticks after real survival placement, after a guest places the
wheel in the host's world, and after saving and reopening between placement
and power. The guest still earns it when the host operates the levers.
The original 32-tick small wheel and 62-tick large wheel motion fixtures
also pass, along with 48 small wheel and gauge render samples. The
[large wheel award probe](tools/java-large-wheel-advancement-trace.patch)
checks 62 ticks. On native `622e91a1426c`, solo and LAN match every score
and award, including the first award at tick 42. The [dedicated Java
restart capture](tools/capture-java-large-wheel-restart.py) saves and stops
the original server, restarts the same world, and opens the gate after
five active wheel ticks. Its [62-tick reference](fixtures/large-waterwheel-server-restart-java.csv)
reproduces both late differences from the uninterrupted trace. The
Horizon replay matches all 62 restart flow scores on natives
`4ffbff0b2a25` and `5d18ba4dd0d3`, preserves the placed wheel's owner,
and gives the original award at tick 42 after reopening. A second run waits
one more active tick after restart. It matches all 62 samples against the
[six-tick Java restart capture](fixtures/large-waterwheel-server-restart-six-ticks-java.csv).
Apply the [Java probe patch](tools/java-large-wheel-server-restart.patch) before
running the capture against the pinned checkout.

The [Java Magma Wheel probe](tools/java-lava-wheel-advancement-trace.patch)
adds falling lava beside a small wheel. It awards only Magma Wheel
to the placer when the score becomes −1 on tick 5. The [Horizon replay](tools/test-waterwheel-advancement.py)
matches all 18 ticks solo and in LAN on native `4ffbff0b2a25`.
The real guest earns the award while the host receives neither wheel
criterion. The [full-size lava probe](tools/java-large-lava-wheel-advancement-trace.patch)
places the falling fluid two blocks from the hub. Native `5d18ba4dd0d3`
matches all 18 ticks for the larger wheel in solo and LAN, including
the same tick-5 award and the bystander's unchanged progress. The
pack carries the original Magma Wheel definition. The advancement
tree presentation remains under comparison.

## Brass pressing and Deployer crafting

The [original Java press probe](tools/java-brass-pressing-trace.patch)
turns two Brass Ingots into two Brass Sheets over
[71 ticks](fixtures/depot_brass_pressing-java.csv), including a brief
power cut. The [Horizon replay](tools/test-depot-pressing.py) with
`--brass` matches the press head motion and both outputs. It then checks
that the original crafting grid patterns give one Brass Hand and one
Deployer in survival, consuming every ingredient. Both new items use
the byte-identical original model and texture. Verified in Create Parity Lab
build `b4b2c9b204c4`. The original iron press replay also matches 71 ticks.
Build `be37f52ce36a` passed both replays again and the four
[original Depot impact cues](fixtures/depot-press-sound-java.csv).
The sounds played at ticks 24 and 43 after the same power interruption.

The [moving-belt Java Press fixture](tools/java-stacked-belt-press.patch)
records [106 ticks](fixtures/stacked-belt-press-java.csv) of a stacked
input through three stamps and Depot deliveries. The [Horizon replay](tools/test-stacked-belt-press.py)
on build `a689ec5c8086` matched head travel, item positions and locks, and
six playback cues. The [LAN replay](tools/test-stacked-belt-press-lan.py)
heard the cues on both clients at ticks 19, 46, and 73. The guest
physically took each sheet from the host's Depot at ticks 51, 78, and 105.
Build `eb3ff28a1935` replayed those checks and both clients heard the
[original Belt-to-Depot slide](fixtures/belt-depot-slide-java.csv) at
each of the three pickup ticks. Both 71-tick Depot checks and the 190-tick
track assembly passed on the earlier Press build.

The [loose-item Java fixture](tools/java-ground-item-press.patch) records
[81 ticks](fixtures/ground-item-press-java.csv) of three dropped iron ingots
falling onto stone and being pressed into separate sheets. The [Horizon replay](tools/test-ground-item-press.py)
on build `5d18ba4dd0d3` matched ground contact at tick 7, the first scan at
tick 15, and sheet conversion and both original impact sounds at ticks 24,
43, and 62. The 132-sample Basin and moving-belt regressions also passed.
The ticket baseline extends that replay with a non-recipe cobblestone spawned
ahead of the valid ingot stack; the Press leaves it untouched and still matches
all 81 Java samples. On build `native-9f42064-b02beacd07a9`, the updated
[Pressing category check](tools/test-pressing-category.py) passed iron, gold and
copper sheet recipe routes and host-to-guest recipe/tag synchronization. A
separate [material route check](tools/test-press-material-routes.py) processed
one gold ingot into a golden sheet and one copper ingot into a copper sheet.
The combined Depot, Brass, stacked-belt, LAN collection, ground-item, category,
material route, placement, and vertical drop checks all passed on this build.

The [Press lifecycle check](tools/test-press-lifecycle.py) filled the Depot's
eight output slots with 512 cobblestone and processed two iron ingots. One sheet
remained in the Depot and one was dropped into the world; both inputs were
accounted for with no duplicate output and all cobblestone retained. The same
check reopened an idle powered Press and an active Press with two ingots. The
active machine retained its input/progress and finished both cycles after
reopen. This is a gameplay save/reopen check; it does not claim Java reload
timing equivalence.

The [Java Press ownership fixture](tools/java-press-advancement.patch)
captures [33 ticks](fixtures/press-advancement-java.csv) from ordinary
placement against a Creative Motor through a second player's Depot use.
Build `bf2b00b6b302` matched the west-facing placement, 128 RPM, and the
first sheet and Bonk! at tick 14. The placer was 64 blocks away. Both LAN
role directions awarded the placer alone. The Depot retained the ingot
after the use, and the previous three empty-handed guest pickups and
all six cues passed again.

The [Press placement replay](tools/test-press-placement.py) matched
[18 original Java survival cases](fixtures/press-placement-java.csv)
on build `15cd1d474de3`. It checks empty-facing and neighboring-shaft
rules, both same-axis shaft ties, and the two-block offset over a Basin,
Depot, Weighted Ejector and horizontal belt. A sloped belt places at the
ordinary height. A blocked Basin retains the held Press.

Build `6e8dc503ce07` matched [seven original Mixer placements](fixtures/mixer-placement-java.csv)
with the same [survival replay](tools/test-press-placement.py) using `--mixer`.
Both devices match the support heights and blocked placement. The
[fresh Depot replay](tools/test-depot-first-click.py) also matched the
[three Java states](fixtures/depot-first-click-java.csv) on the creation
tick, moving three ingots into the Depot and back to the player.
Build `73a19a6be80d` matched the [original slide sound](fixtures/depot-slide-java.csv)
on the deposit tick at volume .125 and pitch 1.5. In LAN the guest moved
the items and both clients heard one slide. Retrieval produced no
second slide.

The Depot baseline checks on `native-9f42064-d7e37b705c75` added
[survival crafting, placement and loaded idle reopen](tools/test-depot-baseline.py):
the player crafts and places the Depot, swaps complete ingot stacks, reopens
the world, then retrieves the held stack with all counts conserved. Its
[pushing Funnel custody case](tools/test-depot-baseline.py) holds both a matching
and a different incoming stack outside occupied Depots for 16 ticks, then
transfers exactly one ingot after each Depot is cleared. The registered checks
`depot-survival-reopen` and `depot-pushing-custody` passed with
`depot-first-click`, `depot-first-click-lan`, `depot-pulling-funnel`,
`depot-pulling-funnel-lan`, `depot-comparator`, `depot-pressing`,
`press-lifecycle`, `weighted-ejector-belt-input-lan`, and
`weighted-ejector-occupied-lan`. The press lifecycle check confirms empty and
active save/reopen; the LAN first-click and pulling cases cover guest actions.
The original first-click checks matched all three Java states solo and in LAN;
the pulling Funnel checks matched all 96 Java rows in both modes, comparator
matched 17 ticks, and pressing matched 71.
The pushing test checks the occupied ordinary Depot's rejection behavior;
Weighted Ejector merge remains covered separately by its original Java trace.
The worktree base commit is `be02d33b1331352ed5a69cba28d93e6f04fafeb7`, with the
pinned Horizon revision `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and pack
SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
To reproduce the finite set on that build:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-d7e37b705c75/horizon-ctl .local/patched-launcher/versions/native-9f42064-d7e37b705c75/horizon-client .local/patched-launcher/versions/native-9f42064-d7e37b705c75/.local/horizon-client/26.3 --jobs 2 \
  --check depot-survival-reopen --check depot-pushing-custody \
  --check depot-first-click --check depot-first-click-lan \
  --check depot-pulling-funnel --check depot-pulling-funnel-lan \
  --check depot-comparator --check depot-pressing --check press-lifecycle \
  --check weighted-ejector-belt-input-lan --check weighted-ejector-occupied-lan
```

All eleven selected checks passed. Three initially failed because the isolated
worktree lacked the copied structure fixtures at their expected path or the new
script indexed chat output from a no-op game-mode command; both harness issues
were corrected and those checks reran successfully. The updated runner includes
the two new focused Depot checks. Full 1:1 remains Open.

The [vertical Depot replay](tools/test-depot-drop-press.py) on build
`beea127aa56c` matched all [41 original Java ticks](fixtures/depot-drop-press-java.csv).
A loose ingot landed in the center of the Depot on tick 7, played the
original plop at volume .25 and pitch 1.25, and became an iron sheet on
tick 15. The earlier solo and LAN deposit and retrieval checks also passed.

### APP-2012 Weighted Ejector gameplay baseline

The receiving Depot baseline established player retrieval, occupied-inventory
rejection and recovery, and custody through reopen. The Ejector pass uses that
Depot on a four-block course.
[APP-1969](https://linear.app/appstu/issue/APP-1969/create-gameplay-baseline-depot) ·
[PR #29](https://github.com/andrhlt/horizon-create/pull/29)

The reference is Create 6.0.10 at `ac0c444d9828da3453ae8cc65338e8de063286fb`
(Minecraft 1.21.1, NeoForge 21.1.219). The native base is
`e8b3918a44b7156a124244af531af911991927ad` on Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` (Minecraft 26.3). The pack SHA-256
is `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Final native build: `native-9f42064-698ea7382493`. All nine targeted checks
passed on this post-rebase build. The initial lifecycle result from the earlier
build is retained under `.local/app-2012-sandbox-diagnostic/`.
Source review covered the Java recipe and placement packet, `EjectorBlock`
contact and signal handlers, and `EjectorBlockEntity` charge, launch, target,
and save rules. The new lifecycle check complements the existing Java
capture replays. [Lifecycle check](tools/test-weighted-ejector-lifecycle.py)

| Case | Check and comparison |
| --- | --- |
| Survival acquisition and configuration | `weighted-ejector-lifecycle` crafts one Ejector from a gold sheet, Depot and Cogwheel, consumes it during ordinary placement, marks a target four blocks east, and sets the stack size to three. `weighted-ejector-target-lan` covers eight Java target cases and clearing the mark. `weighted-ejector-stack-size-lan` compares 46 Java ticks and a guest editing the threshold from three to two. |
| Short transfer, empty or occupied Depot | `weighted-ejector-empty-lan` and `weighted-ejector-occupied-lan` compare 60 ticks each. The empty course launches at tick 14 and delivers on 34. The occupied course waits until the guest removes the blocker on 20, launches on 22, and delivers on 42. The guest retrieves exactly three ingots in each run. |
| Obstructed trajectory and moving Belt input | `weighted-ejector-obstacle-lan` compares 42 Java ticks, including collision, physical stack release, and guest pickup. `weighted-ejector-belt-input-lan` compares 90 ticks of ingestion, merge and delivery. |
| Standing player takeoff and landing | `weighted-ejector-player-lan-host` and `weighted-ejector-player-lan-guest` each compare 27 Java samples aligned to the initial descent. The actual actor lands on the raised course at takeoff +20, at relative position `(4.341349510, 3.0, 0.5)` with 20 health. Each position and velocity axis must differ by less than `2e-7`, and grounded and health fields must match exactly. Both clients hear the launch. |
| Redstone inhibit, retrigger, and save/reopen | `weighted-ejector-lifecycle` checks 24 ticks of held cargo on each side of the idle reopen. It saves with three ingots at flight age six, then verifies the flight or completed Depot delivery after reopen, allowing the short course to finish during startup while requiring exact cargo conservation. After the Ejector recharges, the second batch stays held for another 24 powered ticks. Removing power delivers the second batch. All six ingots end in the player inventory, with no residual source, flight, destination, or loose cargo in a final 24-tick observation. Target direction, range, threshold, and power are checked after both reopens. These are Horizon gameplay save/reopen checks. |

The strict flat-floor guest trace remains intermittent. On
`native-9f42064-4a2ebff12602`, three of five repeats matched all 36 samples. In
two, the guest received the authoritative landing health and velocity correction
at takeoff +24, one tick earlier than the selected Java client trace. Position,
grounded state and subsequent samples matched. A second Java client captured
that correction at +26. Full 1:1 remains Open for packet arrival around contact,
broader geometry and fluids, and remaining presentation cases.

```sh
HORIZON_NO_AUDIO=1 python3 tools/test-parity.py "$build/horizon-ctl" "$build/horizon-client" \
  "$build/.local/horizon-client/26.3" --jobs 1 \
  --check weighted-ejector-lifecycle --check weighted-ejector-target-lan \
  --check weighted-ejector-stack-size-lan --check weighted-ejector-empty-lan \
  --check weighted-ejector-occupied-lan --check weighted-ejector-obstacle-lan \
  --check weighted-ejector-belt-input-lan --check 'weighted-ejector-player-lan-*'
```

The [Weighted Ejector Java probe](tools/java-depot-ejector-launch.patch)
and [Horizon LAN replay](tools/test-depot-ejector-launch.py) matched the
charge, lid motion, flight age and centered three-ingot delivery across
two 60-tick runs on build `52df14ec0fdd`. The
[empty Depot](fixtures/depot-ejector-launch-java.csv) received the stack
at tick 34 after launch at tick 14. In the
[occupied Depot run](fixtures/depot-ejector-blocked-java.csv), the guest
retrieved the blocking diamond at tick 20. The Ejector then launched at
tick 22 and delivered at tick 42. Both clients heard the original launch
and arrival sounds at those ticks, and the guest collected all three ingots.

The [target placement fixture](tools/test-ejector-target-placement.py)
on build `add6251b3a02` matched [eight cases](fixtures/weighted-ejector-target-java.csv)
using the [original Java placement packet](tools/java-ejector-target-placement.patch)
and target directions from Java's client selector. The Horizon player
crouch-clicked a target and placed the Ejector with the expected direction
and distance. Both solo and LAN matched four directions, the 32-block
limit, and the default facing and distances for invalid targets. The solo
run also confirmed that changing hotbar slots clears the selection.

On build `de1457a1ac8b`, a crouch-left-click cleared the target without
breaking its block in solo and LAN. The [wind-up trace](fixtures/depot-ejector-windup-java.csv)
matched all nine original button clicks at the recorded world tick phase,
with pitch following lid motion. Both LAN clients heard the wind-up,
launch and arrival cues, and the occupied-Depot replay passed again.

The [obstacle replay](tools/test-depot-ejector-obstacle.py) on build
`5252897a2147` matched all [42 original Java ticks](fixtures/depot-ejector-obstacle-java.csv)
through a stone collision at tick 17, the release of all three ingots,
and landing at tick 38. The [Java probe](tools/java-depot-ejector-obstacle.patch)
records the item ID phase for vanilla's grounded movement cadence. Both
Horizon clients saw the same released stack and the guest picked it up
where it landed. The clear-flight and winding audio replay passed again.

The [stack-size replay](tools/test-depot-ejector-threshold.py) on build
`f64063cd8804` matched [46 original Java ticks](fixtures/depot-ejector-threshold-java.csv)
as solo and LAN players changed Ejected Stack Size. Two ingots waited
while the minimum was three. Setting it to two at tick 20 launched both
at tick 22 and delivered them at tick 42. The Speed Controller and Copper
Valve Handle passed their earlier control traces on the same build.

The [open-air replay](fixtures/depot-ejector-air-java.csv) matched 60
original ticks on build `5b369a5f1e30`, including release at tick 35,
the falling stack's position and velocity, and the guest's pickup
where it landed. The earlier obstacle and winding replays also passed.

The [Hopper-fed Ejector replay](tools/test-depot-ejector-hopper.py) matched
[66 original Java ticks](fixtures/depot-ejector-hopper-java.csv) in solo
and LAN on `da3523c53274`. The original Hopper fed one ingot at ticks 9,
17 and 25. The queued ingots centered and merged at ticks 26 and 34, and
the three-ingot stack launched at tick 35 and reached the Depot at tick
55. The LAN guest collected the stack. The minimum stack and open-air
replays passed again on the same build.

The [moving Belt replay](tools/test-depot-ejector-belt.py) matched
[90 original Java ticks](fixtures/depot-ejector-belt-java.csv) in solo
and real LAN on `c28568a5b862`. The Ejector accepted one ingot at tick 46
and queued the remaining two at tick 47. It merged them at tick 55,
launched at tick 60, and delivered all three to the Depot at tick 80.
The guest retrieved the stack. The [receiving Belt replay](tools/test-depot-ejector-belt-target.py)
matched [63 original ticks](fixtures/depot-ejector-belt-target-java.csv)
on the same build. The Ejector kept the stack until the stopped receiving
Belt started, launched at tick 26, and placed all three ingots on the
Belt at tick 46 without spilling an item. The Hopper LAN replay passed again.

The [dropped-stack replay](tools/test-depot-ejector-dropped.py) matched
[68 original Java ticks](fixtures/depot-ejector-dropped-java.csv) in solo
and LAN on `8d82989a01a3`. The first surface collision admitted one ingot
at tick 21. The two still in the world followed Java's item motion until
the next collision at tick 25, then merged into the held stack. The
Ejector launched all three at tick 26 and the Depot received them at
tick 46. The guest collected the stack, and the previous Hopper and
moving Belt LAN replays passed again.

The [target click replay](tools/test-ejector-target-click.py) matched
all [four Java cancellation cases](fixtures/weighted-ejector-target-click-java.csv)
on `3e5071400ded`, in solo and with the LAN guest holding the Ejector.
A crouch-left-click breaks an unrelated block before and after marking
a target. The subsequent placement still faces the marked stone four
blocks east. One crouch-left-click on that target clears the mark and
leaves the block intact. The [client probe](tools/java-weighted-ejector-target-click.patch)
calls the original event handlers in a connected Java client.

The [Ejector target reconnect replay](tools/test-ejector-target-rejoin.py)
matched [Java's saved-player reconnect](fixtures/weighted-ejector-target-rejoin-java.csv)
on `e58898425b9f`. The guest marks a block four spaces east and reconnects
as the same player with their original inventory. The next placement shows
the original unmarked feedback, and the Wrench displays the one-block
default range. Both earlier LAN targeting replays passed again. The
[Java probe](tools/java-ejector-target-rejoin.patch) records the target
across two actual client sessions and the resulting server distance.

The [Ejector Wrench preview replay](tools/test-ejector-wrench-preview.py)
matched [Java's target bounds and trajectory](fixtures/weighted-ejector-wrench-java.csv)
on `129c2d8fc025`. Aiming the Wrench at a placed Ejector shows the amber
target outline, green launch outline and green dust along its arc.
Three target shapes and elevations matched, covering stone, slab and air.
The solo client emitted 248 matching dust positions and the LAN guest
193 at their observed render phases. Putting the Wrench away ended new
emissions. The [original Java render probe](tools/java-ejector-wrench-preview.patch)
captures bounds and emission spacing, and the [trajectory probe](tools/EjectorTrajectoryProbe.java)
reads the original launcher coefficients used by the portable replay.

The [held Ejector preview replay](tools/test-ejector-held-preview.py)
matched four [Java aiming cases](fixtures/weighted-ejector-held-preview-java.csv)
on `41ac90f72271`. An aligned placement shows a green arc, a diagonal aim
projects a red arc along the dominant axis, and tied diagonal and vertical
aims show only the amber target outline. Solo and LAN each matched 96 dust
positions at their observed render phases. Switching the held slot, clearing
the mark with a crouch-click, and placing toward the marked block each
ended the preview. The guest's mark only appeared on the guest client.
The [connected Java render probe](tools/java-ejector-held-preview.patch)
records the original outlines, colors and particle positions.

The [Ejector flight model replay](tools/test-ejector-flight-pose.py)
matched 24 solo and 48 host/guest model transforms on `29a89691b39a`.
The [original renderer capture](fixtures/weighted-ejector-flight-pose-java.csv)
covers all four directions and checks a half-scale tumbling ingot and an
upright, enlarged spinning package. Both clients stopped drawing the models
at the normal end of flight. On the same build the powered launch replay
matched 60 Java ticks and nine wind-up clicks, then the guest collected
all three ingots from the receiving Depot.

The [Ejector Pulling Funnel replay](tools/test-ejector-funnel.py) matched
[180 Java tick rows](fixtures/weighted-ejector-funnel-java.csv) in solo and
LAN on `3cfeefd69f2e`. One Funnel diverted the charge to a barrel at
tick 14 without an item flight. A second waited until the barrel had room
for the full stack, then diverted at tick 22. With the Funnel turned
around, it pulled at tick 13 before the Ejector fired. The LAN guest took
three ingots from each of the three barrels. The powered launch, Funnel
placement and original Smart Observer belt-and-funnel replays passed.

The [stationary Depot Funnel replay](tools/test-depot-pulling-funnel.py)
matched [96 Java tick rows](fixtures/depot-pulling-funnel-java.csv) in solo
and LAN on `native-9f42064-d7e37b705c75`. The open barrel accepted three ingots on tick 13.
The powered Funnel held its items through tick 18 and resumed on tick 19.
The partly full barrel accepted one on tick 13 and the other two on tick
21 after space cleared. The full barrel held its Depot output until space
opened, then resumed delivery. The guest retrieved the eight remaining ingots
from the barrels. Ejector Funnel, Depot placement and slide, and powered
Press controls also passed.

The [inward Funnel flap replay](tools/test-ejector-funnel-flap.py)
matched [21 original Java phase samples](fixtures/weighted-ejector-funnel-flap-java.csv)
of all four Brass Belt Funnel flap segments on `ea96c8dcb248`. The solo
player, LAN host and guest rendered the original models and heard two
plays of each original sound layer at the Funnel. The
[connected Java capture](tools/java-ejector-funnel-flap.patch) recorded
the two simultaneous flap cues and the subsequent spring motion. The
three-rig Funnel and powered Ejector LAN replays passed on the same build.

The same replay's outward case matched all
[21 Java phase samples](fixtures/belt-funnel-pushing-flap-java.csv) on
`355490e2b464` in solo, LAN host and LAN guest. The Brass Belt Funnel
pushed one ingot from a barrel onto a Depot, swung outward, and played
each sound layer once. The LAN replay sampled every age on each client
before stepping the game clock. Earlier inward playback and the three
stationary Depot Funnel rigs passed on the same build.

The [plain Funnel replay](tools/test-plain-funnel-flap.py) matched
[21 Java phase samples per route](fixtures/plain-funnel-flap-java.csv)
on `e3b18cf882bb` in solo and on both LAN clients. The horizontal Brass
Funnel swung inward while collecting a loose ingot into its barrel and
outward while returning the ingot to the world. Each client saw the actual
item outcome and heard both original sound layers once per transfer.
The outward Belt Funnel and stationary Depot controls passed again.

The [stationary placement replay](tools/test-stationary-funnel-placement.py)
matched [six Java survival placements](fixtures/stationary-funnel-placement-java.csv)
on `15dc7ec61901` in solo and with a LAN guest placing the Funnels. A
side click on a barrel places the held Funnel and consumes one item.
Stone leaves a plain Funnel. A Depot or Weighted Ejector below selects
a Belt Funnel, with pushing for a normal click and pulling while crouching.
The [Wrench replay](tools/test-funnel-wrench-modes.py) matched
[seven Java actions](fixtures/funnel-wrench-modes-java.csv) on the same
build in solo and LAN. It toggles the plain Funnel modes, swaps pushing
and pulling, extends or retracts over horizontal belts, and leaves a
retracted Funnel on a slope. The acting player's Wrench remains in hand.
Legacy moving Belt placement and both moving and outward flap LAN
replays passed again.

The [Funnel Kiss replay](tools/test-funnel-kiss.py) matched
[four original Java Wrench action states](fixtures/funnel-kiss-java.csv)
on `866e2e588177` in solo and both LAN player roles. Extending a Belt
Funnel toward an already extended, opposite-facing Funnel granted the
original hidden advancement on the action tick. Each other arrangement
left it unearned, and the other LAN player received no award. All seven
ordinary Funnel Wrench actions passed again in LAN.

The [Funnel support-change replay](tools/test-funnel-neighbor.py) matched
all [30 Java observations](fixtures/funnel-neighbor-java.csv) on
`3d765664354e` at the same action tick. It covers immediate changes
between plain and Belt Funnels as supports change, including Depot,
Weighted Ejector, Item Drain, Saw facing, and Belt axis and slope.
The host preserved facing, power, water and Brass filter data. The LAN
guest saw each new block state, and the plain and mounted forms both
kept their filters after reopening the world. Prior placement, Wrench
and Funnel Kiss LAN controls passed again.

The [Belt Funnel geometry replay](tools/test-belt-funnel-shapes.py)
matched 64 player-view rays from the [original Java trace](fixtures/belt-funnel-rays-java.csv)
in solo and again from a LAN guest on `1462263813c0`. It checks the front
and top of both materials in all four forms and all four facings. The pack
also matches the [492 Java shape boxes](fixtures/belt-funnel-boxes-java.csv)
for outline, ordinary collision and item collision contexts. Wrench,
stationary placement, support changes and both prior flap replays passed
in LAN with the same pack. The [falling-item replay](tools/test-belt-funnel-item-collision.py)
matched all [25 Java ticks](fixtures/belt-funnel-item-collision-java.csv)
for two ingots. The rear ingot landed on the Funnel at tick 6 and the
front ingot passed through to the floor at tick 12.

The [moving Belt Funnel replay](tools/test-belt-funnel-moving-flap.py)
matched [21 original Java flap ages](fixtures/belt-funnel-moving-flap-java.csv)
in solo, LAN host and LAN guest on `ebe289d50592`. A connector-built belt
delivered iron to the retracted Funnel's barrel. Both clients saw the
first inward flap pose on the following game tick and each heard both
sound layers once. The plain and outward Belt Funnel LAN controls passed
again.

### Andesite and Brass Funnels gameplay baseline (APP-1970)

The bounded case list covers survival acquisition; placement/orientation;
plain insertion and extraction; Belt Funnel insertion and extraction;
Brass filter and amount settings; one exact stack-limited transfer;
rejected/full-output backpressure; removal/reconnection; representative
guest configuration and transfer; and idle and active save/reopen.

`machine-crafting-java.csv` now includes both funnel tiers. The Andesite
Funnel row follows the pinned generated recipe
`data/create/recipe/crafting/logistics/andesite_funnel.json` (andesite alloy
above dried kelp, output two). The Java trace patch includes that recipe for
future capture. This environment has JDK 27 only, so that added row was
source-derived rather than recaptured by the Java GameTest; the existing Brass
Funnel trace remains from the Java GameTest. On the identified Horizon build,
the survival crafting replay matched all 25 recipes, including both funnel
outputs and their remaining inventory.

The selected Horizon integration run passed 13/13 checks: stationary Funnel
survival placement in solo and LAN; seven Java Wrench mode actions in LAN;
all 30 support-transition observations in LAN and settings retention after
reopen; plain Funnel collecting and extracting in LAN; Depot and Weighted
Ejector routes in LAN; package routes in solo and LAN; Creative Crate Funnel
insertion in LAN; and all 25 survival recipes. The LAN Clipboard Funnel replay
matched six Java configuration snapshots, including exact and up-to counts.

`depot-pulling-funnel-active-reopen` adds a source-aligned lifecycle case. A
Brass pushing Funnel with an exact-two filter moves two of five iron ingots
into a Depot. Active save/reopen preserves the remaining three, Depot contents,
filter and amount mode. The occupied Depot blocks another transfer. Clearing
it lets the Funnel move exactly two more; a powered idle save/reopen retains the
one-item remainder and configuration. The check passed on the same build.

Evidence identity: Java Create `ac0c444d9828da3453ae8cc65338e8de063286fb`,
Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, native build
`native-9f42064-6bdf8691aa42` (main-synchronized source `781c0ef`), and pack
SHA-256 `a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
`native/funnel.rs`, `native/belt_funnel.rs`, and `native/funnel_flap.rs` are
byte-identical between that build source and this ticket branch. The current
source build attempt stopped before compilation because several Horizon patch
hunks do not apply to the cached pinned engine source, including hunks in
`horizon-world/src/level/place.rs`, `horizon-client/src/game/use_hand.rs`,
`remote.rs`, and `dispenser.rs`. Therefore the gameplay findings are reviewable,
but this ticket still needs the affected checks rerun on a successfully built
current-source client before its baseline gate can be marked met. Full 1:1
remains Open; other transfer/count combinations and cosmetic effects remain
follow-ups.

Commands for the passing integration evidence (runtime arguments point to the
identified build and its prepared 26.3 resources):

```sh
CTL=/Users/andrewholt/dev/horizon-create/.local/app-2017-evidence/native-9f42064-6bdf8691aa42/horizon-ctl
CLIENT=/Users/andrewholt/dev/horizon-create/.local/app-2017-evidence/native-9f42064-6bdf8691aa42/horizon-client
RESOURCES=/Users/andrewholt/dev/horizon-create/.local/app-2017-evidence/native-9f42064-6bdf8691aa42/.local/horizon-client/26.3
PACK=/Users/andrewholt/dev/horizon-create/.local/app-2017-evidence/create.hmod
python3 tools/test-parity.py "$CTL" "$CLIENT" "$RESOURCES" --jobs 2 \
  --check machine-crafting \
  --check stationary-funnel-placement \
  --check stationary-funnel-placement-lan \
  --check funnel-wrench-modes-lan \
  --check funnel-neighbor-lan \
  --check funnel-neighbor-reopen \
  --check plain-funnel-collect-flap-lan \
  --check plain-funnel-extract-flap-lan \
  --check depot-pulling-funnel-lan \
  --check package-funnel \
  --check package-funnel-lan \
  --check creative-crate-funnel-insert-lan \
  --check weighted-ejector-funnel-lan
python3 tools/test-parity.py "$CTL" "$CLIENT" "$RESOURCES" --jobs 1 \
  --check depot-pulling-funnel-active-reopen
python3 tools/test-clipboard-copy.py "$CTL" "$CLIENT" "$RESOURCES" \
  --funnel --lan --pack "$PACK"
```

The [Ejector comparator replay](tools/test-depot-ejector-comparator.py)
matched [all 62 Java ticks](fixtures/depot-ejector-comparator-java.csv)
in solo and LAN on `e6e755d336c6`. The comparator and dust stepped through
4, 8, 11 and 15 as the stack grew. The player selected Unlimited in the
Ejector settings and the signal dropped to 1 two ticks later, then to 0
two ticks after launch. The guest saw all six transitions and collected
the four ingots. The original Depot comparator and previous Ejector
settings replays also passed.

The [two-Ejector replay](tools/test-depot-ejector-chain.py) matched all
[88 Java ticks](fixtures/depot-ejector-chain-java.csv) in solo and LAN on
`466d7959fb1f`. The first Ejector waited for the downstream one to charge,
launched at tick 35 and delivered directly to the center of the receiving
plate at tick 55. The receiver launched one tick later and the final
Depot caught the ingot at tick 76. The guest collected it and the earlier
loose-stack LAN replay passed again.

The [mob replay](tools/test-depot-ejector-mob.py) matched both 64-tick Java
courses on `7934b758ce7f`, including position, velocity, grounded state,
health and machine phase. A [centered pig](fixtures/depot-ejector-mob-center-java.csv)
launched at tick 20 and landed on a raised platform at tick 40. An
[off-center pig](fixtures/depot-ejector-mob-offset-java.csv) moved halfway
inward on contact, then launched and landed one tick later in solo and LAN.
The guest saw it airborne and at the landing point. The
[flat-floor course](fixtures/depot-ejector-mob-flat-java.csv) matched
all 64 ticks on `20d9d98e314b` in solo and LAN. The pig landed on tick 44
with 7 health, using Java's fall-damage rule for Ejector-launched mobs.
The raised, off-center LAN regression still passes. An ordinary Horizon
pig control showed identical position, motion and 8 health after landing
with and without the change. The earlier item launch, wind-up sounds
and guest Depot pickup passed again.

The [live player replay](tools/test-depot-ejector-player.py) matched
[27 consecutive ticks](fixtures/depot-ejector-player-java.csv) from two
real Java clients on `c6249ebec243`. The solo player, active LAN host and
active LAN guest all matched descent, centered takeoff, velocity, and
landing 20 ticks after takeoff without losing health on the raised
platform. Both LAN clients heard the original trapdoor and chest cues
once per launch. The [Java capture utility](tools/capture-java-ejector-player.py)
reproduces the reference with the [client probe](tools/java-depot-ejector-player.patch).
The prior offset-mob and item-launch LAN replays passed again.

The [flat-floor player replay](fixtures/depot-ejector-player-flat-java.csv)
matched 36 ticks on `3be6ef97e08d` in solo and with either LAN player
riding. Touchdown occurs 24 ticks after takeoff, and the player loses
3 health using Java's fall rule for that launch. The selected original
client trace receives damage on tick 25. The
[second original client](fixtures/depot-ejector-player-flat-late-java.csv)
receives it on tick 26 and travels slightly farther before stopping.
One concurrent Horizon LAN replay received the same damage on tick 24,
so client packet delivery still varies around contact. A solo run also
skipped two control observations under that load. The replay now checks
the control clock and repeats a capture with missing observations.
An ordinary Horizon stone fall, legacy Seat landing, and prior raised
and Elytra paths passed their regressions.

The same [player replay](tools/test-depot-ejector-player.py) with `--elytra`
matched [17 Java samples](fixtures/depot-ejector-elytra-java.csv) on
`79b5e6466774`, covering the descent, automatic deployment, and the first
11 ticks of unsteered gliding. The solo player, LAN host and LAN guest
matched the original view rotation and motion while both LAN clients
heard the launch cues. The normal player LAN replay also passed.

The [lid render replay](tools/test-depot-ejector-visual.py) matched 20
original [Java lid poses](fixtures/depot-ejector-lid-java.csv) in solo
and all 40 rendered samples across the LAN host and guest on
`402d13f2e597`. It exercises all four facings at five progress values
and checks that the original packed top model emits geometry. The
[Java capture](tools/capture-java-ejector-visual.py) invokes Create's
original renderer helper. The [live launch fixture](tools/java-depot-ejector-lid-motion.patch)
adds the lid position at the start, midpoint and end of [all 62 ticks](fixtures/depot-ejector-lid-motion-java.csv).
The comparator replay matches those lid samples in solo and real LAN on
`native-9f42064-830dc6e7a557`, including the immediate jump to an open lid on tick 39.
Both renderer regressions passed again with the same pack.

## Mechanical Arm gameplay baseline (APP-2014)

The bounded Mechanical Arm pass reuses the pinned Create `ArmBlockEntity.java`
and the existing Java traces. It keeps the broader target/type and presentation
matrix open.

The checked-in survival crafting trace includes the original Mechanical Arm
recipe. A focused run of that one row matched its output and remainders.
`arm-placement` configured a TAKE and DEPOSIT Depot with ordinary player input,
placed the arm in survival, and transferred an iron ingot on tick 59. The
`arm-brass-mixing` replay matched 248 Java ticks through arm custody, basin
processing and the fixture's power transitions. `arm-loop` matched 101 Java
ticks as two arms passed one diamond between Depots, with the item-count
invariant checked on every row. `arm-burners` matched 75 Java ticks while one
arm fed nine burner outputs.

The registered `arm-backpressure` check leaves an empty input idle for 24
ticks, fills all 27 slots of a barrel output, and confirms 32 ticks of blocked
operation preserve the source item. It opens the output, applies redstone for
32 ticks and confirms the arm stays stopped, then removes the signal and
verifies exactly one item transfers within 64 ticks. The `arm-lan` check has a
guest configure both endpoints and place the arm; the host observes the
transfer, then the guest retrieves the output and the host observes the
emptied Depot. This checks resulting state after guest convergence, not Java
packet arrival timing.

The `arm-persistence` check saves and reopens an idle configured arm, then
reopens an active brass fixture at Java trace tick 32 while it holds zinc. The
target list and held item remain present, and the arm resumes the transfer
within 30 stepped ticks. This is a Horizon gameplay save/reopen check; it does
not claim an exact Java reload comparison. The existing APP-1969 Depot
prerequisite is Done ([PR 29](https://github.com/andrhlt/horizon-create/pull/29)),
as is APP-1962 for Blaze Burner, fuels and blaze cakes
([PR 25](https://github.com/andrhlt/horizon-create/pull/25)).

All Horizon runs used `native-9f42064-340cbe866fa7` with pinned Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3 and pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Client SHA-256 is
`39712c37f7f666a2d730506198523f0d0b42ef7b4a15c0ea9142a95b450224ea`; control
tool SHA-256 is
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`.
The Java source was at
`ac0c444d9828da3453ae8cc65338e8de063286fb`; its `ArmBlockEntity.java` SHA-256
is `5d95cdcad9020f5af86a880daa2b7ec1103cfd4f8e417751cb448bdccaee6b57`.
No new Java capture was needed. These checks did not establish every target,
round-robin mode, output combination or exact arm path/animation; Full 1:1
remains Open.

```sh
python3 tools/test-machine-crafting.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --pack .local/create.hmod --reference .local/arm-machine-crafting-java.csv
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 --check arm-placement --check arm-burners --check arm-loop --check arm-brass-mixing
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 --check arm-backpressure --check arm-lan --check arm-persistence
```

## Mechanical Saw

`tools/java-mechanical-saw-trace.patch` drives the original two saws with
creative motors and records 96 ticks in `fixtures/mechanical-saw-java.csv`.
Horizon matches both speeds, the filtered bamboo cut and ejection,
the unrecognized diamond’s pass-through, the horizontal saw’s
countdown and break progress, its refusal to cut stone, and the removal
of the two-block oak trunk on tick 36.

Survival crafting produces the saw from iron sheets, an iron ingot and an
andesite casing. The placement check exercises both orientations, shaft
alignment and the result filter with ordinary player input. The visual
run captures the original casing, raised blade and rotating shaft.
Broader tree shapes, damage, moving contraptions, output choices with
multiple eligible recipes, and exact presentation timing still need comparison.

```sh
python3 tools/test-mechanical-saw.py --visual /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-mechanical-saw.py --configure /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Mechanical Drill

`tools/java-mechanical-drill-trace.patch` records 93 ticks of a stationary
drill in `fixtures/mechanical-drill-java.csv`. Horizon matches its RPM,
break progress, retry delay, targeted block and loot on every recorded
tick. Stone yields cobblestone on tick 24, dirt breaks on tick 42, and
bedrock survives. Power removal pauses the drill and it breaks the oak
planks on tick 85 after power returns. A neighboring block change delays
progress at the same tick as Java.

Survival crafting produces the drill from three andesite alloy, an iron
ingot and an andesite casing. Ordinary placement aligns it to a rear
shaft or preserves source water when placing it upright. The visual
replay captures the original rotating head and break effects. Moving
contraptions, cobblestone generator optimization, entity damage and
exact sound or visual timing still need comparison.

### APP-1983 bounded gameplay baseline

On 2026-11-20, the stationary replay was rerun from the APP-1983 worktree
against the pinned Java tick fixture. All 93 sampled ticks matched RPM, break
progress, retry delay, target block and collected drops; this includes stone
and dirt breaking, the bedrock control, power stop/resume and the neighboring-
block retry. The existing placement replay also passed its two player cases:
shaft-oriented placement and waterlogged source-water placement. Existing
survival-crafting evidence records production of one Mechanical Drill from
its original recipe. These results retain the scope of the stationary fixture
and do not establish moving behavior.

Runtime identity for the fresh replays: Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, client build
`native-9f42064-6bdf8691aa42` (client SHA-256
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`),
pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`,
and prepared Minecraft 26.3 resources from the same evidence directory.
Commands were `python3 tools/test-mechanical-drill.py --visual ... --pack ...`
and `python3 tools/test-mechanical-drill.py --configure ... --pack ...` with
that build's `horizon-ctl`, `horizon-client`, and prepared resources. The
initial sandboxed launch could not create its temporary control socket; the
same isolated checks passed when rerun with local socket access.

### APP-1983 mounted drilling

Mounted straight-line drilling now uses the existing gantry and mechanical
piston actor callbacks. It applies the pinned forward-motion gate and block
eligibility checks, persists each actor's target and break progress, stalls
movement during mining, puts drops into payload cargo before spawning
leftovers, and clears break progress when motion ends. Linear contraptions may
cross a blocked cell only when a forward-facing drill can mine that exact
eligible target. Create tracks, non-breakable blocks, liquids, air and
collision-free blocks remain obstructions.

On 2026-11-20, final build `native-9f42064-581916b5f99f` (Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, client SHA-256
`cc8272cfcb393bc4e793c53d43bcf87014aa415cc032c2c7fa875af495631884`) passed
all six selected regressions: stationary 93-tick drill trace, drill placement,
mounted gantry LAN/save-reopen, existing gantry LAN/save-reopen,
mechanical-piston actor regression, and ploughing. The mounted LAN scenario
starts from an idle saved gantry, lets a guest power the drive and observe it
move, then saves while the drill has a persistent active `BreakingPos`. After
reopen the drill breaks stone, accounts for exactly one cobblestone/stone drop
in cargo or the world, leaves bedrock unchanged, and stops the gantry. The
stationary trace still matches all 93 Java samples; plough timing and piston
actor regressions pass on the same final native build.

These are representative bounded gameplay gates, not exhaustive 1:1 parity.
Full 1:1 remains Open; other moving contraption types, wider block/drop
combinations, cobblestone optimization and exact effects/presentation remain
follow-ups.

```sh
python3 tools/test-mechanical-drill.py --visual /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-mechanical-drill.py --configure /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

## Linear Chassis

The pinned Java GameTests in [the capture patch](tools/java-linear-chassis-trace.patch)
measure five real bearing assemblies, three placement cases, and seven
adhesive actions. Horizon matched the selected blocks and their relative
positions for all five payloads. The fixture includes all three axes, both
sticky ends, same-axis groups, different-axis neighbors, the default range
of eight blocks, and an air gap where capture stops.

The survival player test selects an axis by looking, inherits the adjacent
chassis axis, and uses the clicked side when sneaking. It also verifies
slimeball application without consumption, supplying both ends by clicking
an already coated end, clearing a joined end, and removing the coating
with an empty sneaking hand. The original crafting recipe yields three
chassis in Horizon survival. The pack contains nine byte-identical Java
model and texture resources across the sticky variants.

A separate 19-tick Java trace drives the stationary bearing with a creative
motor. Horizon matched the capture at tick 4, the active payload, and
restoration at tick 13. The startup correction applies when an adjacent
motor restarts an initialized bearing.

Still to verify are group preview transitions, connected-texture transitions,
multiplayer interaction, rotated block states at disassembly, and chassis
capture on other controllers.

## Secondary Linear Chassis

The pinned [Java GameTests](tools/java-secondary-linear-chassis-trace.patch)
capture both directions of the primary and secondary chassis relationship.
Matching types and axes attach directly and clear adhesive at shared ends.
Different types remain separate until an axial sticky face captures the
other chassis, which can then bring along its own matching group.

Horizon matched 18 game ticks across six powered Mechanical Bearing
assemblies. The replay checks the blocks removed, their relative positions,
and the exact block states restored on the server at the next tick. It
also matches four survival placement cases across both variants and five
adhesive actions that keep the original slimeball count. Both original
shapeless 1:1 conversions work in the player's survival crafting grid.
Seven secondary chassis art files match the pinned Java originals byte
for byte.

## Radial Chassis

The pinned [Java GameTests](tools/java-radial-chassis-trace.patch) record
six real bearing assemblies and a full quarter-turn disassembly. The
18-tick payload replay covers traversal across bends, gaps, the default
radius cutoff, matching chassis on the axle, and a second sticky plane.
The 27-tick rotation replay matches the bearing angle and restores both
the east adhesive and its brick on the north face.

A survival player placed the original block along all three axes, verified
that axial faces reject slime, and matched the coating and removal of
perpendicular faces in all 12 sticky interactions. The original recipe
crafts three blocks using two andesite alloy and three logs. The pack has
15 original art files that match Java byte for byte.

Group preview transitions, multiplayer adhesive interactions, additional brittle and
immovable block cases, and other controllers remain unverified.

## Mechanical Bearing moving-payload collision

The bounded APP-1979 fixture in [tools/test-bearing-player-collision.py](tools/test-bearing-player-collision.py)
uses a glued 3×3 smooth-stone payload with a chest holding seven copper ingots.
It checks that both the host and a LAN guest stay grounded and follow six bearing
turns within 0.2 blocks, then verifies active save/reopen, resumed motion, payload
disassembly and chest restoration. The final isolated build was
`native-9f42064-fd8337b584f8`; pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The existing elevator-standing 134-tick replay, Rope Pulley 66-tick Java replay,
Rope Pulley detach case, and Java bearing quarter-turn Gearbox restoration check
also passed on that build. Full 1:1 remains open for other payload shapes,
multi-axis collision, packet latency and unusual player poses.

## Mechanical Bearing gameplay baseline (APP-1980)

The registered [bounded gameplay check](tools/test-mechanical-bearing-gameplay.py)
(`mechanical-bearing-gameplay`) covers survival placement, empty-hand start
and stop, bedrock-obstructed assembly, positive-to-negative RPM reversal,
automatic stop placement for modes 0/1/2 at near and away angles, and an idle
bearing's `ScrollValue` across save/reopen. These cases follow the pinned
`MechanicalBearingBlock.useItemOn`, `MechanicalBearingBlockEntity.tick` and
`BearingContraption.assemble` behavior at Create
`ac0c444d9828da3453ae8cc65338e8de063286fb` ([block](https://github.com/Creators-of-Create/Create/blob/ac0c444d9828da3453ae8cc65338e8de063286fb/src/main/java/com/simibubi/create/content/contraptions/bearing/MechanicalBearingBlock.java),
[block entity](https://github.com/Creators-of-Create/Create/blob/ac0c444d9828da3453ae8cc65338e8de063286fb/src/main/java/com/simibubi/create/content/contraptions/bearing/MechanicalBearingBlockEntity.java),
[contraption](https://github.com/Creators-of-Create/Create/blob/ac0c444d9828da3453ae8cc65338e8de063286fb/src/main/java/com/simibubi/create/content/contraptions/bearing/BearingContraption.java)).
Both focused checks passed on build `native-9f42064-645e120d2506`, using
Create source `ac0c444d9828da3453ae8cc65338e8de063286fb` and pack SHA-256
`3c687913a0bba61bf6de08200887cc5b735b005a11f48ad6d495f1bd6a852379`:

```sh
TMPDIR=/private/tmp python3 tools/test-parity.py \
  .local/patched-launcher/versions/native-9f42064-645e120d2506/horizon-ctl \
  .local/patched-launcher/versions/native-9f42064-645e120d2506/horizon-client \
  .local/patched-launcher/versions/native-9f42064-645e120d2506/.local/horizon-client/26.3 \
  --jobs 1 --check mechanical-bearing-gameplay --check bearing-player-collision
```

`mechanical-bearing-gameplay` passed survival placement/item consumption,
assembly and empty-hand disassembly, obstructed assembly, reversal, the bounded
mode stop cases, and idle setting save/reopen. `bearing-player-collision` passed
active glued cargo save/reopen and disassembly, plus host and LAN guest riding
the rotating payload while remaining grounded. The run used isolated worlds
and reports 2/2 checks passed. These representative cases do not establish full
1:1 parity; other payload geometries, multi-axis collision, packet latency and
unusual player poses remain open. Shared collision code is unchanged.

## Windmill Bearing

The pinned [Java GameTest](tools/java-windmill-trace.patch) covers a
seven-sail failed assembly and loaded eight- and sixteen-sail windmills
that include canvas, sail frames and wool. The [66 sample rows](fixtures/windmill-java.csv)
compare sail capture, generated and shaft RPM, angular position at
single precision, stress, capacity, reversals and restoration. The
Horizon replay starts and stops the bearing with empty-hand use and
uses the actual Rotation Direction board to reverse each active rig.
It verifies six held client ticks, release-to-submit and a short press
that leaves the setting alone. Real host and guest used the same
board to reverse one shared bearing while its 512 capacity and two
stress stayed consistent. The original bearing, white sail, and both
sail-frame conversion recipes passed normal survival crafting.

The [sail GameTest](tools/java-windmill-sails-trace.patch) covers all 17
sail material definitions, seven dye and shearing actions, and an
eight-sail windmill joined without glue. Horizon replay checks the
registered material properties and default state, and uses the real
player controls to dye and shear the sail structure.

The [reload GameTest](tools/java-windmill-reopen-trace.patch) saves and
unloads the original Java contraption and compares its resumed rotation
and restored sails. The Horizon fixture reopens two running windmills,
checks that all 24 original blade displays survive, verifies the first
controlled f32 rotation step, and stops both rotors. The replay also
passed when the original save came from the previous Lab build.

The [facing fixture](tools/java-windmill-facings-trace.patch) covers all
six orientations with eight naturally attached sails each. Its 90 Java
samples match Horizon's capture, rotation, reversal, shaft RPM, and
block restoration.

Run `tools/test-windmill.py --board --visual`,
`tools/test-windmill.py --craft`, `tools/test-multiplayer-windmill.py`,
`tools/test-windmill-sails.py`, and `tools/test-windmill-reopen.py` with
the standard Horizon arguments. Use `tools/test-windmill-facings.py`
for the six-facing comparison. The reopen script accepts
`--initial-client` for a save created by an older build.

The [placement GameTest](tools/java-sail-placement-trace.patch) and
`tools/test-sail-placement.py` match eight real clicks, including alternate
edges, a fully obstructed plane, crouched placement, water replacement,
and frame attachment. The `--lan` replay checks a host placing the upper
sail and a guest extending another edge, with the correct frame cost and
result on both clients. Pixel and audio timing still require comparison.

APP-1996's finite gameplay baseline passed all eight focused checks on
2026-11-20: `windmill`, `windmill-crafting`, `windmill-lan`,
`windmill-sails`, `sail-placement`, `sail-placement-lan`, `windmill-reopen`,
and `windmill-facings`. The checks compared the existing 66-row Java
assembly/load/reversal trace and 90-row six-facing trace, all 17 sail
definitions, seven dye/shearing actions, eight placement actions, and the
existing Java reload fixture. LAN checks verified host and guest actions
converge on bearing direction, capacity, stress, placement and inventory.
The run used `native-9f42064-6ce68a31b125` (Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3) and pack
SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
All eight outcomes are recorded in `.local/parity/` in the ticket worktree.
These are scoped gameplay results; exact sail visuals/audio and broader
layout/load permutations remain open under Full 1:1.

## Train Signal

The [targeting GameTest](tools/java-train-signal-trace.patch) matches
four survival placement and rejection cases, and 129 original samples
across paired rail directions, Redstone Block input, wrench mode change,
and track removal. The [comparator GameTest](tools/java-train-signal-wire-trace.patch)
measures an attached wire on all 43 ticks. Its output goes to 15
on tick 20 and returns to zero on tick 33, two ticks after the
respective lamp transitions. A real host and guest bound opposite
directions to one rail target. The guest changed their side to a Cross
Signal and the other side stayed Entry. Railway Casing and an Electron
Tube craft four signals in survival.

The [moving-train GameTest](tools/java-signal-train-occupancy-trace.patch)
matches 125 consecutive ticks of speed, four wheel positions within
1.2e-6 blocks, and all four lamp states exactly. A train assembled with
two bogeys passes through two pairs of signals on straight track and
later reverses through them. The [curved section GameTest](tools/java-curved-signal-occupancy-trace.patch)
matches a second 160-tick trip through a 90-degree bend, including all
four lamp states exactly and wheel positions within 7e-6 blocks. Both
tests read lamp transitions while the train is moving on the same
world tick. In the [moving junction GameTest](tools/java-branched-signal-occupancy-trace.patch),
a driver steers down the curved branch while six bound signals cover
the junction and both exits. The candidate matches all six lamps on
160 world ticks and wheel positions within 7e-6 blocks. Run
`tools/test-curved-train.py --branch-signals`.

The [lamp client probe](tools/java-train-signal-lamp-probe.patch) captures
a full 40-tick blink cycle with the Java world clock frozen. The placed
signal uses the original red and off partial models. The bright lamp
uses full block light, and the off lamp uses ambient light. This matches
the Java fallback renderer in a dark room. The
[Horizon screenshot replay](tools/test-train-signal-lamp.py) matched
all 40 Java phases using frames sampled on the same client tick. The
three-tick pulse continues while the game clock is frozen. The phase
across level changes and Flywheel's instanced off-state glow remain
under comparison.

The [straight Cross Signal GameTest](tools/java-train-signal-chain-trace.patch)
matches four lamps and their modes on 95 consecutive ticks, including
redstone propagating through two chained signals, clearing and reapplying
power, isolation from a signal facing the other way, and returning to
Entry mode. Java updates boundaries in UUID map order. The reference
uses fixed UUIDs for a repeatable upstream-first update, which is the
one-tick-per-boundary order used in the Horizon replay.

On a settled curve, the [curved Cross Signal GameTest](tools/java-curved-signal-chain-trace.patch)
matches four lamps and modes for 105 ticks on the candidate. A separate
[cold-track trace](tools/java-cold-curved-signal-chain-trace.patch)
captures two lamps that Java holds invalid for an extra tick during
attachment. The [junction trace](tools/java-branched-signal-chain-trace.patch)
captures yellow for one clear route and red when both routes are
blocked. All five signals and modes matched on the 105-tick candidate replay.

Run `tools/test-train-signal.py --comparator`, `--lan`, `--craft`,
`tools/test-signal-train-occupancy.py`, and
`tools/test-train-signal-chain.py`, and `tools/test-curved-train.py --signals`
with the standard Horizon arguments. Branched signal sections,
graph reservations, and rail overlays remain under comparison.

## APP-2050 finite occupancy persistence pass

Train Track/railway casing (APP-2045) and Bogeys/train assembly (APP-2047)
are Done. On candidate `native-9f42064-6bdf8691aa42` with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`,
the existing `train-signal-occupancy` replay matched all 125 Java ticks,
including speed, four wheel positions and four signal lamps. The real LAN
placement check matched host/guest convergence when the guest bound the
opposite direction and changed only that side to a Cross Signal.

The new `train-signal-occupancy-reopen` check establishes a graph through a
station, disassembles the train, and confirms all four clear sections remain
green through idle save/reopen. Its active case saves a train inside a signalled
section, resumes its speed/wheels and all four lamps against the Java trace, and
then samples the settled end state. The capture matched 119 Java samples around
the client restart; startup advances the live world before the harness can
freeze it, so resumed samples use the corresponding shifted Java tick. The
occupied and unoccupied checks exercise one train. The second-station assembly
probe found that the station needs one discovery tick before its bogeys become
eligible; after that, a second two-bogey train assembled with four wheel
TrackPoints. A candidate-only moving probe changed the affected lamps from
green to red as that train entered the signal section, but has not compared a
two-train trace to pinned Java or verified clearance after both trains leave.
This does not complete APP-2050's baseline.

The branched LAN replay matched host train motion and all six lamps to 160 Java
ticks. The guest's local lamp state matched the host at seven reads spanning
five Java occupancy transition points (east-out and north-out changes).

## Track Station naming

The [original Java GameTest](tools/java-track-station-name.patch) renames a
station bound to a real track graph and round-trips its saved `Name`. It
captures the default `Track Station`, a regular name, whitespace-only
rejection, Unicode with surrounding spaces, and a 25-unit name.

On native `e4688dbfa93b`, the [Horizon replay](tools/test-track-station-name.py)
opens the name field through the station header in survival as a solo host
and as a LAN guest. Enter and closing the screen save the name, a blank
edit leaves the prior value, and the edit box caps input at 25 UTF-16
units. The host checks the guest's authoritative value and verifies name
persistence after restarting the solo world. The original six placement
samples and the station disassembly regression also pass on this build.

The [Java station retrieval probe](tools/java-track-station-schedule.patch)
removes a Schedule from a parked train through the original station action.
For an empty main hand, Java returns the item to inventory. With paper in
hand, the same item drops at the station center with no initial motion.
On native `9b3ea8a37b1e`, the [Horizon replay](tools/test-track-station-schedule.py)
hands a two-stop timetable to a real conductor and waits for the train to
advance to its second row. Solo and LAN clicks on Retrieve Schedule return
the exact component, including `Progress: 1`, through both paths.
Creating and discarding auto-schedules remains under comparison.

## Standing players on a straight train

On `native-9f42064-49e14f320685`, an unseated survival player remained on
an assembled straight carriage and followed it in both the [stepped](tools/test-train-standing.py)
and [live](tools/test-train-standing-live.py) replays; the live player walked
off the edge and fell. A [LAN guest](tools/test-train-standing-lan.py) also
remained on the moving carriage at normal tick rate. The earlier `d6a9092ed1ea`
build let a player fall through the stationary deck. On `0f8d0190e661`, a
[save-compatibility replay](tools/test-train-standing.py) assembled and saved
a real train, removed only the new captured collision arrays to reproduce the
older serialized format, reopened it, and kept the player on the moving deck.
Fresh stepped and live train replays also passed. The existing two-player
elevator standing regression passed on `c601610833ba` after the shared
collision changes. Java's collider skips server-side players and handles the
local player on the client; no real Java client trace was captured for this
case, so Java player parity, slopes, and other older block shapes remain open.
On `native-9f42064-3fa96025b369`, a [LAN guest replay](tools/test-curved-train-standing.py)
remained unseated and supported through a straight-to-quarter-turn transition;
the local lateral offset rounded to zero when the driver was kept clear. Java's
collider applies contact-point motion, but this is not a captured Java player
trace. A separate [headless Java train trace](fixtures/train-updown-java.csv)
traversed gradual ascent and descent connections. On
`native-9f42064-90476b859cb6`, a [headless LAN guest replay](tools/test-train-incline-standing.py)
remained supported through both transitions and retained its carriage-relative
position. On `native-9f42064-f92c6abe28bd` the guest fell through the deck at
the start of the ascent. This comparison uses the Java train route, not a Java
player trace. On the same candidate, [two headless LAN guests](tools/test-train-standing-reversal.py)
stood on separate deck blocks throughout forward travel and a reversal while
the driver stayed clear. On `native-9f42064-7f3945f841a4`,
[two headless guests](tools/test-train-standing-disassembly.py) stayed on their
deck blocks through disassembly, walked on the restored planks, and remained
supported after reassembly. Java player behavior and other slope geometries
remain open.

## Manual train steering

The [right-branch Java GameTest](tools/java-train-steer-right-trace.patch)
matches 160 ticks of train speed and four wheel positions within
7e-6 blocks. Holding right sends the train down the curved branch at
a junction with a straight exit. A real Horizon guest took the controls
and followed the Java path for all 84 measured host ticks. Run
`tools/test-curved-train.py --steer-right` and
`tools/test-multiplayer-train-steering.py`. The [mirrored left-branch GameTest](tools/java-train-steer-left-trace.patch)
matches the selected route and all 160 motion ticks within 1e-5 blocks.
The maximum observed coordinate difference was 8.29e-6 blocks.
Run `tools/test-curved-train.py --steer-left --tolerance 1e-5`.
The [manual station approach GameTest](tools/java-manual-station-approach-trace.patch)
matches 198 ticks of braking and arrival on straight track. Holding
Space skips the closer opposite-facing station and stops on tick 100.
Disassembly restores the train at the destination and leaves the
origin clear. A real LAN guest drove the same approach and the host
matched 93 Java ticks. Run `tools/test-manual-station-approach.py`
and `tools/test-multiplayer-station-approach.py`. The [cancellation GameTest](tools/java-cancel-station-approach-trace.patch)
matches 198 more ticks, including releasing Space on tick 68 and
coasting past the station without docking.

The [curved station GameTest](tools/java-curved-station-approach-trace.patch)
and [junction station GameTest](tools/java-branched-station-approach-trace.patch)
each match 208 ticks on the candidate. The driver holds Space and the
train takes the curve, including when a straight exit is available.
It arrives on tick 137 and disassembles with both bogeys on the new axis
and the controls pointing south. A real guest drove the curve while the
host matched 130 ticks with and without the straight exit. Run
`tools/test-curved-station-approach.py`,
its `--junction` variant, and
`tools/test-multiplayer-station-approach.py --curved` or `--junction`.
The maximum
allowed coordinate difference in these curved traces is 7e-6 blocks.
The [reverse docking GameTest](tools/java-reverse-station-approach-trace.patch)
matches all 198 ticks with controls at both ends. The driver moves
backward before holding Space and arrives on tick 100. Disassembly
restores each set of controls facing its original direction, and the
guest replay matches all 93 measured ticks. Run
`tools/test-manual-station-approach.py --reverse` and
`tools/test-multiplayer-station-approach.py --reverse`.

The [two-destination GameTest](tools/java-junction-station-choice-trace.patch)
matches all 208 ticks and disassembly on build `0bfdfbf3d971`. Java
chooses the farther straight station. Both stations sit on graph edges
whose endpoints exceed the 32-block search radius. The straight station
is the last eligible discovery before the search exhausts its frontier.
A real LAN guest drove the two-destination layout and the host matched
133 Java ticks. Run either station-approach replay with `--choice`.
The [short-curve adjustment](tools/java-junction-station-short-curve.patch)
applied after the two-destination patch brings the curved edge endpoint
inside the radius. Java now selects the curve. The candidate matches
all 208 ticks and disassembly in that layout too. Run the local replay
with `--short-curve`. Station prompts, route ordering with signal
penalties, and automatic dispatch remain under comparison.

## APP-2049 Train Station gameplay baseline

The bounded acceptance pass used Java Create `ac0c444d9828da3453ae8cc65338e8de063286fb`, Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, build `native-9f42064-340cbe866fa7`, and Create pack SHA256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`. The existing client contains cursor fix `16af87f`. This ticket changes test coverage and evidence only; it does not modify production behavior.

The finite case list and results are:

- `track-station`: all six Java cases passed, covering selection and placement from either approach, wrong or missing targets, junction rejection, range boundary, saved relative target, and item count.
- `track-station-controls`: passed. A valid idle station offers Create New Train; its empty assembly screen enables Back and disables Assemble Train; a station without a target exposes no train or schedule controls. The placed station retained the selected target. This is a Horizon control-state check, not a Java trace comparison.
- `track-station-name` and `track-station-name-lan`: all five Java rename cases passed for default, blank, Unicode with surrounding spaces, and the 25-character boundary. The host's world reopen retained the last name; guest edits converged on the server.
- `train-bogeys`: all six Java assembly and casing-consumption cases passed.
- `track-station-schedule` and `track-station-schedule-lan`: passed. Retrieval covered an empty hand and an occupied hand, preserving the progressed two-stop Schedule and returning it to inventory or the station center as Java does.
- `scheduled-station-approach-lan`: all 123 Java ticks passed for guest-assigned timetable, departure, arrival, waits, and completion.
- `scheduled-reverse-trip-lan`: all 263 Java ticks passed for departure and return with guest assignment.
- `scheduled-reverse-trip-reopen`: 237 Java ticks passed; parked and moving states reopened at trace ticks 114 and 157, retaining train occupants and timetable.

Reproduce these cases with `tools/test-parity.py` using the matching `horizon-ctl`, client, and prepared 26.3 resources. Raw logs are under `.local/parity/` with the check names above. No Java recapture or native rebuild was needed for this test-only pass. Java capture patch SHA256 values:

The combined gameplay command was `python3 tools/test-parity.py <horizon-ctl> <horizon-client> <prepared-26.3> --jobs 2 --check track-station --check track-station-name --check track-station-name-lan --check track-station-controls --check train-bogeys --check scheduled-station-approach-lan --check scheduled-reverse-trip-lan --check scheduled-reverse-trip-reopen`; schedule retrieval was run separately with `--check track-station-schedule --check track-station-schedule-lan`. Early control-fixture failures were invalid setup only (missing ignored template, wrong target offset, and an omitted world tick); the fixture was corrected and the final control replay passed.

| Capture | SHA256 |
| --- | --- |
| `java-track-station-trace.patch` | `fd4ccacf41752686ef1b81123d1bb9e78fe8ea1c9342042a360f749bc7f605d6` |
| `java-track-station-name.patch` | `1a1dc564faa8c8583463719155242d9e58d5b26d34bc2b6e218f5210b16a44d5` |
| `java-train-bogeys-trace.patch` | `363d7029b49782f38bb56390029ef93cd61a566140acaf60499701399b284927` |
| `java-scheduled-station-approach-trace.patch` | `6c9822cc8a392583cac42ff4a553cd69801259cfb33ea892505fd8c70afa6c8f` |
| `java-reverse-station-approach-trace.patch` | `ef4cf6d63f826d7d882f06e3684239065447626a6ddb584ac0897c0f310806f1` |

Other station layouts, route choices, exact visual behavior, and exhaustive cross-products remain open under Full 1:1.
### APP-2051 Manual driving and Train Controls — November 21, 2026

This finite baseline reuses the pinned Java references rather than capturing
new expected values. Source review covered `Train.tick`,
`CarriageContraptionEntity.startControlling` and `.control`, and
`Navigation` at Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
The Java capture patch hashes are:

| Reference | SHA-256 |
| --- | --- |
| `java-manual-train-trace.patch` | `1c5dab4780a8bb49420fcd54ab3eda1e3e383a0cabe11cb464a77a6d7ec50699` |
| `java-train-steer-right-trace.patch` | `7adf8ab985b049702331f3d7d8cd4ed9958dcf8f6cdd699c52a3405590bb6919` |
| `java-train-steer-left-trace.patch` | `8c295c1787a20e9f4f0101c568a5049260a10e0e4fd255f719008fb8ccd6ef99` |
| `java-manual-station-approach-trace.patch` | `062c3d47f697003f0fe3bc7662adf645558d28b0e1d54154e7dbc872bfaf7cb6` |
| `java-reverse-station-approach-trace.patch` | `ef4cf6d63f826d7d882f06e3684239065447626a6ddb584ac0897c0f310806f1` |

The isolated build used Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`,
launcher `0.2.67`, and private copy-on-write compiler data. It produced
`native-9f42064-84eb353ebb27` in 579 seconds. The client SHA-256 is
`123733fa66ee41c3a6d9ed95c741b159bfa80c557cbe0e5e398e7d53a4781683`.
All fixture worlds used pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

The recorded cases passed on that build:

| Check | Case and outcome |
| --- | --- |
| `manual-train` | 125 Java samples, ticks 13–137. Forward acceleration/coast, reverse acceleration/coast, speed, four wheel positions and spacing matched within `1.2e-6`. |
| `train-steer-right`, `train-steer-left` | 160 Java samples per direction through a curved junction; wheel positions matched within `7e-6` and `1e-5` blocks respectively. |
| `manual-station-approach`, `reverse-station-approach` | 198 Java samples each; braking, stop/arrival, reverse control and disassembly matched the existing traces. |
| `train-steer-lan` | Guest UUID held authoritative controls while driving; host observations matched 84 Java samples. Guest Sneak released the `Driver` field. |
| `manual-train-reopen` | Stopped train state matched before/after reopen. A saved moving train resumed, retained the four bogey-point gaps, and accepted reverse input. Java reload timing is not claimed: normal startup ticks occur before the harness freezes time. |
| `train-multi-carriage` | APP-2047 regression: two carriages/four bogeys assembled, moved, reopened, converged to the LAN guest, and restored both cargo inventories on disassembly. |

The initial run of the augmented LAN check had a test-only `NameError` in a
post-drive host reacquire assertion after its Java-matching route. That assertion
was removed as outside this ticket's acceptance list; the corrected guest
driving and release check passed on rerun. No gameplay mismatch was observed.

The build and focused commands were:

```sh
sh tools/build-native.sh .local/toolchains/launcher-0.2.67/horizon-launcher .local/app-2051-launcher-data
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-84eb353ebb27/horizon-ctl .local/patched-launcher/versions/native-9f42064-84eb353ebb27/horizon-client .local/patched-launcher/versions/native-9f42064-84eb353ebb27/.local/horizon-client/26.3 --jobs 2 --check manual-train --check manual-train-reopen --check train-steer-right --check train-steer-left --check train-steer-lan --check manual-station-approach --check reverse-station-approach --check reverse-station-approach-lan --check train-multi-carriage
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-84eb353ebb27/horizon-ctl .local/patched-launcher/versions/native-9f42064-84eb353ebb27/horizon-client .local/patched-launcher/versions/native-9f42064-84eb353ebb27/.local/horizon-client/26.3 --jobs 1 --check train-steer-lan
```

The first batch passed eight checks; after the test-only correction, the LAN
rerun passed, for all nine cases passing. Existing Java traces were reused;
capture time was zero. The first full build took 579 seconds, and the focused
integration batch took about five minutes plus a one-minute LAN rerun. Stopped
and moving reopen are source-aligned gameplay checks, not exact Java reload
comparisons. Other slopes/layouts, exhaustive kinematics, interpolation and
visual effects remain open; Full 1:1 stays Open.

## Scheduled station travel

In the [original conductor GameTest](tools/java-scheduled-station-approach-trace.patch),
a seated villager accepts a non-looping timetable with a three-tick delay
at Origin and a five-tick delay at Terminal. The train departs on tick 29,
arrives on tick 104 and marks the timetable complete on tick 112.
Horizon build `480f470e02af` matches all 123 sampled ticks, including
the four wheel positions, speed, destination distance, arrival, entry
and pause. A real LAN guest assigned the same timetable while the host
matched all 123 ticks. Replay using
`tools/test-scheduled-station-approach.py` with or without `--multiplayer`.
The fixture seeds station names as world data. The station name editor
has a separate test.

The [Java red-signal variant](tools/java-scheduled-red-signal-trace.patch)
records holding at Origin for a signal four blocks ahead. Navigation clears
the hold on tick 59 and the lamp changes to green on tick 60. Horizon build
`10a4624c426e` matches all 156 ticks and the same trace passes after a real
LAN guest assigns the schedule. The [rolling-stop adjustment](tools/java-scheduled-moving-signal-trace.patch)
moves the signal eight blocks out. Both the local and real LAN replays
match 183 ticks, including spotting the red signal on tick 58, stopping on
tick 86 and moving on tick 119.
These replays include the signal lamp, the train's waiting state and the
distance to the signal. Apply the Java adjustments in order and replay
Horizon with `--red-signal` or `--moving-signal`.

The [cross-signal variant](tools/java-scheduled-cross-signal-trace.patch)
matches all 183 Java ticks on `b51af962230a` in solo and real LAN worlds.
A downstream red holds departure at the upstream signal. Both
lamps match through reservation and physical occupancy, including the
one-tick refresh of the wait before the red clears. Apply the variant
after the rolling-stop adjustment and replay with `--cross-signal`.

Two further 123-tick fixtures pass on the same build locally and after a
real guest assigns the timetable. The [powered and time-of-day trace](tools/java-scheduled-powered-time-trace.patch)
requires the station to receive redstone before testing the repetitive
clock window. The [wireless trace](tools/java-scheduled-link-trace.patch)
requires matching Redstone Link frequencies to turn on and then off in
order. A transmitter with the two slots exchanged stays powered and
does not satisfy the wait. Use `--powered-time` and `--link`.

The [title and throttle trace](tools/java-scheduled-title-throttle-trace.patch)
changes the title to Night freight on tick 29 and applies 10% throttle
on tick 30. The local replay and a real guest assignment on
`2b1a5ce6b7e6` match all 183 ticks, including arrival at the capped speed.
Run `--title-throttle` with or without `--multiplayer`.

A [wildcard route fixture](tools/java-scheduled-route-cost-trace.patch)
names two depots and runs the original train through the closer curve.
The local replay matches all 198 ticks on `b51af962230a`. Apply the
Java adjustment after the manual junction-choice patch. The [forced-red
adjustment](tools/java-scheduled-route-red-cost-trace.patch) places a red
signal on the shorter branch. Horizon build `3d6e2316bfbe` chooses the
farther straight depot and matches all 198 ticks locally and after a real
guest assigns the timetable. Use `--forced-red` with or without
`--multiplayer`. Opposite-side reservations, alternative paths to the
same station, other conditions and rolling stock layouts remain under
comparison.

The [delay-group probe](tools/java-train-schedule-groups.patch) compares two
rows containing both sequential delays and concurrent alternatives. The
[Horizon replay](tools/test-train-schedule-groups.py) hands the program to a
real conductor and compares the stage, row index, each group's delay counters,
and non-looping completion across all 24 Java ticks on natives
`e4688dbfa93b`, `b51af962230a`, and `2b1a5ce6b7e6`. As in the Java
capture, the replay samples the counters while the train waits at its
station. The train stays at the same station throughout.

The [bidirectional trip](tools/java-scheduled-reverse-trip-trace.patch)
uses separate seated conductors at both ends. Horizon matches 263 ticks
locally and after a real guest assigns the timetable. The train reaches
West on tick 98, reverses at tick 106 and docks at East on tick 213.
Run `--reverse-trip` with or without `--multiplayer`.

The [Java save-state check](tools/java-scheduled-reopen-trace.patch)
round-trips the train's wait state at tick 100 and its moving reverse
state at tick 145 through the original train serializer. On native
`539abfaeee59`, the Horizon `--reverse-trip --reopen` replay preserves the
timetable and both seat occupants and matches the Java route on 251
manually stepped ticks and at the first observation after each reopen,
ticks 106 and 151. The test client advances five unobserved ticks during
each startup before control reconnects. The uninterrupted LAN replay
matches all 263 ticks on the same build.

The [Java passenger-count probe](tools/java-scheduled-player-count-trace.patch)
applies after the train-seat trace patch. The exact-one condition waits
while both players are seated. Dismounting the guest on tick 39 satisfies
it on tick 40. The next condition accepts one passenger above its minimum
of zero on tick 41. The train departs on tick 43 and reaches Terminal
on tick 120. The [live Horizon replay](tools/test-train-passenger-count.py)
matched all 123 ticks on native `0b725c3de704`, comparing passenger count,
condition progress and the original route fields with a real host and guest.

## Train Schedule item and blank editor

The [pinned live Java probe](tools/java-train-schedule-probe.patch) crafts
four schedules from one Sturdy Sheet and paper in a survival 2×2 grid.
The main hand opens an empty Train Schedule in the air and against a
block. Crouched use does not open it. Loop Forever starts on and follows
the toggle. Closing leaves all four items without a timetable component,
and reopening the blank editor restores its initial loop state.

The [Horizon replay](tools/test-train-schedule.py) checks the same craft,
inputs, visible loop states and item data. A survival LAN guest opens
and closes their own editor both in the air and against a block. The
editor uses the original atlas and item sprite.

The [destination probe](tools/java-train-schedule-entry-probe.patch)
uses Add Action, enters `Main Platform *` under Travel to Station, and
confirms the card. Java stores one destination, one five-second delay
condition, and the enabled loop flag under `create:train_schedule`.
The [Horizon entry replay](tools/test-train-schedule-entry.py) matches
that component in a solo host and a LAN guest, confirms the guest
receives it over the wire, and reopens the card in both clients.
The host also reloads the world and reopens the saved action.

The [two-action Java probe](tools/java-train-schedule-multi-probe.patch)
adds `Main Platform *` and `Harbor`, turns Loop Forever off, edits
the second row to `East Pier *`, and removes the first row after
reopening. The [Horizon replay](tools/test-train-schedule-multi.py)
matches both ordered destination compounds and the remaining row in
a solo host and LAN guest. It checks the component in the clients'
inventories after synchronization and preserves the disabled loop and
the remaining destination after restarting the host world.

The [item-copy probe](tools/java-train-schedule-copy-probe.patch) puts
a programmed Schedule beside a stack of three blanks and gets two
programmed copies. Splitting the blanks into two slots gives three
copies. The [Horizon replay](tools/test-train-schedule-copy.py) matches
the output and input consumption in survival for host and guest. Copies
retain the exact timetable and custom name and clear both enchantment
components. An unrelated item or a second programmed Schedule prevents
the recipe.

The [live Java Scheduled Delay editor probe](tools/java-train-schedule-delay-probe.patch)
uses the original wheel controls to change five seconds to eight minutes,
then clamps the duration at 120 ticks and zero seconds. The
[Horizon replay](tools/test-train-schedule-delay.py) matched the exact
item component after each confirmation and reopen on native `2b1a5ce6b7e6`
for both a solo host and a LAN guest. Renaming one destination and changing
Loop Forever preserve another row, powered and time-of-day alternatives,
`Progress: 1`, and untouched root and stop metadata. The same build
passed the blank, destination, multi-entry, and survival copy replays.

The [original progress editor probe](tools/java-train-schedule-progress-probe.patch)
starts with a non-looping Schedule on its second row. Skip Current Stop wraps
to the first row, a second skip selects the second row again, and Reset
Progress returns to the first row. On native `3d6e2316bfbe`, the
[Horizon replay](tools/test-train-schedule-progress.py) checks those actions,
enabled states, and the exact component in the host and LAN guest
inventories after reopening. Both Delay editor replays also pass on this build.

The [Java action picker probe](tools/java-train-schedule-action-probe.patch)
selects Update Schedule Title and enters `Night Express`, then reopens the
row and changes it to Limit Max Speed at 75 percent. Neither action saves a
wait condition. Both solo and LAN
[Horizon replays](tools/test-train-schedule-actions.py) on native `0a9f2ff1b84a`
match the exact components and reopen both actions. The blank, destination,
multiple-row, Delay, Progress, and survival copy replays also pass.

The [original condition picker probe](tools/java-train-schedule-condition-types-probe.patch)
replaces a default delay with Time of Day at 10:20 am with hourly rotation.
It then reopens the item, changes that row to Station Powered, and
confirms the saved condition has empty Data. On native `bda388737e37`,
the [Horizon replay](tools/test-train-schedule-conditions.py) matches both
components and opens both editors from the saved item for solo host and
LAN guest. The Title, Throttle, and Delay editor regressions also pass.

The [Java condition-group editor probe](tools/java-train-schedule-group-editor-probe.patch)
appends a six-tick delay after five seconds, adds a separate eight-tick
alternative, then removes the appended term and the alternative.
On native `539abfaeee59`, the
[Horizon replay](tools/test-train-schedule-group-editor.py) matches all
three nested components in solo and LAN use through each save and reopen.
Right-clicking a sole remaining condition leaves it in the schedule.
The Power and Time of Day picker, Delay, Title/Throttle, and 24-tick
group runtime regressions pass on this build.

The [Java row actions probe](tools/java-train-schedule-row-actions-probe.patch)
clicks move-up, duplicate, and move-down in a two-stop Schedule with
unequal waits and `Progress:1`. The
[Horizon replay](tools/test-train-schedule-row-actions.py) matches all
three exact item components after solo and LAN saves and reopens on
native `aac17481f56e`. The group editor, Time of Day and Station Powered,
Progress, and multi-entry regressions pass on the same pack.

The [Java station suggestion probe](tools/java-train-schedule-suggestions-probe.patch)
uses four bound stations on two independent rail lines, with two called
Harbor. The [Horizon replay](tools/test-train-schedule-suggestions.py)
matches the sorted, deduplicated names, the lowercase prefix filter,
Tab selection and its exact five-second item component, the linked
rail restriction, and fallback when no station matches the other row.
Solo and LAN pass with native `b4b2c9b204c4`, as does the prior entry
and reopen check. This through-game comparison covers loaded stations
in the active world on straight rails.

The [Java Players Seated editor probe](tools/java-train-schedule-passenger-count-editor-probe.patch)
checks the default empty-carriage target, a normal notch, Shift snapping from
one to five, the 0 and 20 limits, and both Exactly and Or above.
The [Horizon replay](tools/test-train-schedule-passenger-count-editor.py)
matches the four serialized components after save and reopen in solo and
LAN on native `c364cc91c41a`. The basic entry and both condition-group
editor replays pass on the same pack.

The [Java Redstone Link editor probe](tools/java-train-schedule-link-editor-probe.patch)
selects Powered and Not powered, copies two one-item ghost frequencies
from unchanged inventory stacks with quick-move, and clears the first
frequency after reopening. The
[Horizon editor replay](tools/test-train-schedule-link-editor.py) matches
the three exact components in solo and LAN on native `4d8eb3a09003`. The
[conductor replay](tools/test-scheduled-station-approach.py) on that build
reads Java's `Data.Frequency` and reproduces all 123 ticks in solo and LAN,
including the opposite-ordered decoy; the earlier top-level frequency
format also matches all 123 ticks in solo. Picking up source stacks onto
the inventory cursor and dragging remain under comparison.

The [Java Chunk Unloaded editor probe](tools/java-train-schedule-unloaded-editor-probe.patch)
authors and reopens the no-parameter wait. The
[Horizon editor replay](tools/test-train-schedule-conditions.py) matches
the exact empty condition data in solo and LAN on native
`359451469bec`. Time of Day, Station Powered, Redstone Link, and
Players Seated editor regressions pass on the same pack.

The [Chunk Unloaded Java GameTest](tools/java-scheduled-chunk-unloaded-trace.patch)
removes only the Origin station chunk's forced ticket after tick 34.
The [Horizon replay](tools/test-scheduled-chunk-unloaded.py) matches all
123 samples in solo and LAN with native `586c579cd9cc`. The station stays
resident, its entities stop ticking at 35 while the rail's entities keep
ticking, the wait advances at 35, and the train starts moving at 37.
Station and rail item ages measure their tick status independently.

The [Java Cargo Inactivity editor probe](tools/java-train-schedule-idle-editor-probe.patch)
authors and reopens the default five-second wait, then saves eight ticks.
The [Horizon replay](tools/test-train-schedule-conditions.py) matches both
exact `create:idle` components in solo and LAN with native
`586c579cd9cc`. Cargo exchange timing remains under comparison.

The [Java Package action editor probe](tools/java-train-schedule-package-editor-probe.patch)
adds Deliver Package, changes its delay to seven seconds, and converts the
row to Retrieve Package. It types four wildcards and saves the original
three-wildcard address `Warehouse ***` while retaining the same wait.
The [Horizon editor replay](tools/test-train-schedule-actions.py) matches
both exact components in solo and LAN on native `a689ec5c8086`; the previous
Title and Throttle editors pass on the same pack. Its display-only package
and postbox model chains and textures match pinned Java byte-for-byte.

The [Java cargo comparison editor probe](tools/java-train-schedule-cargo-comparison-probe.patch)
sets Item Cargo to exactly 32 stacks of paper and Fluid Cargo to fewer
than 12 buckets of water. The
[Horizon editor replay](tools/test-train-schedule-cargo-comparison.py)
matches both exact components in solo and LAN on native `5d18ba4dd0d3`,
including string thresholds, integer operator and measure, one-item
ghost references, unchanged source stacks, and reopen. Redstone Link,
Package, and Delay authoring also pass on that build.

The [Java mounted chest GameTest](tools/java-scheduled-static-item-cargo-trace.patch)
assembles one carriage with 64 and seven paper and a full decoy redstone
stack. The [Horizon replay](tools/test-scheduled-station-approach.py) on
native `be37f52ce36a` matches all 123 Java ticks in solo and LAN, including
one full matching stack, 71 matching items, and the rejected strict
greater-than-71 alternative. The no-cargo and Redstone Link routes pass
on the same build.

The Item Threshold waits also match all 123 Java ticks with a mounted Barrel,
a mounted Item Vault, or an empty carriage in solo and LAN on native
`8fd28a1355c0`. The loaded variants distinguish one full paper stack from
71 individual pieces and exclude a full stack of redstone. The empty train
satisfies exact-zero thresholds for both units. The original Chest replays
also pass. [Java fixture overlay](tools/java-scheduled-mounted-stock-trace.patch),
[Horizon replay](tools/test-scheduled-station-approach.py)

The [Java mounted tanks GameTest](tools/java-scheduled-static-fluid-cargo-trace.patch)
uses 2,750 mB of water and 8,000 mB of lava. The
[Horizon replay](tools/test-scheduled-station-approach.py) on native
`8b09db08a528` matches all 123 ticks in solo and LAN, including passing
the water conditions greater than two and less than three buckets,
rejecting exactly two buckets, and excluding lava. The mounted chest
route matches the same 123 Java ticks on this build.

The [Java Cargo Inactivity GameTest](tools/java-scheduled-idle-cargo-trace.patch)
measures an idle carriage with a five-tick threshold and no cargo movement.
The [Horizon replay](tools/test-scheduled-station-approach.py) on native
`2fad732bca0d` matches all 123 Java ticks in solo and LAN, including the
strict greater-than threshold, the frozen clock during travel, and the
reset at arrival. The Redstone Link and Chunk Unloaded routes also pass.

The [Java train hopper GameTests](tools/java-scheduled-hopper-cargo-trace.patch)
unlock one real hopper for a tick at a stationary Portable Storage
Interface. Run the push and pull GameTests separately because they share
the same fixed layout. The
[Horizon replay](tools/test-scheduled-station-approach.py) on native
`15cd1d474de3` matches all 123 samples in both directions in solo and LAN.
They check the counts of the transferred paper stack in both inventories,
the wait clock reset on tick 28, the dock disconnect on tick 48, and timing
and wheel positions through the terminal stop.

Two independent mounted chests match all 123 ticks in each direction on native
`daabfba12364`. A real Hopper transfers one paper on tick 28, resets the Cargo
Inactivity clock and leaves the other chest and the rear chest’s remaining
contents intact. The solo player and a live LAN guest each handed the
timetable to the conductor. The two-chest traces reproduce the original
single-chest trace values. [Java GameTests](tools/java-scheduled-two-chest-hopper-trace.patch),
[Horizon replay](tools/test-scheduled-station-approach.py)

A train with an independent Chest and mounted Barrel matches all 123 Java
ticks in each Hopper direction on native `9c577a1439d3` in solo and LAN. A
stationary Portable Storage Interface transfers one paper on tick 28. The
other stacks stay in the Barrel and the separate Chest stays unchanged.
A connected guest handed the timetable to the conductor in both directions.
The two loaded-Chest order controls also pass with a connected guest on this
build. [Java fixture overlay](tools/java-scheduled-mounted-barrel-trace.patch),
[Horizon replay](tools/test-scheduled-station-approach.py)

A mixed carriage with a 27-slot Chest and a 20-slot Item Vault matches all
123 Java ticks in both Hopper directions, in solo and LAN on native
`8fd28a1355c0`. The Portable Storage Interface exchanges one paper on
tick 28, resets the Cargo Inactivity clock, and preserves the other
stacks in both inventories. A connected guest supplied the timetable
in both LAN replays. Both Barrel transfer controls pass with a connected
guest on this build. [Java fixture overlay](tools/java-scheduled-mounted-vault-trace.patch),
[Horizon replay](tools/test-scheduled-station-approach.py)

A mounted Trapped Chest or purple Shulker Box matched 123 Java ticks in
each Hopper direction and under the Item Threshold condition, in solo
and live LAN on `34f0b58f5120`. The train also passed the adjacent Item
Vault insertion control. [Horizon replay](tools/test-scheduled-station-approach.py)

Two layouts with loaded chests separately match six original Java ticks in solo
and LAN. The relative positions of the mounted chests determine the order of
the combined inventory. On tick 28 the Hopper extracts paper in one layout
and an emerald in the other. The connected guest opened the Hopper and saw
the selected stack. [Java samples](fixtures/train-chest-order-java.csv),
[Horizon replay](tools/test-train-chest-order.py)

The [Java train fluid port GameTests](tools/java-scheduled-train-fluid-port-trace.patch)
connect a mounted tank to a fixed tank through paired Portable Fluid
Interfaces, an adjacent Mechanical Pump and a glass pipe. Run fill and
drain separately because the GameTests share the same fixed layout. The
[Horizon replay](tools/test-scheduled-station-approach.py) matches all 199
Java ticks in both directions in solo and LAN on native `beea127aa56c`.
The pump transfers eight mB per tick from tick 58 through 68, preserving
the combined volume and resetting the Cargo Inactivity clock at each
exchange. The replay also checks connection, wait, wheel positions and
the terminal stop. The original open-pipe pump and train hopper replays
pass on the same build.

A separate powered variant of the [train fluid port replay](tools/test-scheduled-station-approach.py)
matches all 199 Java ticks in solo and LAN on native `eb3ff28a1935`.
Applying redstone after tick 60 cuts the interface before the pump's
next transfer. It holds the receiver at 24 mB through the shutdown and
reconnects at tick 65 without restoring the old pipe flow. The unpowered
drain and train hopper replays pass on the same build.

The [fixed train port lifecycle replay](tools/test-scheduled-station-approach.py)
on native `a74acd16dd81` checks Java's raw connection distance at each
of 199 ticks in solo and LAN. The raw Timer checks begin at the steady
dock on tick 43 and continue through the fixed block's countdown after
disconnect. Each exchange refreshes Timer to 64 in the transfer tick,
and geometric disconnect retracts from 3 to 0 on ticks 138 through 141.
The replay also checks transfer, waits and the complete route.

The [fixed train port render replay](tools/test-scheduled-station-approach.py)
uses the original casing, powered and unpowered middle, and top models
for the stationary Portable Fluid Interface. On native `add6251b3a02`,
solo and LAN match the full 199-tick lifecycle and six sampled render
phases, including the half-block extension, the unlit retraction and the
restored closed model on tick 142. The original rotating-bearing mounted
fluid drain also passes all 65 Java ticks on this build.

The [Java carriage port client probe](tools/java-train-moving-port-trace.patch)
records the moving interface on a parked train as the fixed port unlocks
and locks again. The [Horizon replay](tools/test-train-moving-port-render.py)
matches eight actor ticks for both item and fluid ports in solo and real
LAN on native `f64063cd8804`. It checks both interpolation endpoints,
the change between powered and unpowered models, and the offsets of the
original moving middle and top. Host and guest captures show both ends
meeting when extended. Powered fluid transfer and Hopper pull also pass
all 199 and 123 Java ticks respectively on that build.

The [fluid-port departure replay](tools/test-train-port-departure.py)
matches 86 Java authority samples for carriage position, speed and fixed
port Timer on native `156d01044baa` in solo and real LAN. The fixed port
counts down from 3 to 0 after the train leaves its contact cell. The
carriage matches five consecutive Java poses around that geometric
boundary, including the lit collar and the model offsets during
retraction. The Horizon replay gives the conductor a schedule already
advanced to Terminal to isolate this leg after the ports have settled.

In independent live Java captures, the carriage client lost contact
13 or 14 displayed world ticks after the first positive train speed.
One capture skipped a displayed world tick while preserving the same
five poses. Horizon matches the poses relative to loss of contact.
[Java live departure probe](tools/java-train-port-departure-trace.patch)

The [Terminal receiver replay](tools/test-train-port-arrival.py)
matches 86 authority samples for paired Portable Storage Interfaces and
for paired Portable Fluid Interfaces on native `ebe289d50592`, each solo
and with a real LAN guest. The fixed receiver connects on motion tick 70
with Timer 13 and a separation of 1.0 block. The moving carriage matches
four sampled model poses around the contact cell. Its tip extends 0.25
blocks per step until the collar lights. In the two live Java fluid
captures the first moving opening pose appeared at displayed world tick
72 relative to launch. Horizon draws it on its stepped geometric crossing
at tick 69. The pose comparison uses each client's crossing.
The LAN fixture supplies the same saved schedule directly to the
guest's hotbar. The previous dropped item sometimes went uncollected
before the actual port replay. On `native-9f42064-d542a1892c07` with
the projectile pack, both item and fluid arrival matched all 86
authority samples and four contact-relative poses with that setup.

The powered Terminal receiver matches 141 authority samples and the same
four opening poses in both roles. Its pump is already running at -16 RPM
and the first 8 mB reach the fixed tank on motion tick 97. Each following
sample transfers another 8 mB and refreshes Timer to 64. The departure
replay and prior redstone-controlled train pump also pass.
[Java Terminal receiver probe](tools/java-train-port-arrival-trace.patch)

With the fixed port in the high-speed part of the same route, the
[fast pass replay](tools/test-train-port-arrival.py) matches 86 Java
authority states and four closed actor poses on native `ebe289d50592`,
in solo and real LAN. The original carriage passes the receiver at
0.2775–0.3000 blocks per client step, above the 0.25 scan limit. The
fixed port stays disconnected at Timer 0 for the entire replay.

Saving at motion tick 69 and reopening exposes a separate timing gap.
Across two live Java restores, the carriage became available at world
tick offsets 12 and 18, and the fixed receiver began at Timer 13 on the
following tick. Horizon had already reached the station with Timer 9
when the replay resumed at world tick offset 6.

The [receiver restore replay](tools/test-train-port-restore.py) matches
12 Java ticks from restored carriage availability on native
`1462263813c0` for both the Portable Storage Interface and Portable Fluid
Interface. It saves before contact and at the first connected tick. A
restored receiver clears the saved carriage reference, reacquires the
available carriage at Timer 13 on the next tick, and counts down to
Timer 4 while it stays connected.
Powered terminal arrival and rotating bearing reload also pass. The
readiness point still occurs at different world ticks across live
startup captures.
[Java restore probe](tools/java-train-port-restore-trace.patch)

The [Java portable interface probes](tools/java-portable-interface-readout-and-wrench-trace.patch)
measure a comparator and redstone wire at a parked train dock through two
lock and unlock cycles. Both item and fluid
[Horizon readout replays](tools/test-portable-interface-comparator.py)
match all 53 Java ticks in solo and real LAN on native `d9d936d876ab`.
The [survival Wrench replay](tools/test-portable-interface-wrench.py)
also matches all 72 directional interactions and both crouch pickups on
the host and guest in that build.

The [Java powered item port probe](tools/java-powered-hopper-cargo-trace.patch)
opens the Hopper while the stationary port is still locked, then unlocks
the port for one exchange. The [Horizon replay](tools/test-powered-port-hopper.py)
matches all 23 Java ticks for both push and pull in solo and real LAN on
native `d9d936d876ab`. No item changes hands while the port is powered.
One paper moves on tick 32 after the port unlocks, and both decoy stacks
remain in the mounted chest. The LAN guest supplies the redstone edits.

The [mounted port comparator replays](tools/test-mounted-port-comparator.py)
match 259 item and 71 fluid samples through the original rotating bearing
extraction and disassembly in solo and real LAN on native `79b5e6466774`.
They compare the bearing angle, raw port Timer, cargo totals and physical
comparator and redstone wire through first contact and full retraction.
The LAN guest toggles the bearing and sees the wire turn on and off.
[Java fixture instrumentation](tools/java-mounted-port-comparator-trace.patch)

With the Hopper locked, the [idle replay](tools/test-mounted-port-comparator.py)
matches 141 Java ticks on `3e6dffdca1c1` in solo and real LAN. The bearing
passes the port twice without moving cargo. Each pass resumes rotation
while the port holds Timer at 4, then retracts and releases the wire
after the actor leaves the active cell. The guest sees both wire pulses.
The productive 71-tick fluid extraction also passes on this build.
[Java idle fixture](tools/java-mounted-port-idle-followup.patch)

The [unpowered fluid replay](tools/test-mounted-port-comparator.py) matches
141 Java ticks in solo and real LAN on native `156d01044baa`. The saved
fixture starts with pump pressure of 256 and pipe pressure of 128. With
the pump motor removed, the pump has zero RPM and delivers no fluid
across two docking cycles. All 5,000 mB stay in the mounted tank. The
physical comparator and redstone wire match through both docks. The
71-tick powered bearing drain and both 199-tick powered train fluid
replays pass on the same build.
[Java fluid idle fixture](tools/java-mounted-fluid-idle-trace.patch)

The [last connected tick replay](tools/test-mounted-port-comparator.py)
matches 101 Java samples on native `e6e755d336c6` in solo and real LAN.
Unlocking the Hopper at Timer 4 moves one red sand into it on tick 29,
renews the receiver Timer to 63, and stalls the bearing at its new angle.
The replay compares the three inventories as cargo moves and checks the
comparator and wire throughout. The LAN guest removes the Hopper lock.

The [stationary bearing receiver replay](tools/test-mounted-fixed-port-render.py)
matches 140 stepped visual state rows, 12 drawn poses and six west-facing
outline hits on native `bf8c45d01350` in solo and real LAN. It checks two
docks with the Hopper locked, using the original casing, collar and tip.
The receiver reaches a tip extension of 0.51530343 blocks and retains
full extension during the first unlit retraction step. The comparator
checks also match all 141 idle ticks and 71 productive fluid ticks.

Horizon draws each measured pose while its corresponding server tick is
held. In a steady live Java client capture, the first opening and first
unlit full-extension poses appeared on the following server tick. The
later retraction poses appeared on their own ticks. Client publication
timing differs in that capture. [Java authority and renderer probe](tools/java-mounted-fixed-port-render.patch)

The [moving bearing item port replay](tools/test-mounted-moving-port-render.py)
matches 20 original Java samples from the steady second dock on native
`e081986d3c71`, in solo and real LAN. It checks the bearing angle, the
0.25-block-per-tick motion, and the actual body, collar and tip models,
including the lit state and local transforms. The collar and tip meet
the stationary receiver when settled. The three display identities
survive a saved-world reopen and all three are removed on disassembly.
The 141-tick idle comparator and stationary render checks also pass on
this build. [Java actor and renderer probe](tools/java-mounted-moving-port-render.patch)

The [moving bearing fluid port replay](tools/test-mounted-moving-port-render.py)
matches 20 Java samples from the steady second dock on native
`156d01044baa` in solo and real LAN. It checks the fluid-specific body,
collar and tip meshes, their position and orientation, the lit collar,
and cleanup on disassembly. In two original client captures the collar
became unlit on fixture tick 114 and 115 respectively as the client
bearing angle crossed the release boundary. The replay uses the
second capture, whose sampled poses and authority angles match the
original steady item trace.
[Java fluid actor probe](tools/java-mounted-moving-fluid-port-render.patch)

Drive-by Exchange matched 11 item and 62 fluid observations on native
`a3cc418aff88` in solo and with either player as the placer in LAN.
The survival placement consumes one port and records the placer. Only
that player earns the award, on the same tick as the first paper moves
or the first 8 mB passes through the pump. Both events clear the port's
owner, and the already-awarded player places a fresh port without
recording an owner. The existing Press ownership replays also pass for
both roles. [Java capture](tools/java-portable-interface-advancement-trace.patch)
[Horizon replay](tools/test-portable-interface-advancement.py)

Package dispatch, additional mounted inventories, moving-port animation
on other train routes and bearing docking sequences, larger schedule lists and
scroll animation, unloaded or cross-dimension station suggestions, and
the exact close cooldown remain under comparison.

### APP-2009 paired bearing gameplay

The [paired bearing check](tools/test-dual-port-bearing.py) adds one mounted
Fluid Tank and Portable Fluid Interface below the original item bearing
payload. Both actors rotate with the same bearing and cross the chunk
boundary to their respective fixed receivers.

- An unpowered item receiver beyond both candidate cells and a fluid
  receiver facing the same direction as the moving head. The actors pass
  those controls for 28 stepped ticks before the valid receivers are fitted.
- Both pairs connected while the five-slot extracting Hopper and the fixed
  tank are full. The feed Hopper and reversed pump then send cargo to the
  contraption, filling its 8,000 mB tank. The final flow sends items and water
  back to the fixed chest and tank.
- A survival LAN guest operates the bearing lever, observes both fixed
  interfaces extend, and opens the receiving chest. The host reads
  authoritative cargo amounts.
- A docked save/reopen that preserves the working positions and bearing
  angle, with up to 16 stepped ticks to observe both exchanges advance.
  Disassembly restores the two moving heads facing east,
  then an idle save/reopen checks both connections closed and the cargo
  unchanged. The balance is 16 paper, eight emeralds and 13,000 mB water
  across the mounted and fixed inventories throughout these phases.

The pinned Java movement rule in `PortableStorageInterfaceMovement` scans
the active cell and the next cell in the transformed facing direction. It
requires an opposing face and the matching interface type.
`PortableStorageInterfaceBlockEntity` provides the transfer window and
the item and fluid subclasses renew it on a successful exchange.
The paired bearing check uses those rules and the existing single-interface
Java traces above. It measures Horizon gameplay persistence and guest
convergence. Exact Java cold-start and network publication timing for the
paired rig, and broader layout, speed and automation combinations remain open.

The six cases initially passed on `native-9f42064-698ea7382493`. The
integration build `native-9f42064-645e120d2506` reproduced an active reopen
failure in both paired cases. The saved chunks still contained both working
positions, the bearing angle and stall, and both receiver timers. A frozen
startup retained that state and the first four stepped ticks maintained it.
Ordinary startup could tick the bearing before the receiver chunk was
available and clear the dock. A stationary bearing now preserves its saved
working positions and any actor stall while the receiver chunk loads. Once a
valid receiver is available, the bearing reconnects if the saved owner or
last contact is stale.

All six checks passed on `native-9f42064-48b8f8ede99a`, built on main
`86baa97` with launcher 0.2.67 and Create pack SHA-256
`85c5cd1eb79740f2bba2a8e0f30a9c213ea49e7fbb51621bb1310cdbe9b65645`.
The fixed client also loaded a copy of the exact failing save and exchanged
both resources at the original bearing angle. Both paired fixtures found
valid contact after 66 further ticks, filled the mounted tank in 30 ticks,
and observed both extraction paths within nine ticks of reversal. Their
docked reopens kept both working positions and the original bearing angle.
Both transfers had advanced at the first solo observation and within three
additional steps after the first LAN observation. The guest disconnected
before the host reopened that save. Both idle reopens retained the cargo and
orientation of all four ports. The original extraction and drain matched all
253 and 65 Java samples. The LAN fluid and idle item comparator checks
matched all 71 and 141 samples, including release and retraction.

```sh
python3 tools/test-parity.py CTL CLIENT RESOURCES --jobs 2 \
  --check 'dual-port-bearing*' --check mounted-item-extract --check mounted-fluid-drain \
  --check mounted-fluid-port-comparator-lan --check mounted-idle-port-comparator-lan
```

### APP-2055 mounted train item and fluid storage

The mounted-storage baseline reuses the pinned Java cargo and portable-interface
fixtures instead of expanding the family into an exhaustive storage audit. The
finite acceptance cases are chest/barrel and fluid-tank cargo retained while a
train travels, item and fluid docking transfer in both directions, full and
empty receiver boundaries, disassembly back to the original blocks, host and
guest interaction, and moving/docked save-reopen conservation.

The item and fluid extraction fixtures (`mounted-item-extract` and
`mounted-fluid-drain`) compare the source, mounted and receiving inventories
through assembly, movement and disassembly. The scheduled station checks cover
mounted Chest, Barrel, Item Vault and empty-carriage threshold/cargo behavior,
including LAN variants. `mounted-port-comparator*` covers item and fluid
interface transfer, comparator output, contact/retraction and disassembly in
solo and LAN; `dual-port-bearing*` adds paired item/fluid exchange, full
receivers, docking and active/idle reopen. `mounted-moving-port-render*` and
`mounted-fixed-port-render*` verify the moving and stationary interface state
through contact, retraction and reload.

Run the bounded regression set on one exact compatible build with:

```sh
python3 tools/test-parity.py CTL CLIENT RESOURCES --jobs 2 \
  --check mounted-item-extract --check mounted-fluid-drain \
  --check 'scheduled-train-stock-*' --check 'scheduled-train-stock-*-lan' \
  --check 'dual-port-bearing*' --check 'mounted-port-comparator*' \
  --check 'mounted-idle-port-comparator*' --check 'mounted-moving-port-render*' \
  --check 'mounted-fixed-port-render*'
```

The scoped baseline retains item and fluid identity and amount across the
tested travel, docking, guest, disassembly and reopen transitions. Broader
storage layouts, additional materials and exact Java reload/network timing
remain follow-ups; Full 1:1 stays Open.

#### APP-2055 final compatible-client regression

The bounded checks were rerun in an isolated checkout against compatible
client `native-9f42064-d6dc2ad18d3f` (launcher 0.2.67, prepared 26.3
resources, pack generated from the pinned Create revision). `mounted-item-
extract` matched 253 Java ticks and `mounted-fluid-drain` matched 65. The
scheduled mounted Barrel travel check matched 123 ticks in solo and 123 in
LAN. The scheduled fluid-port drain generated 199 rows in solo and LAN; both
normalized to zero differences against `fixtures/scheduled_train_fluid_port-
java.csv`, including train movement, contact, pump flow, disconnect and
conservation fields. The paired-bearing item/fluid replay reached both docks
after 66 ticks, filled the moving tank after 30 ticks, extracted at both fixed
receivers after nine ticks, and conserved 16 paper, eight emeralds and
13,000 mB water. Its LAN client launched and converged; the long-running
offscreen wrapper did not emit a final summary before timeout, so exact LAN
paired-bearing timing remains unclaimed.

## Train conductor Schedule handoff

The [pinned Java GameTest](tools/java-train-conductor-trace.patch) assembles
a carriage with two occupied Seats, one directly behind facing Train
Controls. Its [trace](fixtures/train-conductor-java.csv) covers ten
right-click observations. The ordinary Seat rejects a saved Schedule,
the controlling Seat accepts it, and an empty hand resumes a paused
Schedule before a later click returns it. Java returns the exact
timetable component in a fresh item and leaves the previous custom
name behind.

On native `0a1a3bb56ec0`, the [Horizon replay](tools/test-train-conductor.py)
matches nine same-level-tick hand and attachment observations for a
solo host and a real LAN guest. It captures villagers already occupying
both static Seats, verifies the controlling direction, and compares
assignment and return item data. Java also records the emitted sounds
and the four-to-five-player-tick cooldown boundary. Horizon's live
checks cover the settled cooldown and the resulting interactions.
The [Java train-seat fixture](tools/java-scheduled-player-seats-trace.patch)
boards two players on the assembled scheduled train through the original
interaction handler. The [Horizon host and LAN replay](tools/test-multiplayer-train-seats.py)
uses in-game clicks to board both players and compares their mounted state
and positions across 123 level ticks on native `539abfaeee59`. Both
[dismount poses](fixtures/scheduled_player_dismounts-java.csv) match, one
while moving and one at Terminal. Both fixtures disable entity pushes for
the two riders so the comparison isolates seating and dismounting.
The replay also checks each player's local view at eight checkpoints. Its setup
waits 20 level ticks after killing the unused conductor before assembling:
the [Java corpse oracle](tools/java-seat-corpse-pickability.patch) shows that a
dead villager remains pickable until removal at death tick 20. Otherwise its
frozen body intercepts the guest's seat click. This wait occurs before boarding;
the 123-tick trip remains measured from the original post-boarding phase.

## Clockwork Bearing

Horizon matched 46 samples in the
[original power and mode trace](tools/java-clockwork-bearing-trace.patch).
Two independently glued hands attach in order to both the east-facing
and west-facing bearings. The trace compares the three modes, signed
RPM, network stress and capacity, single-precision hand angles,
immediate power loss, and restoration on the following tick. The
[fast-motor trace](tools/java-clockwork-settling-trace.patch) adds 82
samples covering 256 RPM, the half-turn tie, and reaching the exact
hour and minute targets without overshooting.

The [removal fixture](tools/java-clockwork-removal-trace.patch) matches
27 samples for empty-hand stop, mining, and wrench rotation. The
[reload fixture](tools/java-clockwork-reopen-trace.patch) reattaches both
Java contraptions to their original UUIDs. Horizon retained both sets
of original displays, matched the first controlled step for both hands,
and restored the parts on stop. Survival crafting uses the original
slab, Brass Casing, and Electron Tube recipe.

Repeat with `tools/test-clockwork-bearing.py --visual` and the same
script's `--settling` and `--craft` switches, plus
`tools/test-clockwork-removal.py` and `tools/test-clockwork-reopen.py`.
The [obstruction trace](tools/java-clockwork-obstruction-trace.patch)
adds 27 samples, including ordinary blocks that drop when replaced and
bedrock that stays in place while the displaced hand block drops.

The [audio trace](tools/java-clockwork-audio-trace.patch) compares six
disassembly cues across three real actions. A host and guest heard the
original positions, block sound channel, gain, and pitch on the same
frozen game tick. Nonstandard assemblies and mounted actors remain open.

## Clockwork Bearing settings

The [pinned Java client probe](tools/java-clockwork-settings-client-probe.patch)
opens the original Clock Hand Arrangement board on a perpendicular side of
the bearing. A two-tick press leaves the mode alone. Holding Use Item for
six client ticks opens the board without a Wrench. The original three
options are ten GUI pixels apart, and right release confirms the selection.

The [Horizon replay](tools/test-clockwork-settings.py) checks those timings,
the original English and German option labels, and the saved values from
the Java sequence of 0, 1, 2 and back to 0. A left click leaves the board
open and preserves the previously saved value. A survival LAN guest
changes the host's saved mode twice with the same board. Board screenshots
are captured for visual inspection. Pixel-by-pixel comparison and hover
sound timing remain open.

## APP-1997 Clockwork gameplay baseline

The finite acceptance set reuses the pinned Java evidence for survival
crafting; both-hand power and mode behavior; the 256 RPM settling limit;
ordinary stop, mining and wrench rotation; obstruction drops; settings; active
reopen; and host/guest audio. It adds an idle persistence case to
`tools/test-clockwork-reopen.py`: set mode 1 while stopped, save and restart,
then verify mode 1 remains, `Running` is not set and no hand displays exist.
The fixture restores mode 0 before its existing Java active-reopen comparison.
This idle check is source-aligned; it does not claim Java reload parity.

Pinned inputs: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`, Minecraft
1.21.1 / NeoForge 21.1.219. The isolated Horizon client is
`native-9f42064-bb1452aaac4d` from source commit
`e8b3918a44b7156a124244af531af911991927ad`, an ancestor of this ticket's
`origin/main` base `1da56f2a0e33936df8e007e3c188e09fd20057e0`. Clockwork's
native behavior modules are unchanged at the ticket base. Prepared resources
were `.local/horizon-client/26.3`; the Create pack SHA-256 was
`cb9a737fce8e9f26c0b0f4f0a8fc2af332959c39f1d4cb3ca06f9a3583e28fcc`.

The reviewed Java paths at that pin were
`src/main/java/com/simibubi/create/content/contraptions/bearing/ClockworkBearingBlock.java`,
`ClockworkBearingBlockEntity.java`, and `ClockworkContraption.java` in the same
directory. They define empty-hand assembly/disassembly, wrench stop behavior,
ordered hand collection, mode targets and ticking, and contraption attachment.
The exact binaries and resources used were under
`/Users/andrewholt/dev/horizon-create/.worktrees/app-2047-bogeys-train-assembly/.local/`:
`patched-launcher/versions/native-9f42064-bb1452aaac4d/horizon-ctl`, the
matching `horizon-client`, and `horizon-client/26.3`.

On that client, the command
`HORIZON_NO_AUDIO=1 HORIZON_CREATE_TEST_AUDIO=1 python3 tools/test-parity.py /Users/andrewholt/dev/horizon-create/.worktrees/app-2047-bogeys-train-assembly/.local/patched-launcher/versions/native-9f42064-bb1452aaac4d/horizon-ctl /Users/andrewholt/dev/horizon-create/.worktrees/app-2047-bogeys-train-assembly/.local/patched-launcher/versions/native-9f42064-bb1452aaac4d/horizon-client /Users/andrewholt/dev/horizon-create/.worktrees/app-2047-bogeys-train-assembly/.local/horizon-client/26.3 --jobs 1 --check 'clockwork-*'`
passed 8/8 checks in about three minutes. Results: 46 powered/mode samples;
82 settling samples; 27 removal samples; 27 obstruction samples; original
survival recipe; English/German settings and two guest mode changes; all six
Java audio cues on both host and guest; active Java reopen plus idle mode
persistence. The muted audio variables are required for software playback
capture. Exact remaining time/layout combinations, visual pixel parity and
hover sound timing remain open.

The seven Java capture/probe patch SHA-256 values are:

| Capture | SHA-256 |
| --- | --- |
| `java-clockwork-bearing-trace.patch` | `3f5fa866bc87c2364e4b6b03a851a5aa2e81e71a0fa5cf6031b830e18f6258e8` |
| `java-clockwork-settling-trace.patch` | `8770ec599ae0c35171a27ee10ddca02c7592289d6a961307649768bb2a2b7f29` |
| `java-clockwork-removal-trace.patch` | `779dcd1c0261c697326ce105e07af7b9286c64aaa5ed1246363aa458f4b103f0` |
| `java-clockwork-obstruction-trace.patch` | `93755509ce7870dc5b0859b9b154f405bbc0cf192be7229082ac8abb66d211fb` |
| `java-clockwork-reopen-trace.patch` | `86a852e517d332df427782a15690296b19224ee69cf7a04a41c12599a8c92f12` |
| `java-clockwork-audio-trace.patch` | `262c054a02fa5ed25a16cdac6a4bc545195ff62ab49ed22a17c92563f9735d29` |
| `java-clockwork-settings-client-probe.patch` | `32ea337571e31c4d304dd64fa986b2b90414afe1c283eb5fd26a4562af435b0e` |

An earlier audio collection attempt on build `native-9f42064-6a3da367a9bb`
timed out waiting for playback events, including a retry with muted software
audio enabled. The later identified client passed the same host/guest trace;
the earlier failure is retained in the local run notes and is not counted as
a product audio regression.

## Chassis range controls

The [Java client probe](tools/java-chassis-range-client-probe.patch) opens
the real Linear and Radial Chassis boards with the Use Item binding. Both
require a wrench, open after six held client ticks, and leave the range
alone on a short press. Their one-row Distance selection clamps to 1–16
on release. The default is 8.

The [Java GameTest](tools/java-chassis-range-trace.patch) compares four
motor-driven payloads at small and boundary settings, including Ctrl
updates to the matching chassis group. Horizon matched all 12 game ticks:
the stored values, captured coordinates, and the values restored after
disassembly. A same-axis neighboring variant remains at its own value.
The replay uses actual Horizon board input, including the hold and
release. A survival LAN guest applied a group setting while the host
verified the two matching block entities changed and the neighboring
variant retained its value. A chassis placed on an earlier Horizon build
also accepted a new range and retained it after restarting the world.
Non-default Java range configuration values remain open.

## Chassis range preview

A [live Java client probe](tools/java-chassis-preview-probe.patch) records
the captured positions, visible faces and edges, saved value, hovered
value, and lifetime of the original Linear and Radial Chassis previews.
Horizon matched 72 samples, including the change before committing a
hovered value, the saved value reaching the rendering client, the
200-tick Wrench lifetime, the 20-tick clamp after putting it away, and
the outline's renderer fade and removal.

Both screenshots exercise the world renderer with the original checker
texture. The atlas quad and cuboid edge submission follows the exposed
cluster boundary measured in Java. Mixed-group preview transitions and
pixel-by-pixel image comparison remain open.

## APP-1995 Linear, Secondary and Radial Chassis

This finite gameplay pass reused the pinned Java references at
`ac0c444d9828da3453ae8cc65338e8de063286fb` and the current Horizon source
pin `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. Five Linear assemblies,
six Secondary Linear assemblies (18 Java ticks), and six Radial assemblies
(18 payload ticks plus a 27-tick quarter-turn) passed. The player checks
covered linear placement and seven adhesive actions, four Secondary
placements and five adhesive actions, Radial placement and 12 sticky-face
actions, and the original chassis conversions. Range controls matched all
12 Java samples, including clamp boundaries; the LAN guest changed a
matching group setting while the neighboring variant retained its value.
The existing preview replay matched 72 samples.

The new [reopen replay](tools/test-chassis-range.py) also uses the mixed
primary/secondary arrangement from
[`secondary-linear-chassis-java.csv`](fixtures/secondary-linear-chassis-java.csv).
It saves and reopens the idle assembly, verifies sticky membership and both
range values, assembles the three-block payload, then saves and reopens while
that payload is active and verifies the captured Java-relative positions.
This is source-aligned gameplay persistence evidence, not a claim of exact
Java active-reload timing.

The selected bounded run passed 12 of 12 checks on the rebased combined
build `native-9f42064-645e120d2506`. The client SHA-256 is
`3e91d78b62415094ef4de108756ecde81c8e39ac4f814e03cc606644019b79c7`; the
prepared Create pack SHA-256 is
`3b914d86881a3d8eb906cdadfaa69981c6f0c9dcff4eaddfc3cf0560f400db49`.
Reproduction used:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-645e120d2506/horizon-ctl .local/patched-launcher/versions/native-9f42064-645e120d2506/horizon-client .local/patched-launcher/versions/native-9f42064-645e120d2506/.local/horizon-client/26.3 --jobs 2 --check linear-chassis --check linear-chassis-player --check secondary-linear-chassis --check secondary-linear-chassis-player --check linear-chassis-conversions --check radial-chassis --check radial-chassis-player --check radial-chassis-spin --check chassis-range --check chassis-range-lan --check chassis-range-reopen --check chassis-preview
```

`git diff --check` and Python compilation passed. The first clean native build
took 969 seconds; the post-rebase incremental combined build took 437 seconds.
The focused gameplay batch passed after enabling the test harness's local
control sockets. Additional mixed layouts, other controllers, non-default
range configuration, and all-layout preview transitions remain follow-ups.
Full 1:1 parity stays Open.

## Desk Bell APP-2037

Gameplay baseline:

The bounded cases are survival recipe crafting; the [55-tick pinned Java
replay](fixtures/desk-bell-pulse-java.csv) of three presses (including an
in-flight retrigger), powered removal, weak and facing-directed direct signal;
all six dry and source-waterlogged placement facings; support removal; and
idle/active save and reopen. The [Java probe](tools/java-desk-bell.patch) also
records three original sound cues. The [Horizon replay](tools/test-desk-bell.py)
compares every tick and both physical dust circuits in solo and LAN; it checks
all three sound IDs, categories, positions, gains and pitches, crafts the
original recipe, and verifies all six placement states in solo and guest play.
Dry placement also checks the outer outline plane hit from each face.

The lifecycle fixture removes the block behind a north-facing bell and verifies
that the bell remains with its state and remains usable. This matches the pinned
`DeskBellBlock.updateShape` implementation, which only updates water and has no
support-loss removal rule. Idle reopen retains facing, waterlogging, unpowered
state and zero adjacent dust output. Active reopen retains facing, powered state
and strength-15 adjacent output; a new ring after reopen completes its 20-tick
pulse and clears the output. This feature has no inventory or configurable
connections to preserve.

All eight registered checks passed on `native-9f42064-d6dc2ad18d3f` with pack
SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`;
client SHA-256 `006bfe15a198b29d6af7633d353dcadaa07039121ae66c2081927299835a8811`.
Java source is Create `ac0c444d9828da3453ae8cc65338e8de063286fb`;
capture-patch SHA-256 `58fd73ebe265eaf157457619eba26570b2064b236de7c19d7288b2e573c3fcc7`.
The pulse, sound, dry-placement and water-placement trace hashes are,
respectively, `4ffca90629f25aa1a8a70f5f3ed72bc0e7f9f97dd4779acc75a983a639f9cc04`,
`76a34332771b1fef6026839b45ab668b24086d782372fb5e119f42d7194b2c96`,
`f7d7cf99324fc7f03afacf0153a7c63c88f9e9a6f168dfbe844bd3df896bf1f8`, and
`cde2dab866e62218bf8c87c38f72724656d8953c7be8475fc064a52beb28fc4d`.
Run the checks through `tools/test-parity.py` named `desk-bell-pulse`,
`desk-bell-pulse-lan`, `desk-bell-placement`, `desk-bell-placement-lan`,
`desk-bell-wet-placement`, `desk-bell-wet-placement-lan`,
`desk-bell-support-removal`, and `desk-bell-persistence`.

Exact animation/collision, sound waveform, concurrent input phases and broader
power/playback combinations remain nonblocking follow-ups. Full 1:1 remains
Open; this bounded gameplay baseline passed.

## Powered redstone latches

The [pinned Java fixture](tools/java-create-latches.patch) records
[41 ticks](fixtures/create-latches-java.csv), ticks 0–40, of Powered Latch
and Powered Toggle Latch state, rear and side inputs, and output read by
adjacent dust. It covers short and held rear signals, a side signal, accepted
manual toggles, rejection while rear and side power disagree, and sneaking.
The [physical Horizon replay](tools/test-create-latches.py) matched every
sample in solo and LAN on `native-9f42064-6bdf8691aa42`; the guest operated
both latches and its observed state converged at every sample. Both survival
recipes also passed in solo.

The [persistence replay](tools/test-create-latches-persistence.py) checks
idle saved outputs, active rear inputs on both latches, the Powered Latch's
side input, and state retention across world restart. After reopening, it
removes the rear input and then the remaining side input, confirming the
Toggle Latch holds its output and the Powered Latch resets when both paths
are off. These are instantaneous block states, so active persistence means
retaining powered state and connections through restart and observing their
subsequent reset transitions; no tile-entity contents apply. It passed on the
same identified build. The registered checks are `redstone-latches`,
`redstone-latches-lan`, and `redstone-latches-persistence`.

Java source: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
Capture patch SHA-256: `5ccdffe850690369dae4f659a23b4d4b4a8f732bf313813829d868fa8bc8e2c3`;
trace SHA-256: `496e0d3ff609bd125b92fb466e081b12cea298ed0fc3cf04cd1b109b12c37c2c`.
Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, client build
`native-9f42064-6bdf8691aa42`, pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Run the three named checks with the documented `tools/test-parity.py`
command. Exact visual presentation and other orientations/mixed layouts
remain outside this bounded gameplay pass.

## Brass pulse diodes

The [pinned Java pulse fixture](tools/java-brass-diode-pulses-trace.patch)
records [270 samples](fixtures/brass-diode-pulses-java.csv) across default
and configured Pulse Extenders, Repeaters, and Timers. It covers brief and
sustained inputs, an inverted Timer, elapsed progress, and front and side
redstone output. The [Horizon circuit replay](tools/test-brass-diodes.py)
matched all authoritative samples in solo and live LAN on
`native-9f42064-a1d0dcf25d6e`. The LAN guest also received the block states
at sampled checkpoints.

The [survival replay](tools/test-brass-diode-actions.py) matched all three
recipes and [12 Java placement and interaction results](fixtures/brass-diode-actions-java.json)
in both roles. A normal click toggled polarity, including with an ordinary
item in hand. Sneaking preserved it.

The [interval board replay](tools/test-brass-diode-settings.py) matched all
[eight Java timing settings](fixtures/brass-diode-settings-java.csv) in
solo and live LAN on `native-9f42064-ca95edd27742`. Holding Use opened
the three unit rows. Release committed the selected interval and clamped
stored progress to the new maximum. A short tap on the same slot toggled
polarity once on release. The 270-sample pulse LAN replay and nearby
latch and valve controls passed on the same build. The animated indicator
and diode click playback still need verification.

## APP-2041 Display Link and Display Board

The pinned Java Create revision `ac0c444d9828da3453ae8cc65338e8de063286fb`
provides two existing references. The [Display Link fixture](fixtures/display_link-java.csv)
samples ticks 0–145 for single and double chest counts, Nixie text, and
redstone gating. The [depot fixture](fixtures/depot_display-java.csv)
samples ticks 0–120 for both depot items, Board rows, and Board RPM.
The capture patches are [Display Link](tools/java-display-link-trace.patch)
and [depot display](tools/java-depot-display-trace.patch).

The [lifecycle replay](tools/test-display-board-lifecycle.py) uses an
offscreen integrated host and a survival LAN guest. The guest selects a
powered Board, attaches a Link to a chest-facing Smart Observer, spends
one Link, and selects the item-count source and second row. The host
checks the resulting source, offset and row, and the guest framebuffer
shows the count. Removing the Board hides the configuration controls.
Restoring it allows the guest to publish 7 again with the same link.

On the pinned Horizon comparison build `native-9f42064-6ce68a31b125`,
the missing-target screen showed “Active”. Java’s `DisplayLinkScreen`
uses `create.display_link.no_target` when the target is absent. The
Horizon settings screen now uses the same translation in place of the
active indicator while the target is absent.

In the redstone-gated reopen, the saved connection and display of 7
survive while the chest contains 11. Removing the redstone signal
publishes 11. In the ungated reopen, the connection and 11 survive, and
a stock change publishes 4 within 100 ticks.

The baseline at port revision `198918987713b18a3cfa87c1ceddd7167f512419`
built as `native-9f42064-f7d9ba41e662` in 19m 1s with launcher 0.2.67
and Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. Its Create
native bundle SHA-256 is
`00ca576b17fc771b005a7af4ac7da74b7606f91cef4007c36b4ce2f9430f4496`.
The prepared `create.hmod` SHA-256 is
`79c140df790d6c578b79c3b027dfab4c825a8439355ed601b5d7cfebf9f47cb0`.

The incremental candidate `native-9f42064-6a55687e3aae` built in 9m 58s.
Its Create native bundle SHA-256 is
`69924e9ecb722a34fa5b6daae5b1503357beb85724947911050f33241e844c6f`.
The client SHA-256 is
`5e78ea032b75c5344631f7678132c759538dfd334fededdce4295acebd410532`.
Run the scoped checks with the candidate's binary and prepared 26.3
resources, and the worktree's `.local/create.hmod`.

```sh
version=.local/patched-launcher/versions/native-9f42064-6a55687e3aae
HORIZON_NO_AUDIO=1 python3 tools/test-parity.py "$version/horizon-ctl" \
  "$version/horizon-client" "$version/.local/horizon-client/26.3" \
  --jobs 1 --check display-board-lifecycle
HORIZON_NO_AUDIO=1 python3 tools/test-parity.py "$version/horizon-ctl" \
  "$version/horizon-client" "$version/.local/horizon-client/26.3" \
  --jobs 2 --check display-link --check depot-display --check depot-display-settings
HORIZON_NO_AUDIO=1 python3 tools/test-parity.py "$version/horizon-ctl" \
  "$version/horizon-client" "$version/.local/horizon-client/26.3" \
  --jobs 1 --check display-link-placement
```

The three existing comparison and depot settings checks passed in
93.70s. Both traces matched every sample, and the survival depot settings
published the item name to the second row of the powered Board.
The Nixie placement check passed in 15.86s, selecting the Nixie,
spending one Link and configuring the live count.

The candidate lifecycle replay passed in 43.90s. The guest screenshots
at `.local/display-board-guest-count.png` and
`.local/display-board-guest-missing-target.png` show the second-row
count and “Not a Display Target”, respectively. All 35 sampled cells
of the guest digit match the installed bitmap font's `7` glyph. The
sample compares the `7` and `?` font masks in
`.local/app-2041-guest-glyph-verification.txt`. The seed menu comparison
at `.local/app-2041-seed-guest-missing-target.png` shows the earlier
“Active” label.

The LAN check measures guest convergence and the reopen check exercises
Horizon saves. Java network timing, Java reload parity, additional source
and target combinations, and exact flap rendering remain open.

## Dyed Nixie Tubes

The [Java dye trace](fixtures/nixie-dye-java.csv) and
[Horizon replay](tools/test-nixie-colors.py) match all 16 colors in headless
solo and live LAN on `cbcf3690ed2f`. Dye recolors the mixed row, keeps the
held stack and existing text, and leaves a differently mounted neighbor
alone. A purple tube dropped the original orange item when mined. The
[redstone trace](fixtures/nixie-power-java.csv) matched the four power-on
and power-off ticks with the other tube retaining its text. The existing
Display Link fixture still matched all 146 Java ticks.

The existing dye replay was rerun in solo and LAN on the same client and pack;
both runs matched all 16 Java dye cases, retained text and held dye count,
preserved the differently mounted neighbor, matched four redstone samples, and
produced the original orange drop.

The survival replay (`tools/test-nixie-survival.py`) crafted four ordinary
tubes from the original electronics recipe, placed one with a real player click,
and verified the held count fell to three. Its registered
`nixie-survival` check passed through `tools/test-parity.py`.

The Nixie persistence replay (`tools/test-nixie-persistence.py`) checks
adjacent purple floor-mounted tubes: one retains custom text and one publishes
numeric redstone strength. Idle save/reopen retained both colors, mounts, and
text. Powered save/reopen retained the output strength; removing power after
the active reopen returned it to zero. This is a Horizon gameplay persistence
check, not a Java reload parity claim.

The replay passed on the pinned Horizon Nightly 9f42064 client with
`horizon-client` SHA-256 `63d4babf8091fe41f7712bc92d85b7467beecc4721dc54e0dfc50da7a5c97887`,
`horizon-ctl` SHA-256 `1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`,
prepared Minecraft 26.3 resources, and the Create pack SHA-256
`6e169b2d4918f54d31d19ee9539b19b6de3d9b4d5464d62c78c9c7a52f51e509`.
Command: `python3 tools/test-nixie-persistence.py <horizon-ctl> <horizon-client> <prepared-26.3> --pack <create.hmod>`.
The successful control log is retained as `.local/horizon-nixiepersistence.log`.
The dye replays used the same arguments with `tools/test-nixie-colors.py`,
adding `--lan` for the guest run; their successful logs are
`.local/horizon-nixiecolors.log` and `.local/horizon-nixiecolorslan.log`.
After syncing current `origin/main` at `a5adcc5`, both registered checks passed together with `python3 tools/test-parity.py <horizon-ctl> <horizon-client> <prepared-26.3> --jobs 1 --check nixie-survival --check nixie-persistence`. Runner logs are `.local/parity/nixie-survival.log` and `.local/parity/nixie-persistence.log`.
Initial harness attempts were invalid: one used the fixture's one-tick step
helper as a two-tick jump, and another combined custom text with the numeric
output tube. The survival fixture first lacked the ignored NBT structure and
then aimed through the crafting table; after provisioning the fixture and
moving the placement to a clear floor tile, it passed. These were test setup
issues. The final persistence fixture uses the Java reference's separate tube
roles.

All 16 original blockstate definitions and their direct models match by
file bytes. The declared geometry matches the
[16 Java mount/facing combinations](fixtures/nixie-shapes-java.csv), and
the muted offscreen client emitted the original
[base palettes](fixtures/nixie-colors-java.csv). Per-frame flicker,
pixel parity, all placement paths and exact Java reload parity remain open.

## Chain Conveyor Java reference

The [Java GameTest patch](tools/java-chain-conveyor-trace.patch) records
[six connection cases](fixtures/chain-conveyor-connection-java.csv),
[147 world ticks](fixtures/chain-conveyor-world-java.csv), and
[165 cargo samples](fixtures/chain-conveyor-package-java.csv). Both original
tests reproduced the same traces in two headless runs. A straight route
delivers an addressed package to the Frogport on tick 33 and leaves
unmatched cargo looping. The rising route covers signed reversal in flight,
power interruption, and restart. Horizon implementation is pending.
Client targeting, riding, rendering, branching, and save/reopen are outside
these reference fixtures.

## Elevator acceptance

- Assemble and disassemble a glued cabin with two linked pulleys.
- Call it with Redstone and verify arrival signals and cabin motion.
- Render the moving belts, spools and magnets at both pulley positions.
- Name and select a destination with the elevator controls.
- Board as a guest, select a floor, ride there and dismount. Verify the trip
  from the host and guest clients.
- Save and reload a stopped and a moving cabin. The replay checks that the
  moving cabin finishes the first trip and that the stopped cabin stays at
  the destination. It then compares the Redstone call back to the bottom
  against the Java descent and disassembles the returned cabin.
- Compare the host-and-guest trip with the 92-tick Java trace in
  `fixtures/elevator-passengers-java.csv`. The same replay checks rider
  positions and lamps in both live clients and invokes server-side dismount.
- Check crouch-key dismount and grounded survival for both players.
- Compare all 101 ticks of the per-floor door fixture with Java, including
  both halves of the moving and landing doors and the emitted sound events.
- Compare indicator angles, button motion, rendered frames, and audio starts
  for both clients. The angle and button reference runs the original Java
  animation and interpolation against the fixture ticks.
- Verify both standing survival riders remain unmounted and supported
  throughout the ascent and descent, and can jump independently at the
  landing. Compare settled clearance with Java. The Java collider fixture
  separately captures pre- and post-contact motion, including transient
  vertical separation and client pose resets. The live Horizon replay
  compares both players’ positions and vertical velocity using the Java
  contact solver at the cabin poses each client received. A second run
  delays the cabin updates briefly and verifies that both riders finish.
- Verify both players can walk while the cabin moves and exit through
  a paired landing door. Check that both leaves open and close in both
  clients.

## Elevator bounded gameplay baseline (APP-2001)

The Rope Pulley and Redstone Contact prerequisites are Done in APP-1999 and
APP-2000. The bounded two-floor baseline passed on 2026-11-20 using
`native-9f42064-395b15d09945` and the `create.hmod` pack with SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`. The
build uses Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0a` and was produced
from commit `5cd93bb`; the current main commit is `a167267`. The post-build
main changes do not modify elevator, rope or contact modules. Java comparisons
reuse the pinned Create 6.0.10 traces at
`ac0c444d9828da3453ae8cc65338e8de063286fb`.

| Bounded case | Result |
| --- | --- |
| Original two-pulley cabin, Redstone trip and return | `elevator`: all 67 Java ticks matched. |
| Active and idle save/reopen, retained cargo and return/disassembly | `elevator-reload`: reopened at trip tick 42; all 66 return ticks matched Java; cabin and seat disassembled, and the cow remained at the upper landing after idle reopen. |
| Two named floors, guest floor selection, door modes/interlock, indicator and sound | `elevator-service`: 101 Java ticks, 85 indicator samples on both clients, and 66 standing-player positions matched. |
| Host and guest board the elevator seats and dismount in survival | `elevator-grounded`: both players boarded, rode to the upper landing, shift-dismounted and remained grounded. |
| Standing host and guest ride to both endpoints and dismount | `elevator-standing`: both players remained unmounted and supported for all 134 travel ticks, then jumped and landed independently. |
| Walking on the moving cabin and crossing paired doors | `elevator-walkthrough`: both players walked while rising, stopped at closed doors, and crossed after the paired doors opened; both clients observed the door states. |
| Host/guest selected-floor trip and shared state | `multiplayer-elevator`: all 92 Java ticks matched for both clients, including names, lamps, cabin position and seated riders. Guest state was checked after convergence. |

Run these checks together with the exact build's `horizon-ctl`,
`horizon-client` and prepared `26.3` resources using
`python3 tools/test-parity.py <build>/horizon-ctl <build>/horizon-client <build>/.local/horizon-client/26.3 --jobs 2 --check elevator --check elevator-reload --check elevator-service --check elevator-grounded --check elevator-standing --check elevator-walkthrough --check multiplayer-elevator`.
All seven passed. Raw logs and sampled Horizon CSVs are retained under
`.local/app-2001-evidence/` in the development environment.

The two registered contacts bound this pass's travel range; upward and
downward trips both settled at their selected endpoints. Closed landing doors
blocked player exit until the guest opened them. APP-1999 independently checks
the shared Rope Pulley blocked-assembly and zero-rope upper-limit behavior.
The checks establish this baseline for the two-floor configuration, not every
height or layout. Full 1:1 remains open for additional layouts, camera and
interpolation timing, delayed updates and remaining edge interactions.

## Copper roofs

The port loads all 48 original copper shingle and tile blocks, including
full blocks, slabs, stairs, and their weathering and waxed variants. All 90
original ordinary crafting and stonecutting recipes are registered.
[Original Java block and drop data](fixtures/copper-roof-blocks-java.csv)
matched the pack declarations and loot, with 204 original asset paths
byte-identical. [The survival replay](tools/test-copper-roofs.py) verified
all 48 default states, both ingot stonecuts, waxed slab crafting, and
slab stacking in solo and with a live LAN guest. The
[original direct-action fixture](fixtures/copper-roof-actions-java.csv)
matched all 72 survival honeycomb and axe interactions in both roles,
including tool durability and the preserved waterlogging and shape.
The [weathering replay](tools/test-copper-roof-oxidation.py) matched the Java
fresh-to-oxidized sequence for full blocks, slabs, and stairs. Waxed variants
stayed unchanged and the vanilla copper control weathered. Elapsed random
tick timing, connected textures, and Deployer recipes remain open.

The focused [save/reopen check](tools/test-copper-roof-persistence.py) covers
six representative age, wax, slab/stair shape, and waterlogging states while
random ticks are disabled; all six survived an idle save/reopen. The registered
check is `copper-roof-persistence`. The bounded six-check batch passed on
`native-9f42064-6ce68a31b125` with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`:
`copper-roofs`, `copper-roofs-lan`, `copper-roof-actions`,
`copper-roof-actions-lan`, `copper-roof-oxidation`, and
`copper-roof-persistence`. The action checks each compared 72 Java transitions
with zero differences; the weathering check observed the expected age order
for full blocks, slabs and stairs over 83 world ticks.

Reproduce with the documented `tools/test-parity.py` command, passing
`--jobs 2` and each of the six names above as `--check`. The pack used was the
prepared `.local/create.hmod`; Java reference is Create
`ac0c444d9828da3453ae8cc65338e8de063286fb`. An active-machine case is not
applicable to these static blocks with no stored process or inventory; natural
aging is exercised separately. Exact Java reload timing and elapsed
random-tick distributions,
connected textures and Deployer recipes remain open.

## Chain Conveyor and Frogport

Two headless runs of original Java Create produced identical
[connection](fixtures/chain-conveyor-connection-java.csv),
[world](fixtures/chain-conveyor-world-java.csv), and
[package](fixtures/chain-conveyor-package-java.csv) traces for straight
delivery and a rising span with a reversal and power cycle.

Run `tools/test-chain-conveyor-math.sh ../horizon` to check the Rust
math with the same pinned Horizon trigonometry as the native build.
The [headless replay](tools/test-chain-conveyor-math.rs) matches the
chain cost, both connected spans, 165 package anchors within
0.00000001 blocks, and all 162 consecutive sampled movement steps at
float precision. The replay consumes wheel speeds and package path
choices from the trace. In these fixtures, a motor update appears in
the world sample one tick before it changes package movement. A ticks
before B, so a package arriving at B can move on its loop in the same tick.

The candidate pack contains the original Conveyor and Frogport item
and block models and both crafting recipes. The [headless Horizon
kinetic check](tools/test-chain-conveyor-kinetics.py) places both blocks
and compares the straight and rising endpoint speeds with the Java trace
at selected milestones. A single stored link leaves the destination
unpowered. A reciprocal link carries the same speed across the gap.
The rising case covers reversal, stopped power, and 16 and 128 RPM
restarts. Removing both links stops the second wheel in each case.

The same headless check can use a survival player or a LAN guest.
Both roles left one chain untouched on an unsuccessful connection.
A stack of 16 established both links and left 13, matching the original
straight fixture. Duplicate selection spent no further chain. Horizon
suppresses client-side vanilla chain placement while the server handles
the conveyor click, so the visible stack agrees with the server.

The [headless game replay](tools/test-chain-conveyor-packages.py)
matched all 147 Java world ticks and 165 package states in the straight
and rising fixtures. It compares endpoint RPM, reciprocal links, reversal
flags, advertised route, package owner and path, cargo, float progress,
Frogport animation progress, and inventory custody. The straight
package leaves A on tick 3, reaches B's loop on 17, enters the Frogport
animation on 24, and reaches its inventory on 33. The package addressed elsewhere stays on A. The rising package changes ownership and span
direction on tick 12 and holds its loop position while power is off.

The [player replay](tools/test-chain-conveyor-player.py) clicks a
conveyor loop with a held Frogport, places it, then loads an addressed
paper package through an actual survival click on the other loop.
Headless solo and LAN guest runs each match all 31 ticks in the
[Java player trace](fixtures/chain-conveyor-player-java.csv). Java
selects the original 45° load point and 135° attachment through its
loop geometry and inserts the package through its server packet
handler. Two Java captures produced identical fixtures. The
Horizon player replay preconfigures the chain and sets the receiving
address through a fixture command.

The [span replay](tools/test-chain-conveyor-span-target.py) matches
Java's selected conveyor, direction, and float position on both straight
and rising spans. It attaches a real Frogport to that point, loads a
survival package at it, then confirms the full payload reaches the
port inventory. Both layouts pass in headless solo and LAN guest worlds.
The receiving address is set by the fixture. The
[wrench replay](tools/test-chain-conveyor-span.py) also passes in both
layouts and roles, removing reciprocal links, refunding three chains,
and releasing a package from each directed span. Drop coordinates
match [the Java trace](fixtures/chain-conveyor-wrench-java.csv) within
0.00000002 blocks. Both LAN clients receive both drops.

The [outbound Frogport replay](tools/test-chain-conveyor-outbound.py)
matches 34 Java ticks of inventory custody, launch animation progress,
and receiving conveyor position. The Frogport keeps the package
addressed to itself, starts dispatching the other package on tick 37,
and hands it to the destination loop at 150° on tick 42. This scenario
uses a preloaded port inventory and runs in headless solo.

The [offscreen replay](tools/test-chain-conveyor-visual.py) compares
an animated shaft, both moving chain spans, and Frogport yaw, head,
tongue, and catch package scale against Java renderer inputs. It runs
the straight and rising layouts with the original models and textures.
The outbound replay also has a muted offscreen mode that checks the
launch pose and rigged package mesh against
[Java launch parameters](fixtures/chain-conveyor-visual-send-java.csv).

The straight replay also matches the
[Java Frogport reload trace](fixtures/chain-conveyor-port-reload-java.csv).
Saving at tick 27 keeps the package in transit. Reopening resets the
catch animation and deposits the package at tick 37. All 80 world
ticks and 100 package states pass in the cold-reopen fixture.

The [dedicated server restart replays](tools/test-chain-conveyor-restart.py)
match the saved snapshot and 15 post-restart states in each layout.
The straight package enters B's loop at 305° after eight active
ticks. The rising fixture starts with a negative saved RPM and
restores the reversed direction on both wheels. The package stays on
its saved span before reaching and advancing around B on tick six.
The Java traces were identical across two captures. Horizon compares
from the first loaded observation, when the conveyors have yet to step.

The [pickup replay](tools/test-chain-conveyor-retrieval.py) confirms
that right-clicking a loop package gives it to an empty main hand.
Picking up a span package while holding a stick puts it in inventory.
Both layouts match the original Java packet outcomes in solo and LAN.
The `--open-air` replay confirms empty-hand loop pickup with a
crosshair miss in both the straight and rising layouts, solo and as a
LAN guest. The guest identifies the package by its replicated ID and
the host checks the hitbox before transferring the stack. The replay
holds the conveyor still at the Java pickup pose. Moving pickups
under latency remain unverified.

The [adjacent barrel replay](tools/test-chain-conveyor-adjacent.py)
matches 18 Java ticks. On tick 37 the port puts a received package
into the barrel and draws a differently addressed package out of it.
The drawn package launches on tick 42. The stick in the barrel stays
in place. This replay covers a barrel in headless solo.

The same replay covers a full barrel. The port keeps the package
and marks its export blocked on tick 37. It transfers the package
on tick 48 after a slot opens and clears the warning. All 18 Java
states match headlessly. Muted offscreen host and LAN guest runs
showed the translated warning without equipped Goggles and confirmed
that it clears after export.

The [branch replay](tools/test-chain-conveyor-branch.py) verifies one
powered source and two addressed Frogports on different spans. The
source learns both exits on tick 1. Each cargo follows its address
and reaches the intended inventory. The headless solo replay and the
headless LAN replay each match 70 Java world ticks and 57 package
states. In the LAN replay the host and guest each load an addressed
package with a normal survival click.

The same replay with `--relay` routes one package to a local
Frogport on the intermediate wheel and sends the other through a
second span. Java advertises the second destination at the
intermediate wheel on tick 1 and at the source on tick 2. Headless
solo and a real headless LAN host and guest each match 70 Java
world ticks and 61 package states.

The `--relink` variant also matches 230 Java ticks and 234 package
states in solo and LAN. A wrench removes the second span on tick
10. The package waits on the intermediate wheel while the route
expires on tick 101. Restoring the span on tick 112 restores power
on the next tick. The source rediscovers the route on tick 183,
and the waiting package reaches the Frogport on tick 223. The
operator gets three chains back and spends those three on reconnect.

The [offhand connection replay](tools/test-chain-conveyor-kinetics.py)
matches Java's chain counts in headless solo and LAN. One chain is
insufficient. Connecting the wheels with sixteen chains consumes
three from the offhand and leaves the main hand empty. The wrench
replay also works from the offhand in both layouts in solo and LAN.
It matches the three-chain refund and the two released packages'
positions and payloads.

The [suspended package replay](tools/test-chain-conveyor-suspended.py)
matches the original Java target, spring position, and swing angles
for 22 straight poses and 65 rising reversal poses in muted offscreen
solo and LAN. The package keeps its identity and both meshes through
the straight handoff and the rising reversal. The rising trace also
covers a power stop, restart, second direction change, and
disconnect. The guest matches the host's snapshot tick for each pose.
The Java fixture calls the original spring code and uses the renderer's
projection against server motion samples.

The same replay with `--lighting` matches all 22 Java light samples
on both package and rigging vertices in muted offscreen solo and LAN.
The package samples the block at its interpolated spring position.
The owning wheels also match Java's block and sky light. Their
non-occluding block states have zero light dampening and admit full
skylight. The fixture also verifies level 15 in the air below the
unobstructed destination wheel.

The [chain distance replay](tools/test-chain-conveyor-visual.py) matches
Java's switch at 48 blocks from the span midpoint. Both directions of
the straight and rising spans were rendered at 47, 48, 49, and 60
blocks in muted offscreen solo and LAN. At 47 blocks the chain uses
scrolling atlas strips. At the three farther samples, four thinner
quads use the original static texture rectangle. The two versions'
base chain PNGs are byte-identical.

The same replay with `--visibility` checks Java's strict 256-block
renderer cutoff. The camera stays above the loaded pair for the
distance sweep and faces away at 96 blocks. Both wheels and their
spans submit when in range, including offscreen. The nearby Frogport
still uses Horizon's default range.

The `--mip --span-light` replay matches Java's two endpoint light
values on both directions of the straight span in muted offscreen solo
and LAN. The ceiling suppresses skylight and a nearby source lights
the wheels differently. The atlas strips interpolate the two sampled
lightmap colors along the chain. The replay checks the submitted
vertex lighting and interpolation positions at 47, 48, 49, and 60
blocks. Pixel comparisons, Frogport address editing, and other
inventory types remain open.

The [riding controller reference](fixtures/chain-conveyor-riding-java.csv)
captures 149 original Java ticks across seven scenarios. It covers
boarding inputs, loop and span handoffs, looking toward a junction,
reversal, a power pause and restart, and dismounting by sneak, tool
release, lost link or failed catch-up. The headless adapter supplies
player poses and records the controller's velocity output before
vanilla movement. The production Rust controller matches all 149
captured ticks.

The [live riding replay](tools/test-chain-conveyor-rider.py) boards a
wheel or span with a wrench in either hand, moves the player, and
dismounts by sneaking or releasing the tool. Both solo and real LAN
guests pass, including a live rising reversal that transfers the
active rider to the other wheel's span. The host observes the guest's
movement through the normal movement packets.

The LAN host verifies each riding keepalive against the held tool,
connected chain, and rider's current position before clearing the
rider's fall and floating counters. A 110-tick ride on a long span
produced 11 accepted keepalives and one explicit stop in each hand.
The disconnect replay expires at the original 20 server ticks after
the last keepalive. The seven-block high-speed return lap can still
dismount a rider before 110 ticks. Its full movement needs comparison
against Java.

The [Java player-pose capture](tools/capture-java-chain-skyhook.py)
produced 168 model-part samples across six animation times, either
grip and both skin widths. The Rust pose math matches all 168
[reference rows](fixtures/chain-conveyor-skyhook-java.csv). A second
LAN guest rendered the original hanging arm angles for both grips.
The pose cleared after sneaking or releasing the wrench. After the
rider disconnected, the host expired the rider after 20 ticks and
the observing guest received the cleared roster. The sustained
110-tick LAN case still passes on the same build.

The live comparison checks the hanging arm angles and roster
transitions. Full player travel and frame-by-frame rendered pose
parity remain open.

### APP-2027 bounded gameplay baseline

The bounded issue pass ran against Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, final rebased build `native-9f42064-fb8446effe86`, using prepared 26.3 resources and pack SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`. The pinned Create reference is `ac0c444d9828da3453ae8cc65338e8de063286fb`. Reused capture patch SHA-256 values: base trace `c86a2ccaab8161037024f301ab34776c6e90668b7c76026fbbafcbab0033bb11`, branch `b7e83ad6e1b6ccade01d78f7b35adb926effbc74178e9ae6cb568f57d3ccc5e3`, blocked barrel `1e634db3945305ae1b005cafedfadbed7df2163ff4b23834f7ff84e1b66153a9`, restart `7c7fab944a25ccfac9ed48e64ddf9d308b758dde4799a6b8bf6f32269208c671`.

- `tools/test-chain-conveyor-kinetics.py`: straight and rising Java traces matched one-sided and reciprocal connections, 128 RPM, reversal to -128 RPM, power loss, 16/128 RPM restart, and disconnection. The survival LAN interaction refused one chain, then consumed three of sixteen for the reciprocal connection; the guest observed both endpoints at 128 RPM.
- `tools/test-chain-conveyor-branch.py --lan`: matched 70 Java world ticks and 57 package states with host and guest loading addressed packages onto separate branches.
- `tools/test-chain-conveyor-adjacent.py --blocked --visual --lan`: matched 18 Java ticks; a full barrel blocked export at tick 37, then accepted cargo at tick 48. The guest saw the warning appear and clear.
- `tools/test-chain-conveyor-rider.py --lan --dismount sneak`: a guest boarded a moving span, traveled, and dismounted by sneaking.
- `tools/test-chain-conveyor-idle-reopen.py`: reciprocal links survived idle save/reopen with no cargo; adding a motor after reopening restarted both endpoints at 128 RPM.
- `tools/test-chain-conveyor-packages.py --scenario straight --reopen-at 27`: matched 80 world ticks and 100 package states through an in-flight save/reopen. `tools/test-chain-conveyor-restart.py` also matched the straight and rising/reversal saved states and 15 post-restart Java package states apiece. The rising restart comparison begins at Java tick 0 because Horizon must tick once to publish the changed motor RPM; the Java tick -1 sample is pre-tick.

These cases cover the gameplay baseline only. Full Java player travel, latency, complex route permutations, pixel-level presentation and animation timing remain open follow-ups.

Elapsed time: no new Java capture; environment provisioning and diagnosis about 15 minutes; restart-fixture repair and evidence updates about 25 minutes; initial isolated build 18m 08s, rebased incremental builds 7m 53s and 3m 20s; production-logic replay 1.5s; headless integration runs about 15 minutes across the builds. The wall-clock estimates exclude wait time between work sessions.

### Frogport inventory

Right-click opens the 18 package slots with the original Frogport
and player inventory artwork. The [Frogport inventory replay](tools/test-frogport-menu.py)
takes a package from the last slot, confirms the slot rejects stone,
puts the package back, and verifies it remains when the menu reopens.
It passes with a standalone player and a LAN guest.

The [Frogport settings replay](tools/test-frogport-menu.py) follows
[seven original server observations](fixtures/frogport-settings-java.csv)
captured with the [Java GameTest patch](tools/java-frogport-settings.patch)
on top of the Chain Conveyor fixture. The offscreen standalone
player and LAN guest each edit the address when unlinked, verify that
Enter only unfocuses the field, and save on Confirm or Escape. Linked
ports expose the send-only and receive choices. The trace checks
the saved values at the corresponding actions. The game rejects the
old address and catches the newly addressed package after the change.
The final address and receive mode survive a complete Horizon
restart in both cases. The original server capture agrees across
two independent Java runs.

The [manual Frogport replay](tools/test-frogport-open.py) checks
opening and closing ticks and the rendered lid and tongue on two
muted offscreen LAN clients. The lid takes three ticks to open
and stays open until the last viewer leaves. The Rust animation
matches [48 Java interpolation observations](fixtures/frogport-manual-open-java.csv),
including reopening during closure. Both LAN clients matched the
observed head and tongue transforms. Opening queues a cue for the
viewer. Closing queues a cue when the lid reaches zero, with six
ticks of delay at 13 blocks and no cue at 21.

The [package effects replay](tools/test-frogport-package-effects.py)
matches the Java catch start on tick 24 and deposit start on tick 37
with a standalone observer and nearby and distant LAN observers.
All observers queue the opening cue. Nearby listeners also queue
the catch or deposit cue. A catch submits five rope particles even
when the listener is outside the sound range. The seeded Rust
particle positions match the [Java effects capture](fixtures/frogport-package-effects-java.csv).
The live clients verify cue order and particle requests while muted.

With Engineer's Goggles held, the first use decorates the Frogport
and leaves the held stack at one. The
[Java headless capture](fixtures/frogport-goggles-java.csv) records
the original saved decoration and held count. A standalone player
and LAN guest each see the decorated head render. The next use
opens the inventory, and the decoration survives a world restart.

The [pre-catch replay](tools/test-frogport-anticipation.py) checks
solo and LAN clients on a wheel loop and a rising span. The loop
sends on ticks 20 through 23 and catches on 24. The span sends on
ticks 3 through 6 and catches on 7. Both match the
[Java requests](fixtures/frogport-anticipation-java.csv), including
[all 19 span custody samples](fixtures/frogport-anticipation-span-custody-java.csv).
The offscreen lid moved before the catch in both paths. Rust
matches all [76 Java pose samples](fixtures/frogport-anticipation-pose-java.csv),
including repeated requests, a completed animation, and a reset.

The [held Clipboard replay](tools/test-frogport-menu.py) crafts
the original recipe and follows
[six Java address-copy observations](fixtures/frogport-clipboard-java.json)
in solo and over LAN. The Frogport ignores blank and duplicate
addresses, writes to the first page with space, and starts a new
page when all pages are full. The saved item data and the copy
received by each client match Java. The offscreen renderer
switches from the original empty sprite to the written sprite
after the first copy.

The [Clipboard block replay](tools/test-clipboard-placement.py)
matches all [six Java placements](fixtures/clipboard-placement-java.json)
in solo and with a LAN guest. It checks floor, ceiling, and four walls
for facing, written state, the outline plane actually hit by the player,
item consumption, and exact components on the block and in the recovered
item. One survival attack recovers the Clipboard in the same frozen
simulation tick. Sneaking and using a written wall Clipboard also
recovers it with the original components in both modes. The exact build
was `native-9f42064-25e2bbd52fbc`. The held recipe and all six Frogport
address-copy cases passed on that same build and pack in both modes.

The [support replay](fixtures/clipboard-support-java.json) matches
four additional floor cases in solo and over LAN. Dry and waterlogged
Clipboards leave air and source water respectively when the player
picks them up or when their support disappears. Pickup returns the
item and breaking the support leaves the selected slot empty. Both
clients see the Java replacement at tick five. The floor collision
box in the pack also matches the original Java collision query.
To recapture the support reference, apply
[the support probe](tools/java-clipboard-support.patch) after the
Chain Conveyor trace and [Clipboard placement probe](tools/java-clipboard-placement.patch).
Run the headless Java GameTest server and collect the
`CREATE_CLIPBOARD_SUPPORT` and `CREATE_CLIPBOARD_SUPPORT_TICK` rows.
Two Java runs produced identical rows.

The [held Clipboard editor replay](tools/test-clipboard-editor.py)
matches [Java item-use and edit-packet snapshots](fixtures/clipboard-editor-java.json)
in solo and with a LAN guest on `native-9f42064-00641631a47a`. Opening writes
the editing component. Closing without text removes it. Two typed pages
retain their exact text, checked state, and last viewed page after closing
and reopening. Using the held item against Stone opens it without placing
it. The original Clipboard background rendered offscreen in both clients.
The Java headless probe invokes the real item use and save packet with a
known two-page payload. Horizon's replay enters those contents through its
editor. Two runs of [the Java editor probe](tools/java-clipboard-editor.patch)
produced the same four held and two placed snapshots. Apply it after the
support probe to recapture those rows.

The placed Clipboard replay in the same script matches the Java
block and item snapshots for save, reopen, and clear on
`native-9f42064-df85197bbfaa`. The host and guest see the written flag
change on the same frozen simulation tick. A solo world restart
preserves both pages, the checked entry, and the remembered page.
Erasing both pages removes the saved component and restores the blank
block. The selected inventory slot stays empty throughout the placed
edit replay.

The [Clipboard copy replay](tools/test-clipboard-copy.py) matches
[the Java block click and settings snapshots](fixtures/clipboard-copy-java.json)
in solo and LAN on `native-9f42064-ca07efeafec7`. Copying a placed
board preserves the recipient's existing duplicate entry and read-only
flag, transfers the new entry and its checkmark, and leaves the source
item icon and quantity on the source board. The Java diode copy
quantizes a 71-tick inverted Pulse Extender to row 1 and value 3.
Pasting applies 60 ticks and inversion to the Pulse Repeater on the
same simulation tick. The exact copy build also passed the 270 original
diode pulse rows in LAN and the held-editor, placed-editor, six-face
placement and sneak pickup regressions. Java repeats were identical. Apply
[the copy probe](tools/java-clipboard-copy.patch) after the editor
probe to recapture the copy rows.

The [live Clipboard replay](tools/test-clipboard-live.py) matches
[three original update tags](fixtures/clipboard-live-java.json)
on `native-9f42064-0b2a54b294a4` with a real LAN host and guest.
The host writes while both editors are open, the guest receives and
checks that entry, and the host receives the check and clears the note.
The authoritative components and written flag match Java on relative
ticks 0, 1, and 2. The draft update leaves the originating player's
caret in place. The source [Java packet probe](tools/java-clipboard-live.patch)
uses two authors and the original server packet and block update tag.
The held, placed, restart, and copy replays also passed on this build.

The [Clipboard layout replay](tools/test-clipboard-editor.py) exercises
the editor's Java source limits on `native-9f42064-20625966006a`.
Notes wrap using the game font, and the 185-pixel height budget replaces
the temporary 12-entry limit. The inputs admit 15 short notes, keep the
last note active when another row would overflow, save Shift+Enter as
an explicit newline, and move the next checkbox below the wrapped note.
These cases passed in solo and over LAN. The actual Java screen was
outside the layout comparison.

The [Clipboard controls replay](tools/test-clipboard-editor.py)
passes in solo and LAN on `native-9f42064-685c67cee6b3`. The rendered
toolbar uses the original Create Check and Close artwork and vanilla
page arrows. The replay verifies those click targets and line-relative
Home, End, Up, Down, and Delete through actual input. The check and
uncheck controls dispatch the original sound events within Java's
pitch ranges. The sound files in the pack are byte-identical to the
originals. Playback was muted, and the Java renderer was outside
the comparison.

[Redstone Link Clipboard transfer](fixtures/clipboard-link-java.json)
also matches Java on this build in solo and LAN. On the same simulation
tick, the first slot copies a custom-named red dye and the second slot
clears. Java's [original interaction probe](tools/java-clipboard-link.patch)
produced identical snapshots in two headless runs. The exact build
also matches all 83 [original Redstone Link signal ticks](tools/test-redstone-link.py)
and passes the live Clipboard, wrapping and brass-diode copy replays.

APP-2032's bounded Redstone Link baseline reuses that trace for ordered
frequencies, analog strengths, independent channel separation, mismatch and
reconnection, source removal, and the downstream lamp. Its survival setup
check verifies placement, receiver toggling, both frequency slots and sample
retention. Existing LAN coverage verifies that a guest can configure a
receiver and observe host power; the handheld-controller binding check covers
the supported held-device path. The new `--persistence` mode saves and reopens
the same world with the rig active and idle, checking the channel bindings and
the sender/receiver output state. Run it with the normal
`tools/test-redstone-link.py` client, control and resource arguments. Range
edge cases, overlapping network combinations and the remaining facings remain
outside this finite pass. Full 1:1 stays Open.

The [Clipboard selection replay](tools/test-clipboard-editor.py)
passes in solo and LAN on `native-9f42064-7a700098bbf4`. Double-click
selects a word without its following space, and dragging selects text
for cut and paste. Both actions are checked against the saved entries.
Normal windows use Horizon's system clipboard. The muted offscreen
replay uses the in-memory clipboard. The original toolbar tooltip is
visible in the offscreen capture.

[Smart Chute Clipboard transfer](fixtures/clipboard-chute-java.json)
matches six original snapshots on the same build in solo and LAN.
The copy and paste apply an exact amount of seven to a quartz filter.
A later paste changes the amount mode to up to four while preserving
the old quartz filter when the player lacks a spare List Filter.
Providing one installs and consumes it. Copying with the amount hidden
omits the amount and mode fields. The [Java probe](tools/java-clipboard-chute.patch)
can be applied after the Link probe. The same build passed all 81
wheat-milling ticks and the live and caret editor regressions.

[Brass Funnel Clipboard transfer](fixtures/clipboard-funnel-java.json)
matches all six Java cases in solo and LAN on `native-9f42064-6efb430b7db0`.
Every paste applies the quartz filter. Plain extracting funnels,
mounted pushing funnels, and mounted pulling funnels over a belt transfer
the exact amount when both sides expose it. Plain inserting funnels
and mounted pulling funnels over a depot leave the target amount as it
was. The [Java probe](tools/java-clipboard-funnel.patch) produced identical
snapshots in two headless runs with all interactions at GameTest tick
seven. Run the [Horizon replay](tools/test-clipboard-copy.py) with
`--funnel`. The exact build also passed the LAN Smart Chute transfer
and all 30 original Funnel support changes in LAN.

The [Clipboard lifecycle replay](tools/test-clipboard-lifecycle.py) passed in
solo and LAN. A Clipboard carrying a Redstone Link payload leaves a Smart
Chute's filter, amount, and mode intact, and the player's held Clipboard
retains its exact component. At the pinned Java revision,
`ClipboardValueSettingsHandler` consumes this attack and passes an empty
compound to `FilteringBehaviour`. With no filter, row, or value in that
compound, the paste changes no settings.

After saving and reopening the world, both the held and placed Clipboards
retain the Java two-page text, checkmarks, and remembered page. The held
Clipboard also retains the copied Link payload, and the first target Link
retains the pasted frequencies. In the LAN replay, the same guest rejoins,
pastes into a second Link, and opens the placed Clipboard to check the
existing entry on its remembered page. The host verifies both changes.
The test checks saved gameplay state and guest convergence after completed
edits. Exact Java world reload and packet timing remain unverified.

Run `tools/test-parity.py` with `--check 'clipboard-lifecycle*'`. Both checks,
the three-tick live share replay, and the six existing Link, Smart Chute,
and Brass Funnel copy replays passed on `native-9f42064-6ce68a31b125` from
main commit `43b2eb0` and pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The subsequent Clipboard dispatch change adds Rotation Speed Controller
support, which was outside these replays.

Additional machine settings families, desktop clipboard integration
verification, and pixel parity remain open. The interaction checks
compare simulation state around the input actions. Packet latency was
outside the comparison.

## Stock Link

The [Stock Link replay](tools/test-stock-link.py) matched all
[24 Java snapshots](fixtures/stock-link-java.csv) across ticks 2–5 in
solo and LAN on build `native-9f42064-e197fff90498`. Survival placement
consumes the item and matches the floor, ceiling, and four wall states,
including waterlogging. The link ignores power from its attachment side,
reacts to external redstone on the same tick, and remains in place when
the attached block is removed. The muted client rays hit the original
outline planes. The earlier Packager fixture also passed all 67 Java
state and wire samples with LAN rendering on the same binary and pack.

The pack includes the original Stock Link model variants and item model.
The [survival crafting replay](fixtures/stock-link-crafting-java.csv)
also produced one Stock Link from the original Transmitter and Item
Vault with an empty grid afterward.

The [Packager linkage replay](fixtures/stock-link-packager-java.csv)
matched 26 consecutive Java ticks in headless solo and LAN on
`native-9f42064-048063273470`. It compares the Packager's linked and powered
states, the link's signal strength, the storage count, and whether a
package is held. The linked Packager keeps all 12 ingots when pulsed,
remains physically linked at strength 15, and ships the 12 ingots on
tick 13, the first periodic check after removing the link. The existing
Packager replay still matches 67 state and wire samples with LAN
rendering. The six-face Stock Link replay also passed in LAN.

[Stock Link tuning](fixtures/stock-link-tuning-java.json) matches four
consecutive Java interaction ticks in solo and LAN on `native-9f42064-4186989480f5`.
A fresh link records the placing player's UUID. Right-clicking it with a
held link copies the frequency without consuming the held item. Placing
the tuned copy preserves that frequency and records its owner. Air use
and the original one-item crafting recipe each clear the held item's
frequency. The replay checks the original action-bar messages and
submitted block entity item data on the acting client and host. Muted
offscreen captures show glint on the tuned item only.

The [typed item patch](patches/horizon-stock-link-typed-item.patch) sends
the original `create:packager_link` component ID in the item packet.
Horizon continues to identify the in-world block entity by its block ID.

The [network inventory and addressed order](fixtures/stock-link-network-java.csv)
trace records Java's visible stock and shipment after excluding duplicate,
isolated and unrelated inventories. The Horizon Requester exercises the
same stock thresholds and verifies the eligible Barrel's shipment.
The direct stock-summary values and cache timing remain open.

The Requester replay also saves and reopens the idle, populated network in
solo before checking its Java-derived 18-item rejection threshold. It then
removes and restores a second link to the same Barrel, confirming the restored
link does not double-count that inventory. A second solo reopen preserves the
reconnected link and its frequency; a subsequent accepted 12-item order empties
the eligible Barrel. The [priority capture](fixtures/stock-link-priority-java.csv)
proves one distinct-inventory source selection sample: with link powers 1 and
7, Java shipped four requested ingots from the lower-power source and three
from the higher-power source, leaving 0 and 6. The Horizon Requester replay
compares that exact per-inventory split in solo and LAN. This is a sampled
interaction, not a global ordering guarantee: Java randomly chooses among
links sharing an inventory, and the network manager groups distinct
inventories through a HashMap. The existing LAN replay compares Requester
states and shipment results between host and guest. The host-only
reopen/reconnect checks are not guest observations, and Java packet-arrival
timing is not claimed.

The priority sample used Java Create `ac0c444d9828da3453ae8cc65338e8de063286fb`
(Create 6.0.10, Minecraft 1.21.1, NeoForge 21.1.219) on JDK 21.0.13.1. The
[capture patch](tools/java-stock-link-priority.patch) SHA-256 is
`06bbd5656bc85450469b0eb507bbedac34be581f4c182ec9db2a0d99bb770575`. Apply
it to a disposable checkout of that pin with
`git apply --unidiff-zero tools/java-stock-link-priority.patch`; the patch was
checked against a clean checkout. The
disposable GameTest passed 1/1 and recorded tick 30 in
`.local/stock-priority-java-tick30.log`. Horizon build
`native-9f42064-e0a9d28b20c7` and pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7` passed
the solo and LAN Requester replays plus the six placement, Packager, and tuning
checks on that same build. The Requester command was
`python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-e0a9d28b20c7/horizon-ctl .local/patched-launcher/versions/native-9f42064-e0a9d28b20c7/horizon-client '/Users/andrewholt/Library/Application Support/horizon-launcher/versions/nightly-2026-11-13-9f42064/.local/horizon-client/26.3' --jobs 1 --check redstone-requester --check redstone-requester-lan`.
The six neighboring checks were `stock-link-placement`,
`stock-link-placement-lan`, `stock-link-packager`,
`stock-link-packager-lan`, `stock-link-tuning`, and
`stock-link-tuning-lan`. Build elapsed 19m37s, warmed Java capture 47s, and
the final Requester pair about 2m; setup, coding, and debugging time were not
measured separately. Detailed Horizon logs are under `.local/parity/`.

## Redstone Requester

The [Requester replay](tools/test-redstone-requester.py) matches eight
consecutive [Java ticks](fixtures/stock-link-requester-java.csv) in solo
and LAN on `native-9f42064-515d72d731ad`. With six ingots in stock, the Requester
rejects an order for eight in full-order mode and dispatches six to
Smelting in partial-order mode. Empty orders and falling edges leave the
indicator off. A second order queues behind the first parcel and drives
a real comparator from 15 to 0. A host in solo and a guest over LAN can
pick up the first parcel with its original order component, then the
queued parcel begins animating on the following tick. The final LAN host
ran headlessly and the guest used muted offscreen mouse input for pickup.

The same binary and pack passed the [survival recipe](fixtures/stock-link-requester-crafting-java.csv),
all 67 Packager regression samples in LAN and the four Stock Link tuning
samples in LAN. The stock dispatch checks cover Barrels and ordinary
items. The dispatch fixture starts with its order and address set
through block entity data.

The [in-game menu replay](tools/test-redstone-requester-menu.py) matched
all four [Java configuration snapshots](fixtures/stock-link-requester-menu-java.csv)
on `native-9f42064-9fb64d078cbd` in solo and with a LAN guest. The replay
uses mouse and keyboard input to replace and clear slots, edit quantities,
set the address and toggle partial ordering. All five sample ingots
remain in the player's inventory. It inspects the rendered ghost slots
in muted offscreen captures.

The same replay matches both [Java tuning snapshots](fixtures/stock-link-requester-tuning-java.csv)
and verifies the full player workflow in both modes. The actor tunes an
untuned Requester on a Stock Link, places it, enters an order for three
Copper Ingots addressed to Warehouse and pulses the Requester. The tuned
network ships all three and leaves the fourth ingot in stock. The same
candidate passed the LAN Requester dispatch, Stock Link tuning and
Package Filter saving regressions. The stock summary UI, address
suggestions, advanced crafting orders, multi-link tie cases and order
effects remain open.

### APP-2024 Redstone Requester gameplay baseline

The finite acceptance cases reuse the pinned Java references and add a
pending-queue reopen check. Java source review at
`ac0c444d9828da3453ae8cc65338e8de063286fb` covered
`RedstoneRequesterBlock` placement/neighbor callbacks and
`RedstoneRequesterBlockEntity` rising-edge, inventory-check, persistence, and
menu configuration rules. The existing eight-sample Java trace at ticks 3–10
checks powered state, success output, comparator, stock, packaged contents,
address and animation. In solo and LAN, full-order mode rejects eight when six
are available; partial mode sends the six available ingots. Empty orders and
falling edges do not dispatch. A second rising edge queues a new parcel while
the first is held. The Java menu and tuning references cover guest edits to
order quantities, address and partial-order mode, plus tuning and placing a
Requester with an order.

The new [pending-reopen mode](tools/test-redstone-requester.py) builds a linked
Barrel/Packager/Requester, ships three of six ingots, drops the signal, then
raises it with a two-ingot order while the first parcel is held. It cold
reopens with the Requester still powered and verifies the remaining stock is
one, the first parcel and queued order retain their contents, and no duplicate
dispatch occurs. The separate existing source-network case saves and reopens
the idle configured network and verifies linked frequencies, stock and
eligibility before successful fulfillment. This is Horizon source-aligned
gameplay persistence evidence, not an exact Java reload comparison.

On build `native-9f42064-d6dc2ad18d3f`, checks
`redstone-requester`, `redstone-requester-lan`,
`redstone-requester-persistence`, `redstone-requester-menu-lan`, and
`redstone-requester-crafting` all passed (5/5).
The pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The Java trace/menu/tuning capture patch hashes are respectively
`9444ee1d95288a0a07b27fb0b87598687631767b7719f28af66e86643b29d1cb`,
`4dd2193dad744bf951c64a0ba2e14ccd0232a00f1e998bac040e500a0e0a5619`, and
`25049db2cb0fb94c4da837b23204f8c4478bcf149c50d8364378c6c87fb00b1c`.
Run the four checks with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check redstone-requester --check redstone-requester-lan --check redstone-requester-persistence --check redstone-requester-menu-lan --check redstone-requester-crafting
```

Full 1:1 remains Open. Advanced crafting orders, address suggestions,
multi-network tie cases and request effects are follow-ups; they were not
needed to establish this bounded gameplay baseline.

## APP-2025 Stock Ticker and Stock Keeper gameplay baseline

The bounded case list reuses keeper eligibility, summary/cache timing,
addressed order, category grouping, search, and tuning/placement evidence below.
The pinned Java reference is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`; the tested Horizon client is
`native-9f42064-6ce68a31b125`, using pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

The eight registered Java replay checks passed on that client and pack:
`stock-ticker-keeper`, `stock-ticker-keeper-lan`, `stock-ticker-summary`,
`stock-ticker-summary-lan`, `stock-ticker-order`, `stock-ticker-order-lan`,
`stock-ticker-categories`, and `stock-ticker-categories-lan`. They cover nine
keeper cases; 24 summary samples and both cache lifetimes; search hide/restore;
six addressed-order samples, including a nine-item request with four available;
and the completed/reordered category groups at ticks 4 and 5. The order replay
also checks package contents/addresses, remaining Barrel stock and retained
order metadata. Packager and Stock Link prerequisites are resolved by APP-2021
and APP-2023, respectively.

The added [ownership and reopen replay](tools/test-stock-ticker-ownership.py)
passed on the same client and pack. It first cold-reopens an idle Ticker, Stock
Link and Barrel with 11 iron ingots. Two LAN guests then send separate orders
to `Guest Depot` and `Host Depot`; their player inventories remain untouched,
and the Packager holds two ingots for the first order while queuing four from
the second player's request for nine when only four remain. The package retains
the requested count of nine. Cold reopen preserves the Ticker frequency and
address, both parcels, and the partial order; the Packager animation advances
on the first stepped tick after reopening. This is gameplay persistence
evidence, not an exact Java reload-timing comparison.

Run the complete bounded replay set with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 \
  --jobs 2 --check stock-ticker-keeper --check stock-ticker-keeper-lan \
  --check stock-ticker-summary --check stock-ticker-summary-lan \
  --check stock-ticker-order --check stock-ticker-order-lan \
  --check stock-ticker-categories --check stock-ticker-categories-lan \
  --check stock-ticker-ownership-reopen
```

The category editor, player-specific hiding, multipart transmissions,
crafting orders, keeper rendering, crafting play tests, and multi-inventory
summary comparisons remain follow-ups. Full 1:1 remains Open.

## Stock Ticker

Two headless Java runs produced identical
[keeper eligibility traces](fixtures/stock-ticker-keeper-java.csv).
An occupied seat on an adjacent horizontal block works at the Ticker's
height or one block below. A heated Blaze Burner works at the Ticker's
height. Empty seats, empty burners, diagonal seats and lower placements
outside those bounds fail the keeper check.

The [Horizon replay](tools/test-stock-ticker-keeper.py) matches keeper
feedback at all nine fixture ticks on `native-9f42064-7356586d7b4e`
in solo and with a LAN guest. It boards actual pigs in Seats and
right-clicks the Ticker at each station. The fixture checks the
missing-keeper message and its absence at eligible stations. The
original model and recipes are in the pack.

The [stock summary timing trace](fixtures/stock-ticker-summary-java.csv)
matched over 24 ticks in two headless Java runs. A Barrel falls from
12 iron ingots to 3 at tick 5. The accurate summary reports 3 on tick 6.
The recent summary served to the stock request screen reports 3 on
tick 25. The trace uses a single contributing Stock Link throughout.

The [Horizon summary replay](tools/test-stock-ticker-summary.py) matched
all 24 samples for both cache lifetimes and the contributing link count
on `native-9f42064-a34d23374577`. It opens the stock screen through the
adjacent Blaze Burner at each sample. In a separate run within the
fixture, a seated pig opens the same screen, which refreshes while
open and closes after the Seat is removed. Muted offscreen captures
verify that the stock count changes and that search hides and restores
the stock row. Solo and LAN passed the same replay, including repeated
opens and closes.

The same replay matches [Java tuning and placement](fixtures/stock-ticker-tuning-java.csv)
for the typed item frequency, frequency preservation in the placed
Ticker, the normal facing, and the reversed sneaking facing.

Two Java runs agreed on the [addressed order trace](fixtures/stock-ticker-order-java.csv).
The first order ships two Iron Ingots and three Copper Ingots to
Warehouse. After the Barrel's iron stock falls from nine to four, a
second order requests nine for Smelting and queues the remaining four
behind the first package.

The [live order replay](tools/test-stock-ticker-order.py) matched all six
ticks in solo and LAN on `native-9f42064-f25b37d50376`. It selects both
items through the original stock grid, types each address, and uses
Send. The replay compares the held and queued package contents and
addresses, remaining Barrel stock and Packager animation each tick.
The second parcel retains the requested count of nine in its order
metadata. Editing the address and closing saves the address without
creating another parcel.

Two headless Java runs also reproduced the [category grouping trace](fixtures/stock-ticker-categories-java.csv).
An item matched by two filters goes into the earlier category. A partial
stock update leaves the previous display in place until the update
completes, and unmatched items go in the final group.

The [Horizon grouping replay](tools/test-stock-ticker-categories.py) matched
the completed and reordered samples at ticks 4 and 5 in solo and LAN on
`native-9f42064-058574d184cd`. It replaces the stored filters through the
fixture and keeps the stock screen open while the headings and item icons
reorder. The category editor, per-player hiding, multipart transmissions,
crafting orders, keeper rendering, crafting play tests, and multi-inventory
summary comparisons remain open.


## Postboxes

Two headless runs of the pinned Java Create version reproduced
[all 16 color defaults](fixtures/postbox-defaults-java.csv),
[eight dry and waterlogged placements](fixtures/postbox-placement-java.csv),
[five comparator inventory samples](fixtures/postbox-inventory-java.csv),
and [all 32 crafting and dye conversion outputs](fixtures/postbox-crafting-java.csv).

The [standalone Horizon replay](tools/test-postbox.py) confirms all 16
block and item IDs load. All eight placements and the five comparator
values match in solo and LAN on `native-9f42064-1dd8e27e9a29`. The same
build crafts all 32 original recipes in survival. In both play modes,
the 18-slot menu opens and closes the block, rejects Stone, accepts a
parcel, keeps it across a menu reopen, and saves the address. The
placement replay compares facing and waterlogging, and comparator
values are sampled after settling.

The APP-2029 follow-up replay used build `native-9f42064-6bdf8691aa42`
(client SHA256 `703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`),
pack SHA256 `a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`,
and that evidence build's prepared 26.3 resources. The standalone replay
passed in solo and LAN; the solo cold-reopen extension set `Warehouse` and
`Dispatch` through each box's menu, retained the package in slot 17, and
restored both boxes closed. A survival pickaxe break then exposed an item-loss
defect: both Postbox blocks dropped, but their addressed package did not. The
source fix captures package contents before the player-break callback and
drops them only when that callback reports success. The rebuild has not
completed: the available source cache failed on the advancement patch, and
reusing its newer patched tree produced duplicate tree-fertilizer definitions.
An initial compile also identified a mismatch between the checkout's Item
Hatch hook and the cached Horizon source. The fix therefore remains unverified
and removal is still an acceptance blocker. The existing offline buffer check
in `tools/test-train-postbox-target.py` does not cover ordinary player break.

Reproduce the baseline commands with the matching `horizon-ctl`, client and
26.3 resources from the build above:

```sh
python3 tools/test-postbox.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 --pack /path/to/create.hmod
python3 tools/test-postbox.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 --pack /path/to/create.hmod --lan
python3 tools/test-postbox.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 --pack /path/to/create.hmod --craft
```

Train station attachment, train delivery, exact animated flag motion and
remaining presentation checks stay open. This work used isolated worlds and
muted offscreen menu replays.


## Nozzle placement and dropped-item airflow

The [Java probe](tools/java-nozzle-trace.patch) ran twice at the pinned
Create revision. It captured six [placement directions](fixtures/nozzle-placement-java.csv),
rejection on stone and on a backwards Fan, support removal and one item
drop, the original crafting result, and seven [radial airflow impulses](fixtures/nozzle-airflow-java.csv).
The airflow cases cover push, pull, the pull dead zone, maximum reach,
positions outside the scan range, obstruction, and a stopped Fan.

The existing [Horizon replay](tools/test-nozzle.py) passed in solo and LAN on
`native-9f42064-70205eb8ade6`. All eight placements or rejections
matched Java, including applicable shape planes and the ordinary Wrench
result. Removing the support dropped one Nozzle. The original recipe was
crafted in solo survival. The seven dropped-item inputs showed no early
motion on the first five Horizon ticks and matched the forced Java
impulse at the scan tick. The guest observed item movement and removal.
The final isolated solo and LAN replays on `native-9f42064-2765e8093db7` saved
and reopened a placed Nozzle with its aligned Fan, matched all seven item
cases and push/pull zombie impulses, and verified host/guest item receipt and
removal. The LAN guest player check also verified push/pull displacement. The
player path uses synchronized Fan network speed, a six-tick acquisition
counter, Java's crouch/creative-flight exclusions, and the Nozzle visibility
ray. Because Horizon reconstructs guest velocity from client-known movement,
the server preserves the authoritative impulse by advancing the guest's
authoritative position in the same tick; this avoids duplicate client/server
impulses while keeping the correction visible to the guest. Client effects,
continuous Java airflow cadence, configurable range, saturation, and exact
presentation remain open.

## Turntable crafting, placement and mob contact

The [Turntable replay](tools/test-turntable.py) matched the original
survival recipe and all four player-yaw placements on
`native-9f42064-83f9aa22ed27`. The [Java live-pig trace](fixtures/turntable-live-java.csv)
covers drive speed, stress impact, landing, reversal and stopping.
The first Horizon candidate published the Creative Motor's reversal and
removal one tick late. The updated `native-9f42064-384de872a90c` build
publishes both changes immediately. Its authoritative speed, disconnected
side and upper speeds, stress, pig height, yaw and on-ground state
matched all 17 Java ticks in solo and in a hosted world with a guest.
The guest saw the Turntable and the same settled pig height. The
per-tick comparison measures the simulation.

The original [client probe](tools/java-turntable-player-trace.patch)
ran twice in an invisible window and produced identical rows. The
[Horizon player replay](tools/test-turntable-player.py) on
`native-9f42064-340be4107ec4` exercised standing rotation, reversal,
stopping and tangential edge pushes. It matched the Java camera formula
at each sampled rendered frame for the solo player, LAN host and LAN
guest. Eleven equal-input frame probes matched Java's view and body yaw
bit for bit. Eight edge probes matched clamping, rejection and the
applied velocity. The pig's body and head angles, guest interpolation,
and visual presentation remain open.

## Toolbox crafting, placement and storage

The headless storage replay on `native-9f42064-70205eb8ade6` matched
[eight Java placements](fixtures/toolbox-placement-java.csv) and the
[storage and comparator samples](fixtures/toolbox-storage-java.csv).
The replay checks insertion, compaction, depletion and remembered
filters. It also checks matching hopper insertion and refusal to nest
another Toolbox. The [crafting replay](tools/test-toolbox-crafting.py)
on the preceding build matched all 16 default blocks, the original brown
recipe and every vanilla dye color, including the same-color output and
portable custom components. The canonical special recipe on
`native-9f42064-88fc0bd3b17a` also passed all different-color and same-color
cases and matched Java's brown fallback for a tag-only Amethyst Shard.
The headless placed recoloring replay on `native-9f42064-e9458d7aa39c`
matched all 16 consecutive Java color changes, retaining facing, source
water, contents, the learned filter and the dye count. The solo and LAN guest
[portable replay](fixtures/toolbox-portable-java.csv) on
`native-9f42064-340be4107ec4` matched pickup on a single survival attack,
source water, absence of loose contents, and replacement with the same
inventory, filter, UUID and custom name.

The [Toolbox GUI replay](tools/test-toolbox-menu.py) on
`native-9f42064-851d9c749270` showed eight visible compartments and
matched all 11 Java state snapshots at the same world tick in solo
and as a LAN guest. The checks cover merges through hidden slots,
incompatible cursor items, half and full withdrawals, remembered
filters and clearing, and shift-click in both directions. The
Deposit All button matched the [Java packet fixture](fixtures/toolbox-menu-deposit-java.csv)
through a real click in solo and LAN on `native-9f42064-02594efd9424`
with the frozen label-probe pack. It filled matching compartments while
retaining overflow and unfiltered items. The final Deposit All replay on
`native-9f42064-0e486313d59d` with `create-automation-and-gear.hmod`
verified the rendered totals of 256 and 9 in solo and LAN. The
[radial replay](tools/test-toolbox-link.py) matched seven Java samples for
linking, restocking, surplus return, leaving and reentering range, and
unlinking. The LAN replay also matched when the guest quit after linking
and rejoined from a fresh client. On `native-9f42064-a0b43e90b1e8` with
the same pack, clicking Confirm returned the live cursor stack on the
same tick in solo and LAN after all 11 menu snapshots matched. Muted
offscreen LAN captures showed the selected linked-slot marker and near,
far and unlinked states. The unselected marker and range boundary need coverage.

The [Toolbox world animation replay](tools/test-toolbox-animation.py) on
`native-9f42064-488a066f200f` with
`create-toolbox-animation-and-copper-ctm.hmod` used a muted host and
guest. Both clients matched the first five Java opening ticks and the
first three closing lid ticks. They held the lid open when the viewer
count went from two to one and rendered the east-facing red lid and two
drawers. The four sound events matched order, timing, gain and pitch
range. The isolated animation math matches 19 Java samples at
partial ticks 0, 0.5 and 1. The GUI preview, more orientations and audible
playback remain open. On `native-9f42064-1d1612ab9153` with
`create-toolbox-animation-and-copper-ctm.hmod`, the [two-player pickup replay](tools/test-toolbox-multi-pickup.py)
returned both linked hotbar stacks before packing. The packed count
was 192 whether the host or guest picked it up. Solo and LAN link
replays also passed. On the scoped `native-9f42064-0cdf90d69773` build,
the [pinned Java oracle](fixtures/toolbox-multi-pickup-java.csv)
matched for distinct compartments. The same-compartment Java action
throws during link removal. Horizon deliberately completes the
pickup and returns both stacks.

### APP-2083 Toolbox gameplay baseline — November 19, 2026

The bounded replay batch passed 15/15 checks on the archived
`2026-11-19-pre-mechanical-piston-b2405826c686` Horizon 26.3 client
(client SHA-256
`63d4babf8091fe41f7712bc92d85b7467beecc4721dc54e0dfc50da7a5c97887`)
with the Create content pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The Horizon source pin is `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`;
Java is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`.

The batch selected `toolbox-storage`, `toolbox-portable`, `toolbox-menu`,
`toolbox-menu-lan`, `toolbox-deposit-lan`, `toolbox-confirm-lan`,
`toolbox-link`, `toolbox-link-lan`, `toolbox-link-lan-reconnect`,
`toolbox-pickup-linked-host`, `toolbox-pickup-linked-guest`,
`toolbox-placed-dye`, `toolbox-crafting`, `toolbox-tagged-dye` and
`toolbox-reopen`. It covers all 16 placed colors, representative and tagged
survival dye crafts, storage and GUI actions, Java-referenced link/refill and
range exit/reentry samples, reconnect, both LAN pickup directions, and player
binding plus compartment state across a cold world reopen. The reopen check
verified the player's saved link sidecar and filter, then refilled a 10-item
hotbar stack to 32 while the compartment fell from 32 to 10. This establishes
Horizon save/reopen behavior, not exact Java reload parity. The exact range
threshold, unselected HUD markers, radial visuals, GUI preview, broader
orientations and audible playback remain follow-ups.

Command (with the archived client paths substituted):

```sh
python3 tools/test-parity.py BUILD/horizon-ctl BUILD/horizon-client BUILD/.local/horizon-client/26.3 --jobs 2 --check toolbox-storage --check toolbox-portable --check toolbox-menu --check toolbox-menu-lan --check toolbox-deposit-lan --check toolbox-confirm-lan --check toolbox-link --check toolbox-link-lan --check toolbox-link-lan-reconnect --check toolbox-pickup-linked-host --check toolbox-pickup-linked-guest --check toolbox-placed-dye --check toolbox-crafting --check toolbox-tagged-dye --check toolbox-reopen
```


## Train Trapdoor and Framed Glass Trapdoor

Two runs of the [Java probe](tools/java-train-trapdoors-trace.patch) matched
on defaults, placement, open and powered transitions, waterlogging and
crafting inputs. The [Horizon replay](tools/test-train-trapdoors.py) on
`native-9f42064-384de872a90c` matched all 12 placement states and both
10-state transition sequences, in solo and LAN. Each material's original
recipe worked with all 11 wooden trapdoors in both crafting slot orders,
for 44 survival crafting cases. The muted sound replay on
`native-9f42064-340be4107ec4` matched the [Java event sequence](fixtures/train-trapdoors-sounds-java.csv)
for each variant in solo and on the LAN guest, including seven iron
open or close events and two silent steps. Connected face culling,
Framed Glass connected textures and use on other contraption types
remain open; mounted-train interactions are covered below.

### APP-2064 gameplay baseline

Completed November 21, 2026.

The finite baseline passed on Horizon `native-9f42064-6bdf8691aa42` (pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, Minecraft 26.3; client SHA-256
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`) with
Create pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
The Java reference remains Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`.

The five checks were `train-trapdoors`, `train-trapdoors-lan`,
`train-trapdoors-reopen`, `train-trapdoors-sound`, and
`train-trapdoors-sound-lan`. The existing Java comparisons covered 12
placement states, ten ordered state snapshots per block, and 44 survival
crafts across 11 wooden trapdoors and both ingredient orders. Host/guest
placements and state transitions converged; each variant's seven iron sound
events and two silent transitions matched. The placement replay also removed
the clicked floor block and verified each trapdoor stayed in place, matching
the pinned `TrainTrapdoorBlock` inheritance of vanilla `TrapDoorBlock`.
The new cold reopen replay saved a closed Train Trapdoor and open Framed Glass
Trapdoor, verified their states after relaunch, then toggled both by hand.
Both content definitions use the vanilla oak trapdoor template for standard
state geometry and collision behavior.

Run the five checks with the corresponding pinned build and prepared resources:

```sh
python3 tools/test-parity.py BUILD/horizon-ctl BUILD/horizon-client BUILD/.local/horizon-client/26.3 --jobs 1 --check train-trapdoors --check train-trapdoors-lan --check train-trapdoors-reopen --check train-trapdoors-sound --check train-trapdoors-sound-lan
```

Exact connected face culling, Framed Glass connected textures, other states
and orientations, and additional collision layouts remain follow-ups.


## Experience Block and Experience Nugget

The [original Java probe](tools/java-experience-trace.patch) captured
[block properties](fixtures/experience-block-java.csv), its
[harvest rules](fixtures/experience-harvest-java.csv), both survival
recipes and 12 standing or crouching uses across stack sizes.
The headless [Horizon replay](tools/test-experience.py) on
`native-9f42064-72c3825b41bc` matched the two recipes, ordinary placement
and light level 15. The authority matched all 12 use cases and 30 signed
orbs for each tested context, including solo, LAN host and LAN guest.
This comparison measures the item counts, signed orb values, spawn
position and size of the random launch offset. Each client received the
negative −2 and −1 orb values from the other player's use. Independently,
Java's seeded launch directions reproduce to 1.5e−12. Live worlds
draw their own random directions. Orb collection timing and ambient block
particles remain open; scoped tool-dependent harvesting is covered below.

### APP-2075 Experience Block harvest and persistence — November 21, 2026

Pinned Java `ac0c444d9828da3453ae8cc65338e8de063286fb` supplies the existing
`fixtures/experience-harvest-java.csv` cases. The new
[`experience-harvest` replay](tools/test-experience.py) mines the placed block
with empty hand, wooden, stone and iron pickaxes, and an iron axe. All five
reported drops matched Java: the three pickaxes returned one Experience Block;
empty hand and the axe returned none. A failed intermediate test run exposed
that the replay counted a prior case's dropped item in the next case; each
case now clears ground items before mining, and the final isolated replay
passed.

The existing craft-and-place replay now reopens its saved world and confirms
the Experience Block and light level 15 remain. The solo and LAN nugget checks
also passed, including the existing 12 use cases and initial signed-orb values
and positions for host and guest. In the lifecycle replay, a LAN guest collected
3 XP from a thrown Nugget; after host save/reopen and guest rejoin, the same XP
total and five Nuggets remained, with no increase or loss. This is the finite
APP-2075 gameplay pass; it does not claim exact orb collection timing, ambient
particle/audio parity, or Full 1:1.

Build/pack used for these replays: Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`,
client `native-9f42064-6ce68a31b125`, Create pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Commands, selecting each registered check from the worktree root:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check experience-nugget --check experience-nugget-lan --check experience-crafting-and-placement --check experience-harvest --check experience-multiplayer-lifecycle
```

Final outcomes: 5/5 registered checks passed. The raw harness logs are in the
worktree's ignored `.local/parity/` directory.

## Item Hatch

Two runs of the [original Item Hatch probe](tools/java-item-hatch-trace.patch)
produced the same direction and shape rows, eight deposit states, and
original craft and close timing. [Horizon replay](tools/test-item-hatch.py)
on `native-9f42064-72c3825b41bc` matched placement, geometric bounds,
selected and sneak deposits, capacity, filter acceptance/rejection,
and open state through tick 9 with closure at tick 10, in solo and
LAN. The original survival recipe passed solo. On
`native-9f42064-02594efd9424`, direct clicks matched Java ordinary
filter set and clear, preserved the held sample's stack size, and kept
the filter intact on Wrench use. Solo and LAN passes also repeated
the seeded placement, deposit and close fixtures. Those historical runs used
Horizon sided insertion; the APP-2017 pass below identified a consequential
unsided-inventory mismatch. Unusual inventory handlers, visuals and exact
sound playback remain open.

### APP-2017 unsided insertion and lifecycle pass

Pinned Java `ItemHatchBlock.useItemOn` queries `ItemHandler.BLOCK` with a
`null` side. The [additional actual Java capture](tools/java-item-hatch-gameplay.patch)
on Create `ac0c444d9828da3453ae8cc65338e8de063286fb` recorded
`SUCCESS,0,9,minecraft:raw_iron,true`: a survival player holding nine Raw Iron
items deposits all nine into Furnace input slot 0 through a horizontal Hatch,
leaving the hand empty and opening the Hatch. The
[one-row reference](fixtures/item-hatch-unsided-java.csv) and
[capture metadata](fixtures/item-hatch-unsided-java.metadata.json) retain this
observation. The same capture exactly reproduced the five original fixture
CSVs (placement, eight deposits, timing, ordinary filter interactions and
crafting) unchanged. The isolated headless Java capture completed successfully
in 2m37s with JDK 21 and a private Gradle cache; the shared checkout/cache were
not modified.

The pre-fix Horizon replay on `native-9f42064-6ce68a31b125` reproduced a
mismatch: all nine Raw Iron remained held, the Furnace stayed empty and the
Hatch stayed closed. Client SHA-256:
`bdbafe5289f2c05ef76009c17070e0320a7c606e042dd5202b142e0e6d123fc9`;
control SHA-256:
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`;
pack SHA-256:
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The build's recorded Horizon pin is
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. The failed command was:

```sh
python3 tools/test-item-hatch.py /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-6ce68a31b125/horizon-ctl /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-6ce68a31b125/horizon-client /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-6ce68a31b125/.local/horizon-client/26.3 --unsided-only
```

`item-hatch-boundaries` and `item-hatch-boundaries-lan` add actual-player
transfers through all four horizontal attachments and the Java Furnace case.
`item-hatch-lifecycle` adds idle and post-transfer save/reopen with a waterlogged
Hatch, retained ordinary filter and Barrel contents, subsequent lid closure and
another manual transfer. A Hatch's operation is instantaneous; its meaningful
active save state is the ten-tick lid window after the transfer. Cold-launch
ticks may finish that window before the harness freezes the reopened world,
so this check establishes continued usability and retained state rather than
exact Java reload timing.

The narrow fix adds `native_insert_item_unsided` in the Horizon native item
helpers and uses it only for Item Hatch deposits. It preserves destination
item rules, stack limits, existing item merges, and remaining held items; all
other native consumers keep their sided API.

The final build `native-9f42064-6bdf8691aa42` was built from APP-2017 base
`781c0ef` and uses Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`.
Its client SHA-256 is
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe`;
`horizon-ctl` SHA-256 is
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`; the
prepared pack SHA-256 is
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
The main-synchronized rebuild completed in 13m12s. An earlier rebased build
`native-9f42064-2777747110f8` on `c9a9d9b` also passed all seven checks;
its logs remain preserved in `.local/parity-app-2017-c9a9d9b/`. The seven-check batch passed **7/7** on base `781c0ef`:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-6bdf8691aa42/horizon-ctl .local/patched-launcher/versions/native-9f42064-6bdf8691aa42/horizon-client .local/patched-launcher/versions/native-9f42064-6bdf8691aa42/.local/horizon-client/26.3 --jobs 2 --check 'item-hatch*'
```

This reran the four existing placement/deposit/filter checks in solo and LAN,
including the original seven placements, eight deposits, ten-tick close and
survival recipe. The new boundary checks transferred through all four
horizontal attachment directions and deposited Raw Iron ×9 into Furnace
input slot 0 in solo and with a LAN guest. The lifecycle check reopened an
idle waterlogged Hatch with its paper filter and Barrel contents, reopened it
after a transfer, observed the lid close within the ten-tick window, and
completed another transfer without losing items. These checks establish
continued gameplay and retained state; cold-launch ticks prevent a claim of
exact Java reload timing. Logs are retained under `.local/parity/`.

`python3 -m py_compile tools/test-item-hatch.py tools/test-parity.py`,
`rustfmt --edition 2024 --check` on the patched `native_items.rs`, patch
applicability against the pinned Horizon source, and `git diff --check` passed.
The original pre-fix mismatch remains recorded at
`.local/item-hatch-unsided-baseline.log`; an invalid block-item placement
attempt remains labeled at
`.local/item-hatch-unsided-baseline-invalid-block-item.log`. Broader specialized
filter swaps, unusual inventory handlers, presentation and exact packet/audio
timing remain follow-ups. Full 1:1 remains Open.

## Java runtime-generated processing recipes

The [capture patch](tools/java-runtime-processing-trace.patch) recorded
the [157 actual recipes](fixtures/runtime-processing-java.json) generated
in two pinned Java runs. Both agree on every ID, ingredient, output and
duration. The pack imports those 141 Cutting and 16 Splashing definitions.
A [Horizon Mechanical Saw replay](tools/test-mechanical-saw.py) on
`native-9f42064-72c3825b41bc` matched all 96 [original Java ticks](fixtures/runtime-saw-java.csv)
for the generated Spruce Planks to Spruce Trapdoor cut. Samples include
RPM, progress, inventory and dropped outputs. The
[generated washing replay](tools/test-fan-depot.py) on
`native-9f42064-851d9c749270` matched all 175 Java ticks in each
of two lanes, Blue and Red Concrete Powder. Both covered a power
interruption and the transition to Concrete. The registry audit
covers all recipe IDs. Individual gameplay comparisons cover the
specified outputs.


## Crushed materials cooking and Create Copper Nuggets

The [Java recipe probe](tools/java-crushed-materials-and-runtime-saw-trace.patch)
looked up the six original cooking recipes for Crushed Raw Iron, Gold
and Copper. The [Horizon furnace replay](tools/test-zinc-progression.py)
on `native-9f42064-72c3825b41bc` compared progress through the same
sampled times and observed the output on tick 100 in the blast furnace
or tick 200 in the furnace.

The two [Java copper crafting recipes](fixtures/copper-nugget-crafting-java.csv)
passed on `native-9f42064-851d9c749270`. Minecraft 26.3 also has a
vanilla Copper Nugget recipe for the identical ingot slot. While the
Create recipe is loaded, the shared crafting table tries its original
result first. The neighboring Zinc cooking replay also passed all
eight inputs on this build. Washing and crushing outputs have a separate
gameplay comparison.


## Copper diving equipment

The [Java capture](tools/java-copper-backtank-trace.patch) resolves the
original Copper Backtank, Diving Helmet and Diving Boots recipes and
samples three Backtank lanes at low speed, high speed and underwater.
All three [survival recipes](fixtures/copper-diving-crafting-java.csv)
matched on `native-9f42064-02594efd9424`. The first charging replay
was one tick early when a new default-speed motor boots. The correction
in `native-9f42064-18338e7d2169` matches all 108 Java RPM, air and timer
observations, including high-speed fill, underwater inhibition, and
motor interruption and restart. Three settled redstone comparator outputs
matched. On `native-9f42064-a0b43e90b1e8` with
`create-standalone-deploying.hmod`, the [charged pickup replay](tools/test-copper-backtank-pickup.py)
matched Java in solo and with a LAN guest. Placing the named tank under water
retained its 284 air. Right-clicking it equipped it in the chest slot on the
same tick, preserved its name and charge, and restored source water. Diving
movement, wearable breathing and full presentation remain open.


## Fluid Pipe, Glass Fluid Pipe and Smart Fluid Pipe

APP-1972 covers the two basic survival recipes, Smart Fluid Pipe crafting,
and Glass Fluid Pipe acquisition by wrenching a basic pipe. The pinned
`FluidPipeBlock` and `AxisPipeBlock` callbacks define the connection and
conversion rules. A side click converts a straight pipe to glass, glass
uncases back to a basic pipe and reconnects, and both conversions keep
waterlogging and cached flow. The Glass variant returns a basic pipe when
dismantled. `SmartFluidPipeBlock` uses the Y axis for wall placement, and
`SmartFluidPipeBlockEntity` tests incoming fluid against its filter. The
filter slot accepts a replacement sample or clears with an empty hand.

The [gameplay replays](tools/test-fluid-pipe-gameplay.py) exercise those
interactions in survival and with an acting LAN guest. They check the
authoritative host state and eventual guest block-state convergence.
The solo save cases reopen a wet Glass Pipe and a configured Smart Pipe
while idle, then reopen a powered vertical line with water still moving.
The powered runs cover accepting and rejecting fluid, a full receiver, an
empty source, independent water and lava lanes, and a blocked segment
removed and reconnected while the pump remains powered. Tank contents are
measured in millibuckets and checked separately by fluid ID.

The existing [split/combine replay](tools/test-branched-pipes.py) is the
402-tick Java comparison for single-fluid branch traffic. The
[collision GameTest patch](tools/java-fluid-pipe-collision.patch) changes the
north source in the same combine template to lava and runs only that test.
Apply it to a disposable Create checkout at
`ac0c444d9828da3453ae8cc65338e8de063286fb`, then run
`./gradlew --offline --no-daemon --max-workers=2 runGameTestServer` on JDK 21.
The `CREATE_MIXED_PIPE` rows form the
[26-sample reference](fixtures/fluid-pipe-collision-java.csv).
The patch SHA-256 is
`fac5fc6cf0e6007c76f9201c3fe6f6341125fa751fcfa68fa59ef65eccb426b4`.

Both engines were sampled from tick 0 after switching the pump to combine.
The junction block, dropped basic-pipe item count, destination fluid and
amount, and three source amounts all matched at zero tolerance. The
junction became cobblestone and dropped one basic pipe on tick 15.
All three sources retained their initial fluid and the destination stayed
empty through tick 25. Horizon server commands sample authoritative block
state because the local client block view showed the change one tick later.
The player stands outside pickup range for the drop count.

The baseline at `native-9f42064-6ce68a31b125` left the junction intact
despite completed water and lava fronts and transferred 126 mB of lava.
It also left basic pipes unchanged on a side wrench, kept an empty-hand
filter click from clearing the slot, and placed a disjoint pipe beside a
tank. The original Encased Pipe static replay now supports the three-way
junction during its actual player click and removes those neighbors once
encased. The Java probe stops after the block interaction returns
`PASS_TO_DEFAULT_BLOCK_INTERACTION`, before the held casing can place next to
the pipe and cause a shape update.

The final runtime is `native-9f42064-14b1dcb81282`, built using launcher
0.2.67 and the pinned Horizon revision
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. The clean build after syncing
current `main` took 148 seconds. The client SHA-256 is
`efe122e6573776f9194188ffe7af2cb497003ef7c958764b68dffbc90fde9245`.
The pack was prepared from the pinned Java checkout with `tools/prepare.py`.
Its SHA-256 is
`6ca7517cee3017056b629d6649f837334c6d36bf5f1714a577b12bc813abe1cc`.
The focused regression run passed all 14 selected checks on this runtime and
pack, including solo and LAN pipe gameplay, collision, lifecycle, encased
transfer, branch traffic, and dependent fluid regressions.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 \
  --jobs 3 --check 'fluid-pipe-*' --check 'encased-fluid-pipe*' \
  --check branched-pipes --check open-pipes --check world-pump \
  --check pump-startup-pressure --check fluid-observer --check fluid-valve-neighbors
```

The new interaction and lifecycle cases use source-derived properties and
conservation bounds. Exact Java save/reopen and guest packet timing,
further fluid reactions, complex filter configurations, chunk boundaries,
and additional model and animation combinations remain open.

## Mechanical Pump gameplay baseline (APP-1973)

This finite pass preserves the original world-pumping, open-pipe,
split/combine and startup-pressure references. The new
[pump gameplay replay](tools/test-mechanical-pump-gameplay.py) reuses the
APP-1972 player, storage and tick helpers and the existing pinned
[crafting reference](fixtures/machine-crafting-java.csv).

At the pinned Create revision, `PumpBlock.getStateForPlacement` inherits
look/shaft preference, chooses the nearest connectable fluid neighbor on
another axis for ordinary placement, and preserves source waterlogging.
`PumpBlock.getRotatedBlockState` flips facing regardless of the clicked
face. `PumpBlockEntity.isPullingOnSide` depends on facing alone: changing
the sign of RPM does **not** reverse fluid transfer. Pressure uses absolute
RPM; a facing flip reverses the inlet and outlet. These source-derived
rules guide the added checks; they are distinct from tick-by-tick Java
runtime comparisons.

| Finite case | Evidence |
| --- | --- |
| Survival acquisition | Original shapeless Cogwheel + Fluid Pipe recipe, exact one-Pump output and no remaining inputs |
| Placement and Wrench | North view, sneaking reversal, adjacent Tank preference; two facing flips and exactly one item returned by sneaking Wrench, solo and acting LAN guest |
| RPM and direction | Both motor signs at magnitude 128 retain upward transfer; facing reversal swaps ports and transfers downward |
| Start/stop and storage | Zero RPM and zero pump pressure halt transfer; restoring drive resumes without changing the 7,000 mB total |
| Full, empty, blocked and non-water | Reuse APP-1972 `fluid-pipe-lifecycle`, including a full Tank, empty powered source, blocked/reconnected pipe and separate water/lava lanes; `honey-pipe` retains the existing non-water Java reference |
| Branch pressure | Reuse the eight exact Java `pump-startup-pressure` samples and the 402 split/combine samples |
| Persistence | Wet idle Pump retains facing; powered and stopped two-Tank setups retain fluid and resume or remain stopped after reopen |

The original runtime `native-9f42064-6bde2ea90cf2` passed the new ten-stage
source-derived lifecycle check. Its log and CSV were preserved separately
as `.local/mechanical-pump-baseline-lifecycle-unsandboxed.log` and
`.local/mechanical-pump-lifecycle-baseline-horizon.csv`. The first two
launches were invalid because sandbox restrictions prevented the control
socket from opening; their logs remain in `.local`. A survival attempt
with an extra crafted Pump in the inventory was also invalid; the fixture
now clears that item before setting up each placement case.

The valid original-runtime probe recorded north-facing placement from a
north-looking player, where Java requires south. A Wrench click on a
south-facing Pump left it facing south, where Java requires north. The
actual states are preserved in
`.local/mechanical-pump-baseline-probe-final.log`. The narrow repair adds
Pump placement to the existing fluid placement helper and adds Pump to
the Wrench's facing-flip and pickup paths.

The [placement callback probe](tools/java-mechanical-pump-placement.patch)
ran in the disposable `.local/java-pump-reference` clone at the pinned
commit with JDK 21.0.13.1. It captured three actual Java placement and
Wrench-facing pairs: ordinary south/north, sneaking north/south and Tank
preference west/east. The
[three-row reference](fixtures/mechanical-pump-placement-java.csv) is read
by both solo and LAN tests. These are exact block-state expectations from
the Java callbacks, not a Java network or save comparison. The Gradle
GameTest passed in 5 minutes 26 seconds; patch SHA-256 is
`48edd159971f5683d3f8de68bb06946f4dc5948e6fec991777da9b3abcc27d63`.
Capture metadata is in
[the reference metadata](fixtures/mechanical-pump-placement-java.metadata.json).

The final runtime `native-9f42064-1bafbe76cae9` used Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and mixins
`5a64af938ec86b00d53d16a408aabc0038fb3e57`. The rebuilt client SHA-256 is
`8f2875a3e675b18b86491f6183b51abf36213495b14f180e9b90f86dfa51356b`; the
pack SHA-256 is `6d73c6a59c48085fe929e00603f980f95337047a212ed0bb79d4f92a9bb368ac`.
The finite check list passed all eight selected checks on this build: Pump
survival placement/Wrench, acting LAN placement/Wrench, pump lifecycle,
startup pressure, original world pumping, open pipes, branched pipes, pipe
lifecycle, and honey pipe. The lifecycle samples matched both RPM signs,
absolute pressure, zero-pressure stop, restart, reopen, and reversed-facing
transfer. The updated placement/Wrench checks matched all three Java rows.
The initial sandboxed batch could not open control sockets; the successful
batch ran with the documented headless/offscreen helpers and isolated worlds.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 \
  --jobs 1 --check mechanical-pump-gameplay --check mechanical-pump-gameplay-lan \
  --check mechanical-pump-lifecycle --check pump-startup-pressure --check world-pump \
  --check open-pipes --check branched-pipes --check fluid-pipe-lifecycle --check honey-pipe
```

Syntax checks (`tools/check-source.py`) and `git diff --check` passed.

Run the bounded checks with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 \
  --jobs 2 --check 'mechanical-pump-*' --check pump-startup-pressure \
  --check world-pump --check open-pipes --check branched-pipes \
  --check fluid-pipe-lifecycle --check honey-pipe
```

LAN results establish authoritative host state and eventual guest block
convergence, not Java packet arrival timing. Reopen checks establish the
Horizon gameplay baseline, not exact Java reload parity. More network
layouts, speed/pressure cross-products, chunk boundaries, other fluids and
exact animation, sound and rendering remain open.

## Encased Fluid Pipe

The [original Java probe](tools/java-encased-fluid-pipe-trace.patch)
captured the casing, wrench, clone, geometry and pressurized transport
cases. The [Horizon transfer replay](tools/test-encased-fluid-pipe.py)
on `native-9f42064-18338e7d2169` matched five static states and
ownership cases in solo and with a LAN guest operating the pipe.
Its 103-sample transfer replay was byte-identical between Horizon roles.
Casing and uncasing preserved flow,
cleared pressure immediately and paused transport until the Java
restart ticks. Java varied which side received the spare unit when
splitting flow. The deterministic side-pair total is compared.
With the same `create-encased-pipe.hmod`, `native-9f42064-a0b43e90b1e8`
matched all 103 transport rows in each role, including the previously
differing startup pressure. The [independent startup probe](tools/test-pump-startup-pressure.py)
matched eight original Java samples across split and combine layouts.
The connected pipe pressure changes on tick 1, and the pump ports
change on tick 2. The branched split and combine, world pump and open
pipe replays also passed all 492 samples. On `native-9f42064-a0b43e90b1e8`
with `create-toolbox-animation-and-copper-ctm.hmod`, the [offscreen casing replay](tools/test-copper-casing-ctm.py)
matched all 84 faces sampled from Java’s baked quads. It checks mixed casing
neighbors, open ports, corners and occlusion on all six directions.
All 47 connected-texture tiles match the original pixels.

On `native-9f42064-1e4e2bf31423` with
`create-encased-drain-isolated.hmod`, the [drain fitting replay](tools/test-encased-pipe-drain-fitting.py)
matched all 204 Java classifications in solo and on both LAN clients.
It checks 17 neighbor types on open and closed ports in all six directions.
The 12 fitting models and sprite match Java byte for byte. In offscreen
captures the fittings appeared and disappeared as the adjacent block
changed. The existing 103-row fluid transfer fixture also passed.
Ambient occlusion, contraption-mounted fittings and Copycat material
connections remain open.

### APP-1985 focused gameplay pass

This pass retains the five Java casing/wrench/clone cases, the 103-row
transport comparisons in solo and with an acting LAN guest, the 84 casing
faces, and the 204 drain classifications above. The finite additional case
list is powered Encased → basic → Glass → Encased conversion, full receiver
and empty source limits, and representative idle and active save/reopen.
Existing LAN replays cover representative guest casing and wrench edits;
they assert host authority and eventual guest convergence, not packet timing.

The pinned `EncasedPipeBlock.onWrenched`, `AxisPipeBlock.useItemOn` and
`FluidPipeBlock.onWrenched` callbacks cache and restore flows around their
block conversions. Glass accepts Copper Casing directly, restoring its two
axis openings. `FluidTransportBehaviour.read`/`write` retain the transport
interfaces. These rules are the source basis for the new bounded
[lifecycle replay](tools/test-encased-fluid-pipe.py), which reuses the
APP-1972 tank-content, conservation and tick-step helpers. It checks a
128-RPM vertical line with an Encased segment and a Glass neighbor. The
receiver initially holds 8,000 mB and the source 7,000 mB. A stalled/full
reopen must preserve both tanks, pipe identities and openings. Clearing the
receiver starts transport; each player conversion must retain the measured
fluid immediately and then continue pumping. Active reopen must retain
casing, openings and fluid and resume transfer. Once empty, the powered
source must stay empty without increasing the receiver.

The replay records phase, authoritative world tick, pipe ID, openings,
waterlogging, source and receiver mB, and pump RPM in
`.local/encased-fluid-pipe-lifecycle-horizon.csv`, including completed
milestones before a failure. Its assertions use exact discrete state and
fluid identity/amount conservation; continued-flow bounds do not establish
exact Java transition or reload timing. The idle setup is powered but
stalled against a full receiver. Integration of this new check is pending;
no native behavior changes have been made in this pass.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 \
  --jobs 2 --window-culling --check 'encased-fluid-pipe*' --check pump-startup-pressure \
  --check copper-casing-ctm --check 'encased-pipe-drain-fitting*' \
  --check fluid-pipe-lifecycle
```

The complete bounded APP-1985 suite passed after rebasing onto current `main`
on `native-9f42064-b527cbe807b8`, built with launcher 0.2.67 and Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. Client SHA-256:
`0c44ac860625ad3e87fe947dbdee71d43dfec29299ffa66b507e7fa0e4fb8a4e`; pack
SHA-256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
`--check encased-fluid-pipe-lifecycle --check 'encased-fluid-pipe*'` passed
5/5: idle/active reopen and pumped casing transitions, solo/LAN casing state,
and all 103 Java transfer samples in both solo and LAN. Existing bounded
pump startup, casing-face, and drain-fitting checks also passed on build
`native-9f42064-d7e37b705c75` before the upstream mechanical-pump changes; the
APP-1985 final rerun targeted the rebuilt current-main code.

Exact Java save/reload, additional network layouts and chunk boundaries,
guest arrival timing, ambient occlusion, contraption-mounted fittings and
Copycat material connections remain unverified. Full 1:1 remains Open.

## Deployer item applications

On `native-9f42064-0e486313d59d`, the [in-world replay](tools/test-deployer-applications.py)
matched all 150 sampled states in solo and LAN with
`create-automation-and-gear.hmod`. It covers all four original brass and
copper casing variants, Bound Cardboard and an Andesite Casing control.
The [standalone belt replay](tools/test-standalone-deploying.py) matched
all 150 sampled states in solo with `create-standalone-deploying.hmod`.
It covers consumed planks, reusable Honeycomb Block and axes with
unchanged durability. The original 108-tick Precision Mechanism replay
also passed with that pack. Other variants and guest belt presentation
need gameplay coverage.

### APP-2089 Deployer sheep shearing

The pinned Java `DeployerHandler.activateInner` selects entities in the
clicked block and runs their normal entity and living-item callbacks. The
existing Horizon sheep interaction path handles adult/sheared eligibility,
the Java wool loot table, tool wear, the shear event, and saved sheep state.
The APP-2089 change passes the Deployer's shears through that path and
restores the actual player's held item afterward.

`tools/test-deployer-shearing.py` is registered as `deployer-shearing`. Its
bounded cases cover adult shearing during an active save/reopen, baby and
already-sheared controls, Unbreaking III, wool output, one tool-wear point,
and a LAN guest loading the shears and observing the output. Manual shearing
continues to use the original `shearing` GameTest and trace.

The new replay has not run yet. The compatible-launcher build first stopped
because the launcher-data source already included an engine patch from the
repository patch series; a build against the cached patched source then
could not resolve Horizon revision `9f42064` through GitHub or its mirror
because DNS/network access was unavailable. Treat the APP-2089 implementation
and new regression as pending runtime validation; this is not a parity-pass
claim.

## Basin materials and cooking

### Basin compacting lifecycle check

`basin-lifecycle` adds a bounded multiplayer and persistence check alongside
the four original compacting traces. A LAN guest drops nine Iron Ingots into
the Basin; the check verifies the actual guest action reached the input
inventory, preserves idle input across reopen, starts compacting, stops motor
speed mid-cycle, reopens the active world, resumes, and sends the Iron Block
through a horizontal Basin output into a chest for guest collection. This is a
source-aligned gameplay check, not an exact Java reload or packet-timing
comparison. The guest extracts from the routed chest because a Basin has no
player inventory screen; the output still originates in the Basin recipe.

The translated Java paths are `BasinBlock.updateEntityAfterFallOn` (dropped
item insertion), `BasinInventory.insertItem` (unique item slots),
`BasinRecipe.apply` (ingredient/output simulation and consumption),
`MechanicalPressBlockEntity.tryProcessInBasin`, `PressingBehaviour.tick`
(mid-cycle processing and zero-speed pause), and `BasinBlockEntity` read/write
and spout routing. The check is registered as `basin-lifecycle` in
`tools/test-parity.py`. It passed on `native-9f42064-3916961b0c42`. The case
is Horizon gameplay evidence, not an exact Java reload or packet-timing
comparison.

The same build passed the scoped Java replays:

- `basin-compacting`: four rigs, 132 sampled rows.
- `brass-mixing`: the heated brass route matched all 186 Java ticks; a
  separate 186-tick no-heat run retained its ingredients and produced no brass.
- `basin-dry-alloy`: iron and zinc alloy paths, 106 samples.
- `basin-wet-materials`: dough, three Mud inputs and grass rejection, 265 samples.

Reproduce them with the actual check names in `tools/test-parity.py`, for
example:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 --check basin-compacting --check brass-mixing --check basin-dry-alloy --check basin-wet-materials --check basin-lifecycle
```

The [material recipe replay](tools/test-material-recipes.py) on
`native-9f42064-488a066f200f` with `create-material-recipes-v2.hmod`
matched 265 samples across Dough, Mud from Dirt, Coarse Dirt and Rooted
Dirt, and Grass Block rejection. Furnace Bread and Scoria finished on
tick 200 and Smoker Bread finished on tick 100. All 609 cooking samples
matched Java. This pack adjusts the original smoker recipe to account
for the separate Horizon fast-fuel multiplier. Both dry Andesite Alloy
routes produced the correct result one tick early on this build.

On `native-9f42064-7f0b3254fd60` with the same frozen materials pack,
all 371 Basin samples match, including both dry alloy paths. Each
starts on tick 2 and produces one alloy on tick 39. The same build
matched 186 original brass ticks, 248 arm-fed brass ticks, 258
heated-fluid samples and 86 spout samples.

## Table Cloths

### APP-2030 bounded shop baseline

On Java reference `ac0c444d9828da3453ae8cc65338e8de063286fb` and Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, build
`native-9f42064-bfe421a867b6` with pack SHA-256
`314690f98e6aef8de270a6fbea6704d073cd71c071d6f79fd489e7eab75f912d`, the
[configured shop replay](tools/test-table-cloth-shop.py) issued a shopping
list from an owner-configured cloth, refused an empty-stock request, and
preserved a list across world reopen. Existing Table Cloth recipe, placement,
storage, reset and LAN checks also passed. A LAN guest issuance replay passed
once and subsequently timed out waiting for the list, so guest issuance is not
yet a stable pass. The fixture seeds cloth request/price/owner data directly;
there is no player-facing setup flow. Paid checkout, payment validation,
fulfillment and ownership transfer remain unimplemented. This is bounded
evidence only; full Java parity remains open.

The `create-tablecloth-scaffolding.hmod` pack loads all 19 block and
item IDs and 35 original recipe IDs. On `native-9f42064-7f0b3254fd60`,
the [survival recipe replay](tools/test-table-cloth-recipes.py) obtained
two White Table Cloths from wool and alloy, recolored one to red and
stonecut two of each metal cloth. A separate [placement smoke check](tools/smoke-table-cloth.py)
placed a red cloth, captured its original model and confirmed the empty
state of all variants after restart. The [survival placement replay](tools/test-table-cloth-placement.py)
on `native-9f42064-1d1612ab9153` matched adjacent placement across colors,
closest edge selection, blocked sides, item consumption and solo sneak
bypass. A LAN guest replay checked adjacent placement and blocked sides
on both clients. Connected fringe, item displays, shops and data-reset
recipes remain open.

## Metal Scaffolding

The [placement and support replay](tools/test-metal-scaffolding.py)
on `native-9f42064-1d1612ab9153` with
`create-tablecloth-scaffolding-outlines.hmod` matched all 27 [Java samples](fixtures/metal-scaffolding-java.csv)
in solo and LAN. Andesite, Brass and Copper stacked by a side click.
The Copper base waterlogged and removing the floor did not break the
scaffolding. Command-seeded unsupported blocks retained their raw
states. All three [stonecutter recipes](fixtures/metal-scaffolding-recipe-java.csv)
also passed in survival. On `native-9f42064-0cdf90d69773` with the same
pack, the [descent replay](tools/test-metal-scaffolding-descent.py)
matched 39 Java position and velocity samples across the three materials
in solo and as a LAN guest. The persistence check below also verifies ascent
and exit after reopening. Longer runs, mixed support and visual parity remain
open.

The [persistence check](tools/test-metal-scaffolding-persistence.py) saves and
reopens five-block stacks of each metal, checks all 15 block states, and
confirms the player can ascend and walk off a restored stack. It passed on
`native-9f42064-6bdf8691aa42` with pack SHA-256
`65fe01c27a564f92bb25124ca48c021cc1a3b1496a08bc98b029b8c52f4e4b84` using:

```sh
TMPDIR=/private/tmp python3 tools/test-metal-scaffolding-persistence.py \
  /path/to/native-9f42064-6bdf8691aa42/horizon-ctl \
  /path/to/native-9f42064-6bdf8691aa42/horizon-client \
  /path/to/prepared/26.3
```

This covers ordinary idle persistence and a representative post-reopen movement
interaction; it does not claim Java save-format equivalence. Extended horizontal
placement limits and mixed-support combinations remain follow-ups.

## Sweet Roll, Chocolate Glazed Berries and Honeyed Apple

The [food replay](tools/test-foods.py) on
`native-9f42064-1d1612ab9153` with `create-foods.hmod` ran each
original spout recipe and consumed 250 mB of milk, chocolate or honey.
A survival player ate each result and gained the pinned Java nutrition
and saturation values of 6 and 9.6, 7 and 11.2, and 8 and 12.8
respectively. The fixture seeds the source fluids in the Spout. Fluid
acquisition and transport, multiplayer eating and presentation remain open.

## Placard

The [Java capture](tools/java-placard-trace.patch) logs all six
attachment faces at four player yaws. The [Horizon orientation replay](tools/test-placard-orientations.py)
on `native-9f42064-d21a99bf48d2` and `placard-create.hmod`
matched all 24 states. The [gameplay replay](tools/test-placard.py)
passed in solo and LAN. The stored item could be inserted, retrieved
and dropped when the backing block was removed. A matching item
powered the lamp at ticks 0–18, with zero signal at tick 19.

The expanded Placard cases passed on `native-9f42064-d6dc2ad18d3f` with
pack SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`:
the 24 placement orientations, solo and LAN use, one survival Item Frame +
Brass Sheet craft, whitelist rejection/acceptance without consuming either
held item, and idle plus active pulse save/reopen. The re-opened pulse resumed
and expired while retaining its displayed diamond.

Pinned Java `PlacardBlock.canAttachLenient` accepts support only when its
collision shape is nonempty. The new [support regression](tools/test-placard-support.py)
reproduced the defect on that earlier client: a Placard remained attached to
`minecraft:structure_void`, whose collision shape is empty. The source fix now
checks the cached collision shape on placement, survival and neighbor updates.
On matching rebuilt client `native-9f42064-52b6c8b17ac4` with the same pack
SHA-256, the support regression passed after correcting the fixture to exercise
a supported placement followed by an empty-shape neighbor update. The bounded
solo, LAN, 24-orientation, crafting, filter and idle/active persistence checks
also passed. Position-dependent dynamic collision shapes still need a
Level-aware query.

The renderer now uses Java's 0.5 scale for registered block items and 0.375
for flat items; the matching client includes this source change. Exact pixel
comparison of the two scale branches remains open.
Sounds, particles and broader visual equivalence remain open.

## Builder’s Tea

With `create-builders-tea.hmod`, `native-9f42064-1d1612ab9153`
[brewed and bottled tea](tools/test-builders-tea.py). Oak leaves, 250 mB of
water and 250 mB of milk produced 500 mB of tea in the heated Basin. A
glass bottle took 250 mB from the Spout. At full hunger the drink gave
hidden Haste, 1.2 saturation and an empty bottle.

The [Java countdown probe](tools/java-builders-tea-drink.patch) sampled
the held item, hunger, saturation and hidden Haste for
[45 player ticks](fixtures/builders-tea-drink-java.csv). The first
Horizon builds returned the bottle on Java tick 42 and immediately
decremented Haste to 3,599. Candidate `native-9f42064-c218e039de3c`
matches all 45 ticks in the [headless authority replay](tools/test-builders-tea-drink.py)
with the creative-tab pack. The bottle and 6.2 saturation appear
at tick 42 along with all 3,600 ticks of Haste. Its first decrement
is on tick 43. The ordinary brewing, bottling and player drinking
replay and the three-food Spout/eating regression also passed on
c218. The original frozen client timing failure remains archived.
Fluid sourcing and transport, held-item presentation, and a
separate live LAN drinking replay remain open.
On `native-9f42064-d21a99bf48d2` with
`create-placard-extendo-tea-fixed.hmod`, the [offscreen render check](tools/test-tea-fluid-render.py)
distinguished the warm Tea sprite from both water and the older
fallback. The still and flow textures and animation metadata match
the pinned Java files byte for byte.

## Utility crafting and vanilla stone recovery

On `native-9f42064-d21a99bf48d2` with `create-utility-palette.hmod`,
the [survival crafting replay](tools/test-machine-crafting.py) matched
[all 12 Java recipes](fixtures/utility-crafting-java.csv). These include
the Fluid Tank, Item Vault, Steam Engine, Cake with its empty bucket,
Brass Block splitting, and unpacking Bound Cardboard. The same pack
passed [all seven reverse Stonecutter recipes](tools/test-palettes-reverse-cutting.py)
using a Create cut-stone ingredient and taking the original vanilla
stone output.

## Extendo Grip

The [survival reach replay](tools/test-extendo-grip-reach.py) on
`native-9f42064-0ef55b85cb6c` with
`create-placard-extendo-tea-fixed.hmod` verified crosshair targeting and
actual note-block interaction at four distances in both solo and LAN.
One grip in either hand gives +3 block reach and two grips give +5,
as in the pinned Java source. Mechanical crafting gameplay, entity reach,
knockback, durability and backtank use, attribute multipliers and animated
presentation still need coverage.

### APP-2085 scoped gameplay baseline

On `native-9f42064-cefc6d90e4e9` with pack SHA256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`, the
bounded replay passed all seven selected checks: `extendo-grip-reach`,
`extendo-grip-reach-lan`, `extendo-grip-crafting`, `extendo-grip-wear`,
`extendo-grip-wear-lan`, `extendo-grip-placement`, and
`extendo-grip-placement-lan`. The reach cases compare the existing four block
distances with no grip, either hand and both hands against Java's 4.5/7.5/7.5/9.5
survival reach values. The same fixture targets entities with no grip, either
hand and both hands; the dual-grip target is farther than the single-grip
target. A guest attack reduces the pig from 10 to 9 health on the host. The LAN
guest then leaves, rejoins with both grips still equipped, and loses the
extended entity reach after unequipping. The solo fixture reopens the world
with both grips and confirms the same retained/removed reach behavior.

The equipped hands are read when Horizon queries the interaction attributes;
there is no separate persistent reach modifier to restore. Horizon's entity
range query adds four blocks for a single survival grip and six for dual grips,
accounting for its one-block-shorter survival entity base to match Java's
block-reach ray. The pinned mechanical-crafting recipe produced an Extendo Grip
in the output barrel at tick 50 using a Brass Hand, brass ingots, wooden rods
and a Precision Mechanism. APP-1965 remains the independent Mechanical Crafter
baseline. The wear and placement regression checks also passed in solo and LAN,
including Backtank air use, main-hand priority, successful placement wear and
rejected-placement no-wear.

Combat durability, the Java +2 knockback effect, arbitrary external attribute
modifier stacks, exact animation, exhaustive recipe/layout combinations, and
packet/interpolation timing remain open. The scoped gameplay baseline does not
establish Full 1:1 parity.

## Steam Whistle

On `native-9f42064-b72bb1a821ed` and
`create-steam-whistle-fixed.hmod`, the [Horizon replay](tools/test-steam-whistle.py)
matched the [pinned Java trace](fixtures/steam-whistle-java.txt) for
the sampled tank attachment, wrench sizes and first three extensions
across 12 growth actions. It also checked power transitions, placement
beside existing redstone and cascaded removal after breaking an
extension or its tank. Longer columns beyond the sampled states,
audible playback, the standalone chiff cue and LAN audio remain open.
On `native-9f42064-a55af2b6a899` with `create-steam-whistle-audio.hmod`,
[the muted replay](tools/test-steam-whistle-audio.py) verified a Whistle-only
passive boiler, silence without heat, records-category loop onset,
1/12-octave pitch steps, fading and high-octave redstone retrigger.
The original Steam Engine replay passed all 13 samples on that build.
APP-1994's [bounded evidence record](fixtures/steam-whistle-app-1994.md) adds
passing idle/active cold reopen and dedicated-server LAN gates on
`native-9f42064-d6dc2ad18d3f`, using a pack prepared from the pinned Java
checkout (SHA-256 `979e715441e3771b25a819364075894133e689d271348e7a5fc5f7e8e7ffaa79`).
Both LAN clients observed the guest's extension and octave changes and recorded
muted boiler onset, pitch change, redstone fade/retrigger, boiler heat loss fade
and heat restoration. Idle and active reopen retained pitch 3, the double+single
extension, large octave and expected power state; the active setup resumed its
sound request, then faded fully after redstone was removed. Chiff waveform and
actual backend playback, exact Java reload equivalence, full-height layouts,
cosmetic phases and packet timing remain open.

## Table Cloth display and reset

On `native-9f42064-b72bb1a821ed` with `create-extra-recipes.hmod`,
the [display replay](tools/test-table-cloth-storage.py) inserted four
items, rejected a fifth and retrieved them in reverse order. Solo and
LAN passed restart retention and breaking the cloth dropped stored
items. Offscreen captures showed all four items, including on the LAN
guest. Display scale, connected fringe and configured shops remain
open. On `native-9f42064-0eeab3378ef0` with the same pack,
all 19 [reset crafts](tools/test-table-cloth-reset.py) removed a custom
name during survival crafting. Shop-specific data still needs an
in-game fixture after the shop implementation.

## Extendo Grip block-break durability

The pinned Java headless callback recorded one durability point for
each successful break, with the main grip selected when both hands held
one. At 900 or 1 air the Backtank spent one unit and preserved grip
durability. At zero air the grip took damage. All six cases passed
through [survival block breaking](tools/test-extendo-grip-wear.py)
in solo and LAN on `native-9f42064-b72bb1a821ed`. Placement, combat and cancellation
remain open.

## Extra recipes and diving upgrades

On `native-9f42064-0eeab3378ef0` and `create-extra-recipes.hmod`,
the [material replay](tools/test-extra-material-recipes.py) made
50 mB of lava with each of four pinned cobblestone variants, rejected
ordinary heat, and filled a honey bottle with 250 mB. The Campfire
retained raw Dough through tick 599 and dropped Bread at tick 600.
On `native-9f42064-b72bb1a821ed` with `create-diving-smithing.hmod`,
the [smithing replay](tools/test-diving-smithing.py) completed all six
pinned Netherite diving upgrades and retained the base name.

## Cuckoo Clocks

APP-1998's [bounded survival replay](tools/test-cuckoo-clock.py) passed on
`native-9f42064-3413df617042` with `create.hmod` SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The replay crafted the regular clock from planks, andesite casing and a clock,
then crafted the mysterious variant with four gunpowder. It placed both in
survival, consumed each item, and read 16 RPM from each rear-shaft network.
Idle reopen retained both powered clocks. At noon, the regular clock selected
PIG and the mysterious clock selected SURPRISE; active reopen retained the
surprise and progress. The guest placed a regular clock in survival with the
same facing/state as the host. After the synchronized 50-tick event boundary,
the mysterious clock disappeared on both clients while the separate regular
clock survived. The block-only blast's exact shape, other speeds/orientations,
Display Link output, and exact animation/audio timing remain open; this is the
gameplay baseline, not exhaustive Java parity.

## Extendo Grip placement and terrain recipes

On `native-9f42064-633fa4658824` the [placement replay](tools/test-extendo-grip-placement.py)
matched the pinned Java event probe and the [block-break replay](tools/test-extendo-grip-wear.py)
passed again after changing the hook to observe other handlers’
cancellation. In solo and LAN, a stone block and a two-block door
each used one offhand grip durability point. An obstructed door
used none.

The [Dirt Path replay](tools/test-dirt-path-pressing.py) used
`native-9f42064-b72bb1a821ed` with `create-clock-whistle-grip.hmod`.
The Press stamped all six original terrain inputs into Dirt Path and
left Sand unchanged. The pack restores the original Sandpaper
Rose Quartz recipe ID.

## Placeable Honey and Chocolate

The [stone-channel replay](tools/test-honey-chocolate-flow.py) on
`native-9f42064-a55af2b6a899` with `create-placed-liquids.hmod`
matched [all 120 Java block states](fixtures/honey-chocolate-flow-java.csv).
Both fluids advanced on ticks 25, 50 and 75, at levels 2, 4 and 6.
The fourth position stayed dry through tick 100. On
`native-9f42064-7f38a76a10f4` with the same pack, the [bucket replay](tools/test-placed-liquids.py)
poured and recovered both source fluids in survival in solo and LAN.
On `native-9f42064-008abfc9ea02` with `create-bells-fluid-machines.hmod`,
the [machine replay](tools/test-fluid-bucket-machines.py) filled both
buckets from stocked Spouts into Depots and returned an empty bucket
and 1,000 mB of the correct fluid from each Item Drain. The previous
candidate failed independently at each machine. Java machine timing and fluid presentation remain open.

The [lava contact replay](tools/test-lava-contact.py) on the same build
matched all [224 Java block states](fixtures/lava-contact-java.csv) in
16 horizontal cases. Source lava immediately became Obsidian. Flowing
lava immediately became Limestone next to Honey or Scoria next to
Chocolate. Both fluid levels and both placement orders matched through
tick 50. The preceding c30 candidate differed on 100 samples.

On `native-9f42064-17fce985eb74` with `create-quill-radiance.hmod`,
the [vertical replay](tools/test-lava-vertical-contact.py) matched
[all 360 Java states](fixtures/lava-vertical-contact-java.csv) in
16 cases. Lava below a source reacted immediately. Lava above
replaced the source after 30 ticks, or after 60 ticks when falling
through a one-block air gap. The preceding build differed on 28
downward arrivals. The horizontal 224-state regression passed
again on the exact same build and pack.

## Repackager

On `native-9f42064-c30ff8a26280` with `create-repackager.hmod`,
the [survival replay](tools/test-repackager-initial.py) passed both original
conversion recipes, ordinary placement facing away from an attached
barrel, insertion and powered passthrough. A complete two-package order
merged its iron and gold contents while incomplete and unrelated orders
stayed in the barrel. The existing Packager matched 67 Java redstone and
wire samples. A sparse crafting pattern exposed a shifted ingredient
slot. It passed on `native-9f42064-008abfc9ea02` with
`create-bells-fluid-machines.hmod` using the [order replay](tools/test-repackager-orders.py).
The pinned Java GameTest invoked the real Repackager's order method
with a placed Repackager and an item handler. The
[recorded order outcome](fixtures/repackager-orders-java.json)
retained incomplete orders 77 and 88. Completing order 77 yielded one
queued package with two iron ingots followed by two gold ingots and
retained order 88. The [exact outcome replay](tools/test-repackager-orders.py)
matched on `native-9f42064-f550e55a9faa` with
`create-factory-gauge-block.hmod`. Java's timed redstone path and broader
attached-inventory behavior remain open.

### APP-2022 Repackager gameplay baseline

The bounded APP-2022 pass reuses the original survival and order fixtures and
adds [lifecycle/LAN coverage](tools/test-repackager-lifecycle.py). The finite
cases are: (1) one incomplete split order remains in the attached Barrel, then
completes after a redstone off/on cycle and the Repackager cooldown; (2) the
merged package retains its address and ordered iron/gold contents; (3) a
second complete order remains in the Barrel while the first output occupies
the machine queue; (4) idle state with a partial order and active output state
survive save/reopen; and (5) a LAN guest toggles a lever and the host observes
the package dispatch. The backpressure fixture resets the machine's cooldown
field immediately before the second pulse to isolate the queue guard from the
separate cooldown gate. After reopen, the queued item resumes as the held
package/animation; its address and contents remain intact.

On `native-9f42064-6ce68a31b125` (Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, including cursor fix
`16af87f5046ccbf0438a4b8aaeddca2ee0b50b24`) with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`,
`repackager-initial`, `repackager-orders`, and the new `repackager-gameplay`
check passed. The first two reuse the existing survival actions and Java
method-probe outcome; that probe retains incomplete orders 77/88 and verifies
the completed order 77 contents plus sparse crafting context. The lifecycle
case checked one host and one guest dispatch and two save/reopen states. The
portable case list is registered in `tools/test-parity.py`; detailed runtime
logs are under `.local/app-2022-evidence/`.

The ticket baseline does not claim Java-equivalent redstone/attachment timing
or exhaustive inventory, recipe, and layout coverage. Those combinations,
other inventory providers and optional ComputerCraft integration remain
follow-ups; Full 1:1 remains Open.

## Peculiar Bell and Haunted Bell

Both original IDs passed survival floor placement and responded to
adjacent power after game ticks on `native-9f42064-7f38a76a10f4` with
the isolated `steve-bells.hmod` pack. The Peculiar Bell recipe consumed
a brass block and sheet in the survival grid. On
`native-9f42064-008abfc9ea02` with `create-bells-fluid-machines.hmod`,
the [bell replay](tools/test-peculiar-haunted-bells.py) turned a Peculiar
Bell into a Haunted Bell after 153 fan-processing ticks on a Depot
next to a lit Soul Campfire. Both bells passed floor placement and
the powered state cycle. The original fan timing, direct soul-fire
conversion, animation, sounds, shapes and Haunting effects remain open.

APP-2038 adds source-aligned direct conversion when a Peculiar Bell is
placed over Soul Fire or a lit Soul Campfire, and when either catalyst
appears below an existing Peculiar Bell. The callback carries facing,
attachment and power into the Haunted Bell state. The rebuilt-client
[bounded replay](tools/test-peculiar-haunted-bells.py) passed Soul Fire,
lit Soul Campfire and unlit Soul Campfire rejection, while retaining the
survival craft, 153-tick Depot fan conversion and both bells' floor
placement/power checks. The [hit probe](tools/probe-peculiar-haunted-bell-hit.py)
kept the Haunted Bell intact after a valid creative left-click. The pinned
control log exposed no sound/event lines, so event delivery remains
unverified. The [LAN lifecycle replay](tools/test-peculiar-haunted-bells-lifecycle.py)
passed host/guest power convergence and active/idle save/reopen. These
runs used pinned Java source
`ac0c444d9828da3453ae8cc65338e8de063286fb` and compatible client build
`native-9f42064-55bc0a64ce79`. Exact Java hit geometry, swing/audio timing
and Haunting effects remain open.

## Sticker

See the [complete Sticker behavior checklist](STICKER-PARITY.md) for the subsequent
source-first completion pass, original Java batches, fast callback loop,
multiplayer lifecycle evidence and remaining verification limits.

The [pulse replay](tools/test-sticker.py) passed on
`native-9f42064-30c63b3219dc` using `create-sticker-crafter-cover.hmod`.
Two rising edges each toggled extension. Both falling edges preserved
the current extension state. On `native-9f42064-673f99e57bfa` with
`create-track-observer.hmod`, survival placement beside existing
power started powered with the head retracted. The [Java landing
probe](tools/java-sticker-bounce.patch) gives an upright Sticker a full
vertical rebound. On `native-9f42064-73cd83f87233` the [headless
replay](tools/test-sticker-bounce.py) matched five pig position and velocity
samples each for upright retracted and extended Stickers, a north-facing
Sticker, and stone. Both upright states bounced the pig, and the north-facing
Sticker matched stone.
The engine data restricts this restitution to upward-facing states.
A subsequent [source-first Sticker experiment](STICKER-SOURCE-PORT.md), on
`native-9f42064-abde3add95e2` with the unchanged `create.hmod`, translated
`StickerBlockEntity` animation before batching the comparisons. The
[Java capture](tools/capture-sticker-java.py) factors the original client
routine into a shared method and executes it with the actual cached Ponder
LerpedFloat dependency on a dedicated Java GameTest server. This verifies
the client algorithm without launching a Java client; it is not a Java
rendering or network-delivery comparison.

The [repeatable comparison](tools/test-sticker-source.py) matches all 192
animation records and 960 partial-frame offsets by float bits, plus 36
six-direction redstone/attachment records and 18 original bearing assembly
records. It includes initial extended/retracted states, interrupted movement,
and repeated update notifications. The same Rust animation core runs in the
production client. An actual offscreen Horizon client draws the original
40-vertex head, shows extension and retraction through intermediate offsets,
and emits attachment/detachment events. Its observed transitions are checked
against the Java trace. Powered-placement and the existing four-state
pig-bounce comparison also passed on this build.

Broader support-face classification, drag, fall-damage and bounce cases,
particle/sound presentation equivalence, six-direction visual geometry,
mounted animation and lifecycle/LAN behavior remain open. This experiment
does not establish full Sticker parity.

## Placeable Netherite Backtank

With frozen `create-netherite-backtank.hmod` on
`native-9f42064-0616b90288fb`, [the Backtank replay](tools/test-copper-backtank-pickup.py)
placed and picked up the named Netherite item with 284 air in solo and
LAN. It waterlogged when placed and restored source water on pickup.
The Copper control matched its Java recording on the same build. A
[dedicated Java Netherite GameTest](tools/java-netherite-backtank-pickup.patch)
later captured the same scenario with the original Netherite block and item.
The [Netherite fixture](fixtures/netherite-backtank-pickup-java.csv) matched
solo and LAN on `native-9f42064-46eefb85bfea`. The south-facing tank consumed
the hand item on placement and went into the chest slot on pickup, preserving
its name and 284 air. Pickup restored source water.

## APP-2082 Netherite Backtank and diving gear baseline

The finite acceptance cases were: six Netherite smithing upgrades with custom
name retention; charged named Netherite Backtank placement and pickup in solo
and LAN; the original full-suit mob air/lava trace; Netherite diving boot
underwater movement in solo and LAN; player fire immunity for a complete
charged suit with a missing-helmet control; charged and partially depleted
player air across save/reopen; and the completed Copper prerequisite's breathing,
movement and reopen regressions.

The source review covered `DivingBootsItem.accelerateDescentUnderwater`,
`BacktankUtil`, `DivingHelmetItem`, `NetheriteDivingHandler`,
`BacktankBlock`/`BacktankBlockEntity`, and the six registered smithing recipes.
This exposed two player gaps: Netherite boots were absent from the shared
underwater movement hook, and the player's fire damage path did not apply the
four-piece Netherite diving protection rule. The movement hook now accepts both
diving boot items. Fire damage is blocked only when the player has the
Netherite Diving Helmet, a charged Netherite Backtank, Netherite Leggings, and
Netherite Diving Boots or vanilla Netherite Boots. The Netherite Java mob
trace covers the suit's lava movement, fire immunity and tank consumption.

On Horizon build `native-9f42064-caec674f121a` from source pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, using Create pack SHA-256
`f110417f6cc906f60d6a4113c0e7038f1448ec428c52128800a8b24ce355addb`, all
13 focused checks passed. The original Netherite fixture matched all 181
observations (ticks 0–180, including air, fire immunity, health, and lava
movement). Netherite movement produced the Java callback's -0.05 per-tick
downward effect and 1.3 forward acceleration; the observed eight-tick vertical
velocity change was -0.805887 versus -0.019712 bare, with three-tick forward
speed 0.151677 versus 0.077265 bare. LAN host and guest both sank with the
Netherite boots. The fire immunity check held health at 20 with the full suit;
removing the helmet restored lava damage (health fell to 18.569). Charged
900-air and partially depleted 899-air Backtanks both survived reopen, and
breathing resumed after reload. The six smithing recipes retained the base
custom name. Netherite placement/pickup matched the dedicated Java fixture in
both modes with 284 air, restored water and the item name intact. All 98
Copper mob breathing samples, both Copper movement modes, and Copper charged /
partially depleted reopen passed as neighboring regressions.

Reproduce the bounded suite with the exact client and prepared 26.3 resources:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 \
  --jobs 2 --check netherite-backtank --check netherite-backtank-pickup \
  --check netherite-backtank-pickup-lan --check diving-smithing \
  --check netherite-diving-movement --check netherite-diving-movement-lan \
  --check netherite-diving-reopen --check netherite-diving-fire-immunity \
  --check copper-diving-breath --check copper-diving-breath-lan \
  --check copper-diving-movement --check copper-diving-movement-lan \
  --check copper-diving-reopen
```

The player fire check is a source-aligned damage test rather than an exact Java
player trace. Charged and partially depleted ordinary persistence was checked
in Horizon; Java save-format equivalence, exact warning/animation presentation,
and exhaustive placements, charge boundaries and movement samples remain open.
The first isolated build took 392 seconds and the incremental final build took
119 seconds. The suite passed across the final build in a 12-check batch plus
the isolated fire-immunity check; the initial fire-check failure was a fixture
setup issue (the test had not actually equipped the Backtank) and was corrected
before the passing run.

## Crafter Slot Cover

The [survival replay](tools/test-crafter-slot-cover.py) on
`native-9f42064-673f99e57bfa` with `create-track-observer.hmod`
crafted the original brass-nugget recipe, installed a cover on an
empty crafter and recovered it by clicking with an empty hand. The
preceding candidate crafted the same recipe but failed to install the
cover. The [APP-1965 gameplay baseline](#mechanical-crafters-app-1965)
exercises a covered grid. Cover drops, rendering, and installing or
removing a cover as a LAN guest remain open.

## Mechanical Crafters (APP-1965)

The Java reference is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`, Minecraft 1.21.1 and
NeoForge 21.1.219. The Horizon checks used `native-9f42064-72dd88a3d19f`
on Minecraft 26.3. The candidate was built from port base `1ff398eaac3e`
and tested with `create.hmod` with SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 \
  --jobs 3 --check mechanical-crafter --check 'crafter-*' --check mechanical-tools-crafting
```

| Check | Result |
| --- | --- |
| `mechanical-crafter` | The arm-fed grid matched all [144 Java samples](fixtures/crushing_wheel_crafting-java.csv) from ticks 0–143. Four sampled crafters matched speed, phase, countdown, held input, and transferred grid size. Two Crushing Wheels arrived on tick 143. |
| `mechanical-tools-crafting` | The existing chute-fed Wand of Symmetry and Potato Cannon recipes reached their output barrels by Horizon ticks 55 and 65. |
| `crafter-slot-cover` and `crafter-survival` | Survival crafting produced a Slot Cover and three Mechanical Crafters in their respective checks. The cover installed and came off with an empty hand. A placed crafter faced the player and its neighbor inherited the facing and pointed into it. A front wrench click cycled the arrow. A hand click fed one of two sticks, and an empty hand recovered it. |
| `crafter-invalid-grid` | A Potato Cannon grid with a stick in place of Andesite Alloy produced no cannon and returned its seven ingredients. |
| `crafter-process-reopen` | The missing cover kept the filled idle grid from starting for 25 stepped ticks. Reopening retained its arrow configuration and ingredients. Adding the cover started the craft. A second save captured an exporting leaf and accepting inlet with their ingredients in the grouped grid. After reopening, the full barrel held the result in the outlet's `INSERTING` phase. Freeing one barrel slot delivered exactly one Potato Cannon and every crafter returned to idle with empty input. |
| `crafter-lan` | A survival guest changed the arrow and inserted one of two sticks. Host and guest agreed on the arrow, the host saw one stick in the crafter, and the guest retained one stick. |

The new survival and recovery cases in [the gameplay fixture](tools/test-crafter-gameplay.py)
use the pinned source rules for placement, input, cover completion, and ejection.
Save/reopen was checked in Horizon and LAN evidence covers eventual state
convergence. Java reload and packet timing, broader routing layouts, shared
input connection controls, ordinary crafting recipes, active removal, and exact
presentation remain open.

## Schematic and Quill

The [survival recipe replay](tools/test-schematic-and-quill.py) on
`native-9f42064-673f99e57bfa` consumed the original empty schematic
and feather, and returned one Quill. The packaged assets match the
original. The [Schematic Table replay](tools/test-schematic-table.py)
on `native-9f42064-a4246de72557` crafted the table in survival and
placed it facing the player from two directions. On
`native-9f42064-0fa36e41334f` with
`create-lit-burner-quill-capture.hmod`, the
[Horizon capture round trip](tools/test-schematic-capture.py) captured
inclusive reversed corners and wrote compressed structure NBT. It
verified stair orientation, chest NBT, omitted air and a structure
void captured as air, then loaded the file and placed the blocks.
The scenario reaches the serializer through an internal test hook.
Quill controls, naming and glue clipping, Java 1.21.1 file
interoperability, and Table upload remain open.

## Track Observer

### APP-2048 gameplay baseline

Built the native client as `native-9f42064-a7485cf0edab` from the pinned
Java Create source `ac0c444d9828da3453ae8cc65338e8de063286fb` and the local
`create.hmod` pack (SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`).
The recovered launcher used a private copy-on-write compiler cache.

`python3 tools/test-parity.py <ctl> <client> <resources> --jobs 2 --check 'track-observer*'`
ran the focused Track Observer cases. On the identified build:

- `track-observer` passed crafting both original recipes across all five
  pressure plates, player targeting and attachment on straight and diagonal
  track.
- `track-observer-train` passed train entry/passage/exit detection and drove
  an adjacent wire to strength 15, then back to 0 after the train left.
- `track-observer-filter-accept` passed for one matching item in carriage
  cargo. Active and idle save/reopen retained the target and filter and
  restored the corresponding powered state.
- `track-observer-filter-reject` passed for nonmatching cargo; the Observer
  stayed idle and its target and filter survived idle save/reopen.
- `observer-lifecycle-lan` passed as an adjacent regression. The rendered guest
  launcher now has an explicit 120-second startup allowance because this build
  can spend more than 45 seconds loading the offscreen client and its Create
  pack. A rerun reached the train fixture but hit the existing simple-train
  assembly guard before the guest joined; guest filter editing and multiplayer
  state convergence therefore remain unverified for this ticket. The focused
  rerun command and preserved logs are recorded in the PR.

Pinned Java `TrackObserverBlockEntity.tick()` keeps the powered state for
eight ticks after `keepAlive(train)`. The source-based timeout is implemented;
exact Java arrival timing has not been independently traced. Curved-rail
attachment and broader train layouts also remain open. Keep Full 1:1 Open.

## Linked Controller

The [survival crafting replay](tools/test-linked-controller-crafting.py)
on `native-9f42064-17fce985eb74` produced the original Linked Controller
from one Redstone Link and six oak buttons, consuming every input.
The [Lectern Controller replay](tools/test-lectern-controller.py) on
`native-9f42064-7d1aeccec803` and
`create-lectern-inherited-state.hmod` attached a named controller,
preserved the lectern facing, and left a book-filled lectern unchanged.
Its comparator wire went from 15 to 0 when detached. Solo and real
LAN guest runs passed. That build gave the original stack back to the
player, while pinned Java saves only its frequency slots and spawns
the reconstructed controller as an item entity on detach or break. A
correction on `native-9f42064-22077cbad4db` passed solo with one
portable frequency pair, plus an unrelated item name and marker.
The block and dropped controller preserved the pair. Detach spawned
one controller item for normal pickup, survival mining dropped one
controller and one vanilla lectern, and creative pick-block returned a
vanilla lectern. On `native-9f42064-d4d07b511f32` and
`create-lectern-frequency-sounds.hmod`, the same replay passed from a
real LAN guest and in solo, including the east-facing Java item
spawn at `(5.75, 171.0, 20.5)`. The server queued Java's attach and detach
events at the original block center, category, volume and pitch.
Audio output stayed disabled. Mounted control, swapping, exact
presentation and client audio playback remain open.

The [binding replay](tools/test-linked-controller-binding.py) on
`native-9f42064-f4a607d04120` with `create-factory-gauge-block.hmod`
read the authoritative held stack after both input bindings. Forward
saved diamond and emerald in slots 0 and 1, and Left saved gold and
iron in slots 4 and 5. Both pairs and the original custom-data marker
were preserved. This passed in solo and from an actual LAN guest.
The same replay on `native-9f42064-efe93f2e7145` and the same pack
checked that Forward powered the matching receiver and adjacent wire
from 0 to 15, release cleared both, and switching the held item during
a second press cleared the receiver. Both solo and actual LAN guest
runs passed. The [original server timing trace](fixtures/linked-controller-wireless-java.csv)
on pinned Java calls the real controller handler. The [Java probe
patch](tools/java-linked-controller-wireless-trace.patch) reproduces it.
Press changes
`Receive` immediately and powers the receiver and wire on the next
observed tick. Release leaves the immediate state intact, then clears
`Receive` on the first following tick and receiver power and wire on
the second. Without refresh, the timeout clears `Receive` at 30 ticks
and clears power on the next tick. Horizon's initial replay updates
the power on the first stepped tick after release. The corrected
`native-9f42064-d4d07b511f32` solo and LAN replays matched those separate press and release phases.
The fixture waits for processing to complete within the stepped world
tick. Disconnecting the guest while held then matched expiry: receive
remained 15 through tick 29, reset at 30, and the wire reset at 31.
On `native-9f42064-98b2ada58dbe`, the mounted replay passed solo
and real two-guest LAN. The first user activated the controller and
toggled receiver power. A second guest could neither take ownership
nor transmit with movement keys. Escape cleared the original user.
On `native-9f42064-f2c710cdd816`, a stale saved user was
recoverable in solo. In LAN, disconnect cleared ownership on the
first following tick. Input remained live through 29 ticks, receive
dropped at 30, and the wire dropped at 31. On `native-9f42064-e1f836744b54`, the
owner changing dimensions cleared the original Lectern user by the
next tick. A competing guest visiting the Nether left the existing
Overworld owner in place. Swapping, visuals and original client
transport timing remain open.

The bounded persistence checks (`linked-controller-persistence` and
`lectern-controller-persistence`, each with solo and LAN variants) passed
on `native-9f42064-6ce68a31b125` with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The handheld retained both pairs (diamond/emerald in slots 0/1 and
gold/iron in 4/5) and its custom-data marker through a host save/reopen;
the same named LAN guest rejoined, used the saved bindings, and drove the
matching receiver and wire 0→15→0. The attached Lectern retained its
diamond/emerald `ControllerData`, and the host or rejoined guest acquired
it and resumed input to a matching receiver and adjacent wire after reopen.
These are source-aligned Horizon save/reopen checks, not Java reload
comparisons. The four new checks can be rerun with
`python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client
/path/to/prepared/26.3 --jobs 1 --check 'linked-controller-persistence*'
--check 'lectern-controller-persistence*'` after preparing the pack as in
the README. The first post-rebase LAN run exposed a fixture race before the
rejoined guest received its test item; the failed output is retained at
`.local/app-2033/failed/lectern-controller-persistence-lan-first-attempt.log`.
The fixture now waits for the item to reach the guest inventory before use.

## Shopping List

The [APP-2031 bounded flow](tools/test-shopping-list-flow.py) passed on the
pinned `native-9f42064-3a2d3eb65fc6` build with `create.hmod`
(`sha256=67ea72a5c560188616f9ac28dd33e97f134fe65d4b14adf1b2f6adbffd039e96`).
The sampled rules follow pinned Java `TableClothBlockEntity.useShop`,
`ShoppingListItem.bakeEntries`, and Stock Ticker request handling. In solo, two
iron ingots could not create a three-ingot purchase; after restocking, the
list recorded the purchase and refused to increment it beyond available stock.
The list survived a cold save/reopen. An underfunded attempt retained both the
list and the buyer's gold. A funded attempt dispatched exactly one `Warehouse` package with three iron
ingots, left two in stock, removed exactly two gold ingots from the buyer,
recorded both in the Stock Ticker's payment inventory, and consumed the list
once. The equivalent LAN
guest flow passed with payment and list state owned by the guest and delivery
state shared by the host.

The [discard replay](tools/test-shopping-list-discard.py) passed on the same
build: ordinary use retained the list and sneak-use discarded it in air or on
a block. The [Table Cloth storage regression](tools/test-table-cloth-storage.py)
and [Stock Ticker order replay](tools/test-stock-ticker-order.py) passed in
solo and LAN. The [Item Hatch unsided-input regression](tools/test-item-hatch.py)
also passed after adapting the insertion call to the pinned API. These results
close the bounded APP-2031 gameplay flow; they do not claim exhaustive parity.

Full 1:1 remains open for exact Create tooltip styling and less common
shop/filter and transaction edges. The implementation reads each referenced
cloth's saved request, owner, address, target and price, builds readable item
and cost tooltip lines, enforces current Stock Ticker availability, preflights
payment, and clears the buyer's list only after package dispatch succeeds.

## Elevator Contact item

The [item replay](tools/test-elevator-contact-item.py) on
`native-9f42064-fbcbb68676be` with
`create-elevator-contact-shopping-list.hmod` accepted the exact
`create:elevator_contact` item ID. Pick Block and a survival break
each returned one Redstone Contact as in the original source and loot
table. The prior candidate incorrectly cloned an Elevator Contact in
the control replay.

## Minecart Anchor

The [headless Anchor replay](tools/test-minecart-anchor.py) on
`native-9f42064-18472b3bb96b` with `create-minecart-anchor.hmod`
assembled and disassembled carts on both axes. The payload included
the original hidden anchor, and the assembler rail and cargo were
restored. The existing Cart Assembler replay matched all eight
placement samples and 13 fill, drain and drop samples on the same
build and pack.

## Crafting Blueprint

The [survival crafting replay](tools/test-crafting-blueprint.py)
on `native-9f42064-18472b3bb96b` with
`create-crafting-blueprint.hmod` combined the original Painting and
Crafting Table ingredients into one Crafting Blueprint. Display
placement, result programming and recipe handling remain open.

## Lit Blaze Burner

The [survival interaction replay](tools/test-lit-blaze-burner.py) on
`native-9f42064-fac0f278b640` with
`create-minecart-contraption-items.hmod` ignited the empty cage with
Flint and Steel, changed to a soul flame, and used a Shovel to return
to an empty cage. Soul Sand remained in both client and server
inventories. The preceding client incorrectly predicted a decrement.
The [same fixture](tools/test-lit-blaze-burner.py) on
`native-9f42064-24deca5c6180` plus `create-fake-track-coupling.hmod`
observed comparator wire strengths of 1, 2 and 0 across the three
states. The same build observed passive boiler heat from both flame
states and its loss after extinguishing. Presentation remains open.

On `native-9f42064-b0213de77789`, the Blaze Burner survival replay passed
normal fuel and Blaze Cake, refuel threshold and overflow, rejected fuel,
expiry, lava-bucket remainder, and idle/active save-reopen. Acquisition mode
captured a Blaze with an empty burner and placed the resulting burner. The LAN
fueling replay passed with a survival guest consuming coal into a cold burner;
the host observed 1,600 fuel ticks and kindled heat, and the guest observed the
kindled state. The first fixture placed host and guest at the same coordinates,
so the guest targeted the host entity instead of the burner. Separating the
players corrected the fixture; no multiplayer production-code change was
needed. These replays are registered as `blaze-burner`,
`blaze-burner-acquisition`, and `blaze-burner-lan` in
`tools/test-parity.py`. The earlier [heated-fluid replay](tools/test-fluid-food.py)
matches three Basin recipes over 86 ticks; its first four samples keep all
three burners smouldering and each mixer idle before fuel is applied,
providing the insufficient-heat control. Source review also corrected
creative capture to preserve the empty burner, matching
`BlazeBurnerBlockItem.giveBurnerItemTo` at the pinned Java revision.

## Minecart Contraption items

The [survival replay](tools/test-minecart-contraption-items.py) on
`native-9f42064-18472b3bb96b` with
`create-minecart-contraption-items.hmod` made a vanilla Minecart
and Furnace Minecart from their corresponding contraption items.
The Chest Minecart Contraption had no conversion recipe, matching the
original. The Minecart Coupling recipe also passed on
`native-9f42064-fac0f278b640` with `create-fake-track-coupling.hmod`.
Coupling, pickup, saved contraption data and redeployment remain open.

## Mechanical tool recipes

On `native-9f42064-fac0f278b640` with `create-mechanical-tools.hmod`,
the [powered-crafter replay](tools/test-mechanical-tools-crafting.py)
fed the last ingredient through a Chute and checked the result in a
Barrel. The Wand of Symmetry was present by tick 55 and the Potato
Cannon by tick 65 in their respective Horizon setups. These are
Horizon outcome checks. Item use and Java timing remain open.

## Train Track and Railway Casing (APP-2045)

The [Java removal trace](fixtures/track_removal-java.csv) exercises three
curves from the [placement trace](fixtures/track_curve-java.csv). The
pinned Create build at `ac0c444d9828da3453ae8cc65338e8de063286fb`
ran one headless GameTest on Minecraft 1.21.1, NeoForge 21.1.219, and
JDK 21. Each row samples the opposite endpoint and newly dropped tracks
immediately after removal. The 23-segment survival curve returned
12 curve tracks and one endpoint. Mining the secondary endpoint with
block drops disabled and removing a 13-segment curve in creative mode
both returned zero tracks. All three removed the reciprocal connection.
The creative probe invokes Java's `playerWillDestroy` before removing
the block. The run took 4m 15s including initial offline setup.

Apply [the curve capture patch](tools/java-track-curve-trace.patch),
then [the supplemental removal patch](tools/java-track-removal-trace.patch)
in a disposable checkout of the pinned Java source and run
`./gradlew --offline --no-daemon runGameTestServer`. The patch SHA-256s
in application order are
`93f00b668bc1fe82c0f0987a01db5b623d36d7a6ba6ade7238130fc77b2a0b86`
and
`e2234ef339a669804069b9ad705b3d2f790a209faad5575f0995cf616e47e16e`.

The exact Horizon baseline at `e83bffc743a48041961aacc57de88281fa901217`
built as `native-9f42064-8cc365d013ad` in 17m 6s with compatible
launcher 0.2.67. With the updated content pack it still paid for the
23-segment curve (32 tracks in inventory before placement and 15 after),
then left the reciprocal endpoint active after survival mining and
returned only one track. The same baseline with that pack applied one
Sturdy Sheet to Brass Casing and recovered one Railway Casing with a
pickaxe.

On fixed build `native-9f42064-d0cdcece38f9` and a pack prepared from
the same Java checkout with `python3 tools/prepare.py <java-checkout>`,
the [offscreen lifecycle replay](tools/test-track-lifecycle.py) matched
all three drop counts and immediate reciprocal cleanup. Replacing a
curve endpoint with air by command returned the 12 curve tracks once.
In the same run a survival player obtained and mined Railway Casing,
then placed and recovered one straight track and one east-ascending
track. After 24 ticks of player gravity the flat piece supported the
player at 2/16 above the block base. The ascending piece had no player
collision and the player landed on the supporting floor.

The replay saved and reopened before and after the first curve removal.
Both endpoints retained their original reciprocal offsets on the first
reopen. The surviving endpoint remained flat with an empty connection
list on the second reopen. Horizon retains the empty block entity to
send a clearing update to clients. The render and path readers enumerate
the connections, so the empty entity contributes no curve. The Java
capture covered removal without a Java world reopen.

The fixed Horizon build used engine revision
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` and mixins
`5a64af938ec86b00d53d16a408aabc0038fb3e57` with native Create bundle
`a7b5879abb38119f`. Build using `sh tools/build-native.sh <launcher> <launcher-data>`
with the compatible 0.2.67 launcher and a private writable cache. The
fixed rebuild took 4m 12s. The prepared `create.hmod` SHA-256 was
`1d6c3b38fedbf8f4d0d69499e10a278093d756cf79a35ff44e180fd484b4b590`.

An independent offscreen LAN guest placed one straight piece and the
23-segment quarter-turn in survival. The host read reciprocal endpoint
data, and the guest saw both endpoints and the 32-to-15 track cost.
The fixture moved the host away from the guest's interaction position
to keep players from intercepting the click. The run checks guest
convergence.

Final-build regressions matched 15 single placements, all seven line
cases including the orthogonal crossing, all ten curve-placement cases
including refusals, all 190 sequenced-crafting ticks, and 160 curved-train
ticks with speed and four three-dimensional wheel positions. The
Fake Track marker replay also passed. The offscreen curve capture
showed both rails and the ties along the tested turn. An initial line
test missed the span's first click. After the fixture waited for the
server's selection before moving the player to the target, all seven
line cases passed.

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --check 'track-lifecycle*'
python3 tools/test-parity.py "$ctl" "$client" "$resources" --check track-crafting --check track-placement --check track-line --check fake-track --check curved-train
python3 tools/test-track-curve.py "$ctl" "$client" "$resources" --visual
```

The removal comparison breaks endpoints. Direct curve targeting,
remaining branch layouts, track skins, and exact render parity remain open.

## Fake Track

In the [curve fixture](tools/test-fake-track.py) on
`native-9f42064-24deca5c6180` with
`create-fake-track-coupling.hmod`, placing a curve created its hidden
markers and kept them for 120 ticks. Deleting the owner left two
markers behind. Original Java places markers for primary Bézier
connections and expires unused ones after three random ticks.
Portal connections use real track shapes. On
`native-9f42064-f88edc65213a`, physical break removed the markers.
Standalone markers expired and a waterlogged marker restored water.
Command replacement previously bypassed cleanup by clearing the old
block entity before its usual removal hook. On
`native-9f42064-7d1aeccec803` with
`create-lectern-inherited-state.hmod`, the same fixture passed
placement, refresh, physical and command cleanup, standalone expiry
and water restoration. It covers one flat curve. Shared markers
and an exact raster trace remain open.

## Tree Fertilizer

APP-2088 preserves the existing family evidence, which
covers the ordinary survival recipe, valid and rejected use, one-item and
last-item consumption, main/offhand priority, drops, representative saplings,
obstructions and seeded full-volume Java comparisons. The pinned Java
implementation is `TreeFertilizerItem` at
`ac0c444d9828da3453ae8cc65338e8de063286fb`; its use is immediate, so an active
operation reload is not applicable.

The finite delivery checks on `native-9f42064-6ce68a31b125` passed:

- `tree-fertilizer`: crafted two, rejected stone without consuming fertilizer,
  and grew oak with one use.
- `tree-fertilizer-obstructions`: matched the pinned Java obstruction cases for
  oak through stone with bedrock retained, plus all four giant spruce base logs
  and no podzol.
- `tree-fertilizer-obstructions-lan`: a survival guest grew those trees; the
  host observed the matching blocks and consumption.
- `tree-fertilizer-reopen-lan`: a guest grew oak, then its complete captured
  block volume and remaining inventory survived host save/reopen and guest
  rejoin. Coordinates, block IDs and non-derived properties matched. Vanilla
  leaf `distance` values recalculated on load and were treated as derived state.

The new replay compares the resulting state before and after Horizon reload; it
does not claim Java-equivalent reload timing. Host and guest convergence is
verified, not packet-arrival timing. Commands:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 \
  --check tree-fertilizer --check tree-fertilizer-obstructions \
  --check tree-fertilizer-obstructions-lan --check tree-fertilizer-reopen-lan
```

Java obstruction fixture SHA-256:
`1dae2c95763427ee7b1b29878e4ca2879b54518720065e0720aa0b4c90d72970`;
capture patch SHA-256:
`d341b499cb0b357784aba5398737092af6292ce241fb298f6eea3a6caeb9438c`.
Runtime Horizon pin is `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`; client
SHA-256 is `bdbafe5289f2c05ef76009c17070e0320a7c606e042dd5202b142e0e6d123fc9`,
control tool SHA-256 is
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`, and
pack SHA-256 is
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The leaf-distance reload refresh is the only newly observed state variation.
Other seeds and environments, additional sapling geometry, Java map tree-bin
cases, other overlay drops, item trajectories/pickup and particles remain
nonblocking follow-up coverage; Full 1:1 remains Open.

## Factory Gauge item

The [survival recipe replay](tools/test-factory-gauge-item.py) on
`native-9f42064-f88edc65213a` with
`create-lectern-inherited-state.hmod` crafted two Factory Gauges
from a Stock Link and Precision Mechanism and returned one gauge
in the clearing recipe. That initial clearing control used an untuned item.
The [full placement replay](tools/test-factory-gauge-item.py) on
`native-9f42064-f550e55a9faa` with
`create-factory-gauge-block.hmod` passed untuned rejection, inventory
resynchronization, Stock Link tuning, and survival placement on a
north-facing wall. The bottom-right panel stored the original network
frequency and consumed the held gauge. The clearing recipe removed
tuned data. The original passive panel was visible in an offscreen
capture on a63b. On `native-9f42064-f4a607d04120` and the same pack,
the upper-right panel accepted a second gauge while preserving the
bottom-right one. Retrying the occupied quadrant retained the held
item and preserved both panel entries. Both models were visible in an
offscreen capture. On f4a, removing the support left the assembly in
place and mining one panel removed the whole block. Both failures
have focused regression checks. On `native-9f42064-efe93f2e7145`,
those checks passed with two distinct frequencies: support removal
dropped both gauges, and survival mining on the upper panel dropped
one while preserving the lower panel and its frequency. The [orientation
replay](tools/test-factory-gauge-orientation.py) on the same candidate
matched the Java-derived south-facing floor `top_left` and north-facing
ceiling `bottom_left` placements, each consuming one tuned item. Other
facing and quadrant combinations, Java timing, recipe configuration
and restocking remain open. On `native-9f42064-ac4ba38a15f0`, the
[Display Link replay](tools/test-factory-gauge-display.py) discovered
and selected the Gauge status source in the menu, saved
`create:gauge_status` and cleared the previously populated Nixie
for an empty linked-panel list. On `native-9f42064-0dae880cd174`,
the survival filter replay copied the held iron ingot into the selected
empty panel and retained all five items. On
`native-9f42064-f42de31a335f` and `create-factory-gauge-config.hmod`,
a real configuration-screen click closed the menu, and the subsequent
click on a same-surface Display Link saved the selected bottom-right
panel in `LinkedGauges`. On
`native-9f42064-2bf765040d26` and `create-ponder-assets.hmod`, a
matching Stock Link network with 12 iron ingots displayed the full
value-first row `12   Iron Ingot ` on a Nixie. The [guest replay](tools/test-factory-gauge-lan.py)
passed the entire flow from tuning through the Nixie result.
Promises, restocking,
multiple rows, and exact Display Board sections remain open.

### APP-2026 Factory Gauge configuration and replenishment

The prerequisite Redstone Requester issue APP-2024 is Done. This work extends the existing Factory Gauge port with player-facing target amount/unit controls and a periodic panel restock path. Matching Stock Link sources are discovered through the existing stock network code; inventory insertion is preflighted before source withdrawal, both sides commit together, and packager notifications refresh the affected inventories. Factory Panels are now included in native block-entity ticking.

The [item replay](tools/test-factory-gauge-item.py) first filled the destination barrel with unrelated items and verified the source stayed at 12. It then removed the matching Stock Link frequency and verified the target stayed at two iron and the source stayed at 12. Restoring the matching frequency let five-item mode move exactly five iron ingots (source 12 → 9, target 2 → 5). It then switched the same panel to stack mode and verified the remaining nine move (source 9 → 0, target 5 → 14), with no additional transfer through two further 100-tick windows. The target amount, unit setting (`UpTo: 0b`), target inventory, and source inventory survived cold save/reopen. The [LAN replay](tools/test-factory-gauge-lan.py) had a guest set the target to one item and toggle units, then confirmed host state synchronization, one-item replenishment (source 12 → 11), and no duplicate after another 100 ticks. Existing filter, Display Link stock output, and idle reopen checks also passed.

The checks ran against Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, build `native-9f42064-63b75493cc50` (client SHA-256 `e5efb1b4d79c04352a2894694a9fcefb61d01b3c0d794944099f4bd593db30f7`) and Create pack SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`. The five final checks were `factory-gauge-filter`, `factory-gauge-stock-display`, `factory-gauge-reopen`, `factory-gauge-restock`, and `factory-gauge-stock-display-lan`; all passed. Run them with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check factory-gauge-filter --check factory-gauge-stock-display --check factory-gauge-reopen --check factory-gauge-restock --check factory-gauge-stock-display-lan
```

For reproducibility, the initial isolated build attempt hit the patch mismatch at `horizon-advancement-initial-inventory.patch`; resolving the mismatch in this APP-2026 private source/cache enabled the actual build without changing other workers' caches. The first regression attempt also hit OS socket denial before gameplay; rerunning fixtures with the authorized socket access produced the results above. These invalid attempts are summarized in `.local/app-2026-evidence/attempts.md`.

The bounded gameplay path is implemented and verified. Broader Java logistics-manager package/address/promise semantics and remaining orientations/timing are follow-ups; this evidence does not claim exhaustive 1:1 parity. Restocking here is synchronous into the target packager's attached inventory, so there is no in-flight request state to persist or reopen.


## Portable Minecart Contraption pickup

The [survival replay](tools/test-minecart-pickup.py) on
`native-9f42064-22077cbad4db` and `create-factory-gauge-block.hmod`
assembled a normal Minecart with a stone payload. The cart reached an
exposed rail and the client caught up with its position. A real Wrench
click removed it and gave one portable item with the Java component key
and anchor and stone entries in the palette. Placing the item on the
destination Cart Assembler restored the stone and preserved the
assembler. This scope covers the simple stone case in solo. On
`native-9f42064-ac4ba38a15f0`, stone and oak-plank payloads passed
the same workflow and the expanded Java bounds assertion. An
unsupported loaded chest stayed mounted with all seven ingots. On `native-9f42064-0dae880cd174`, the original anchor at
`(8,170,24)` survived motion, redeployment and another Wrench pickup.
An immediate repeat click retained exactly one portable item.
On `native-9f42064-f2c710cdd816`, west-facing stone and east-facing
oak retained their Java initial orientations after moving to rails
on the other axis, picking up, placing, and picking up again. Final
disassembly restored the payload. On `native-9f42064-e1f836744b54`,
cobblestone, glass and X-axis oak log also passed, alongside the prior
stone and planks, with exact restored block states. The codec accepts
captured vanilla states without block-entity or inventory data and
rejects the original vanilla movement actors. On the same build the
[real LAN guest replay](tools/test-multiplayer-minecart-pickup.py)
checked wrench interaction, original anchor and orientation, host
cart removal, item consumption and final stone restoration. Cargo
rotation, Create actors, coupling and more LAN variants remain open.

APP-2004 extends the portable codec to vanilla chest/barrel block-entity inventory.
On `native-9f42064-7ed7f56ac77a`, the seven solo payload cases passed, including
seven copper ingots retained through moving and picked-up reopen, two pickup/place
cycles and final disassembly. Restored block states match their pre-assembly states. Survival LAN guest stone
and loaded-chest pickup/redeployment also preserved host cargo and consumed the item.
The existing assembly capture omits the container display name; this cosmetic
limitation is documented separately from the verified cargo. See the bounded
[APP-2004 evidence](APP-2004-EVIDENCE.md) for commands, source/build/pack identity,
regressions, failures and remaining limits. All 16 selected checks passed, including
324 Java curve/slope-reversal samples in solo and LAN. Full 1:1 remains Open.

## Clockwork broad-suite follow-up

The frozen full-catalog replay on `native-9f42064-f4a607d04120`
diverged after motor removal. Beginning at tick 19, both Clockwork
Bearings retained their moving display entities. The tick lost the
prior speed when a network refresh published zero first. A fix for an
adjacent disconnected motor passed all 46 Java samples on
`native-9f42064-d4d07b511f32`. The separate settling replay
configured 256 RPM at tick 1. Moving the setting to pinned Java's
tick 2 matched all 82 Java samples on both the frozen and corrected
builds. The first frozen suite skipped the software audio engine
and could not validate playback. On `native-9f42064-98b2ada58dbe`,
the [muted software playback replay](tools/test-clockwork-audio.py)
matched all six original stop cues on host and guest, including tick,
position, volume and pitch. Running with `HORIZON_NO_AUDIO=1` and
`HORIZON_CREATE_TEST_AUDIO=1` enables software processing with no
hardware output.


## Sequenced Gearshift render follow-up

On the frozen broad-suite build, a motor could publish RPM before the
Sequenced Gearshift published its input side. The authoritative entity
knew which end was the input but the renderer drew both at the same
RPM. Synchronizing when the input side changes fixed that discrepancy.
The [render replay](tools/test-sequenced-gearshift-render.py) on
`native-9f42064-0dae880cd174` matched all 88 Java horizontal and
vertical states across 28 submitted render fractions. In the LAN
replay both renderers showed the guest-programmed +64 RPM output and
its stop at the guest's save tick.


## More muted audio replays

The software-only audio candidate `native-9f42064-98b2ada58dbe`
also replayed the Train Trapdoor and Framed Glass Trapdoor. Each
matched nine ordered Java block snapshots, seven toggle cues and two
silent steps in solo and LAN. Both game processes ran with hardware
audio disabled.

On `native-9f42064-f2c710cdd816` and
`create-factory-gauge-config.hmod`, the Package opening replay matched
seven original Java openings in solo and real LAN: exact inventories,
spills, and the spawned pig. Each connected client processed all 14
original playback events with hardware audio disabled.


The frozen broad-suite Display Link placement fixture aimed through
the gap between the two Nixie tubes. A real mouse click at the first
original tube shape passed on `native-9f42064-f4a607d04120`: selection
stored the Nixie, placement spent one Display Link, and the configured
source published the expected count.


On `native-9f42064-8e22ef86bd44`, the software-only replay also
matched 12 Package charge cases, 13 unlanded flight samples, and
10 damage/contact cases, each in solo and real LAN. This retested
the audio assertions the original muted broad run could not observe.

## Ponder assets

`create-ponder-assets.hmod` contains all 178 original Ponder NBT
structures and both Create Ponder textures, compared byte for byte
with pinned Java. All 34,747 Ponder name and text entries matched
their original locale values. The original registration has 179
storyboard calls referring to 166 unique paths.

On `native-9f42064-2bf765040d26` with that archive, the
[Shaft relay replay](tools/test-ponder-shaft.py) opened the scene
through the original item hover and hold interaction. It read the
32-block NBT, submitted actual block-model geometry, matched the
Java scene events at ticks 5, 20, 25, 30, 35, 45 and 65, and verified
replay, exit, and preservation of the underlying game world and
inventory. On `native-9f42064-4ecaf15f8dbb` the same replay passed,
and its [offscreen frame](.local/ponder-shaft-dossier/4ecaf15f8dbb-final-caption.png)
shows the corrected camera tilt, opaque backdrop, and visible
Speedometer face. On `native-9f42064-7b31405bb89e` with
`create-worldshaper-screen.hmod`, the same fixture's `--encasing`
replayed the 36-block original second Shaft storyboard. It checked
ticks 20, 27, 37, 44, 54 and 124, navigated back to the first scene,
and verified replay, exit, and preservation of the game world and
inventory. The [Small Cogwheel relay](tools/test-ponder-cogwheel.py)
also passed on `native-9f42064-7cb574b2896d` with the same archive.
It exercised the original 37-block scene, the cog train, gauge, two
captions, timeline through tick 205, replay, and close.
On `native-9f42064-4a2ebff12602`, [Ponder Back](tools/test-ponder-back.py)
returned to survival inventory via Backspace and the Back control,
and Escape returned to gameplay. The Creative check restored the
Redstone Blocks tab with a byte-identical item-grid crop.
On `native-9f42064-94f8d290fd69`, the [Large Cogwheel relay](tools/test-ponder-large-cogwheel.py)
loaded its original 35 blocks, exercised the right-angle and alternate
axis scenes, verified 12 original timeline events through tick 190,
and passed opening, replay, and close. On `native-9f42064-6afd0fa98700`,
the [preceding gearshifting scene](tools/test-ponder-gearshift.py)
matched its timed events through tick 390. Both Cogwheel items
navigate through it in the original order and back to their relays.
The screenshot shows the lifted, turned, and swapped gear
configurations. Rotation-speed particles, exact movement
interpolation, full catalog, and container return remain open.

### APP-2101 bounded gameplay baseline

The finite case set for this ticket reuses the Shaft relay and encasing,
Small and Large Cogwheel relays, Gearshift navigation, survival Back/Escape,
and Creative-tab return above. The [Shaft replay check](tools/test-ponder-shaft.py)
now also pauses at tick 5, waits eight client ticks, confirms the tick-20 event
has not fired, then resumes through the existing Java event markers to tick 65.
It passed with nonempty scene geometry, replay, Escape, and unchanged inventory
and world marker. The new [LAN check](tools/test-ponder-guest.py) passed with
both host and guest opening Ponder from their survival inventories, returning
to inventory, and retaining their Shaft counts; the guest UI did not change the
host's state. Existing [Creative Back evidence](tools/test-ponder-creative-back.py)
shows the selected Redstone Blocks tab and item grid restored byte-for-byte.
The LAN fixture then stopped and reopened the dedicated world and rejoined both
players; their Shaft inventories and the diamond-block world marker survived.
Ponder itself is a read-only client presentation with no mutable scene save
state, so this inventory/world save-reopen and the Creative selection across
opening and closing are the applicable persistence checks.

The two new focused replays ran against pack SHA-256
`6925a9a1e4c1a01acbdc6a72f3b40bcb8e88f4d75e9dce103b747591b0b7c678`,
prepared 26.3 resources from installed build `native-9f42064-68c7ab9c0826`,
`horizon-ctl` SHA-256
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`, and
the offscreen `native/target/fast/horizon-client` SHA-256
`7de8fae06dd9f92a2ccb059e732120931f3f56e15396325fb5bf0fef4b185b96`.
Commands from the repository root:

```sh
python3 tools/test-ponder-shaft.py "$CTL" "$CLIENT" "$RESOURCES" --pack /path/to/create.hmod
python3 tools/test-ponder-guest.py "$CTL" "$CLIENT" "$RESOURCES" --pack /path/to/create.hmod
```

The guest test is registered as `ponder-guest` in `tools/test-parity.py`.
These representative cases establish the gameplay baseline only; the full
catalog, remaining storyboards, container return, exact pixels, and exact
movement interpolation remain open in the matrix.


The Depot replay on `native-9f42064-e1f836744b54` also matched all
21 original Package frames in solo and LAN using muted software
playback.


## Empty Belt direction and Package insertion

The broad suite reproduced a +0.125 position offset at the first
forward Package insertion. The Belt had no cargo when its motor began
turning, so it returned before persisting the new traversal direction.
On `native-9f42064-525aae01ff81` with `create-ponder-assets.hmod`,
the [original Package Belt replay](tools/test-package-belt.py) matched
all 108 Java frames in each of solo and LAN, across running and stopped
Belts in both directions. The observations include entity motion,
inserted item, retained movement direction, and belt positions.


## Toolbox and Turntable regression follow-up

The Toolbox reconnect fixture opened LAN with forced default
Creative mode. The real player consequently left Survival on
reconnect. Disabling force in this fixture preserved Survival and
the original restock and pickup assertions passed. The separate
placed Toolbox dye replay on `native-9f42064-2bf765040d26` matched
all sixteen recolors while preserving facing, waterlogging, stored
items, filters, and dye consumption. Its menu guard prevents the
empty offhand from opening a screen after a main-hand dye action.

Turntable player trace rows are now written atomically, after a
disconnect log interrupted a formatted row during the frozen run.
The rerun on `native-9f42064-69a110adaadf` matched 402 host and 169
guest camera frames and observed three edge pushes per client.


## Brass Diode click timing

The swept fast-click replay could press and release between client
ticks without the value-box tracker observing the press.
On `native-9f42064-708e263497a4` with `create-ponder-assets.hmod`,
the original quick-click fixture matched 12 Java states and all
three recipes in solo and LAN. The held Redstone Interval replay
matched all eight settings and the short top click in both roles.

## APP-2087 Worldshaper gameplay baseline (November 21, 2026)

The [bounded replay](tools/test-worldshaper-baseline.py) supplements, rather than
replaces, the Java comparisons in [Worldshaper selection](#worldshaper-selection).
The source contract is Create `ac0c444d9828da3453ae8cc65338e8de063286fb`:
`AllItems.WORLDSHAPER` registers the Creative Worldshaper, `ZapperItem` limits
stacks to one and rejects missing block selection, `WorldshaperItem` rejects
missing brush settings, and `TerrainTools.run` directly edits blocks without
consuming materials or creating drops. Creative acquisition and zero-material
operation are therefore intentional; no survival crafting/material requirement
is invented for this tool.

The finite new cases, in both solo and LAN, are:

- Acquire one tool from Creative Search using its hotbar-number shortcut.
- Reject an unconfigured shot, then a configured Fill without block selection;
  retain the source, adjacent air, and inventory counts.
- Select actual Stone and configure Solid Cuboid 1×1×1 Attached Fill in the UI;
  preserve unrelated custom data and save/reopen this idle state.
- Fill the adjacent cell with zero Stone items, matching host/actor blocks and
  one-tool/zero-Stone counts. Save/reopen and retain the edit and complete item.
- Configure Merged Clear, remove only the filled cell, and save/reopen again;
  retain selected Stone, Clear settings, custom data, source and stack counts.

Each replay performs four shots (two rejected, one Fill, one Clear), advances
four authoritative ticks per shot, and compares discrete state exactly. The
three reopen boundaries cover idle, post-Fill and post-Clear. LAN repeats four
guest connections around those host restarts and checks guest convergence.
These instantaneous edits have no persistent in-flight operation. This is
Horizon gameplay persistence, not an actual Java reload or packet-arrival trace.
Existing selection, shape, pattern, seeded chance, connected brush, Flatten,
range and effects evidence above remains valid; broader combinations, exact
shot timing, beam width, hand animations and dynamic model remain open.

Validation used `native-9f42064-de4782e18b5b`, rebuilt from committed main
`6b060e2`, Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, compatible
launcher 0.2.67 and the build's own prepared 26.3 resources. Native bundle SHA256:
`a3f397468ddc99fc19dad33cabcfe9b21780a04b7aa2605c8ac5482be19e088d`.
Client SHA256: `c907c923f868818ac12fd46b5b35cb62185efb88567e1b8fa98d97877c748ddd`.
Pack SHA256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
No native production code changed in this pass. Existing Java capture patches
were reused unchanged: selection SHA256
`ced21d800bd741dbc71e017df8920fecf9d1f86542f4ac5d2942b8a398893aba`,
Fill `38869ed89d6a78e4b5a97eb1230857c98d08499b1e16773821badda8bf01a15c`,
and Cuboid tools `b52c39efb538679b5d459e024b1602f514a2d3df4a484a8a638751601e0d1584`.

From the ticket worktree, with `build=.local/patched-launcher/versions/native-9f42064-de4782e18b5b`:

```sh
python3 tools/check-source.py
python3 tools/test-parity.py "$build/horizon-ctl" "$build/horizon-client" \
  "$build/.local/horizon-client/26.3" --jobs 2 \
  --check 'worldshaper-baseline*' \
  --check worldshaper-selection --check worldshaper-selection-lan \
  --check worldshaper-preserve-selection-creative \
  --check worldshaper-preserve-selection-creative-lan \
  --check 'worldshaper-cuboid-tools*'
```

All eight scoped checks passed, including all five tools' eight-cell Java grids
in solo and LAN (80 compared grid cells across ten tool cases). Syntax and
`git diff --check` passed. After adding an explicit nearby dropped-item assertion,
the two baseline replays were rerun on the same build. No native Rust changes
required a separate standalone Rust/Clippy pass; the complete native build passed.

Raw artifacts are retained under `/private/tmp/horizon-app-2087/.local/`:
`evidence/final-checks.log`, `evidence/final-baseline-drops.log`,
`evidence/sha256.txt`, `evidence/source-checks.log`, `evidence/build-*.log`,
`parity/worldshaper-*.log`, and copied host/guest runtime logs. Setup failures
are preserved: the shared source cache was already patched; a fresh pinned
archive contained documentation symlinks rejected by the launcher; sandbox DNS
and local socket restrictions required approved execution outside the sandbox.
Only private source/cache inputs were repaired. Initial harness failures were
an empty no-op gamemode response and use of Shift-click rather than the tested
Creative hotbar shortcut; neither establishes a gameplay defect. Successful
preflight solo/LAN runs used the older `native-9f42064-6bde2ea90cf2` and are
kept as harness development evidence, not final-build acceptance.

Approximate effort: source/setup 6 minutes, replay/evidence authoring and debugging
7 minutes, native build 276 seconds, source checks 1 second, and the first final
integration batch 140 seconds. These phases overlap. No Java recapture or
native gameplay repair was needed.

## Worldshaper selection

The [pinned selection probe](tools/java-worldshaper-selection-trace.patch)
called Java's actual selection code. On `native-9f42064-e1f303c2882d`,
Survival solo and LAN matched the [Java component states](fixtures/worldshaper_selection-java.csv).
Stone preserved its name. Waterlogged inner-left East/top Oak Stairs
stored East/top, straight, and dry. Each input block and held stack
count remained intact. Creative uses a separate instant-break entry
point. With its selection hook, the same two cases passed via actual
Creative clicks in solo and LAN on `native-9f42064-4ecaf15f8dbb`.
A repeated stair selection on an older candidate could fall through
into Creative breaking. On `native-9f42064-60dbf5b9f4b5`, a repeated
stair selection and rejected chest selection both preserved the
blocks and held component in Creative and Survival, solo and LAN.
The [original 1×1×1 Attached Cuboid Solid Fill case](fixtures/worldshaper_fill-java.csv)
matched in solo and LAN on `native-9f42064-7cb574b2896d` with
`create-worldshaper-screen.hmod`. It used the Java component state,
placed stone in the same adjacent air cell, preserved the source,
and retained the Worldshaper. On `native-9f42064-5c8ca33c80d8`,
the [live editor replay](tools/test-worldshaper-screen.py) confirmed
2×3×4 Solid Cuboid settings, all three placement choices, and the
preserved block selection in solo and LAN. The editor handles both
use packets from the same click as a single opening.

On `native-9f42064-4a2ebff12602`, the same 1×1×1 Fill also
placed the matching block from 20 blocks away, beyond normal
interaction reach, in solo and LAN. The [five Java Cuboid tools](fixtures/worldshaper_cuboid_tools-java.csv)
then matched the full eight-cell grid in each real UI scenario in
both scopes. Changed-cell counts were 1 for Fill, 3 for Place,
2 for Replace, 3 for Clear, and 2 for Overlay. Clear was configured
and used without selecting a block. Through the same editor,
[2×3×4 Cuboid Fill](fixtures/worldshaper_cuboid_fill-java.csv)
matched each Java changed cell in solo and LAN. Merged south
and Inserted south changed 23 cells each, and Attached north
changed 24. The clicked stone and held Worldshaper stayed intact.
On `native-9f42064-94f8d290fd69`, [Sphere and Cylinder Fill](fixtures/worldshaper_rounded_fill-java.csv)
matched both serialized editor settings and every placed cell in solo
and LAN. Radius-2 Sphere Attached south placed 81 cells. Radius-2,
height-4 Cylinder Attached up placed 84. Both kept the clicked stone
and placed no extra gold in the inspected volume. All 22 registered
Worldshaper and Ponder cases passed in a separate regression run on
that candidate.

The [Worldshaper pattern oracle](fixtures/worldshaper_pattern_fill-java.csv)
matched on `native-9f42064-6afd0fa98700`. At each of two negative
coordinates with opposite parity, Solid placed all 24 cells and
each checkerboard placed its complementary 12 cells. The replays
used the actual settings editor and matched saved components,
changed cells, kept item and target, and the absence of extra
placements in solo and LAN. The exact 128-block cutoff, Surface
and Cluster brushes, Flatten, and presentation remained open on
that build. On `native-9f42064-dc039270e887`, [Surface Overlay and Cluster Clear](tools/test-worldshaper-connected.py)
also matched every cell of the corresponding Java Worldshaper probes
in a real editor-and-use replay in solo and LAN. Surface Overlay
changed 23, and Cluster Clear changed 5. Each 11³ before/after volume
checked all changes, including untouched obstructions.

On `native-9f42064-b54ba548b587`, the [Java chance stream](fixtures/worldshaper_chance_stream-java.csv)
matched the actual editor and every output cell in solo and LAN.
From seed `123456789`, the three successive uses placed the same
9, 10, and 21 cells. The isolated replay seeds just the placement
pattern RNG, and ordinary gameplay uses the world RNG. The replay on
`native-9f42064-944519a8b386` also compared the post-shot
random-state fingerprint `-1135198989088998967` in both scopes.
The same candidate passed the original 128-block source range in
a [boundary replay](tools/test-worldshaper-selection.py): a
128.1-block shot missed and a 127.9-block shot placed stone in the
Java cell in solo and LAN. The distant result was read from the
authoritative server.

On `native-9f42064-b7f33c92f94d`, [Flatten](tools/test-worldshaper-flatten.py)
matched the [Java upward and west-facing mound cases](fixtures/worldshaper_flatten-java.csv)
in solo and LAN. Through the editor it stored 7×7×7 Cuboid,
Solid, Merged, and Flatten without requiring a selected block.
Every cell in the inspected 11³ volumes matched, including the
single removed summit per case. Additional terrain and fluids remain open.

On `native-9f42064-65809fd910bd`, the [muted shot replay](tools/test-worldshaper-effect.py)
delivered one event to each client in solo and LAN. Each client
submitted ten End Rod particles and ten Fireworks and received the
main-hand basedrum cue at the original pitch and volume. The shot
used the exact accepted ray endpoint. On `native-9f42064-1d51b8455a4f`,
the left-handed LAN guest's off-hand shot also reached both clients
once with the alternate pitch. Recoil state appeared only on the
shooter, and the barrel origin pointed along the accepted ray in both
the solo and LAN replays. Beam width and exact first-person animation
remain open.

## Single-plane Wand of Symmetry

On `native-9f42064-b7f33c92f94d` with `create-worldshaper-screen.hmod`,
the [live solo and LAN replay](tools/test-symmetry-wand-plane.py)
matched the [Java oracle](fixtures/symmetry_wand_plane-java.csv) for
XY and YZ activation, the stored plane, stone placement on the other
side, one additional Survival block consumed, and deactivation that
retained the plane. The Horizon test also checks that insufficient
items leave the mirror position empty. The dedicated Java capture
annotated three render methods client-only to run the probe; its
gameplay code remained identical. Additional modes, mirrored breaking,
placement transforms and visual effects remain open.

On `native-9f42064-60dbf5b9f4b5`, [live mirrored breaking](tools/test-symmetry-wand-break.py)
matched the [Java pre-source BreakEvent](fixtures/symmetry_wand_break-java.csv)
for both planes, a different-material survival target, and empty-hand
stone. In live Horizon, two successful stone breaks produced two
cobblestone and two damage to the pickaxe, including the original
break. Empty hand produced the one reflected drop. Both solo and
LAN passed. Creative mismatch is present in the Java oracle and needs
its own Horizon replay.

## Postbox station binding

On `native-9f42064-dc039270e887` with the same archive, the [survival replay](tools/test-train-postbox-target.py)
selected a placed Train Station, placed the bound Postbox, observed
the original relative target `[-2,0,-1]`, and opened its address
screen automatically in solo and with a real LAN guest. Horizon now sends the placed block before its
menu packet so the client can resolve the menu.

`native-9f42064-65809fd910bd` also persisted the station and Postbox
registration, address `Depot`, and empty 18-slot buffer across a
solo save and restart. A separate replay confirmed both chunks unloaded
before saving the registry and that the entry persisted when reloaded.
Both actual player breaking and command
replacement cleaned up the saved entry. On `native-9f42064-1d51b8455a4f`,
the same replay inserted an addressed package through the Postbox inventory;
the 18-slot station buffer retained its item and address through confirmed
chunk unload and restart, and taking it back cleared the saved buffer. The
[Java buffer oracle](fixtures/postbox-offline-buffer-java.snbt) confirms those
insertion and withdrawal snapshots with a synthetic registered station. The
attachment uses the station position in its dimension. On
`native-9f42064-a87d65f7cb67`, a synthetic offline buffer change made while
the Postbox was unloaded restored its addressed package and cleared Primed
on reload; the Java oracle also verifies restoration of two slots. This does
not exercise a train transfer. Java graph identity, track rebinds, and full mail transfer remain open.

On `native-9f42064-eaa55eaaa5bb`, the [offline arrival replay](tools/test-train-postbox-mail.py)
matched the [Java scheduled-train trace](fixtures/train-offline-mail-java.csv):
a real assembled carriage reached Terminal at tick 102 and moved its addressed
package into a Primed offline buffer, retaining unrelated cargo. Both Java and
Horizon used a synthetically registered unloaded port for this transfer; actual
Postbox binding and Primed reload are verified separately above.

On `native-9f42064-1b39e3f2383b`, the same replay used a physically bound,
loaded Postbox and matched the [loaded Java trace](fixtures/train-loaded-mail-java.csv):
the Postbox was empty and the cargo present at tick 101, then at tick 102 the
addressed package was in the live Postbox, absent from the carriage, and Primed
remained clear. Other cargo remained in the carriage; the Postbox contents and
buffer also survived a save and reopen. On `native-9f42064-298f4f6553ef`,
the [import replay](tools/test-train-postbox-import.py) matched the independent
[Java trace](fixtures/train-import-mail-java.csv): at tick 102, an outgoing
package moved from a synthetically registered unloaded Postbox to the arriving
carriage, its offline buffer became Primed, and a package matching the Postbox
address stayed behind. The original cargo remained intact. The same import replay also passed with a
physically bound loaded Postbox, matching the [loaded Java trace](fixtures/train-loaded-mail-import-java.csv). Both prior loaded
and offline delivery replays passed on the same candidate. On
`native-9f42064-d6a9092ed1ea`, the loaded replay also inserted a second outgoing
package during the stop: it remained in the Postbox at tick 122 and moved into
the carriage at tick 123, matching the [Java dwelling trace](fixtures/train-loaded-dwell-import-java.csv).
Loaded and synthetic offline arrival imports also passed on that candidate.
On the same candidate, the [track replacement replay](tools/test-train-postbox-import.py)
removed and replaced the station's targeted rail, preserved both loaded Postbox
packages, and routed a subsequently scheduled train to import the outgoing one.
The [Java rebind oracle](fixtures/train-postbox-rebind-java.csv) observed the
global station disappear while the rail was absent and return with the same
UUID and Postbox buffer after replacement. The [full-carriage replay](tools/test-train-postbox-full.py)
matched the [Java backpressure trace](fixtures/train-postbox-full-java.csv):
at arrival tick 102, outgoing mail stayed in the loaded Postbox while matching
train cargo exported into it; the freed carriage slot accepted outgoing mail at
tick 123. All unrelated cargo slots stayed intact. The [two-Postbox replay](tools/test-train-postbox-two.py)
matched the [Java trace](fixtures/train-postbox-two-java.csv): at tick 102,
mail imported from one loaded port was exported to a second matching loaded
port in the same arrival, leaving carriage cargo unchanged. Both native port
buffers matched their live inventories after saving. Native graph UUID identity
and other rebinding and dwelling-transfer cases remain open.

## Sequenced Gearshift release timing

On the older broad-run candidate, the Contraption Controls replay
released the completed gearshift state one tick early at ticks
40, 61, 82, and 103. Java schedules its redstone neighbor update
for the following tick. With the falling-edge correction,
`native-9f42064-7cb574b2896d` matched all 105 Contraption Controls
samples and all 56 Sequenced Pulley samples in headless replays.

The 1,022-check baseline on `native-9f42064-7f3945f841a4` exposed a
late reset after editing a running program. Resetting on every falling
edge cleared Contraption Controls a tick early. On
`native-9f42064-4a8f29fd78fb`, the sequencer schedules its reset at the
next block tick, as in Java. The comparator and editor matched 44 samples
each, Contraption Controls matched 105, Sequenced Pulley matched 56, and
LAN stop and both render replays passed. The original baseline failures
remain in its suite log.

On `native-9f42064-7b31405bb89e`, the muted software mixer replays
also matched the Elevator service fixture through all 101 sampled
Java door, cabin, and sound ticks, with 85 indicator samples on both
clients and 66 standing passenger checks. Depot Brass Pressing and
Deployer matched 71 Java ticks and four impacts. All five scoped
stacked Belt, ground-item Press, and first Depot slide tests passed.
The suite enables the software mixer when launched with
`HORIZON_NO_AUDIO` so its playback assertions can observe sounds.


The [flat Weighted Ejector LAN guest](tools/test-depot-ejector-player.py)
remains intermittent on `native-9f42064-4a2ebff12602`. Three of
five isolated repeats matched every sample. In two, the tick-24
sample already observed the authoritative landing health and velocity
correction expected at tick 25. Positions, grounded state, and the
subsequent samples matched. Independent authoritative and guest
sampling still needs a reliable shared tick boundary.


## Rope Pulley network transition

On the older broad-run candidate, the shared kinetic publication
updated Rope Pulley RPM before its block-entity turn. The pulley
missed the start transition. On `native-9f42064-0908886fd3e5`, the
[Rope replays](tools/test-rope-payload.py) matched all 66 payload ticks
and the original detached landing and copper recovery. The 56-tick
[Sequenced Pulley replay](tools/test-sequenced-pulley.py) also passed.

APP-1999 bounded acceptance ran on the combined latest-main build
`native-9f42064-b47e135a9b67`
(`create-worldshaper-screen.hmod`, SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`).
`tools/test-parity.py` passed the original motion, detach and sequence
checks plus blocked assembly, the upper zero-rope limit, idle and active
save/reopen with cargo restoration, and a LAN host/guest ride on a moving
glued payload (7/7). The independent bearing-player-collision regression
also passed on this build. The rider check exposed missing previous-pose
motion publication; Rope Pulley now publishes its per-tick payload delta
for shared collision resolution. Full rope-height/configuration coverage,
render interpolation and other interaction variants remain open.


## Fluid Valve opening and closing

The [Java GameTest](tools/java-fluid-valve-cycle.patch) recorded a
Fluid Valve driven at 64 RPM, reversed at tick 13. The initial Horizon
replay matched the movement and open/closed state but published the
new chase target and speed a tick late at both transitions. On
`native-9f42064-300ffc6b5d1a` with `create-worldshaper-screen.hmod`,
the [headless replay](tools/test-fluid-valve-cycle.py) matched all
19 Java rows, including the original float32 residual that keeps
the Valve open until tick 19. A separate `fluid-threshold` replay
passed the existing 337 Java ticks.

On `native-9f42064-668af61de86a` with `create-fluid-valve.hmod`,
the same 19 authority samples and original upward-facing pointer
geometry passed offscreen. All sampled angles followed Create's
interpolation formula across 468 solo, 830 LAN host, and 1120 guest
frames. Other orientations and detailed pixel alignment remain open.

On `native-9f42064-c038049dc73c`, the [placement replay](tools/test-fluid-valve-placement.py)
matched all 24 [Java placement states](fixtures/fluid_valve_placement-java.csv)
in solo and from a real LAN guest, covering four yaw angles, three
pitch angles, and both sneak states. On `native-9f42064-1e137bac748c`,
another [26 Java rows](fixtures/fluid_valve_neighbors-java.csv) matched
in both modes, including compatible and perpendicular glass pipes,
shafts, conflicting preferences, pump, Smart Fluid Pipe, Tank,
Cauldron, water sources, and flowing water.

APP-1986's bounded gameplay pass ran on `native-9f42064-fb8446effe86`
with Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, the pinned Java
source `ac0c444d9828da3453ae8cc65338e8de063286fb`, and the prepared Create
pack (SHA-256 `af85c21d48dae13afa98251632b9c126c4410e617a734f229dbb28fa2467b553`).
The [Fluid Valve line fixture](tools/test-fluid-valve-flow.py) moved water
through a mechanically pumped line with a separately powered Fluid Valve.
Its solo and LAN runs both verified powered opening, closed-flow rejection,
reopening, reversal, and 7,000 mB conserved across the source tank, line and
destination. On the solo run the tanks held 6,872/128 mB after opening and
6,488/512 mB after closing; active flow resumed after save/reopen and retained
the motor setting. A second idle, closed save/reopen retained both the closed
state and destination amount. In the LAN run a guest changed the Creative
Motor board to close and reopen the line, and the host observed the same
resulting state and fluid movement. The [survival recipe check](tools/test-fluid-valve-flow.py)
consumed an iron sheet and Fluid Pipe and produced one Fluid Valve.

The registered flow, flow-LAN and recipe checks passed 3/3 on that build.
The existing cycle, placement, placement-LAN, neighbor and neighbor-LAN
checks also passed 5/5 on the same build, retaining the 19 Java cycle rows,
24 placement cases and 26 neighbor cases. Commands:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check fluid-valve-flow --check fluid-valve-flow-lan --check fluid-valve-recipe
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check fluid-valve-cycle --check fluid-valve-placement --check fluid-valve-placement-lan --check fluid-valve-neighbors --check fluid-valve-neighbors-lan
```

The powered-flow fixture is a scoped state and conservation check, not a new
Java-tick trace. Other fluids, port combinations and pointer rendering across
orientations remain open in the Full 1:1 matrix.
Effort log: Java recapture 0; pack preparation 24 s; runner/source review and
fixture debugging about 25 min (motor direction, frozen-tick stepping and guest
interaction corrections); private native builds took 9 min 50 s cold, 9 min 16 s
after the first rebase, and 5 min 25 s on the latest main; Python syntax check
under 1 s; the final eight focused integration checks took about 4 min.

## Copper Diving Helmet and Backtank breathing

The [pinned Java GameTest](tools/java-copper-diving-breath.patch) submerged
an equipped pig and an ordinary pig with 280 initial air. The helmet and
two-unit tank restored the first pig to 300 air. It consumed one tank
unit after 8 ticks and the second after 28 ticks, at world tick multiples
of 20. Its ordinary air started falling the next tick.

The [Horizon replay](tools/test-copper-diving-breath.py) matched all 98
air and tank observations on `native-9f42064-21f659789205` in solo and
on `native-9f42064-90476b859cb6` with a real LAN observer beside the pools.
The [Java player probe](tools/java-copper-diving-player.patch) ticks a
survival mock Player in water on the pinned Java server. It captures 49
samples of ordinary air and the worn Copper Backtank's charge. On
`native-9f42064-fe50f900823d`, the [player replay](tools/test-copper-diving-player.py)
matched all 49 in solo and LAN with a real headless guest. Air stayed at
300 while the 200-unit tank fell to 198, one unit per twentieth world
tick. The guest received the final charge and air. The existing Extendo
Grip wear checks passed in both modes. Warning feedback, suit rendering,
and a real Java client comparison remain open.

The expanded Java probe also equipped Water Breathing. The ordinary
suit drained on each twentieth world tick; combining it with the effect
kept all 200 tank units while air stayed at 300. On
`native-9f42064-af6ef21890e5`, Horizon matched all 98 observations from
those two cases in both modes and showed the final tank charge on the wearer.


## Potato Cannon basic launch

The [pinned Java GameTest](tools/java-potato-cannon-trace.patch) captures
[empty use and launch](fixtures/potato-cannon-launch-java.csv) and the
[first three flight ticks](fixtures/potato-cannon-flight-java.csv). A
normal main-hand Potato Cannon consumed one of three potatoes, lost one
durability, and blocked immediate repeat use. An empty use left the
cannon unchanged. On `native-9f42064-1a99b59d30ea`, the [offscreen player
replay](tools/test-potato-cannon.py) matched the launch position, velocity,
and sampled air flight within 0.000001 in solo and LAN. Host and guest
audio output were disabled. Existing Arrow Dispenser and gantry Dispenser
replays passed on the same candidate.

For this replay use `--pack` with a prepared pack that includes
`data/create/horizon/entity_type/potato_projectile.json`. The verified
candidate added that entry to the frozen baseline pack and has SHA-256
`122365995daba25d3a10c8f097f11f0b991f132955699098338a4794aa921ae3`.
The original 1,022-check run continues on its original pack.

The [first impact probe](tools/java-potato-cannon-impact.patch) records a
basic potato hitting a stationary pig. On `native-9f42064-4a8f29fd78fb`,
the [replay](tools/test-potato-cannon-impact.py) matched five damage, target
position and knockback velocity, and removal of the projectile on tick 2
in solo and LAN. Later target motion, other ammunition and targets, PvP,
damage-source semantics, impact cues, recovery, block effects and
exact visuals remain open.

The [Copper Backtank probe](tools/java-potato-cannon-backtank.patch)
records [six starting air charges](fixtures/potato-cannon-backtank-java.csv)
for ordinary main-hand potato shots with default settings. On
`native-9f42064-e0d199cb5609`, the [replay](tools/test-potato-cannon-backtank.py)
matched the resulting charge, ammunition, cannon wear and projectile
creation in solo and LAN with the projectile candidate pack above. For
example, the 100-air tank retained 96, and the empty tank left the cannon
with one wear. Enchanted capacity, Netherite tanks and warnings remain
open.

The [cooldown probe](tools/java-potato-cannon-cooldown.patch) and
[17 player tick samples](fixtures/potato-cannon-cooldown-java.csv) matched
the [muted solo and LAN replay](tools/test-potato-cannon-cooldown.py) on
`native-9f42064-e0d199cb5609` with the same projectile candidate pack.
Actual repeat clicks were blocked on ticks 1–14, fired at tick 15 and
were blocked on tick 16 by the renewed cooldown. The fixture batches
input and counts player ticks because world freeze leaves player item
cooldowns ticking.

The [carrot launch and impact probe](tools/java-potato-cannon-carrot.patch)
matched on `native-9f42064-9232e2103643` with the same projectile pack
in fully headless solo and LAN. It fires the same projectile entity with
a carrot stack and matches launch position and velocity, ammunition,
wear, and the first pig hit at Java tick 1. Matching the Java projectile
target margin corrected a one-tick delay. Plain potato (first hit at tick
2) and a 100-air Copper Backtank also replayed in both modes. A separate
[Java cooldown trace](fixtures/potato-cannon-carrot-cooldown-java.csv)
and [muted offscreen replay](tools/test-potato-cannon-carrot-cooldown.py)
matched ticks 1–11 blocked, firing at tick 12, and renewed cooldown
blocking tick 13. Four [potato/carrot priority cases](tools/test-potato-cannon-priority.py)
matched headlessly in solo and LAN. A fifth Java case selected an earlier
apple over a later carrot. On `native-9f42064-e420833b5c2b` with the same
projectile pack, the [apple replay](tools/test-potato-cannon-apple.py)
matched launch, wear, consumption, and the first pig hit on tick 1 in
headless solo and LAN. The [10-tick apple cooldown](tools/test-potato-cannon-apple-cooldown.py)
and all five [mixed priorities](tools/test-potato-cannon-priority.py)
also matched in both modes. Carrot and potato with a 100-air Copper
Backtank passed preservation. Other ammunition, carrot crop planting,
projectile persistence, PvP and audiovisual details are open.

The [six-ammunition Java batch](tools/java-potato-cannon-ammo-batch.patch)
expanded the replay to beetroot, melon slice, and golden carrot. On
`native-9f42064-ca27c19e4052`, matching [launch and first hit](tools/test-potato-cannon-ammo-batch.py)
met Java for all six types in headless solo and LAN. Eight mixed
inventory and offhand cases also matched. Actual second-shot
[cooldown captures](fixtures/potato-cannon-batch-cooldown-java.csv)
matched in muted offscreen solo and LAN, refiring at 15 ticks for
potato, 12 carrot, 10 apple, 5 beetroot, 8 melon slice and 15 golden
carrot and then entering cooldown again. The projectile pack hash
above is unchanged.

The [Java save probe](tools/java-potato-projectile-save.patch) records
that reloading a fired apple projectile preserves the full three-apple
source stack and owner UUID. The [headless solo reopen](tools/test-potato-projectile-save.py)
on `native-9f42064-ca27c19e4052` preserved those fields and the Horizon
entity UUID. For a LAN guest, the original `/data` readback substituted
the host UUID for the projectile’s retained shooter. On
`native-9f42064-77debedb6eee`, that readback matched the shooter both
before and after restart in headless solo and LAN. Continued motion
after reopen, custom item components and recovery remain open.

The [carrot-to-farmland Java probe](tools/java-potato-cannon-carrot-farmland.patch)
found that vanilla carrots do not satisfy the pinned crop action’s
planting interface. An actual downward shot hit the top of the farmland
on tick 1 and left the block and the air above it unchanged through tick
5. On `native-9f42064-2260975c4495`, [headless solo and LAN](tools/test-potato-cannon-carrot-farmland.py)
matched launch, consumption, wear, projectile removal and those block
states using the same projectile pack. Other crop-action paths remain
open.

The [offhand Java probe](tools/java-potato-cannon-offhand.patch) captured
five potato and carrot cases, including the selected main hand
taking priority over an earlier matching inventory slot. On
`native-9f42064-77debedb6eee`, the [headless launch replay](tools/test-potato-cannon-offhand.py)
matched the mirrored barrel position and horizontal velocity, ammo
consumption and one durability lost on the offhand cannon in solo
and LAN. The [muted offscreen cooldown replay](tools/test-potato-cannon-offhand-cooldown.py)
matched blocked and accepted shots plus the renewed cooldown in all
five cases, refiring at player tick 15 for potato or 12 for carrot.

The [enchanted and Netherite Backtank Java probe](tools/java-potato-cannon-armor.patch)
recorded six ordinary potato shots with Capacity I, II or III, an empty
or overfilled tank, and one offhand cannon. On
`native-9f42064-6a772ccfc6b8`, the [headless replay](tools/test-potato-cannon-armor.py)
matched tank air, ammunition consumption, durability and projectile
creation in solo and LAN. An overfilled Capacity II Netherite tank
went from 1,550 to 1,496 air. The empty tank incurred one wear, and the
charged Netherite tank spent four air for the offhand shot. Warnings
and additional equipment combinations remain open.

The [baked potato Java probe](tools/java-potato-cannon-baked.patch)
matched the [first hit](tools/test-potato-cannon-baked.py) on
`native-9f42064-1f482346114d` in headless solo and LAN using the same
projectile pack. It sets the fire timer to 60 on tick 2, including when
the target refuses damage or was already burning for longer. Target
health, velocity and projectile removal matched at impact for all
three pigs. The [countdown replay](tools/test-potato-cannon-baked-countdown.py)
matched fire 59 and 58 on ticks 3 and 4 and the corresponding health
in both modes. The pinned baked cooldown replay matched clicks through
tick 16 in both cannon hands, including the second shot on tick 15 and
renewed cooldown, in muted offscreen solo and LAN on the same build.
Later velocities, PvP, visuals and sounds remain open.

The [left-handed launch replay](tools/test-potato-cannon-left.py)
matched Java for both cannon hands on `native-9f42064-d542a1892c07`.
In headless solo and LAN, main-hand and offhand potato shots used the
correct mirrored barrel and velocity, consumed one potato, and wore
the actual cannon once. The six-ammo launch and first-hit batch and
the five right-handed offhand cases also passed in both modes.

The [poisonous potato probe](tools/java-potato-cannon-poison.patch) and
[headless replay](tools/test-potato-cannon-poison.py) matched on
`native-9f42064-a8ee252312ee` in solo and LAN. A normal pig reached
five health and Poison I on impact tick 2, with 160, 159, and 158
effect ticks remaining at samples 2–4. An invulnerable pig took no
damage or poison. Launch, ammo, wear and projectile removal matched,
and left-handed and right-handed offhand regressions passed. The
player-target effect remains unverified.

The [golden and enchanted golden apple replay](tools/test-potato-cannon-gapple.py)
matched Java on `native-9f42064-846e2873d256` in headless solo and LAN
using the same projectile pack. It compares both launch states and
pig impact on tick 1, including health, knockback and absorption.
Regeneration and absorption durations matched for both types through
tick 4, with resistance and fire resistance on enchanted shots.
Poisonous and baked potato preservation passed. The replay uses a
fresh world per case after the combined setup timed out on its second
case. The [100-tick refire probe](tools/java-potato-cannon-gapple-refire.patch)
matched both apple types from player tick 0 through 101 on the same
Horizon build in muted offscreen solo and LAN. The attempts at tick
99 were blocked, tick 100 fired a second shot with one ammo spent and
one wear, and tick 101 used the renewed cooldown.

The [golden-apple cure probe](tools/java-potato-cannon-cure.patch) and
[headless replay](tools/test-potato-cannon-cure.py) matched ticks 0–4
in solo and LAN on `native-9f42064-89e551a852ca` with the projectile
pack. The weakened zombie villager began converting on impact tick 2,
lost Weakness, received Strength I and recorded the shooter. Both
initial timers fell within Java’s random 3,600–6,000 tick range, then
decremented once per tick. The no-Weakness control gained four
absorption points without starting conversion. Both pig regressions
passed. Conversion completion and player-target effects remain open.

The [honeyed-apple Java probe](tools/java-potato-cannon-honey.patch)
and [replay](tools/test-potato-cannon-honey.py) matched launch,
ammunition, wear and pig impact in solo and LAN on
`native-9f42064-782abd1b6fb3` with the projectile pack. A normal pig
took six damage and received Slowness II for 160 ticks at impact
tick 2. The effect decremented through tick 4. The ordinary
invulnerable pig took no damage or effect. On
`native-9f42064-175b1b10f580` with the prepared creative-tab pack,
all four registered impact and refire replays passed, including
the burning invulnerable pig. Poisonous potato, baked potato
and regular golden apple checks passed on 782. The
[actual refire replay](tools/test-potato-cannon-honey-refire.py)
matched [all Java ticks 0–16](fixtures/potato-cannon-honey-refire-java.csv)
in both modes, including a blocked attempt at tick 14 and a second
shot at tick 15 with one ammo spent and one wear.

The [Java player probe](tools/java-potato-cannon-honey-player.patch)
called the projectile’s collision handler on a real ServerPlayer
after launch. Real projectile flight in [Horizon LAN](tools/test-potato-cannon-honey-player.py)
matched the resulting six damage, Slowness II, spent ammo, wear,
and projectile removal in both host-to-guest and guest-to-host
directions on `native-9f42064-175b1b10f580` with the creative-tab
pack. A separate [deterministic ownerless projectile replay](tools/test-potato-cannon-honey-player-ticks.py)
on `native-9f42064-2cabcb22eed2` matched the
[four Java player-tick samples](fixtures/potato-cannon-honey-player-ticks-java.csv)
from the direct hit handler and subsequent player ticks, including
14 health and Slowness II at 159, 158, 157 and 156.
A separate [Java flight probe](tools/java-potato-cannon-honey-player-flight.patch)
launched the actual shot into a registered ServerPlayer. At
[impact tick 2](fixtures/potato-cannon-honey-player-flight-java.csv)
Java removed the projectile, applied 160 ticks of Slowness II and
recorded 14 health and velocity `(0.012983781, 0, 0.259675613)`.
The disposable Java probe disables JourneyMap’s unrelated runtime
join hook to allow the test player to register. Horizon’s real LAN
shots still lack exact initial duration, velocity and flight timing.

The [golden-apple player probe](tools/java-potato-cannon-gapple-player.patch)
used a real Java ServerPlayer with the projectile hit handler.
The [LAN replay](tools/test-potato-cannon-gapple-player.py) matched
ordinary and enchanted player absorption (4 and 16) and every
effect type and amplifier in both shot directions on
`native-9f42064-0dbc59facfe7` with the projectile pack. Horizon
sampled a live target after player ticks, so it compared remaining
durations within Java’s initial values and health within the
19–20 impact-to-regeneration range. Initial effect duration,
impact health, and player flight timing remain open for actual LAN
shots. A separate [ownerless projectile replay](tools/test-potato-cannon-gapple-player-ticks.py)
matched four Java player ticks of health, absorption and all effect
countdowns for both apple types on 2cab with the projectile pack.
Earlier honeyed-player, golden-pig, poison and zombie-villager cure
checks also passed on 0dbc.

The [melon top-face probe](tools/java-potato-cannon-melon-block.patch)
and [north-face flight probe](tools/java-potato-cannon-melon-flight-side.patch)
matched both launches, ammo, wear and impact on
`native-9f42064-2cabcb22eed2` with the projectile pack in solo and LAN.
A downward shot placed the melon on the stone at tick 1. A horizontal
shot spawned a falling melon at the Java position, zero velocity and
age 1 on tick 1. The falling block landed on solid support at tick 2.
Its [replay](tools/test-potato-cannon-melon-side.py) waited for the
block update while the world stayed frozen before sampling the
landing. Ordinary potato launch and first pig impact also passed.
The [melon refire replay](tools/test-potato-cannon-melon-refire.py)
matched [Java ticks 0–21](fixtures/potato-cannon-melon-refire-java.csv)
on the same build in both modes. The tick-19 retry was blocked,
tick 20 fired and spent another melon and wear, and tick 21 remained
on cooldown. In the [occupied top-face replay](tools/test-potato-cannon-melon-occupied.py),
the projectile disappeared at tick 1 and a supported torch remained
through tick 5, matching the [original Java case](tools/java-potato-cannon-melon-occupied.patch)
in solo and LAN with the projectile pack. Other impact directions,
unsupported flight and other occupied destinations remain open.

The Java pumpkin [top-face](tools/java-potato-cannon-pumpkin-block.patch)
and [north-face](tools/java-potato-cannon-pumpkin-side.patch) probes
captured a different ammunition tuple with the same block impact
path. On `native-9f42064-2daa71b5b44b` with the projectile pack,
both replays matched launch, ammo and wear, top-face placement on
tick 1, and the north-face falling block on tick 1 and supported
landing on tick 2. Solo and LAN passed, as did the two melon
preservation cases. The [pumpkin refire replay](tools/test-potato-cannon-pumpkin-refire.py)
matched Java on every tick through 16, with the attempt at 14 blocked and
a second shot at 15. The [torch-occupied top face](tools/test-potato-cannon-pumpkin-occupied.py)
removed the projectile at tick 1 with the torch intact through tick 5.
The [pumpkin pig impact](tools/test-potato-cannon-pumpkin-hit.py) matched
the normal and invulnerable targets at tick 2, including health,
knockback and projectile removal. These three cases passed in solo
and LAN on the same build and pack. Other face impacts remain open.

The [pumpkin-pie GameTest probe](tools/java-potato-cannon-pie.patch)
recorded an accepted hit at tick 2 with pig health 10→3. The
projectile stayed attached at its original relative point, then
slid by 0.007 blocks on the next tick and 0.014 on the following
one. An invulnerable pig kept 10 health and the projectile disappeared
at impact. The [lifetime trace](tools/java-potato-cannon-pie-lifetime.patch)
followed the normal-pig attachment through removal at tick 15 and
absence through tick 20. On `native-9f42064-573de5e0ba2f` with the
projectile pack, the [sticky replay](tools/test-potato-cannon-pie-sticky.py)
matched both outcomes in solo and LAN, including ammunition, wear,
projectile presence, relative position and velocity on every sampled
tick. The honeyed-apple and glistering-melon normal pig controls also
passed. A [controlled moving-pig replay](tools/test-potato-cannon-pie-moving.py)
moved the target by (+2, 0, +1) after tick 3. Both solo and LAN retained
the projectile position through that sample, followed the target at
tick 4 and matched the relative slide through tick 6. A [stationary Java player probe](tools/java-potato-cannon-pie-player-stationary.patch)
with knockback resistance 1 matched [both live LAN directions](tools/test-potato-cannon-pie-player.py)
for damage at tick 2 and attached projectile offset and velocity
through tick 4. On the same 573d build and projectile pack, an
[ownerless headless shot](tools/test-potato-cannon-pie-player-ticks.py)
also matched exact player health and projectile state at ticks 1–4.
A [target-death replay](tools/test-potato-cannon-pie-death.py) killed
the attached pig after tick 3. On the same build and pack, the
projectile detached at tick 4 with vertical velocity −0.1495 and
matched Java position and velocity through tick 8 in solo and LAN.
Default-knockback moving players, free-running targets and save
behavior remain open.

A [Java sticky ammunition probe](tools/java-potato-cannon-sticky-batch.patch)
captured cake, cod, cooked cod, salmon, cooked salmon and tropical
fish. The [extended replay](tools/test-potato-cannon-sticky-batch.py)
on `native-9f42064-f49095b31d17` and the frozen projectile pack
matched all six at ticks 0–20 in solo and LAN. It covers launch,
consumption and wear, damage, attached position and velocity, and
removal at tick 15. Cake used a stack of one and the fish used stacks
of three. Pie lifetime and ordinary potato launch and impact also
passed in both modes. Other targets and feedback remain open for
the batch.

The [pinned Pufferfish probe](tools/java-potato-cannon-pufferfish.patch)
recorded a tick-2 hit, four damage, Poison II for 1,200 ticks, Hunger III
for 300 ticks, and Nausea I for 300 ticks. The projectile attached and
expired at tick 15. The invulnerable pig received no damage or effects
and the projectile vanished on impact. On `native-9f42064-3ec911595d40`
and the archived projectile pack, the [replay](tools/test-potato-cannon-pufferfish.py)
matched both pigs through tick 20 in solo and LAN, including each effect
countdown and the attached motion. Pumpkin Pie lifetime also passed
in both modes on the same build. The [extended pinned probe](tools/java-potato-cannon-pufferfish-slow.patch)
and replay matched all 101 samples in solo and LAN. Poison reduced the
pig to one health on tick 63 and left it there through tick 100. Actual
[LAN player impacts](tools/test-potato-cannon-pufferfish-player.py) matched
the 20→16 health change, attached shot, and all three effect amplifiers
with either shooter role. An [ownerless authority replay](tools/test-potato-cannon-pufferfish-player-ticks.py)
matched four exact countdown samples for all three player effects.
Default-knockback movement and longer player effects remain open.

The [blaze cake probe](tools/java-potato-cannon-blaze-cake.patch)
captured a tick-2 hit on a 40-health cow. The normal target took 15
damage and the projectile attached. Invulnerable targets retained 40
health and the projectile disappeared. All three targets, including an
already-burning invulnerable cow, had their fire counter set to 240.
On `native-9f42064-686a6276d3d1` and the archived projectile pack, the
[replay](tools/test-potato-cannon-blaze-cake.py) matched launch, impact,
burning and attachment through tick 4 in solo and LAN. The burning
control initialized its tick-0 fire counter to Java’s captured 119.
Baked Potato impact and Pufferfish sticky preservation passed in solo.

The [empty suspicious-stew Java probe](tools/java-potato-cannon-stew.patch)
recorded three damage and one bowl on an accepted pig hit at tick 2.
An invulnerable target kept its health and produced no bowl. On
`native-9f42064-352d59d17c49` and the archived projectile pack, the
[entity replay](tools/test-potato-cannon-stew.py) matched ticks 0–4
in solo and LAN. Its [wall impact](tools/test-potato-cannon-stew-block.py)
matched the tick-1 hit, removed projectile and one bowl through tick 3.
A [tick-paced refire](tools/test-potato-cannon-stew-refire.py) matched
all 42 inventory samples and a second shot at sample 40 in both modes.
The precise LAN authority interval, stew effects and recovery upgrades
remain open. The [seeded Java chorus fruit probe](tools/java-potato-cannon-chorus.patch)
teleported its target on impact, which the baseline does not yet support.

A [dual-effect suspicious-stew probe](tools/java-potato-cannon-stew-effects.patch)
and [replay](tools/test-potato-cannon-stew-effects.py) matched normal
and invulnerable pigs on `native-9f42064-d9385526d9cd` in solo and
LAN. At tick 2, the normal pig gained Night Vision I for 100 ticks
and Weakness I for 160 ticks. Both effects decremented exactly
through tick 4. Damage and bowl state matched, including no effects
or bowl for the invulnerable pig. Empty-stew preservation also passed.

The [seeded Java berry launch probe](tools/java-potato-cannon-berries.patch)
captured three projectiles for Sweet and Chocolate Berries, and two
for Glow Berries. [Actual launch replays](tools/test-potato-cannon-berries.py)
on `native-9f42064-3cc5408f35bf` matched those counts, barrel position,
distinct motion in Java’s 0.1 cone, one consumed item and one wear
in solo and LAN. A [separate refire](tools/test-potato-cannon-berries-refire.py)
matched all 12 tick-paced inventory samples, including a second
shot at sample 10 for all three berries in both modes. The replay
does not set both runtimes to the same random state. Exact specific
vectors and authoritative LAN refire timing remain open. A separate
[controlled Glow Berries replay](tools/test-potato-cannon-glow-control.py)
matched a single Java ownerless projectile in solo and LAN on the
same build. It dealt two damage at tick 1 and applied Glowing I for
200 ticks, counting down through tick 4. The invulnerable control
received neither damage nor effect. The [Sweet and Chocolate Berries control](tools/test-potato-cannon-berry-control.py)
also ran on `native-9f42064-fe00c2f5ddec` in solo and LAN. The
normal pigs took three and four damage respectively on tick 1,
and the replays matched motion and projectile removal through tick 4.
The invulnerable pigs took no damage. Random split-shot impacts and
player effects remain open.

The [headless owner authority replay](tools/test-potato-cannon-gapple-authority-refire.py)
on `native-9f42064-69fd2b989c04` matched all 102 player ticks for
ordinary and enchanted golden apples. Both shots were blocked at 99
and fired at 100. One frozen live LAN client replay observed the
enchanted inventory change at sample 99. An isolated rerun passed.
The [guest shot trace](tools/test-potato-cannon-gapple-guest-shot-clock.py)
on `native-9f42064-759bd1b35a4e` records successful shots on the
authority player clock. Both variants fired 100 ticks apart in the
measured run. The guest replay checks the 100-tick minimum because
networked input may arrive after the first eligible tick.

The [Glistering Melon Slice probe](tools/java-potato-cannon-glister.patch)
recorded a tick-1 pig impact with health 10→5 and Glowing for 100 ticks,
then the 99, 98 and 97 tick countdown. Invulnerable targets retained
10 health with no effect. The projectile disappeared on impact in both
cases. On `native-9f42064-69fd2b989c04` and the projectile pack,
the [impact replay](tools/test-potato-cannon-glister.py) matched launch,
ammunition, durability and impact in solo and LAN. The
[refire replay](tools/test-potato-cannon-glister-refire.py) matched Java
ticks 0–9, including a blocked attempt at 7 and a shot at 8. The prior
poisonous potato and honeyed apple hit replays also passed in both modes.
The [server-player direct-hit probe](tools/java-potato-cannon-glister-player.patch)
recorded 15 remaining health, Glowing I for 100 ticks, knockback and
projectile removal. In [both live LAN directions](tools/test-potato-cannon-glister-player.py)
the target retained 15 health and had Glowing I after the sampled
network delay. Projectile removal, ammo and wear matched. The initial
duration and exact knockback remain open for the live player replay.

## Minecart Coupling creation and removal

The [pinned Java server probe](tools/java-minecart-coupling.patch) coupled
two carts three blocks apart and consumed one coupling. On
`native-9f42064-28b595fa9e6b`, two actual [solo clicks](tools/test-minecart-coupling.py)
and [LAN guest clicks](tools/test-multiplayer-minecart-coupling.py) reproduced
the pair, three-block length, and one-item cost. The solo replay checked the
cart identities after reopening, rejected a repeat click on the same cart and
an overlength pair without consumption. A Wrench removed the link and
refunded the coupling in both modes.

The [middle-cart Wrench probe](tools/java-minecart-coupling-wrench-save.patch)
removed both links from a three-cart chain, refunded two couplings and
kept all controller sides empty when Java recreated the carts from NBT.
On `native-9f42064-90b9392ccb4f`, the [Horizon restart replay](tools/test-minecart-coupling-wrench-restart.py)
matched both refunds and link removal after a complete world reopen in
solo and LAN. The same survival guest rejoined without a forced mode and
recoupled the retained carts, consuming two couplings. Single-cart chunk
unload remains unverified.

The [reversed four-cart Java probe](tools/java-minecart-coupling-four-reverse.patch)
observed controller traversal in ascending UUID bucket order despite
reversed link creation. All [81 samples](fixtures/minecart-coupling-four-reverse-java.csv)
matched in solo on `90b9392ccb4f` and `f49095b31d17`, and the LAN guest
replay matched all 81 on the latter, including the independent cart.

The [Java damage probe](tools/java-minecart-coupling-chain-destroy.patch)
destroyed the middle cart of a live linked chain, clearing both
surviving controller links and dropping two couplings. Build
`3ec911595d40` left two stale markers and dropped no couplings in solo
or LAN. On `native-9f42064-686a6276d3d1`, the [actual player attack replay](tools/test-minecart-coupling-chain-destroy.py)
cleared both links, kept both surviving carts and restored inventory
from one to three after pickup in both modes. Wrench restart and
reversed order preservation passed in solo. Unloaded neighbors and
other removal paths remain open.

The [Java command-removal probe](tools/java-minecart-coupling-chain-kill.patch)
and [Horizon replay](tools/test-minecart-coupling-chain-kill.py) tested
the same linked chain with the middle cart removed by `/kill`. The
previous Horizon build left both markers and spawned no coupling
items. On `native-9f42064-27315d94ff35` both links were removed and
both dropped items were collected in solo and LAN. Solo player-damage
removal still passed.

The [shielded Java TNT probe](tools/java-minecart-coupling-chain-tnt-shield.patch)
and [actual player replay](tools/test-minecart-coupling-chain-tnt.py)
kept both links during priming. Detonation cleared both, dropped two
couplings, and left the shielded endpoints present. The
[pickup replay](tools/test-minecart-coupling-chain-tnt-pickup.py)
collected both items and left none on the ground. Build
`native-9f42064-e8609cbeddb0` matched both scenarios in solo and LAN.
Java's pickup probe used direct player touch, and Horizon's player moved
onto each drop. The solo command-removal replay also passed.

A separate [flaming-arrow Java probe](tools/java-minecart-coupling-chain-flaming-arrow.patch)
detonated the shielded TNT cart within five ticks, with both end
carts remaining and two coupling drops. On
`native-9f42064-fe00c2f5ddec` and the exact-shape pack, the
[replay](tools/test-minecart-coupling-chain-flaming-arrow.py) matched
the links and drops in solo and LAN. The Horizon player collected
both items. Java pickup is outside this arrow scenario's comparison.

The [Java motion probe](tools/java-minecart-coupling-motion.patch) records
[21 ticks](fixtures/minecart-coupling-motion-java.csv) of two ordinary
minecarts on a flat straight rail. On `native-9f42064-1756a1393652`,
the [solo replay](tools/test-minecart-coupling-motion.py) and [LAN replay](tools/test-multiplayer-minecart-coupling-motion.py)
matched both carts' positions and velocities on the host at every sampled
tick. The LAN guest created the link. The separate stationary coupling and
Wrench lifecycle tests also passed on this build. Curves, slopes, chains,
moving-cart targeting after teleport, and link rendering remain open.

On `native-9f42064-c55944e6c518`, real solo and LAN clicks verified
that switching away cancels the player's pending selection. Solo kept
the selection when the coupling was in the offhand. On LAN one player's
switch did not clear the other player's selection. The original Java
client tick supplies the cancellation rule; these replays exercise it
through Horizon player inputs. The [chain probe](tools/java-minecart-coupling-chain.patch)
also verifies that Java supports a three-cart chain and rejects a loop.
On `native-9f42064-fd31bbbadf29`, the [solo](tools/test-minecart-coupling-chain.py)
and [LAN guest](tools/test-multiplayer-minecart-coupling-chain.py) replays
matched the two links, item cost and rejection of the loop. A Wrench on
the middle cart refunded both couplings in either mode, and the solo
chain survived restart.

A [fixed-UUID Java probe](tools/java-minecart-coupling-chain-motion.patch)
recorded 21 motion ticks for a straight, flat three-cart chain. The
[solo](tools/test-minecart-coupling-chain-motion.py) and
[guest-created chain](tools/test-multiplayer-minecart-coupling-chain-motion.py)
matched on `native-9f42064-3d850878bfb6`. The
[reversed UUID order](fixtures/minecart-coupling-chain-motion-reverse-java.csv)
also matched 21 solo ticks on that candidate. An unrelated pair still
disabled the chain solver on that build, while the [Java independence
probe](tools/java-minecart-coupling-chain-motion-independent.patch) held
the same chain trace. The component-scoped correction on
`native-9f42064-5d6b1dcd736b` passed all 21 ticks with the separate pair
present and passed the isolated chain and standalone pair regressions in
solo and LAN, plus reversed order in solo. The pinned Java
[A-before-B](fixtures/minecart-coupling-collision-ab-java.csv) and
[B-before-A](fixtures/minecart-coupling-collision-ba-java.csv) probes
produced distinct results for the same colliding UUID buckets. Colliding
buckets, controller refresh and collection growth history, hard
corrections, slopes and unloaded carts remain open.

The [two-cart Java curve probe](tools/java-minecart-coupling-curve.patch)
recorded [81 samples](fixtures/minecart-coupling-curve-java.csv) on a flat
rail with a south-west curve. Horizon originally matched through tick 13
and first diverged in coupling velocity on tick 14 as the second cart
entered the curve. On `native-9f42064-467b1b74c4cd`, the
[solo](tools/test-minecart-coupling-curve.py) and
[LAN guest](tools/test-multiplayer-minecart-coupling-curve.py) replays
matched both carts’ positions and velocities within 0.00001 through
entry and exit. Straight pair, straight chain, reversed ordering and
separate pair regressions also passed. This covers a low-stress pair
with at most one cart on a flat curve.

The [two-curve Java probe](tools/java-minecart-coupling-two-curves.patch)
recorded 81 samples below the hard-correction threshold. Candidate
`native-9f42064-76c03a3f0d39` matched all 81 coupled samples in
[solo and LAN](tools/test-minecart-coupling-two-curves.py), including
the small curve-to-straight movement at tick 7. The linked carts use
Java 1.21.1’s resolved movement threshold. The independent Horizon
cart matched through tick 77 and first differed at tick 78, where
Horizon advanced by about 0.000216 blocks on each horizontal axis
while Java stayed in place. Single-curve, cardinal slope, straight
pair, straight chain and flat hard correction preservation passed.
A [strong two-curve probe](tools/java-minecart-coupling-two-curves-hard.patch)
captured [81 ticks](fixtures/minecart-coupling-two-curves-hard-java.csv)
and the [first correction phases](fixtures/minecart-coupling-two-curves-hard-java-phases.csv).
On `native-9f42064-dce2c7d786df`, the linked pair matched all 81 ticks
in solo and guest LAN. The hard move displaced the lead cart on tick 1.
On tick 2, the offset tracks still needed the three-dimensional soft
correction. The independent strong control matched all 81 ticks in
both modes. The soft two-curve pair and flat hard and straight-rail
controls also passed.

The [three-cart Java probe](tools/java-minecart-coupling-chain-curve.patch)
recorded [81 ticks](fixtures/minecart-coupling-chain-curve-java.csv)
with two links crossing straight and curved track and a separate
parallel cart. Horizon initially skipped the second link’s curved
projection on tick 1. The first fix matched ticks 0–75. The next
fix applies Java’s near-zero stress cutoff to straight corrections.
The [replay](tools/test-minecart-coupling-chain-curve.py) then matched
all 81 ticks for both links and the independent cart in solo and LAN
on `native-9f42064-761341ecc5dd` with the projectile pack. The
standalone parallel-cart control also matched 81 ticks in solo and
LAN on 175b and 761. An independent [mirrored Java probe](tools/java-minecart-coupling-chain-curve-mirror.patch)
captured a westward chain entering a south-east curve. Its
[81 samples](fixtures/minecart-coupling-chain-curve-mirror-java.csv)
matched both the chain and parallel cart in solo and guest LAN
on 761, with an additional standalone solo replay. Straight pairs,
forward and reversed straight chains,
and the strong two-curve pair passed on 761. Other curve layouts,
strongly stressed chains remain open.

The [ascending-east three-cart probe](tools/java-minecart-coupling-chain-slope.patch)
captured the second link’s soft correction on tick 23 as its lead cart
entered the slope. The [Horizon replay](tools/test-minecart-coupling-chain-slope.py)
matched [all 81 ticks](fixtures/minecart-coupling-chain-slope-java.csv)
for the chain and separate flat-rail control on
`native-9f42064-c39fe54a89a4` with the projectile pack, in solo and
LAN. Standalone controls also passed in both modes. Flat straight,
reversed and mixed-curve chains and the strong two-curve pair passed
on the same build. The [mirrored ascending-west Java probe](tools/java-minecart-coupling-chain-slope-west.patch)
reproduced the same tick-23 transition. On `native-9f42064-2cabcb22eed2`
with the projectile pack, the chain and standalone control matched
[all 81 ticks](fixtures/minecart-coupling-chain-slope-west-java.csv)
in solo and LAN. The east and mixed flat-curve preservation replays
also passed. Separate [ascending-north](tools/java-minecart-coupling-chain-slope-north.patch)
and [ascending-south](tools/java-minecart-coupling-chain-slope-south.patch)
Java probes reproduced the same transition along the Z axis. Both
chains and separate controls matched all 81 ticks in solo and LAN
on `native-9f42064-25bc691de170` with the projectile pack. The
east, west, straight and mixed-curve replays also passed.
The [strong flat-chain probe](tools/java-minecart-coupling-chain-hard.patch)
recorded Java’s order for each link. On tick 1, the first hard
correction moves both carts before the second link reads their
positions and velocities. Horizon now uses the existing
collision-aware hard correction at that point in the recognized
flat-chain path. The [replay](tools/test-minecart-coupling-chain-slope.py)
matched all [81 ticks](fixtures/minecart-coupling-chain-hard-java.csv)
for the chain and independent cart in solo and LAN on
`native-9f42064-e4ca973fe31c` with the projectile pack. Standalone
solo and LAN controls, straight and mixed-curve links, the south
slope and the isolated strong pair also passed. The [far-edge expansion probe](tools/java-minecart-coupling-chain-expand.patch)
then matched [all 81 ticks](fixtures/minecart-coupling-chain-expand-java.csv)
for the chain and independent cart on the same build in solo and
LAN. Its first link was unstressed at tick 1. The second link’s
hard phase moved both endpoints 0.15 blocks toward each other.
Hard corrections on sloped or curved chains remain open.

The [short rail-end Java probe](tools/java-minecart-coupling-offrail.patch)
showed a tick-6 split when the lead cart left the rail while its mate
remained constrained. Horizon now applies the projected correction to
the railed endpoint and the normalized three-dimensional correction to
the free endpoint in an isolated pair. On `native-9f42064-3dd37c693802`
with the creative-tab pack, the [off-rail replay](tools/test-minecart-coupling-offrail.py)
matched all 81 sampled position and velocity ticks for the pair after
a solo or LAN guest link. The unlinked control matched ticks 0–16
in solo and when run alongside the pair in LAN. At tick 17, its
vanilla movement differs by about 0.000229 blocks in Horizon.

The [two free endpoints Java probe](tools/java-minecart-coupling-both-offrail.patch)
starts both carts airborne and rolls the trailing cart off the short
rail on the first sample. It exercises normalized soft correction at
tick 1 and a collision-aware hard pull at tick 3. On
`native-9f42064-a8c4178aec90` with the creative-tab pack, both solo
and guest LAN matched all [81 sampled ticks](fixtures/minecart-coupling-both-offrail-java.csv).
The separate unlinked control matched ticks 0–11 before a low-speed
movement difference at tick 12. The earlier one-free-endpoint pair
still matched 81 ticks in both modes.

The [three-cart rail-end probe](tools/java-minecart-coupling-chain-offrail.patch)
recorded the 2→3 soft correction at tick 1, hard correction on that
edge at tick 3, and hard correction on edge 1→2 at tick 4. The
[chain replay](tools/test-minecart-coupling-chain-offrail.py) matched
all 81 Java position and velocity samples on
`native-9f42064-06ad48ac67bb` with the creative-tab pack after actual
solo and LAN guest links. The standalone control matched through tick 11 in solo and alongside the pair in LAN.
Flat, strong flat and mixed-curve chains and both isolated rail-end pair
cases passed preservation checks.

The [chain with both endpoints of one edge off rail](tools/java-minecart-coupling-chain-bothfree.patch)
exercised both its normalized three-dimensional soft impulse at tick
1 and hard corrections on consecutive edges at ticks 3 and 4. All
[81 samples](fixtures/minecart-coupling-chain-bothfree-java.csv)
matched on `native-9f42064-b98e915a1aa0` with the creative-tab pack
in solo and LAN. Independent carts matched through tick 11 in both
modes. Broader off-rail layouts and the standalone drift remain open.

The [four-cart straight Java probe](tools/java-minecart-coupling-four-chain.patch)
showed all three links update in Java's UUID-bucket order. The earlier
Horizon candidate skipped the component and differed on tick 1.
The [four-cart replay](tools/test-minecart-coupling-four-chain.py)
matched all 81 position and velocity samples on
`native-9f42064-90b9392ccb4f` with the creative-tab pack after actual
solo and LAN guest attachment. Independent solo and guest LAN controls
also matched all 81 samples. The strong flat and rail-end three-cart
chains passed on the same build. Hash-bucket collisions, longer paths
and other layouts remain open.

The pinned [compression](tools/java-minecart-coupling-hard.patch) and
[expansion](tools/java-minecart-coupling-hard-expansion.patch) probes
capture 31 ticks for a strong push on a flat straight rail. Earlier
Horizon applied the velocity correction but left the first cart at
8.7 instead of Java’s 8.6 on compression tick 1. On
`native-9f42064-1f793c3df7f7`, compression matched in
[solo](tools/test-minecart-coupling-hard.py) and
[LAN](tools/test-multiplayer-minecart-coupling-hard.py), and
[expansion](tools/test-minecart-coupling-hard-expansion.py) matched in
solo. Low-speed straight pair, chain, and curve replays also passed.
This covers dry rideable standalone pairs on the same flat straight
rail. Hard corrections on curves, slopes and chains remain open.

The [ascending-east Java probe](tools/java-minecart-coupling-slope.patch)
recorded 81 ticks through entering, leaving and reversing on the slope.
The independent cart matched before the coupling correction. The
coupled pair first differed in velocity at tick 13, then at tick 25
after the initial three-dimensional correction. The final handover
correction on `native-9f42064-dad0ea237430` matched all 81 samples in
[solo](tools/test-minecart-coupling-slope.py) and
[LAN](tools/test-multiplayer-minecart-coupling-slope.py), with the
maximum absolute difference in the archived solo trace below 0.000000006.
Straight pair, curve, flat hard correction and chain regressions
also passed. The [mirrored west Java probe](tools/java-minecart-coupling-slope-west.patch)
and [solo](tools/test-minecart-coupling-slope-west.py) and
[LAN](tools/test-multiplayer-minecart-coupling-slope-west.py) replays
matched all 81 coupled and standalone samples on
`native-9f42064-6a772ccfc6b8`, alongside east and flat preservation.
The [north–south Java batch](tools/java-minecart-coupling-slope-ns.patch)
and [parameterized replay](tools/test-minecart-coupling-slope-ns.py)
matched all 81 samples in each direction on `native-9f42064-1f482346114d`,
including paired and independent carts in solo and LAN. East, west and
flat checks also passed.

The [strong ascending-east probe](tools/java-minecart-coupling-slope-hard.patch)
applies a controlled velocity impulse to the front cart of a player-linked
pair and to an independent control. Java moves the carts horizontally
and vertically during hard correction after tick 13. On
`native-9f42064-d542a1892c07`, the [solo](tools/test-minecart-coupling-slope-hard.py)
and [LAN](tools/test-multiplayer-minecart-coupling-slope-hard.py)
replays matched all 81 samples. The maximum absolute field error in
the archived solo trace was below 0.00000034. Flat hard correction,
soft slope, curve and chain preservation passed. The mirrored
[west](tools/java-minecart-coupling-slope-hard-west.patch) and
[north–south](tools/java-minecart-coupling-slope-hard-ns.patch) probes
also matched all 81 samples in each direction in solo and LAN on
`native-9f42064-148becc3adc3`. East hard, flat hard, curves, straight
pairs and low-speed slope cases passed preservation. These cases
use command-supplied impulses and dry standalone pairs. Chain slopes
and other hard-correction geometries remain open.

## Creative Crate Dropper

The [pinned Java GameTest](tools/java-creative-crate-dropper.patch) compared
a powered Dropper aimed into a filtered crate with one aimed into air. Both
dispensed at tick 4. The crate absorbed its iron ingot without spawning an
item and preserved its seven-gold filter, while the air control spawned an
iron ingot. The [solo and LAN replays](tools/test-creative-crate-dropper.py)
matched all 26 observations on `native-9f42064-28b595fa9e6b`.

## Creative Crate supply

On `native-9f42064-1d51b8455a4f`, the [Creative Crate replay](tools/test-creative-crate-supply.py)
matched the [Java supply oracle](fixtures/creative_crate_supply-java.csv) in solo and with a LAN guest.
A top value-box click saved a seven-item tagged iron sample without consuming it;
two Brass Funnel extractions each produced 64 iron with its tag while the filter
remained unchanged. An empty-hand top click cleared the filter. Filter items and
their refund behavior, other automation targets, and visual fidelity remain open.


## Super Glue player selection

The pinned [Java selection-packet oracle](tools/java-super-glue-selection.patch)
selected three connected stone blocks, saved the region and measured item wear.
The two server-side availability and consumption calls each wear the held Glue,
so the selected stack gained two damage; starting at damage 97 or 98 broke the
stack while still creating the region. On `native-9f42064-a87d65f7cb67`, the
[solo replay](tools/test-super-glue-selection.py) used actual player clicks,
matched those outcomes and the saved `From`/`To` bounds, then verified the
region after reopening. The [LAN replay](tools/test-super-glue-lan.py) matched
the same normal region and two damage for a guest. The existing Rope payload
replay matched all 66 Java ticks and the train assembly/motion replay matched
all 125 ticks with the corrected wear. Logs are in `.local/super-glue-a87-*.log`.
Removal, other connectivity and inventory cases, selection rendering and
particle/sound effects remain open.

On `native-9f42064-435d7a419078`, the [refund replay](tools/test-creative-crate-refund.py)
matched all four [Java short-interaction cases](fixtures/creative_crate_refund-java.csv)
in solo and LAN. In Survival, insertion consumed the tagged List Filter. In
Creative, the held copy stayed in the hotbar. Replacing the stored filter with
seven iron ingots refunded the tagged item when the inventory held no copy or
a copy with different components. An exact component match suppressed the
Creative refund. The fixture checks the normalized block data and unchanged
count of the seven held iron ingots. The [Java probe](tools/java-creative-crate-refund.patch)
records the original interaction outcomes and the component comparisons.

On `native-9f42064-3fa96025b369`, a real Brass Funnel took 16 tagged iron
ingots from a crate filtered to a sample with a 16-item stack limit. The
[Java supply probe](tools/java-creative-crate-supply.patch) measured the same
cap and refused an exact request above it. Horizon also refused the request
for 17 and filled two exact requests for nine. The ordinary 64-item, capped
and exact [replays](tools/test-creative-crate-supply.py) passed solo and LAN
while keeping the tagged sample and the crate filter.

On `native-9f42064-e663362abd53`, the muted filter replay recorded one
item-frame insertion cue for each of the two crate clicks. Its block
position, category, 0.25 volume, and 0.1 pitch match the Java source.
Playback was observed in solo and on both offscreen LAN clients.

On `native-9f42064-acab1def3fd5`, the [vanilla Hopper replay](tools/test-creative-crate-hopper.py)
matched all 21 [Java observations](fixtures/creative_crate_hopper-java.csv)
in solo and with a LAN guest setting the Crate filter. The Hopper below
took one tagged iron ingot at ticks 1, 9, and 17. The adjacent Hopper
discarded one gold ingot into the Crate on those same ticks. The filter's
seven-item sample stayed intact, and the player kept all seven held
ingots. Horizon uses the existing Hopper scheduler and inventory events
for both directions.

On `native-9f42064-f8b38d39a1e0`, the expanded Hopper replay matched
all 84 samples from four Java cases in each mode. The empty crate still
consumed incoming items. The two powered Hoppers transferred nothing.
A full receiving Hopper retained its cobblestone while the sending Hopper
continued to discard gold. These comparisons cover a stationary arrangement.


## Shadow Steel and Refined Radiance dropped motion

The [Java GameTest](tools/java-legacy-material-float.patch) spawned
both metals and an iron control motionless in the air. Horizon initially
let all three fall. On `native-9f42064-83fec42eba70`, the [headless
replay](tools/test-legacy-material-float.py) matched the metals' height,
velocity, and saved no-gravity flag on every sampled tick. The iron
control fell within 0.0000001 blocks of the Java measurements with
Horizon’s float32 drag. All 26 observations passed in solo and on the
LAN host, and a real guest saw both metals remain at their initial height.

The [original Void GameTest](tools/java-legacy-material-void.patch)
captured Chromatic Compound falling below the Overworld. On
`native-9f42064-7d2822469898`, the muted solo replay matched the nine
[Java samples](fixtures/legacy-material-void-java.csv). The three-item
stack converted on tick 4, and on tick 5 it gained the rise, no-gravity
and sound-suppression flags. Positions, velocities and fall distance
matched within 0.0000003, accounting for Horizon's underlying drag.
Refined Radiance conversions, visible effects and conversion across
a restart remain open.

On `native-9f42064-9ac150228fd1`, the [Funnel insertion replay](tools/test-creative-crate-funnel-insert.py)
matched [Java's actual Funnel uses](fixtures/creative_crate_funnel-java.csv) in solo
and LAN: two five-gold stacks entered the crate through an Andesite Funnel,
while its seven-iron supply filter remained unchanged. A Brass Funnel then
extracted iron from the same crate. Chutes and other insertion paths remain open.


## Observed train name display

The pinned [Java source oracle](tools/java-observed-train-source.patch) recorded
an empty value without an observed train, the train name during the observer's
eight-tick keepalive, and an empty value after expiry; passive refresh is 400
ticks. On `native-9f42064-eaa55eaaa5bb`, the [moving-train replay](tools/test-observed-train-display.py)
assembled and drove a train across a Track Observer: its Nixie text changed from
blank to `Unnamed Train` at tick 38 and back to blank at tick 60. A LAN guest
configured the source through the Display Link screen and the same authoritative
text transitions passed. The Java source oracle used a controlled observer and
train identity; it did not reproduce the full moving-train timeline. Logs are
`.local/observed-train-display-eaa-solo.log` and
`.local/observed-train-display-eaa-lan.log`. Other train and station sources,
announcements, audio and pixel-level rendering remain open.

## Java schematic capture and import

The [pinned Java SchematicExport replay](tools/java-schematic-capture.patch)
exported a reversed-corner selection containing stone, oak stairs,
Structure Void, and a named chest. The [original compressed
NBT](fixtures/schematic_capture-java.nbt) placed all four explicit
states on `native-9f42064-26ae14e31627`. The original Structure Void
cleared a granite block, and an omitted air cell left its granite block
in place. The authoritative chest name matched exactly as plain text.
A separate Horizon capture and placement replay preserved block entity
names and the same geometry. The current import covers the original
1.21.1 plain component name. Styled names, exporting back to Java, and
Quill selection through its original UI remain open. The muted LAN replay
on the same candidate confirmed that a real guest could open the imported
chest and see its original title, `capture chest`.

APP-2092 adds a bounded player-facing Quill path: two main-hand clicks select
inclusive corners, sneaking cancels, an anvil name is sanitized (or defaults
to `schematic`), duplicate names receive a suffix, and the export is saved in
the authoritative world's generated template directory. The exported
Schematic item retains the template ID and enters the existing placement
flow. Quill exports turn Structure Void cells into explicit air while
omitting ordinary air. The Table now has a persistent input/output container
and a Load Template action for an existing, registered Schematic item. The
focused offscreen host replay in `tools/test-schematic-capture.py` passed on
`native-9f42064-1811f947e145` with `--java` and the pinned 26.3 resources. It
covers malformed and oversized selections, unsafe and duplicate names, Quill
retention, Structure Void clearing, named block-entity data, world reopen,
rejected Table insertion, template loading, and Table input/output save and
reopen. The Java fixture placed every block and property and preserved its
named chest.

A separate `--lan` attempt did not reach guest assertions: the guest loaded
resources, disconnected before the host logged a join, and `joined_client`
timed out after 45 seconds. The earlier Java chest guest-open evidence remains
valid; this pass claims no new guest Table or Quill action. The Table load
action operates on a template-backed Schematic item already in the world. The
local `.nbt` file picker and Java's chunked upload, the editable placement
preview and separate edit controls, and the original Java prompt screen
remain open. The checks are registered under `schematic-capture` and
`schematic-java-import-lan` in `tools/test-parity.py`.


## Creative Crate Chute delivery

The [Java oracle](tools/java-creative-crate-chute.patch) captured the
downward Chute sending five gold into the crate at tick 6. On
`native-9f42064-26ae14e31627` the [Horizon replay](tools/test-creative-crate-chute.py)
matched all 13 held-count samples and retained the crate's seven-iron supply
filter. The LAN replay compared authoritative host samples and confirmed that
the guest could see both blocks. On `native-9f42064-1f2743f4b4c4` an
[upward fan-fed Chute](tools/java-creative-crate-upward-chute.patch) also
matched all 13 Java count and position samples solo and with a LAN
observer. The crate received five gold at tick 6 and the empty Chute
retained its position at 1.0, matching Java capability semantics.

The [upward Chest-capacity fixture](tools/java-upward-chute-capacity.patch)
matched all [19 Java samples](fixtures/upward_chute_capacity-java.csv) in
solo and with a LAN observer on `native-9f42064-0f8d0190e661`. A full
Chest held the Chute's item at 0.5. After two spaces opened, two items
entered on tick 10 and three remained. When an empty slot opened,
the three remaining items entered on tick 14.

## Mounted train sliding doors

A [pinned Java GameTest](tools/java-scheduled-train-doors.patch) assembled
two two-block train doors and scheduled an actual trip. The [123-sample
trace](fixtures/scheduled-train-doors-java.csv) captures both doors open at
the origin, all four halves closing on tick 29 after departure, Terminal
arrival at tick 102, and only the north halves opening at tick 103.
The [Horizon replay](tools/test-scheduled-train-doors.py) on
`native-9f42064-0400962737f7` matched all samples in solo, including
the two doors' four `open` states, train speed and arrival. A real LAN
guest assigned the schedule and the host matched the same 123 samples. The fixture
sets Terminal's north-only mode in station data.

On `native-9f42064-298f4f6553ef`, the [station selector replay](tools/test-station-door-modes.py)
used the real screen to select all six modes in solo and LAN, closing and
reopening after each change; the solo result also survived a world reload.
The [player-configured trip](tools/test-station-door-control.py) selected NORTH
at Terminal through the same screen and matched all 123 Java samples in solo
and with a LAN guest. The selector's order and save behavior follow the pinned
Java StationScreen and StationEditPacket source; the Java trip trace itself
sets the mode directly.

The [Java platform-door fixture](tools/java-train-platform-doors.patch)
placed two aligned Iron Doors beside the mounted doors at the origin.
On `native-9f42064-3b57c0072b2a`, the origin hardware matched all eight
[Java samples](fixtures/train-platform-doors-java.csv) in solo and on a LAN host after the guest assigned the schedule. Both
platform doors were open through tick 28 and closed on tick 29 when the
mounted doors closed. This trace ends immediately after departure.

The same origin scenario with Create Train Doors on the platform has its own
[pinned Java oracle](tools/java-train-sliding-platform.patch) and [eight-sample
trace](fixtures/train-sliding-platform-java.csv). The [replay](tools/test-train-sliding-platform.py)
matched in solo on `native-9f42064-5fc957a5adb3` and in LAN on
`native-9f42064-90476b859cb6`, including both halves closing on tick 29.

The [terminal-platform replay](tools/java-train-terminal-platform.patch)
uses a fresh Java world and introduces the two platform Iron Doors at
the Terminal on tick 102. The [84 Java samples](fixtures/train-terminal-platform-java.csv)
matched on `native-9f42064-d6a9092ed1ea` in solo and on a LAN host after a guest assigned the schedule. Only the north-side
mounted door and aligned north platform door opened at tick 103, one
tick after the train reached Terminal. Both south doors stayed closed.


The [manual mounted-door oracle](tools/java-manual-train-door.patch) invokes Java’s
actual moving interaction on one assembled Train Door and records both halves
through close, open and their next ticks. The [real-player replay](tools/test-manual-train-door.py)
matched all five [Java rows](fixtures/manual-train-door-java.csv) in solo and
with a LAN guest on `native-9f42064-df0fe61cf5b1`. The manually chosen state
persists while the station controller target is unchanged. This scope uses one
stationary north-facing door.

The [paired-leaf Java oracle](tools/java-paired-train-door.patch) records four
open halves closing together when the left of two adjacent north-facing,
opposite-hinge doors is clicked. Before the fix the clicked leaf closed and the
mate stayed open. On `native-9f42064-77cace12c4d5`, the [player replay](tools/test-paired-train-door.py)
matched all five [Java observations](fixtures/paired-train-door-java.csv)
in solo and with a LAN guest. All four halves closed, stayed closed on the
next tick, reopened, and stayed open on the following tick. Pairing is
limited to an adjacent matching block, facing, and half with opposite hinges
and the same pre-click open state. This replay exercises a straight, stationary
train. A mirrored [right-leaf Java probe](tools/java-paired-right-train-door.patch)
and its [five observations](fixtures/paired-right-train-door-java.csv) also
matched in solo and LAN on `native-9f42064-e0d199cb5609`, using the same
replay with `--right`. Both stationary leaf selections replayed on
`native-9f42064-fd31bbbadf29` in solo and LAN: the two halves of each
leaf changed in the same frozen world tick as the click and persisted
through the explicitly stepped next tick. A [stationary upper-half probe](tools/java-paired-upper-train-door.patch)
matched [all five Java states](fixtures/paired-upper-train-door-java.csv)
when the actual player clicked the upper half of the left leaf on
`native-9f42064-1f793c3df7f7` in solo and LAN. With the same hinge
on both leaves, the [Java probe](tools/java-same-hinge-train-door.patch)
and Horizon replay matched five states on `native-9f42064-6a772ccfc6b8`
in solo and LAN. The clicked leaf changed independently. For reopening,
the fixture aims at the exposed edge of the closed leaf because the
adjacent open leaf also occupies its center ray. The [different-facing probe](tools/java-different-facing-train-door.patch)
likewise matched all five samples on `native-9f42064-846e2873d256` in
solo and LAN. The click on the exposed edge changed the north-facing
leaf while the adjacent south-facing leaf stayed open.

The [mixed-state Java probe](tools/java-mixed-state-paired-train-door.patch)
starts with a closed left leaf and an open right leaf of the same
north-facing pair. On `native-9f42064-2cabcb22eed2` with the creative-tab
pack, the first actual click opened just the left leaf. With their
states now equal, the next click closed both. All
[five observations](fixtures/mixed-state-paired-train-door-java.csv)
matched in solo and LAN, including the next tick after each click.

The independent [east- and west-facing Java probes](tools/java-end-facing-paired-train-door.patch)
returned the same five states as the north-facing pair. With the
left or right leaf clicked from its matching end of the carriage,
`native-9f42064-2cabcb22eed2` matched all four door halves at the
click and next tick in both directions, solo and LAN, with the
creative-tab pack.

The [paired door save probe](tools/java-paired-train-door-save.patch)
serialized and reloaded Java’s carriage contraption in both manually
[open and closed states](fixtures/paired-train-door-save-java.csv).
On `native-9f42064-1f482346114d`, two actual world restarts preserved
all four half states after clicks in solo and after the LAN guest
rejoined. This scope covers the saved block state of the stationary
north-facing pair.

The [moving Java reload probe](tools/java-moving-paired-door-reload.patch)
round-tripped the carriage contraption on the quarter turn while the
panels were at 15% open. Fresh Java door animations use the saved
open flag and the original carriage rotation. The
[open and closed snapshots](fixtures/moving-paired-door-reload-java.csv)
therefore restore to 100% and 0%, respectively. A normal Horizon reopen
advanced several ticks and masked its saved 15% pose. On
`native-9f42064-a2ca986044de` with the creative-tab pack, the exact
saved-tick snapshot matched all four flags, animation endpoints and
world-space panel offsets before any world tick, in solo and for a
world saved during LAN play. Both states also remained correct after
the host reopened normally and the guest rejoined.

The [moving left](tools/java-moving-paired-train-door.patch) and
[moving right](tools/java-moving-paired-right-train-door.patch) Java probes
sample a north-facing pair between stations at ticks 51–54. On
`native-9f42064-fd31bbbadf29`, the [left-leaf trace](fixtures/moving-paired-train-door-java.csv)
and [right-leaf trace](fixtures/moving-paired-right-train-door-java.csv)
matched both same-world-tick clicks, next-tick persistence for all four
halves, and speed magnitude at every sample within 0.000002, in solo
and LAN. A [mirrored south-facing Java probe](tools/java-moving-paired-south-train-door.patch)
also matched both moving left-leaf transitions, next-tick persistence
and speed at the [same five samples](fixtures/moving-paired-south-train-door-java.csv)
in solo and LAN on `native-9f42064-3d850878bfb6`. The south door
fixture used the north approach to place the schedule. An independent
[right-leaf Java probe](tools/java-moving-paired-south-right-train-door.patch)
recorded the same five states and speeds. Horizon matched them in
solo and LAN on `native-9f42064-c218e039de3c` with the creative-tab pack.
An independent [east/west Java probe](tools/java-moving-end-paired-train-door.patch)
captured all four facing and clicked-leaf combinations. Horizon matched
the five observations for all four halves and speed at ticks 51–54
for each case in solo and LAN on `native-9f42064-2daa71b5b44b` with
the creative-tab pack. The west-facing centerline click uses a closer
standing position. The original position interrupted the scheduled
acceleration on the tick following the click. With
`CREATE_MOVING_END_UPPER=1`, the Java probe clicked the upper half of
either leaf in both facings. All eight Horizon solo and LAN upper-half
replays on `native-9f42064-3dd37c693802` matched the same five
observations and four speeds. A separate [north/south upper-half Java probe](tools/java-moving-side-paired-upper.patch)
produced the same five observations and four speeds for either leaf in
both facings. All eight Horizon north and south upper-half replays
matched in solo and LAN on the same build and pack.

The earlier train renderer left the mounted andesite and copper
folding panels at progress 0.0 during the station's close transition.
The [headless Java render transform probe](tools/java-train-folding-door-animation.patch)
uses the original chaser and renderer transform sequence. The
[station replay](tools/test-train-folding-door-animation.py) matched all
72 display submissions across 18 ticks on `native-9f42064-06ad48ac67bb`
with the creative-tab pack. It compares an andesite north-facing left
hinge and a copper south-facing right hinge, including both panes,
each submitted translation and rotation, the open states, and timed
opening and closing cues. Solo and LAN passed, with the host and guest
both receiving the cues. Ordinary stationary and moving paired doors,
a cold reload and the elevator service replay also passed on this build. The
same Java probe also captured east and west. On
`native-9f42064-f2fcebd19cb9` with the creative-tab pack,
the east-facing andesite left hinge and west-facing copper right
hinge matched 72 further panel submissions and both timed cues
in solo and LAN.

The [moving andesite and copper pair probe](tools/java-moving-material-paired-door.patch)
then verified the manual click on the lower north-facing left leaf.
On `native-9f42064-06ad48ac67bb`, Horizon failed to open the
four halves. The interaction path now uses the original block's
bounds and only links a matching material. A guest can target the
folding panes using the original door state and carriage pose.
`native-9f42064-b98e915a1aa0` with the creative-tab pack matched
all five state observations, four speed samples, one immediate open
cue and no immediate close cue for each material in solo and LAN.
The immediate audio checks use the shared Java sliding-door cue.
The same pinned probe also recorded brass and framed-glass pairs.
Both matched all five states, four speed samples and immediate cues
on the same Horizon build and pack in solo and LAN.
With an andesite left leaf next to a copper right leaf, the
[mixed-material Java samples](fixtures/moving-paired-mixed-materials-train-door-java.csv)
recorded only the andesite half-pair opening and closing.
`native-9f42064-f2fcebd19cb9` reproduced all five states, four speeds
and immediate cues in solo and LAN with the creative-tab pack. Both
folding materials also passed the [quarter-turn Java probe](tools/java-curved-folding-paired-door.patch):
an actual lower-left click on the rotating carriage matched all five
door states and speed samples at ticks 76–79 in solo and LAN, on
`native-9f42064-90b9392ccb4f` with the creative-tab pack.

The [pinned fresh folding probe](tools/java-train-folding-door-animation.patch)
constructed both original block entities. Java starts at progress 0
for a saved closed state and 1 for a saved open state. Horizon had
retained 0.85 at a mid-close save. On
`native-9f42064-90b9392ccb4f` with the creative-tab pack the
[headless cold snapshot](tools/test-train-folding-door-animation.py)
matched the fresh chaser, states and all four model positions and
angles before advancing the saved world tick. Both open and closed
scenarios passed solo and after a LAN guest rejoined. The train pose
and folding rotations are stored separately in the display transform.

The [moving left-leaf sound probe](tools/java-moving-paired-door-audio.patch)
recorded [one immediate opening cue and no immediate closing cue](fixtures/moving-paired-train-door-audio-java.csv).
The muted software mixer on `native-9f42064-5d6b1dcd736b` matched that
cue count and sound, Blocks category, 0.3 volume and Java’s pitch range
in solo and on both LAN listeners. Exact pitches depend on RNG.
The same cue checks passed in solo and LAN on
`native-9f42064-2daa71b5b44b` with the creative-tab pack for the
north-facing right leaf and either south-facing leaf. These replays use
the north-left Java sound capture. Java selects the cue independently
of the leaf's facing and hinge.

With the pair under station control, `native-9f42064-9232e2103643`
matched all 18 [Java chaser samples](fixtures/train_door_animation-java.csv)
for both halves of both north-facing leaves, plus the south-facing
control door. The [panel replay](tools/test-train-door-animation.py)
compares opposite slide directions, linear progress, facing offsets
and one closing cue per leaf on sample 7 in solo and on both LAN
listeners. On `native-9f42064-467b1b74c4cd`, real manual clicks while
stationary matched these same 18 chaser samples for the four panels in
solo and LAN, including one close cue per paired leaf on sample 7.
The unclicked south-facing leaf remained fully open. On
`native-9f42064-b3c30e2c5917`, manual clicks while a straight
train remained at speed matched the same 18 progress samples for all
four north-facing panels, opening first and then closing. All four
display translations matched the Java renderer’s slide and normal
offsets on each step. The muted mixer matched both delayed close cues
on the solo client and on both LAN listeners. On
`native-9f42064-c218e039de3c` with the creative-tab pack,
north-facing right-leaf and both south-facing leaf clicks also
matched all 18 samples for all four panels and both closing cues,
in solo and LAN. South panels move along the same slide axis with
the facing-normal offset mirrored, as in the Java renderer.

On the pinned Java quarter turn, the [left-leaf probe](tools/java-curved-paired-train-door.patch)
and [right-leaf probe](tools/java-curved-paired-right-train-door.patch)
each captured five states at ticks 76–79 while the train turned.
The [offscreen player replay](tools/test-curved-paired-train-door.py)
aims along each rotated door normal and matched train speed and all
four halves, including both same-world-tick transitions and next-tick
persistence. Left matched solo and LAN on `native-9f42064-e420833b5c2b`,
and right matched solo and LAN on `native-9f42064-1f793c3df7f7`.

The [animation probe](tools/java-curved-paired-train-door-animation.patch)
used the actual Java door states from left-leaf clicks, the original
chaser and the carriage entity’s rotation. Horizon matched all
[nine ticks 76–84](fixtures/curved-paired-train-door-animation-java.csv)
on `native-9f42064-782abd1b6fb3` in solo and LAN. All four
panels matched progress and world offsets after opening at tick 76
and reversing the animation at tick 78. Both closing cues played
at tick 81 on each listener. The fixture now returns the driver
to the controls before each step, matching Java’s mock-player
positioning. Earlier offscreen runs let the driver walk out of
range while waiting to sample frozen ticks. A second pinned Java
run with `CREATE_CURVED_PAIRED_RIGHT=1` yielded identical samples
for right-leaf clicks. The [Horizon replay](tools/test-curved-paired-train-door.py)
matched both leaf inputs on `native-9f42064-175b1b10f580` in solo
and LAN with the prepared creative-tab pack. Other facings and
curve layouts remain open.

A separate [Java moving-train oracle](tools/java-moving-train-door.patch) exercised
the same handler at speed 0.1875 between stations. On `native-9f42064-df0fe61cf5b1`,
real host and LAN guest clicks on a straight moving train matched all five
[Java observations](fixtures/moving-train-door-java.csv), including persistence
on the next tick; the [replay](tools/test-moving-train-door.py) also checks the
interaction proxy follows the train. This covers one north-facing door.

The [controlled Java animation oracle](tools/java-train-door-animation.patch)
ran the same Catnip linear chaser and renderer offset calculation as the
mounted Sliding Door code, starting fully open and then closing and opening.
On `native-9f42064-bb398be739ea`, the [muted replay](tools/test-train-door-animation.py)
matched all 18 [Java samples](fixtures/train_door_animation-java.csv) for both
train-door panels' progress and display offsets in solo and LAN. The muted
software mixer recorded both doors' opening cues on the opening step and local
closing cues one tick after progress reached zero, as Java's `settled()`
requires. The Java oracle controls the chaser rather than capturing a live
client rendering timeline. Moving and rotated folding-door variants and other
mounted door interactions remain open.

The [mounted Trapdoor Java oracle](tools/java-mounted-trapdoors.patch)
invoked Create's moving interaction twice on each of the Train and Framed Glass
Trapdoors. On `native-9f42064-0f8d0190e661`, a host and LAN guest used actual
mouse clicks to match the six [state observations](fixtures/mounted-trapdoors-java.csv).
A click through the empty space above a closed panel left it closed; opening and
closing sounds reached the host and guest at Java's volume and randomized pitch.
The solo replay also restored missing target proxies after a simulated older save
was reloaded and removed them on station disassembly. Interaction metadata is
now sent to clients with the proxy dimensions, so the thin panel is targeted
instead of its full block. The Java test called the moving interaction directly;
the Horizon test exercises player targeting. The [moving-train replay](tools/test-moving-train-trapdoor.py)
also passed in solo and LAN on `native-9f42064-0f8d0190e661`: after travelling
more than 1.5 blocks from the origin, a player opened the north Train Trapdoor
at speed 0.1875, heard the matching cue, and saw its target proxy continue
with the carriage. The Java oracle invoked the same interaction on a controlled
carriage rather than on this live trip. A [separate curved-trip replay](tools/test-rotated-train-trapdoor.py)
passed on the same candidate when a LAN guest clicked the panel center while the
carriage was rotating (heading component 0.604); its state and opening cue
matched the Java interaction. The [separate Java shape oracle](tools/java-rotated-trapdoor-edges.patch)
clipped 50 controlled rays against the original north-facing bottom Trapdoor
shape after a 37° transform. On `native-9f42064-f8b38d39a1e0`, a LAN guest's
[seven inside/outside edge rays](tools/test-rotated-trapdoor-edges.py) matched
those results for the closed and open panel while the train was turning; a glass
block and an armor stand also occluded the panel. The client transforms the ray
into the synced display's local coordinates, and the server checks the reported
hit against the authoritative carriage pose and shape. A [second Java oracle](tools/java-rotated-framed-trapdoor-edges.patch)
measured east-facing top Framed Glass Trapdoor shapes, and a LAN guest matched
14 [edge rays](tools/test-rotated-framed-trapdoor-edges.py) across two nearby
same-type panels on the same candidate, with the neighboring panel unchanged.
Other orientations and collision behavior remain open.

The [pressing category collector](tools/test-pressing-category.py) checks Horizon category data described by the pinned Create JEI registration
and iron pressing recipe on `native-9f42064-64022dd91e36`. In solo and on a LAN guest it
collected the Mechanical Press catalyst and iron ingot to iron sheet. A
host-only world datapack's 50% two-gold output reached the guest, and a
subsequent server tag replacement reached that already connected guest on
`/reload`. The collector itself is a fixture-only consumer; the inventory lookup below
provides a limited player-facing entry point.


The [inventory pressing lookup](tools/test-pressing-lookup.py) on
`native-9f42064-0c674427b610` pressed R over an iron sheet in the survival
inventory and displayed the resolved iron ingot input, iron sheet output and
Mechanical Press catalyst in solo and on a LAN guest. It clicked the rendered
Back button, and checked that R over stone and during gameplay did not open the
panel. This is a single category in the player inventory; JEI's other entry
points, searches, animation, categories and presentation remain open.


On `native-9f42064-f4b621608334`, the same [inventory lookup fixture](tools/test-pressing-lookup.py)
also pressed U over an iron ingot to show its pressing use and the Mechanical
Press, then closed it with Back in solo and LAN. R and U over stone or during
gameplay left the panel closed; R over a sheet and U over an ingot in a chest
screen also left it closed. Other categories and JEI functionality remain open.


The [Millstone lookup](tools/test-milling-lookup.py) on
`native-9f42064-022f2d5b128d` showed the pinned clay-to-four-clay-balls milling
recipe and Millstone catalyst with R and U, and Back closed the panel in solo
and LAN. The category collector exposed all three wheat outputs with their
original counts and chances on both clients. At that build the lookup skipped multi-output recipes; the later panel below
shows them separately. The pressing R/U fixture also passed on this build.


On `native-9f42064-05814e82e495`, the [Millstone lookup fixture](tools/test-milling-lookup.py)
used R over wheat flour and U over wheat, showing the three simultaneous wheat
outputs in separate slots with their counts and 100%, 25%, and 25% labels. The
real Back button, clay lookup and host-to-guest recipe data passed in solo and
LAN; the pressing lookup fixture also passed. This is Horizon's panel, not a
pixel or animation comparison with JEI's original presentation.


The [Sawing lookup](tools/test-sawing-lookup.py) on
`native-9f42064-0f8d0190e661` displayed the original Create cutting recipe
Bamboo Planks → Bamboo Mosaic and Mechanical Saw catalyst using R and U in
solo and on a LAN guest. Its category uses Create cutting recipes; Java's
separate, configurable automatic stonecutting category is not included. The
pressing and multi-output milling lookup fixtures also passed on this build.
The existing [physical Saw replay](tools/test-mechanical-saw.py) compares the
bamboo cut with [Java samples](fixtures/mechanical-saw-java.csv).


The [dry Mixer lookup](tools/test-mixing-lookup.py) on
`native-9f42064-68290498d5eb` showed andesite plus iron nugget into andesite
alloy with no heating required, and copper plus zinc ingots into two brass
ingots with a Heated label. R and U, separate inputs, Mixer and Basin catalyst
icons, and Back passed in solo and LAN. That build omitted fluid recipes;
the later water input below is a narrower extension. Automatic shapeless and
brewing categories remain open. The pressing, milling and
sawing lookup fixtures passed on the same build.


On `native-9f42064-f2cdb7f1ac90`, the [Mixer lookup fixture](tools/test-mixing-lookup.py)
showed the original Dough recipe via R over Dough and U over Wheat Flour in
solo and LAN. Its separate water slot renders the water sprite and shows
Water, 1,000 mB on hover, alongside the flour input, Mixer and Basin catalysts,
and no-heating label. Only exact component-free water inputs are represented;
other fluid ingredients, additional fluid outputs and multi-output mixing remain open.
Pressing, milling and sawing lookup regressions passed on the same build.


On `native-9f42064-e663362abd53`, the [Mixer lookup fixture](tools/test-mixing-lookup.py)
used U over a Honey Block to display its heated 1,000 mB Honey output in solo
and LAN. The output uses Create's Honey sprite and its tooltip names Honey and
the amount; it is a fluid slot, not an item. The original [heated fluid
production replay](tools/test-fluid-food.py) matched all 258 Java samples and
the accompanying Spout replay matched 86. Water, dry Mixer, pressing, milling
and sawing lookup regressions passed. Fluid-focused R lookup and other fluid
ingredients or outputs remain open.


On `native-9f42064-f92c6abe28bd`, the [Mixer lookup fixture](tools/test-mixing-lookup.py)
used U over a Chocolate Bar to show 250 mB Chocolate with Heated, and U over
Mossy Cobblestone to show 50 mB Lava with Super-Heated, in solo and LAN. The
original still textures and hover amounts rendered, and the Honey, water and
dry Mixer cases and pressing, milling and sawing lookup regressions passed.
A targeted [gameplay replay](tools/test-extra-material-recipes.py) also produced
50 mB Lava from each of four cobblestone variants only when superheated.
The Java Chocolate recipe's `c:milk` ingredient is still omitted: no verified
server-authoritative fluid-tag resolver is available to preserve its variants.
Fluid-focused R lookup and other unrepresented fluid forms remain open.


On `native-9f42064-cbdbe7d596c6`, [Copper uses navigation](tools/test-recipe-navigation.py)
pressed U over Copper Ingot and switched between its Copper Sheet pressing and
heated Copper plus Zinc → two Brass mixing recipes by clicking the actual
Mechanical Press and Mechanical Mixer tabs, in solo and LAN. The Mixer page
labels the Basin requirement; Back closed the page. Pressing, milling, sawing
and mixing lookup regression fixtures also passed on this build. Other category
entry points and full JEI presentation remain open.


## APP-1959 Crushing Wheels and controller gameplay baseline

On the rebased final build `native-9f42064-c76d4df0e346` with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`, the
bounded APP-1959 cases passed against Create
`ac0c444d9828da3453ae8cc65338e8de063286fb` and Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`:

- `crushing-wheel-placement` selected the adjacent shaft axis, honored sneak
  orientation override, rejected an invalid adjacent wheel without consuming
  the held wheel, and formed a controller between aligned wheels.
- `stone-crushing` matched 146 Java ticks through cobblestone-to-gravel and
  gravel-to-sand/flint processing and transfer; the final chest held five sand
  and one flint. `mechanical-crafter` matched all 144 Java ticks and produced
  the crafted wheel pair at tick 143.
- `crushing-wheel-rotation` measured same-sign wheel speeds `(128, 128)` as
  invalid, opposing `(128, -128)` as valid at 2.56 speed, and reversed
  `(-128, 128)` as valid facing north. A loaded 64-gravel input and its progress
  remained still while power was stopped, then processing resumed after power
  returned.
- `crushing-wheel-blocked-output` held the guaranteed 64-sand output while a
  Depot was occupied, then transferred it after the Depot was cleared without
  losing or duplicating optional flint and clay-ball outputs.
- `crushing-wheel-reopen` retained idle controller state and active input and
  progress across reopen; active processing continued afterward.
- `crushing-wheel-lan` had a host process 16 gravel while the guest observed the
  active controller, then collected the host's 16-sand output from the shared
  Depot.

The repeatable command is listed in the [README's Crushing Wheels section](README.md#crushing-wheels-and-upward-chutes).
This baseline does not establish exhaustive recipe, mob/entity crushing,
particle/effect, pixel, Java reload, or packet-timing parity; Full 1:1 remains
Open.

The [Crushing Wheel lookup](tools/test-crushing-lookup.py) on
`native-9f42064-90476b859cb6` used R and U and actual category-tab clicks in
solo and LAN. It showed Cobblestone → Gravel in both Milling and Crushing,
and Gravel → Sand, Flint and Clay Ball in Crushing with separate 100%, 10%
and 5% output labels. The category includes Milling recipes unless their first
resolved input matches a Crushing recipe, following the pinned Java JEI rule;
the overlapping Gravel milling recipe is excluded. The original
[stone/cobblestone factory replay](tools/test-stone-crushing.py) matched all
146 Java ticks, and the existing navigation and four lookup fixtures passed.
This does not claim exact JEI animation or complete category parity.


The [Bulk Washing lookup](tools/test-fan-washing-lookup.py) on
`native-9f42064-3f607b317b26` displayed the pinned Gravel recipe, its separate
25% Flint and 12.5% Iron Nugget outputs, and the named Fan behind Flowing
Water. Actual U and R, category tabs and Back passed in solo and LAN; the
Crushing, Copper navigation and Mixer lookup regressions passed as well. The
fixture's [existing physical replay](tools/test-fan-processing.py) compares
the seeded Java gravel processing trace. That build rendered the Fan name
italic; `native-9f42064-7f3945f841a4` explicitly sets it non-italic and passed
the same solo and LAN fixture, with an upright tooltip confirmed offscreen.
Exact JEI presentation remains open.

## Refined Radiance conversion in a beacon beam

The [Java probe](tools/java-legacy-radiance-beacon.patch) captured [27 item
samples](fixtures/legacy-radiance-beacon-java.csv) at ticks 0–8 under an active
beacon beam, a blocked beam and a control without a beacon. Both
[Horizon replays](tools/test-legacy-radiance-beacon.py) matched on
`native-9f42064-f30286a3e7ee`. A stack of three Chromatic Compound turned
into three Refined Radiance on tick 1. On tick 2, it became silent, gained
no-gravity and accelerated upward. Both controls kept falling as Chromatic
Compound. The LAN guest received the converted stack. The existing Shadow
Steel void and ordinary floating materials replays also passed on this build.
The [saved snapshots](fixtures/legacy-radiance-reload-java.csv) capture Java
after conversion and after ascent begins. The Horizon replay reopened each
world at its saved tick and matched item identity, stack, motion and flags
through tick 8.
At the default light threshold, the [charge trace](fixtures/legacy-radiance-charge-java.csv)
matched 14 samples on `native-9f42064-73cd83f87233`. At charge nine the original
compound kept falling. At charge ten it produced a fresh Refined Radiance
entity on tick 1 and began rising on tick 2. The samples include age and charge
data. The [placed-light trace](fixtures/legacy-radiance-collection-java.csv)
matched the first seeded lookup on `native-9f42064-9eef81efe32b`. Visible
Glowstone disappeared and a stack of two split into one uncharged and one
charge-one item. Occluded Glowstone and an unlit block remained unchanged.
Light acquisition from Depots and Belts, synchronized charge display and
remaining random sequences stay open.

APP-2073 adds a finite Depot transport case. The pinned Java path checks a
nearby `TransportedItemStackHandlerBehaviour`, derives the light from a carried
`BlockItem`, and removes one transported item when it collects light. On
`native-9f42064-ecb7b798b6e6` with the prepared Create pack, the seeded Horizon
fixture selected the Depot at `(6, 178, 5)`, consumed its Glowstone, retained one
plain Chromatic Compound from the input stack of two, and spawned one compound
with collected-light value `1`. The new [transport check](tools/test-legacy-radiance-beacon.py)
compares these discrete before/after states; it does not claim Java packet timing
or full Belt transport parity. Existing references cover the Java conversion,
beacon controls, void transition, threshold and item reload behavior. The
isolated build used the pinned Horizon revision and source-mixin launcher 0.2.67;
the source tree came from the installed pinned launcher cache, with the current
unsided item insertion patch applied in the isolated build tree. Other current
engine patch interactions were not re-audited for this family pass.

Bounded APP-2073 results on that build: `legacy-material-float`,
`legacy-material-float-lan`, `legacy-material-shadow-void`,
`legacy-radiance-beacon`, `legacy-radiance-beacon-lan`,
`legacy-radiance-beacon-reload`, `legacy-radiance-light-threshold`,
`legacy-radiance-light-collection`, and `legacy-radiance-transport` passed.
The eight established checks replay the existing Java fixtures for dropped
motion, void conversion, beacon conversion and controls, cold reopen, threshold
and placed-light collection. The transport check is a one-tick source-aligned
Depot case with an input stack of two; counts and item identity are exact. The
LAN guest saw both floating metals and the converted beacon stack, and reopened
worlds retained conversion state and subsequent motion through tick 8. Belt
transport, the dynamic charged-stack display/limit, additional configuration
values and full lifespan expiry remain follow-ups.

## Creative Search membership

The [Java tab capture](fixtures/creative-tabs-java.csv) has 265 Base and 392
Palettes search entries. The pack lists all 657, and the pinned Horizon
candidate `native-9f42064-f30286a3e7ee` honors that membership in global Search.
The [offscreen replay](tools/test-create-creative-search.py) matched both lists
and verified that Blaze Cake Base appears and Chromatic Compound is excluded.
The existing tab replay passed the Base and Palettes display membership checks,
Palettes ordering, and the first live page of each. Java client Base ordering
and the remaining search interactions are open.

## APP-2095 creative inventory baseline

On the archived Horizon `native-9f42064-340cbe866fa7` client built from
`adfa875` with the 0.2.67 launcher, the
[tab replay](tools/test-create-creative-tabs.py) matched 203 Base and
377 Palettes display entries, Java Palettes order, and both first live pages.
The [search replay](tools/test-create-creative-search.py) matched all
265 Base and 392 Palettes search entries in the pack. Live Search returned
Blaze Cake Base and excluded Chromatic Compound. Both checks passed in
25.93 seconds. The [colored seat search](tools/test-colored-seats.py) and
[Ponder Back replay](tools/test-ponder-creative-back.py) also passed on
the same client and pack.

The [LAN replay](tools/test-create-creative-lan.py) passed in 60.95 seconds.
A guest joined a local host, entered Creative, opened both Create tabs,
and saw the same first 45 entries per tab as the pack. Closing and reopening
the guest inventory retained the selected Building Blocks tab and its first
page. Search returned Netherite Diving Boots, Ornate Iron Window and its
pane, and Blaze Cake Base in three queries. Chromatic Compound, Incomplete
Precision Mechanism, and Incomplete Track each returned an empty grid.
The game state in scope is the selected tab during the current client
session. These checks do not cover a cold process restart.

Guest screenshots showed the Create and Create’s Building Blocks titles
with their Cogwheel and Ornate Iron Window icons. Search rendered names
and textured icons for the hovered boots, window, and Blaze Cake Base.
The boots and window displayed their respective blue tab attribution.
Blaze Cake Base is present in Search but lacks the blue Create line on
this build. Pinned Java's `CreativeModeTab.contains` uses the tab's search
membership, so its `SEARCH_TAB_ONLY` entries are credited. Horizon's
tooltip lookup uses display membership and omits the label for this
entry. The screenshot for the Palette tab also shows overlapping vanilla
and Create tab hover labels. The selected panel title remains legible.
The captures are in the worktree’s `.local/creative-lan-*.png`.

Client SHA-256
`39712c37f7f666a2d730506198523f0d0b42ef7b4a15c0ea9142a95b450224ea`.
Matching content pack SHA-256
`0dc4da44753fdf6dd94d1cdd8d26b82bc35446899a3ad1219a9990377e74b852`.
The prepared Horizon 26.3 resources came from the
`native-9f42064-6ce68a31b125` installation on the same upstream pin.
The Java reference is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb` with NeoForge 21.1.219.
The [capture patch](tools/java-creative-tabs-inventory.patch) SHA-256 is
`b7efc29a0446decff4ffe4e2a66c1564843917812ed128a370396ba6d19dd8ee`.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 \
  --check create-creative-tabs --check create-creative-search
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 \
  --check create-creative-lan
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 2 \
  --check create-creative-lan --check colored-seats-search --check ponder-creative-back
```

The first LAN fixture stopped on the host's empty chat reply after a
targeted game-mode command. The replay now waits for the guest's reported
game mode. An earlier sandboxed invocation reached client startup and
could not bind its local control socket. The offscreen results above used
isolated game directories and a local socket-enabled run.

## Tank bucket interaction

The [pinned Java probe](tools/java-tank-bucket-trace.patch) captured [eight
water and empty bucket interactions](fixtures/tank-bucket-java.txt). Creative
players filled ordinary tanks to 1000 mB and drained them. Survival and
creative players configured a single Creative Fluid Tank to 8000 mB and
cleared it. A survival player retained the held water bucket when filling and
received a water bucket when clearing. A client-prediction gap on
`native-9f42064-f30286a3e7ee` let vanilla consume the survival player's bucket.
Both the [solo](tools/test-tank-bucket.py) and [LAN guest](tools/test-tank-bucket-lan.py)
replays passed with the correction on `native-9f42064-46eefb85bfea`.
An ordinary tank declined the survival player's interaction in the Java probe.
The [two-block split replay](tools/test-tank-split.py) on
`native-9f42064-73cd83f87233` matched all 32
[Java observations](fixtures/tank-split-java.csv). The controller held
12,000 mB before each split. The surviving part kept 8,000 mB when either
part was removed, including actual creative-player mining of either part.
The [same-fluid merge replay](tools/test-tank-merge.py) on
`native-9f42064-9eef81efe32b` matched all 27
[Java observations](fixtures/tank-merge-java.csv). Adding the middle block to
two tanks holding 4,000 and 5,000 mB formed a three-block group. All three
positions reported capacity 24,000 mB and contents 9,000 mB, with the transferred
storage cleared. Both bucket replays and the split replay passed on this build.

## APP-1987 tank fluid rendering and client synchronization

The [render fixture](tools/test-tank-render.py) exercises real bucket fills and
a drain, then reads both authoritative block data and the client block-entity
render trace. On `native-9f42064-5079f533f884`, it rendered a 3,000/8,000 mB
ordinary tank, a full 8,000 mB creative lava tank, and a 16,000/32,000 mB joined
2x2 tank. It observed both sides of the live 4,000→3,000 mB change, repeated
the final state after a cold world reopen, and verified the same fluid meshes on
a joining LAN guest. Offscreen host and guest screenshots show the rendered
water and lava in their windows.

The initial empty screenshot was traced to an actual replication omission, not
missing render dispatch. Server block data held fluid after writes, but clients
received an empty `TankContent` compound because tank update tags omitted the
entity NBT and fluid writes did not mark the controller updated. The tank update
tag now carries the controller and fluid fields, and fluid writes notify the
block entity update path. The fixture now uses bucket interactions, so it
asserts the real synchronization path as well as geometry.

The grouped tank/fluid regressions passed 37/38 checks; the only failure was
the offline production-core runner missing locked `serde_json` from its isolated
Cargo cache. After fetching that exact locked dependency,
`python3 tools/test-parity.py ... --check tank-script-core` passed separately,
for 38/38 affected checks overall. The same runs passed LAN bucket and
encased-pipe transfer, the active fluid-pipe lifecycle, and the mechanical-pump
LAN case. Full 1:1 visual parity remains open for interpolation, particles,
client lighting, and exact Java pixels.

## Intermediate survival crafts

Six [Java-captured recipes](fixtures/intermediate-crafting-java.csv) matched the
[Horizon survival crafting grid](tools/test-machine-crafting.py) on
`native-9f42064-f30286a3e7ee`. The six outputs were Electron Tube, Transmitter,
Rose Quartz, Sand Paper, Red Sand Paper and Andesite Alloy using an iron nugget.
The [Java probe](tools/java-intermediate-crafting-trace.patch) checked recipe
IDs, outputs, counts and crafting remainders.

The [LAN craft and reopen replay](tools/test-multiplayer-common-parts.py) passed
on `native-9f42064-6ce68a31b125` with pack SHA256
`fae54c37367475be514f4565f2bc8f72b089e129601cde3275bc9486c8799187`.
A survival guest crafted one Andesite Alloy from two Andesite and two Iron
Nuggets in the player grid. Both inputs were consumed, and the host and guest
agreed on the resulting inventory. After the guest disconnected, the host
world was reopened and the guest rejoined with the alloy retained. This checks
the meaningful persistence path for an instantaneous craft; an active machine
case does not apply to this recipe fixture. It checks resulting state after
guest convergence, not exact packet-arrival timing.

## Sweet Roll, Chocolate Glazed Berries and Honeyed Apple use timing

The [headless replay](tools/test-food-use.py) matched item state, hunger and
saturation across [36 Java ticks per food](fixtures/food-use-java.csv) on
`native-9f42064-46eefb85bfea`. All three finished on tick 32. Hunger rose
from 10 to 16, 17 and 18 respectively. Saturation rose from zero to 9.6,
11.2 and 12.8.
The [LAN completion replay](tools/test-food-use-lan.py) matched host-authoritative
inventory, hunger and saturation after a survival guest ate each food; the
guest also received the inventory update. The subsequent per-player observer
on `native-9f42064-2eee295871e3` captured the real LAN guest immediately
before item-use advancement. The replay matched all 36 consecutive Java
player-tick samples per food, including use ticks remaining, held item/count,
hunger and saturation. Per-connection sequence numbers detect missing samples.
All three foods finished on relative player tick 32. This observation is
independent of the world's frozen clock.

## Tree Fertilizer on Birch, Cherry and Acacia

The [pinned Java probe](tools/java-tree-fertilizer-species-trace.patch)
recorded the survival use result, consumption and initial trunk blocks for
each stage-zero sapling on dirt. The [offscreen replay](tools/test-tree-fertilizer-species.py)
on `native-9f42064-73cd83f87233` consumed one fertilizer and matched the base
log for all three species. It also matched the next trunk block for Birch
and Cherry. The [LAN Acacia replay](tools/test-tree-fertilizer-species-lan.py)
matched the base log and consumption, with inventory and the base visible
to the guest. The later seeded full-volume comparison below verifies the
complete tree geometry and transient leaf properties for its captured seeds.

## Wand of Symmetry creative break

The [Java break probe](tools/java-symmetry-wand-break.patch) removed mirrored
dirt during the original Creative XY break event. The [headless creative
replay](tools/test-symmetry-wand-creative-break.py) confirmed a creative player
breaking the source stone removed both blocks without drops or Wand wear on
`native-9f42064-73cd83f87233`.

## Honey and Builder’s Tea in a three-way pipe

The [Java probe](tools/java-honey-pipe-trace.patch) used the original
three-way pipe structure with 11,000 mB of physical Honey. The [headless
Horizon replay](tools/test-fluid-split-trace.py) on `native-9f42064-9eef81efe32b`
matched all 101 [Java samples](fixtures/honey-pipe-java.csv) for source
amount, total destination volume and fluid identity at the destinations.
All 11,000 mB transferred by tick 99. Per-branch distribution was outside
the sampled comparison.
The same replay matched all 101 [Builder’s Tea samples](fixtures/tea-pipe-java.csv).
The [Java Tea probe](tools/java-tea-pipe-trace.patch) filled the source tank
through its fluid capability. All 11,000 mB reached the destinations by tick 99.
The virtual fluid can be stored and pumped through the network.

## APP-2090 Create foods and Builder’s Tea gameplay baseline

The bounded acceptance cases reuse completed source-derived evidence for the
three processed foods and Tea. The pinned Java source is Create
`ac0c444d9828da3453ae8cc65338e8de063286fb`; `BuildersTeaItem` uses a 42-tick
drink and returns a glass bottle in survival, while its registered food
properties apply hidden Haste for 3,600 ticks.

| Acceptance case | Evidence and result |
| --- | --- |
| Survival acquisition and use | Existing spout replay produces Sweet Roll, Chocolate Glazed Berries and Honeyed Apple from their representative ingredient/fluid pair. Three 36-tick Java comparisons match item, hunger and saturation; each is consumed on tick 32. Basin Dough and Bread cooking are covered by the Basin and recipe checks. |
| Important food interactions | Existing guest replay matches 108 Java player-tick samples for the three foods. Release and hotbar-swap interruption, replacement, creative/full-hunger controls, death/respawn and disconnect/rejoin retain the recorded outcomes. Bar of Chocolate and other Tea variants remain broader follow-ups. |
| Tea use and return | Existing 45-tick authority replay matches the Java Tea use, nutrition, glass bottle and hidden Haste (3,600 ticks on tick 42). The survival brewing/bottling replay verifies 500 mB Tea, 250 mB bottling and bottle return. |
| Guest ownership after reconnect | New [`test-builders-tea-rejoin-lan.py`](tools/test-builders-tea-rejoin-lan.py) makes a survival LAN guest drink Tea, disconnect, and reconnect with one glass bottle, no Tea, and hidden Haste. It observed 3,589 Haste ticks after reconnect. The initial harness attempt used the optional forced LAN mode and did not restore survival on reconnect; the accepted run uses the same LAN mode as the existing food rejoin harness. |
| Persistence dependency | Basin idle/active save and reopen are covered by [`test-basin-lifecycle.py`](tools/test-basin-lifecycle.py). APP-1992’s Tea network reopen preserved its fluid identity and amount and resumed transfer after reopen. Food use itself has no machine settings or connections to retain; player inventory/effect ownership is covered by the guest reconnect case above. |

The new check and focused regressions passed with the available compatible
client `native-9f42064-d6dc2ad18d3f` (SHA-256
`006bfe15a198b29d6af7633d353dcadaa07039121ae66c2081927299835a8811`) and
`create.hmod` SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
This pass reused that binary and did not compile a new native build; treat its
runtime results as candidate evidence. The captured Java comparisons remain
separate and pinned to the reference revision above.

The focused registered command was:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 \
  --jobs 2 --check create-foods --check food-use --check food-use-lan \
  --check food-rejoin-lan --check food-mode-lan --check builders-tea \
  --check builders-tea-drink --check builders-tea-rejoin-lan
```

All eight selected checks passed on the candidate runtime. Exact eating poses,
other food/Tea mode and interruption combinations, other fluid networks and
Full 1:1 remain open; these are not blockers to this finite gameplay baseline.

## APP-1992 Honey, Chocolate and Tea gameplay baseline

The finite recipe paths come directly from the pinned Create generators:
`CreateMixingRecipeGen` makes 1,000 mB Honey from a Honey Block, 250 mB
Chocolate from a Bar of Chocolate, and 250 mB Chocolate from milk, sugar and
cocoa beans. It makes 500 mB Builder's Tea from 250 mB water, 250 mB milk and
leaves. `CreateEmptyingRecipeGen` returns 250 mB Honey or Tea and a glass
bottle from the corresponding bottle item. Existing
[`test-fluid-food.py`](tools/test-fluid-food.py) and
[`test-builders-tea.py`](tools/test-builders-tea.py) exercise those Basin and
Spout recipe outcomes; the latter also drinks the Tea and checks the bottle,
Haste and saturation. Existing placed-fluid bucket checks cover Honey and
Chocolate in solo and LAN, and `test-fluid-bucket-machines.py` checks 1,000 mB
bucket fill/drain paths. Existing Java traces remain the reference for 120
Honey/Chocolate channel states and 101 ticks each of Honey and Tea through the
three-way pipe. APP-1961 (Basin) and APP-1990 (Spout) are Done.

The added `--reopen` mode in [`test-fluid-split-trace.py`](tools/test-fluid-split-trace.py)
stops each Java pipe replay at tick 50, after 51 matched samples, and saves the
active Honey or Tea network. It verifies that fluid identity and the 11,000 mB
total survive reopening, that a separate 1,000 mB Chocolate tank retains its
identity and amount, and that active transfer continues for another 100 ticks.
The server can tick during startup before the fixture is frozen again, so the
post-open assertion checks conserved quantity and resumed progress, not
per-destination amounts or reload timing.

Both new cases passed on available client `native-9f42064-6ce68a31b125` with
pack SHA-256 `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
That client predates current main fluid changes, so these are candidate results
only; the new checks and carried acceptance evidence still need a
source-matched current build before this gameplay baseline can be called
verified. A current build attempt could not stage the pinned Horizon source:
the launcher source cache already contains some repository patches, and
applying the remaining patch set privately stops at
`horizon-create-potato-impact.patch`. The shared launcher source and cache were
left unchanged. Details and preserved exploratory logs are under
`.local/parity/app1992/` and the worktree-local `.local/` logs. The shared fluid
pipe lifecycle check also fails on the old client; this is not evidence about
the current integrated build. Full branch distributions, other pipe layouts,
fog/rendering and registry-wide audits remain follow-ups.

## Mixed-fluid vertical tanks

The [Java mixed tank probe](tools/java-tank-mixed-trace.patch) recorded
[60 samples](fixtures/tank-mixed-java.csv) for both water-under-lava and
lava-under-water. Connecting an empty middle tank leaves the lower fluid
in an 8,000 mB group and joins the middle and upper blocks into a 16,000 mB
group containing the upper fluid. Removing the middle block restores two
independent single tanks and preserves both contents.

The [headless replay](tools/test-tank-mixed.py) matched on
`native-9f42064-665133b372c9`, including all six ports accepting and
releasing 1,000 mB via player bucket use without affecting the other controller.
The same-fluid merge and two-block split regressions passed on this build.
A [LAN guest replay](tools/test-tank-mixed-lan.py) exercised all three ports
with water under lava, then retained both fluids when the middle block was
removed. Wider mixed groups and full mixed-fluid behavior remain open.

The [mixed-tank cold reopen](tools/test-tank-mixed-reopen.py) on
`native-9f42064-2eee295871e3` preserved both fluid orders, both controllers
and all six ports across six observed post-reopen ticks.
The [Java serialization fixtures](fixtures/tank-mixed-save-java.csv) record
controller contents, group heights and the upper part's controller pointer.
The original [water-below](tools/java-tank-mixed-save.patch) and
[lava-below](tools/java-tank-mixed-save-reverse.patch) probes reload block
entities in process. Full Java server restart timing remains open.

## Seeded Acacia geometry and leaf updates

The [Java geometry probe](tools/java-tree-fertilizer-acacia-geometry-trace.patch)
runs one seed at absolute position (10,170,22), with nearby chunks forced.
The disposable Java clone's `run/world` must be removed before each invocation.
A new server process can load persisted scheduled ticks from the previous world.
Earlier reference runs that reused that world were discarded. A repeated
seed-two capture in newly created worlds matched exactly.

The [full-volume replay](tools/test-tree-fertilizer-acacia-geometry.py)
on `native-9f42064-798749c753e7` matched every coordinate and block-state
property in a 25×25×25 volume for seeds 1–12 at ticks 0–3.
All 48 snapshots and [3,836 non-air state observations](fixtures/tree_fertilizer_acacia_geometry-java.csv)
matched, including transient leaf-distance updates. It also verifies that
growth and consumption finish in the same frozen world tick, with one
fertilizer left from a stack of two.

The prior native application order produced eight leaf-distance differences
on seed two's first tick. The correction preserves the Java map's insertion
order within hash buckets when applying the simulated tree. Other seeds,
environments, sapling geometry and Java map tree-bin behavior remain open.

## Mixed tanks, Acacia and LAN food verification bundle

Final isolated candidate `native-9f42064-798749c753e7`, using
`create.hmod` SHA-256
`fcdebbf8a3a7fc47a8040a92b95d512e0797f5cc8d51932be3b18d8959a9540b`,
passed all 16 adjacent tank, food, fertilizer and fluid-transport checks.
The separate full Acacia replay passed all 48 snapshots, and the normal
offscreen LAN food replay passed all 108 consecutive guest player-tick samples
on this same candidate. These are 18 focused checks. The full registered suite
was not rerun for this bundle.

The matrix retains the remaining family scopes, including wider mixed-fluid
groups, exact Java server-restart timing, other tree seeds and environments,
and interrupted or additional multiplayer consumption paths.

## Additional Acacia seeds

The full-volume Acacia replay also matched seeds 13–24 on
`native-9f42064-798749c753e7`, comparing each tree at ticks 0–3 in the same
25×25×25 volume. All 48 further snapshots matched complete block states,
with same-tick growth and one fertilizer consumed. Each pinned Java capture
used a newly created disposable world.

## Tree obstacles, soils, Birch and Cherry

On `native-9f42064-798749c753e7`, the [Acacia environment replay](tools/test-tree-fertilizer-acacia-environments.py)
matched seven original Java cases across ticks 0–3. The 28 snapshots contain
2,608 exact block-state observations including the soil beneath each sapling.
Bedrock in a generated trunk remained, stone in a log position became a log,
and stone/bedrock in confirmed foliage positions remained. Coarse dirt beneath
the tree stayed coarse dirt. The clear Acacia seeds 13–24 add 4,204 observations
across 48 matching snapshots.

The [Birch and Cherry replay](tools/test-tree-fertilizer-species-geometry.py)
matched both species at seeds 13 and 20, with 16 snapshots and
[2,716 block-state observations](fixtures/tree_fertilizer_species_geometry-java.csv).
Each replay compares the complete 25×25×25 tree volume plus the origin soil,
and checks that growth completes in the frozen tick while consuming one
fertilizer. The shared [pinned Java probe](tools/java-tree-fertilizer-acacia-geometry-trace.patch)
selects the species and environment. Every reference uses a newly created
disposable Java world.

## Interrupted LAN food use

On `native-9f42064-28d9ddffe8ec`, a real offscreen LAN guest released use
or changed hotbar slots during each of Sweet Roll, Chocolate Glazed Berries
and Honeyed Apple consumption, then restarted. The
[reusable replay](tools/test-food-interrupt-lan.py) compares consecutive
per-player samples anchored to actual packet receipt against the
[Java interruption oracle](tools/java-food-interrupt-trace.patch).
It validates Java's unchanged canceled-state rows before extending that idle
state over the observed pause.

A second [pinned Java probe](tools/java-food-interrupt-exact-trace.patch)
used all six exact LAN action schedules, including slot-return times.
The [exact reference](fixtures/food-interrupt-exact-java.csv) directly matched
all 308 consecutive guest-player samples, without extending or rebasing idle
periods. The [direct comparison tool](tools/compare-food-interrupt-exact.py)
checks selected hand, retained food slot, stack counts, remaining use,
hunger and saturation. The original trace and both oracle captures are
archived in `.local/partial-family-replays/food-interrupt-lan-28d9ddffe8ec/`.

## Eating across LAN disconnect and rejoin

The [LAN rejoin replay](tools/test-food-rejoin-lan.py) passed for all three
foods on `native-9f42064-28d9ddffe8ec`. A survival guest left during use,
rejoined idle with the original food and nutrition, then restarted.
Each fresh use matched all 36 [Java player ticks](fixtures/food-rejoin-ticks-java.csv).

The [Java lifecycle probe](tools/java-food-rejoin-trace.patch) exercises
`PlayerList.remove` and `PlayerList.load` with a connected FakePlayer.
Its [save/load reference](fixtures/food-rejoin-java.csv) records food
preservation and cleared use. The Horizon replay uses a real LAN connection;
the Java probe uses the server lifecycle with a simulated connection.

## Wider stacked tanks and immediate transitions

On `native-9f42064-1b742296a7dc`, [storage replays](tools/test-tank-wide-storage.py)
matched all 858 Java observations for stacked 2×2 and 3×3 layouts in both
water/lava orders, covering every port at ticks 9–19. Immediate join and removal
samples are taken at the command boundary, before advancing the world.
The previous build exposed untransferred fluid immediately after joining and
allowed 9,000 mB into an upper part that Java temporarily limited to 8,000 mB.

The correction transfers compatible fluid synchronously when tanks join and
preserves individual part identity until the next block-entity phase after
the tested wider controller is removed. Both [command and player joins](tools/test-tank-wide-join-immediate.py)
preserved 5,000 mB and immediately accepted another 1,000 mB. All four
[split/refill replays](tools/test-tank-wide-split.py) rejected the ninth bucket,
then retained 8,000 mB through regrouping and accepted that bucket on the next
tick. Exterior player interactions passed all 24 2×2 ports and all 48 exposed
3×3 ports. Enclosed ports use the authoritative storage observer. Horizontal
mixed-fluid layouts and high-fill split distributions remain open.

## Legacy fertilizer soils and giant spruce

The [Create-only compatibility patch](patches/horizon-tree-fertilizer-zz-legacy-growth.patch)
normalizes the pinned Java dirt-tag members inside the simulated growth world
and selects the original spruce feature from the seeded random stream.
The Minecraft 26.3 tag and weighted spruce selection differ from 1.21.1.
On the earlier candidate, grass became dirt and each giant spruce seed selected
the opposite variant.

On `native-9f42064-1b742296a7dc`, all 13
[environment cases](tools/test-tree-fertilizer-acacia-environments.py) matched
52 snapshots and 4,708 block/soil states. Grass, podzol and mud stayed in their
original states at ticks 0–3. Both [giant spruce seeds](tools/test-tree-fertilizer-spruce-giant.py)
matched all 7,256 tree and full-floor state observations in a 25×42×25 volume,
including all 625 dirt floor blocks and the absence of podzol. Acacia seeds
1–24 and Birch/Cherry regressions also passed on this candidate.

## Oak and mangrove variant selection

On `native-9f42064-76686557dafc`, the generalized Create-only legacy selector
matches Java's secondary-feature float threshold for spruce, oak and mangrove.
Minecraft 26.3 instead uses weighted-list integer draws. Before correction,
oak seed 9 selected fancy instead of normal and seed 4097 selected normal
instead of fancy. Both directions now match every sampled block state.
The [eight species cases](tools/test-tree-fertilizer-species-geometry.py)
match 32 snapshots and 3,824 states at ticks 0–3.

The [mangrove replay](tools/test-tree-fertilizer-mangrove.py) matched four
mud-grown seeds and a hanging-propagule control. All 20 snapshots and
56,732 states in a 25×45×25 volume, including four complete soil layers,
matched Java. Seeds 2 and 2048 exercised the previously mismatched variant
choices. Grown trees consumed one fertilizer. The hanging control left
two fertilizer and all blocks unchanged, following Java's PASS result.

## Food use interrupted by death

The [offscreen LAN death replay](tools/test-food-death-lan.py) passed all
three foods on `native-9f42064-28d9ddffe8ec`, with the current game's
`keep_inventory` rule verified enabled. Food remained after respawn,
active use cleared, and hunger/saturation reset to Java's respawn values.
A controlled hunger reset allowed a fresh use, which matched 36 Java
player ticks per food.

The [Java oracle](tools/java-food-death-trace.patch) invokes
`ServerPlayer.die` and the `restoreFrom(false)` state transfer used by
respawn. Its simulated connection does not exercise Java respawn packet
delivery. The Horizon side uses a real LAN guest and respawn input.


## Horizontal mixed-fluid tank groups

The [horizontal replay](tools/test-tank-horizontal.py), on
`native-9f42064-c898d19804c3`, matched 64 Java storage observations for a
2×2 footprint and 144 for a 3×3 footprint, across both water/lava orders.
It also filled and drained all 24 exposed ports. The enclosed center in
the 3×3 layout was checked through actual storage observations. In these nonempty-controller layouts, unlike
fluids remain separate; the compatible 2×2 region inside the 3×3 layout
forms its own controller. The vault comparator regression still matched
69 Java ticks after the shared candidate-selection change.

High-fill controller removal and regrouping has a separate comparison
below; the horizontal results alone do not establish parity for that case.


## LAN held-food replacement

The [replacement replay](tools/test-food-replace-lan.py), on
`native-9f42064-cd2cb1ff3166`, passed six host/guest cases. Each of Sweet
Roll, Chocolate Glazed Berries and Honeyed Apple was replaced during use
with either a count-two stack of the same food or a different food.
Consecutive authoritative guest ticks matched the
[Java capture](fixtures/food-replace-java.csv) through cancellation or
consumption. Same-food replacements consumed one at the original completion
tick and applied the original nutrition. Different-food replacements
canceled on the next player tick; after releasing use, all three retained
count two and unchanged hunger/saturation through the original tick 33
window. Raw traces and logs are archived under
`.local/partial-family-replays/food-replace-no-phantom-cd2cb1ff3166/`.

The Java oracle contains replacement boundaries 0–31. Live observed
boundaries in this run were 7–9; the implementation captures the original
stack at action time, but replacement before the first guest player tick
has no live verification. When a held button
produces a new use at consumption, the comparison uses Java's explicit
`same_repeat` input sequence. The post-release no-nutrition window is an
outcome assertion, not a claim that the client and Java received identical
release packets on every tick.

The engine now retains the original Create food stack when use begins.
Following NeoForge's default continuation rule, a different held item ends
that use, while the same item continues even if its count changes. That initial
correction covered the three tested Create foods; Bar of Chocolate was
subsequently added after the separate failures documented below.


## High-fill tank removal and regrouping order

On `native-9f42064-5548b7a9aac9`, the
[controller-removal replay](tools/test-tank-full-split.py) matched all
192 Java storage observations across three 2×2×2 cases: 12,000 mB,
48,000 mB, and 48,000 mB with reversed block placement order. This includes
the immediate singleton storage at removal and each subsequent sampled
tick through tick 16.

Fresh-world Java captures establish a surprising result: after removing
the 48,000 mB controller, the surviving upper 2×2 group retains 8,000 mB
for forward placement but 24,000 mB for reverse placement. Java transfers
a part's local tank before splitting its previous group; intermediate
vertical groups and block-entity ticker order therefore affect the result.
The native implementation now follows that sequence, including equal-score
queue order, rather than imposing an amount adjustment for this layout.

The same candidate retained the earlier 858 wider vertical observations,
60 mixed-column observations, 27 same-fluid merge observations, 32 pair-split
observations, and four immediate split/refill cases. That candidate’s regrouping path
reconstructed pending survivors of the removed controller.
Adjacent pre-existing nonpending tanks and other widths/heights require
separate captures and remain open.


## Wider high-fill tank connectivity phases

On `native-9f42064-09b278117d6e`, the same controller-removal replay with
`--amount 120000` matched all 144
[Java observations](fixtures/tank-full3-split-java.csv) for a 3×3×2 group.
The immediate split produces individual 8,000 mB capabilities. On tick 11
the upper 3×3 group holds 32,000 mB in 72,000 mB capacity while lower
survivors remain singletons. On tick 12 a lower 2×2 subgroup forms with
32,000 mB. Root positions, capacity, fluid and amount match through tick 16.

The previous candidate exposed that lower subgroup one tick early. The
correction follows Java's `updateConnectivity` lifecycle: splitting dirties
released controllers, ticking clears their flag, and a later split can
leave work for their next eligible tick. No fixed one-tick delay is applied
for this layout. The previous three 2×2×2 cases still matched all 192
observations on the same candidate. Adjacent pre-existing tanks and other
sizes, removals and ticker orders remain open.


## Combined LAN food regression and received-action schedules

On `native-9f42064-5548b7a9aac9`, normal eating (108 samples), all six
held-stack replacements, all three disconnect/rejoin cases, all three
death/respawn cases and all six release/hotbar-swap interruption cases
passed. A [fresh Java capture](fixtures/food-interrupt-5548-exact-java.csv)
using the measured action schedules directly matched 336 consecutive guest
player ticks: Sweet Roll release/swap 54/53, Berries 47/52, Honeyed Apple
50/80. Selected hand item/count, slot-zero item/count, remaining use time,
hunger and saturation matched without extending or rebasing idle rows.

The [capture patch](tools/java-food-interrupt-5548-exact-trace.patch),
comparison output and all five suite traces are archived under
`.local/partial-family-replays/food-combined-5548b7a9aac9/`. The earlier
308-sample reference remains preserved for its original received inputs.


## Jungle and Dark Oak full geometry

On `native-9f42064-09b278117d6e`, the
[Jungle/Dark Oak replay](tools/test-tree-fertilizer-jungle-dark-oak.py)
matched 32 full 25×42×25 snapshots at ticks 0–3, including the dirt plane,
28,456 nonair block states and leaf properties. All eight cases consumed
one fertilizer in the same frozen world tick:

- Giant and single Jungle for seeds 13 and 4096.
- Giant Dark Oak for seeds 13 and 4096.
- Giant Jungle and giant Dark Oak seed 13, each with confirmed stone-trunk,
  bedrock-trunk and stone-foliage obstructions in the same environment.

The obstruction cases replaced trunk stone with log while retaining
bedrock and canopy stone. Fresh Java worlds were used for every capture.

Two version differences caused the original failures. Java 1.21.1 chooses
a sole mega feature without drawing a random value; newer vanilla draws
from a weighted list. Dark Oak side-branch foliage in Java 1.21.1 attaches
relative to the leaned trunk tip, while newer vanilla uses the original
trunk coordinates. Both compatibility paths apply only to Create's Tree
Fertilizer simulation. Ordinary 26.3 growth retains its own behavior.
Discriminating oak seeds 9/4097 and both giant-spruce variants still matched
on the same candidate. Other seeds, environments and rendering effects
remain open.


The same candidate also matched 96 [adjacent-tank observations](fixtures/tank-adjacent-java.csv)
using `test-tank-full-split.py --adjacent`: a separate 3,000 mB tank next
to the removed 48,000 mB 2×2×2 controller retained its contents as the
original survivors regrouped. This single neighbor cannot complete a
new square and does not establish parity when external tanks can join
the new multiblock. High-fill, phase and adjacent evidence is archived
under `.local/partial-family-replays/tank-rephase-09b278117d6e/`.


## Waterlogged mangrove environment

The saved `waterlogged:13` case in the
[mangrove replay](tools/test-tree-fertilizer-mangrove.py) passed on
`native-9f42064-09b278117d6e`. It matches 2,993 nonair Java states at each
of ticks 0–3 in the full 25×45×25 volume, including four soil layers,
consumes one fertilizer and leaves `minecraft:water[level=0]` at the
original propagule position. With this case added, the mangrove fixture
contains six cases, 24 snapshots and 68,704 nonair state observations.
The previous five cases and discriminating oak/spruce variants remain
verified; this does not cover arbitrary submerged layouts.


## Fluid-machine regression bundle

All 12 selected machine and tank guards passed headlessly on
`native-9f42064-5548b7a9aac9`: pump startup pressure, Builder’s Tea brewing
and drinking, Steam Whistle, Tea pipe, Steam Engine, steam placement,
Fluid Threshold Switch, ordinary and LAN tank buckets, Fluid Observer
and the original nine-lane spouting fixture. Threshold Switch matched
337 Java ticks. Individual logs and complete threshold/spouting CSVs are
archived in `.local/partial-family-replays/fluid-machine-5548b7a9aac9/`.
This is a targeted regression bundle, not a rerun of the full suite.


## Offhand LAN food replacement

On `native-9f42064-d46d837bf961`, the
[offhand replacement replay](tools/test-food-offhand-replace-lan.py)
passed all six Sweet Roll, Chocolate Glazed Berries and Honeyed Apple
cases. The main hand stayed empty, and the authoritative guest trace
confirmed use slot 40. Different-food replacements canceled the original
use, retained count two and applied no nutrition through the original
tick 33 window after release. Same-food replacements consumed one with
Java's nutrition on the original tick 32. The held client immediately
started another offhand use in all three same-food cases, matched against
Java's explicitly captured `same_repeat` sequence.

The [fresh Java oracle](fixtures/food-offhand-replace-java.csv) includes
boundaries 0–31; live boundaries in this run were 7–9. The exact boundary-zero
LAN interleaving remains open. Raw evidence is archived under
`.local/partial-family-replays/food-offhand-replace-lan-d46d837bf961/`.
The new observer fields are opt-in and do not drive gameplay.


## Existing tanks participating in regrouping

On `native-9f42064-389cc927bda3`,
`test-tank-full-split.py --adjacent-pair` matched all 96
[Java observations](fixtures/tank-adjacent2-java.csv). Two independent
external water tanks, holding 3,000 and 1,000 mB, complete a shifted lower
2×2 group after the original 48,000 mB controller is removed. Java and
Horizon form that lower group with 20,000 mB and the upper group with
16,000 mB on tick 11, retaining those results through tick 16.

The previous pending-only reconstruction left a survivor at 8,000 mB in
8,000 mB capacity. The reconnect search now includes connected existing
tanks with their current controller/layout and local contents, without
queuing connectivity work for unchanged neighbors. Only touched entities
are committed. The same candidate passed the prior 432 high-fill/adjacent
observations, 858 wider vertical observations and 208 horizontal storage
observations. Physical horizontal ports were verified on the earlier
`c898d19804c3` candidate; this latest horizontal replay was storage-only.

## Azalea full geometry

On `native-9f42064-09b278117d6e`,
[Azalea and Flowering Azalea](tools/test-tree-fertilizer-azalea.py) each
matched Java for seeds 13 and 4096, ticks 0–3: 16 full 25×42×25 snapshots
and 11,456 nonair state observations including the entire soil plane and
rooted dirt beneath the tree. Java returned SUCCESS and both runtimes
consumed one fertilizer per use. No runtime correction was needed. Evidence
is archived under `.local/partial-family-replays/tree-azalea/`.

## Exact food saturation representation

Food comparators now reconstruct the Java and Horizon float32 values
from their decimal traces and require identical bits, using
`food_trace.same_f32`. This replaces the former 1e-6 absolute tolerance,
which could admit a one-ULP difference near saturation 10. Archived normal
eating, 308- and 336-tick exact interruption schedules, main/offhand
replacement, and rejoin/death restart comparisons all passed this stronger
check. A deliberate one-ULP difference is rejected. No gameplay change or
new live input run was needed for this trace comparison.


## Clicked corners and clay soil

On `native-9f42064-09b278117d6e`, all six added clicked-corner cases in
the Jungle/Dark Oak replay matched Java: the three remaining corners of
each 2×2 group for seed 4096, in addition to the previously tested minimum
corner. The new cases matched 24 full-volume snapshots and 25,400 tree/soil
states, preserving exact leaf properties and one-item consumption. The
combined Jungle/Dark Oak tool now covers 14 cases, 56 snapshots and 53,856
nonair state observations.

The separate [clay replay](tools/test-tree-fertilizer-azalea-clay.py) also
matched both Azalea variants, seed 13, at ticks 0–3: 733 nonair states per
snapshot, including rooted dirt replacing the clay below the tree. Both
uses consumed one fertilizer. The original dirt-plane Azalea cases remain
separate and preserved. Evidence is saved in
`.local/partial-family-replays/tree-jungle-dark-oak/` and
`.local/partial-family-replays/tree-azalea/`.


## Further tree and mixed-fluid controls

Four incomplete/mixed-species 2×2 tree cases matched Java at ticks 0–3:
Jungle fell back to a single tree, Dark Oak retained three stage-one
saplings, and neighboring Birch survived. Each accepted use consumed one
fertilizer. The Jungle/Dark Oak tool now contains 18 cases, 72 snapshots
and 64,392 nonair state observations. Single spruce seeds 13/4096 matched
eight full-volume snapshots and 5,836 tree/soil states. Mycelium, moss
block and muddy mangrove roots soil cases matched all four sampled ticks
on the tree-equivalent `d46d837bf961` candidate, preserving the original
soil and consuming one fertilizer. The Acacia environment fixture now
contains 16 cases, 64 snapshots and 5,704 block/soil state observations.

The external lava-pair control on `389cc927bda3` matched all 96
[Java observations](fixtures/tank-adjacent-mixed-java.csv): lava stayed
separate from the water survivors while the upper water group reformed.

A separate empty-bottom vertical placement-order capture initially failed
on the pre-ownership candidate. With water at y2 and lava at y4, bridging y3 then y1 forms one
40,000 mB Java group, retaining the first fluid and draining the second.
Bridging y1 then y3 instead retains water in a 32,000 mB group and lava
in an independent 8,000 mB tank. The static native layer partition did
not preserve this placement history. Both orderings were subsequently
verified by the controller-ownership implementation below.


## Empty horizontal controller transfer behavior

On `native-9f42064-a8f54e76a010`,
`test-tank-horizontal.py --empty-anchor` matched all 64
[Java observations](fixtures/tank-empty-anchor-java.csv), exercised all
eight exposed ports, and verified the rejected source was drained.
An empty 2×2 controller accepts the candidate containing water and lava,
then retains the first transferred 4,000 mB and discards the other
5,000 mB. Both fluid orders matched. Candidate validation now compares
against the original controller fluid; transfer attempts drain the entire
source as Java does, including rejected or excess amounts. The same
candidate retained the 208 nonempty-controller horizontal, 858 vertical
and 624 high-fill/adjacent observations. All 12 selected fluid-machine
regressions also passed again after the transfer change. The separately
captured vertical placement-history cases remain open.

## Creative growth and immature propagule control

On the tree-equivalent `native-9f42064-d46d837bf961`, creative oak seeds
9/4097 matched eight full-volume Java snapshots and retained the original
two fertilizer items. An immature hanging mangrove propagule (age zero)
matched Java PASS, unchanged full-volume state and no item consumption
for ticks 0–3. The mangrove tool now defaults to seven cases, 28 snapshots
and 78,712 nonair state observations.

## Live replacement before the first guest tick

On `native-9f42064-eaae3fae3f43`, a second ordinary LAN operator sent the
inventory command after Sweet Roll use started and before its first
player tick. The opt-in trace identifies the original used item separately
from the newly held berries stack, proving the intended ordering. All
34 consecutive samples matched Java's boundary-zero capture directly:
item/count, remaining use, hunger and exact float32 saturation, with no
new use in that capture. Earlier host-command probes produced 60 missed
orderings; none were counted as this scenario. Raw successful and missed
traces are archived under
`.local/partial-family-replays/food-replace-zero-lan-eaae3fae3f43/`.
This establishes one observed Sweet Roll boundary-zero path, not general
network scheduling determinism or the other foods/offhand at that boundary.


The ordinary second-operator boundary-zero probe subsequently matched all
three foods on `eaae3fae3f43`, 34 consecutive samples each, including exact
float32 saturation. Sweet Roll and Berries hit the required ordering on
the first attempt; Honeyed Apple hit on attempt five after five explicitly
recorded misses. Evidence is in
`.local/partial-family-replays/food-replace-zero-three-eaae3fae3f43/`.
The probe is not yet a default suite check: repeated fresh-world scheduling
needs verification. Three concurrent repeat attempts failed during hunger
setup under resource contention, before reaching the packet-order scenario;
these are retained as setup failures, not parity mismatches.

The post-transfer-change 12-check machine bundle and its complete threshold
and spouting CSVs are preserved under
`.local/partial-family-replays/fluid-machine-a8f54e76a010/`.


## Tree overlay drops and a surrounding water pool

On the tree-equivalent `native-9f42064-d46d837bf961`, the saved
[drop replay](tools/test-tree-fertilizer-drops.py) matched all eight Java
item snapshots for stone and oak-plank obstructions in oak seed 9. Each
tick 0–3 contained two item entities: one oak sapling and one cobblestone
for the stone case, or one oak sapling and one oak plank for the plank
case. The source sapling and obstruction became oak logs, and one
fertilizer was consumed. This compares IDs, total counts and entity counts;
item positions, trajectories and pickup after tick 3 remain unverified.

The `pool:13` mangrove case also matched all four full-volume snapshots:
3,001 nonair states each, including all nine surrounding water sources
and four soil layers. One fertilizer was consumed. The mangrove tool
now defaults to eight cases, 32 snapshots and 90,716 state observations.


## Tank placement ownership and old-world extension

On `native-9f42064-95db5cfccb21`, both
[vertical bridge orders](tools/test-tank-vertical-empty.py) matched all
160 Java observations. Bridging y3 then y1 produces one 40,000 mB
group; bridging y1 then y3 retains the 32,000/8,000 mB split.
Formation now reuses the source-derived connectivity queue and retains
controller identity, rather than recalculating grouping from fluid-root
positions after every transfer.

The [cross-version replay](tools/test-tank-legacy-extend.py) saved both
mixed-fluid orders using pre-ownership build `a8f54e76a010`, cold-opened
them using `95db5cfccb21`, and matched Java when extending the upper group.
The just-placed tank is excluded while old neighbors reconstruct their
pre-placement groups, then participates in normal formation. This check
requires `--old-client /path/to/a8f54e76a010/horizon-client` and is kept
separate from the default runner. Wider prior guards still need the next
combined candidate; these results do not imply they ran on 95db.

A flat 2×2 removal fixture initially failed before the flat-split fix: Java retains 8,000 mB in
each survivor when a 24,000 mB group loses its controller, whereas the
native survivor was empty. The verified flat-split result is recorded below.

## Offhand tree fertilizer

The [offhand oak9 replay](tools/test-tree-fertilizer-offhand.py) passed
on `native-9f42064-d46d837bf961`: the main hand stayed empty, offhand
fertilizer decreased from two to one, and all four full-volume snapshots
matched Java, including 61 tree/soil states per snapshot.


## Flat 2×2 controller and member removal

On `native-9f42064-951b116a7fa2`, the
[flat split replay](tools/test-tank-flat-split.py) matched all 64 Java
observations for removing either the controller or the opposite member
of a 24,000 mB 2×2×1 group. Each survivor exposes 8,000 mB in 8,000 mB
capacity immediately and through tick 16. The separate `--player` replay
mined both targets and checked all six survivors' immediate raw amounts
plus the subsequent capability traces.

The wider split path now resolves the removed member's stored controller
and handles height-one groups. A surviving controller retains its first
8,000 mB before the remainder is distributed in Java's y,x,z order; a
removed controller redistributes the full remaining amount. Earlier
column-pair behavior remains a separate path and is included in the
combined candidate's pending regression checks.


## Tick-zero repeat trials and food modes

Three independent fresh-world serial runs passed all nine boundary-zero
food cases, 34 direct Java samples each. Required attempts by food were
[3,1,1], [1,1,10], and [1,8,2]: 28 total ordinary-input attempts, nine
observed target orderings and 19 explicitly excluded other orderings.
All results are preserved under
`.local/partial-family-replays/food-replace-zero-repeat-eaae3fae3f43/`.
The tool remains a manual scheduling probe, not a default CI check; it
can fail to reach the required interleaving under resource contention.

The [food-mode LAN replay](tools/test-food-mode-lan.py), on
`native-9f42064-eaae3fae3f43`, matched 216 consecutive Java samples across
six cases. All three foods completed in creative mode with nutrition
applied and the stack retained. Full-hunger attempts left inventory,
hunger, saturation and active-use state unchanged for 36 ticks per food,
with a later guest command response establishing that the preceding input
reached the server. Java independently returned FAIL for those full-hunger
attempts.

The creative traces compare separately captured Java inputs for the exact
observed second use: tick 32 for Sweet Roll/Berries and tick 33 for Honeyed
Apple. Java repeat schedules 32–35 are captured independently; no rows are
shifted to make the comparison pass. Saturation comparison requires
identical reconstructed float32 values.


## Combined tank regression and further fertilizer controls

On `native-9f42064-951b116a7fa2`, tank guards passed 858 wider-vertical,
208 horizontal, 624 high-fill/adjacent, 60 ordinary mixed-column, 27
same-fluid merge, 32 pair-split and 64 empty-anchor observations, plus
all four physical wide split/refill cases. The two 80-sample bridge-order
cases, flat command/player removal and actual old-world reopen/extension
also passed. Evidence is archived in
`.local/partial-family-replays/tank-final-951b116a7fa2/`.

Remaining tank scopes include taller width-one removal, other wider
noncontroller removals, moving/copying ownership records, other fluids and
components, unloaded-group lifecycle and additional reconnection layouts.
Passing these selected cases does not close the family’s full 1:1 column.

On `d46d837bf961`, both-hands fertilizer used only the main stack
(main 2→1, offhand unchanged at three); last-item use emptied the stack.
Both oak9 controls matched all four tree/base-soil snapshots. Five
non-sapling controls matched Java PASS and unchanged targets/items:
brown/red mushrooms, crimson/warped fungi and bamboo sapling. Their
20 full aboveground-volume snapshots plus support states matched, and
both fertilizer items remained. The saved non-sapling path was additionally
smoke-tested on bamboo.

The final food-mode replay also checks the complete interval from input
through the FIFO response and then 36 consecutive ticks strictly after
that response. All six cases passed. The final creative input schedules
were Sweet Roll tick 34, Berries tick 32 and Honeyed Apple tick 32; each
uses its independently captured Java schedule. Earlier schedule-specific
results remain valid for their earlier traces.


The final tank candidate `951b116a7fa2` also passed the 12-check
fluid-machine bundle after controller ownership and member splitting
changed. Full threshold/spouting CSVs and individual logs are saved in
`.local/partial-family-replays/fluid-machine-951b116a7fa2/`. Actual player
placement also extended both old pre-ownership fluid groups after cold
reopen; the new port accepted and returned a bucket at the immediate
placement boundary before subsequent Java-matching ticks.


## Bar of Chocolate: precision and interrupted use

The [isolated Bar of Chocolate replay](tools/test-chocolate-bar-lan.py)
found two concrete failures in the previous implementation. Java produces
float32 saturation `3.6000001430511475` from nutrition six and modifier
0.3f; the former pack literal 3.6 became the adjacent lower float32
`3.5999999046325684`. Replacing an actively used bar also failed to cancel
it because the use-start identity guard listed only the other three foods.
Both failures were reproduced separately against the
[original Java capture](fixtures/chocolate-bar-java.csv).

On `native-9f42064-6f6533d3f402`, with pack SHA256
`036218cf690405199aa24e67e63433bc138cfd3272742d435f7ec602992ccc85`, all
three final saved-tool cases passed. Normal eating matched all 36 Java
player ticks with identical reconstructed float32 saturation. Same-food
replacement continued through the original tick-32 consumption. Different
replacement at tick nine canceled on tick ten and matched Java through
that boundary; after ordinary release, the replacement count two, hunger
ten and zero saturation stayed unchanged through the original tick 33.
That post-release interval is an outcome check, not a claim of identical
active-use packet schedules.

A separate trace contained an immediate fresh Sweet Roll use after old
Bar cancellation. It matched Java's explicitly captured `different_repeat`
input; the new use was not misclassified as continuation of the old bar.
All baseline failures, final passing data and the separate repeat input
are archived in `.local/partial-family-replays/chocolate-bar-baseline-eaae3fae3f43/`
and `.local/partial-family-replays/chocolate-bar-extended-6f6533d3f402/`.

The pack was rebuilt atomically. Entry sets were identical and the only
changed entry was `data/create/horizon/item/bar_of_chocolate.json`; the
old pack and diff record are preserved in `.local/partial-family-replays/`.
The native change adds Bar of Chocolate to the existing food identity
guard; tank code is unchanged from verified `951b116a7fa2`. The broader
tank and 12-machine regression bundles ran on 951b with the prior pack,
while the new Bar cases ran on 6f6533 with the corrected pack.

## Evening consolidation

The matrix still records 160 families: 120 playable and 40 partial, with
all full-1:1 cells open. The new exact scopes above close specific observed
gaps; they do not establish full Create parity or a Steam ’n’ Rails port.
The normal Create Parity Lab installation was not changed. All Minecraft
verification in this work used isolated headless or offscreen worlds.


The final three-food normal LAN regression also passed on
`6f6533d3f402` with the corrected `036218cf…` pack: all 108 consecutive
Java player samples matched for Sweet Roll, Chocolate Glazed Berries
and Honeyed Apple, including identical float32 saturation. The world
closed normally; output and full guest trace are preserved in
`.local/partial-family-replays/food-normal-final-6f6533d3f402/`.

The repeatable runner now registers 1,444 unique checks and all referenced
scripts resolve. This work ran the focused new comparisons and regression
bundles recorded above; it did not rerun all 1,444 checks together.


A final static data audit also confirmed nutrition and float32 saturation
for all four ordinary Create foods plus Builder’s Tea against the pinned
Java arithmetic. This checks the stored food values; it adds no claim
about untested Tea or Bar interruption/mode combinations.


Work stopped at the requested 7 p.m. Eastern cutoff on November 18,
2026. The `continue-create-parity-work` reminder is PAUSED, confirmed
through the app and its saved state. All isolated verification clients
were closed. Final verified food build: `6f6533d3f402`; tank regression
build: `951b116a7fa2`; final pack SHA256:
`036218cf690405199aa24e67e63433bc138cfd3272742d435f7ec602992ccc85`.


## Fluid-tank architecture experiment

The pre-experiment `6f6533d3f402` build, pack, source and fixtures are
preserved independently under
`.local/baselines/2026-11-18-pre-architecture-6f6533d3f402/`, with a complete
file manifest and successful baseline replay. The experiment continues this
repository and keeps the same Horizon/Java pins and content pack.

The [architecture audit](ARCHITECTURE-AUDIT.md) records the findings and
measurements. The actual production formation and wider-split calculations
now live in `native/tank_connectivity.rs`, called by the Horizon adapter
and the fast fixture adapter. One generic Java capture patch and shared
action scripts replace scenario-specific logic for the selected comparisons.

All six scripts matched 432 records per adapter against Java on experimental
native build `7e4344e38662`: 416 probe observations plus 16 accepted-fill
results, including controller identity. Both data-only high-fill additions
matched the prior 128 Java observations. A deliberate production-core
8,000→8,001 mutation failed the fast check; restoration passed. The focused
integration batch passed 15/15 checks.

Core incremental compilation measured about 0.4 seconds versus 110.6 seconds
for the game-linked native build. Six core scenarios repeated 1,000 times
each took 0.30 seconds in-process; repetition is a benchmark, not additional
coverage. Four original headless checks took 29.90 seconds, while equivalent
shared-script checks took 31.67 seconds. Thus the demonstrated gain is the
algorithm development loop, not faster engine integration tests.

Current-SDK migration remains an unproven separate experiment: the cached
9f42064 tooling is the old game-linked route, and no matching current SDK
was installed. Fast fixtures also do not replace live tick eligibility,
legacy reconstruction, fluid-component, bucket, network or rendering tests.
The matrix retains all full-parity cells as open.


The full warm six-scenario core command (cached build check, process startup
and all Java comparisons included) measured 0.55, 0.45 and 0.37 seconds,
median 0.45 seconds. These repeat trials measure latency, not new coverage.
The complete 35,320-file preserved baseline was rehashed after execution
and remained unchanged; the content pack also remained identical. A separate
actual-player old-world reopen/extension guard passed on the refactored build.


## Expanded fluid-tank workflow — November 18, 2026

The [tank evidence matrix](TANK-PARITY.md) records 31/31 scripts and 1,430 exact Java records passing through headless Horizon `92ef2557669b`. Its applicable shared production core also passes 19/19 scripts (1,093 records). The integrated build closes sampled split, component, creative, clone/move, window, boiler, comparator, source-light and real container inventory gaps. Original steam timing matches all 13 ticks. Physical local/reopen/LAN light, imported ownership through partial/full unload, vanilla clone inventory, solo/LAN bucket and muted sound-event guards pass. Java client rendering/particles, propagated-light and unload timing, audio pitch verification, mounted storage and remaining consumers are still open. Full-family parity was not promoted.


## APP-2099 Sounds, particles and effects

The bounded gameplay baseline reuses the existing pinned Java event traces and
adds one registered save/reopen check. The Java reference is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`.

| Case | Evidence and outcome |
| --- | --- |
| Powered machine stop cues | `clockwork-audio` matched all six Java cues at tick 6, including source, position, gain and pitch on host and guest. |
| Interaction cues and silent steps | `train-trapdoors-sound` and `train-trapdoors-sound-lan` matched seven toggles and two silent transitions in solo and LAN. `package-open` and `package-open-lan` passed. |
| Processing and event boundaries | `desk-bell-pulse` and `desk-bell-pulse-lan` matched 27 Java state samples and all three cues. `desk-bell-pulse-reopen-lan` additionally saved and reopened the world, retained the bell and both redstone wires, then let a newly joined guest press it; host and guest observed the Java cues. |
| Event validity, range and particles | `worldshaper-effect` and `worldshaper-effect-lan` delivered one shot, ten End Rods, ten Fireworks and the main-hand cue to each client. The Frogport package-effects replay hit Java catch/deposit starts at ticks 24/37. Nearby guests heard two cues per event; distant guests heard one in-range cue per event. All observers still received five seeded catch-rope particles outside sound range. |

The repeatable test changes are in `tools/test-desk-bell.py` and
`tools/test-parity.py`. The reopen check compares the saved block and wire
states before and after `FixtureWorld.restart()`. Sound playback and particles
are transient events, so they have no independent idle/active setting or
contents to serialize; the persistent Desk Bell setup is the meaningful
before/after state. The guest joins after reopening, and the subsequent cue is
checked on both clients.

Final focused Horizon checks passed on existing compatible candidate
`native-9f42064-340cbe866fa7` (Minecraft 26.3 / Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`). Client and control tool were taken
from `/Users/andrewholt/dev/horizon-create/.local/app-2097-evidence/native-9f42064-340cbe866fa7/`;
the exact pack SHA-256 was
`0dc4da44753fdf6dd94d1cdd8d26b82bc35446899a3ad1219a9990377e74b852`.
Prepared 26.3 resource metadata SHA-256 was
`c666426f77cadd1e8db01ad53e4900aa9e53930895c3f92243634e27e6ecf0ae`.
No native runtime source changed between that candidate and this baseline;
the ticket changes only the Desk Bell test path and evidence. The exact final
commands were:

```sh
APP2099_CTL=/Users/andrewholt/dev/horizon-create/.local/app-2097-evidence/native-9f42064-340cbe866fa7/horizon-ctl
APP2099_CLIENT=/Users/andrewholt/dev/horizon-create/.local/app-2097-evidence/native-9f42064-340cbe866fa7/horizon-client
APP2099_RESOURCES=/Users/andrewholt/dev/horizon-create/.local/app-2017-evidence/native-9f42064-6bdf8691aa42/.local/horizon-client/26.3
APP2099_PACK=/Users/andrewholt/dev/horizon-create/.local/app-2097-evidence/native-9f42064-340cbe866fa7/create.hmod

TMPDIR=/private/tmp python3 tools/test-parity.py "$APP2099_CTL" "$APP2099_CLIENT" "$APP2099_RESOURCES" --jobs 2 \
  --check clockwork-audio --check train-trapdoors-sound --check train-trapdoors-sound-lan \
  --check desk-bell-pulse --check desk-bell-pulse-lan --check desk-bell-pulse-reopen-lan \
  --check package-open --check package-open-lan --check worldshaper-effect --check worldshaper-effect-lan

TMPDIR=/private/tmp python3 tools/test-frogport-package-effects.py "$APP2099_CTL" "$APP2099_CLIENT" "$APP2099_RESOURCES" \
  --pack "$APP2099_PACK" --lan
TMPDIR=/private/tmp python3 tools/test-frogport-package-effects.py "$APP2099_CTL" "$APP2099_CLIENT" "$APP2099_RESOURCES" \
  --pack "$APP2099_PACK" --lan --remote
```

The ten registered checks and both Frogport range runs passed. The first
unprivileged attempt was invalid because the sandbox denied Horizon's local
control socket; the same checks passed with the required local socket access.
An initial LAN-reopen attempt also exposed that the Desk Bell harness assumed
every successful `/gamemode` command returned chat text. The helper now uses
the command result directly, and the host/guest reopen case passes. Raw logs
are preserved under this worktree's `.local/parity/` and `.local/` directories.
No new Java capture or runtime build was needed. Reuse setup: 0; harness/docs
changes: about 5 minutes; build: 0; focused runtime checks: about 5 minutes.
Remaining follow-ups are the other registered sound IDs, actual waveform and
mixing, exact audio output timing, and exact cosmetic/particle presentation.
## APP-1949 sequencer validation on latest main — November 19, 2026

After rebasing onto `origin/main` at `9341ef5cb462c3bb3f13c028b54a38c6c7ce2853`,
the updated `tools/build-native.sh` produced build
`native-9f42064-41316457f440`. The build's `horizon-client` SHA256 is
`ac4d4b543c70c0e5217b38b7ff37690d0c9f39f1cc9aa147fcd3009ca7a48ced`.
All checks below ran against that build and the pinned 9f42064 resource pack.

The bounded sequenced-gearshift host/guest, editor, comparator/stop, reload,
gantry/piston distance, orientation, Wrench and rendering checks passed 11/11.
Affected mechanical-piston, dispenser, roller and contraption-controls
regressions passed 13/13. The sequenced-pulley cross-regression passed 1/1,
including its 56-tick trace. These results replace earlier APP-1949 build
identifiers; broader combinations and the matrix's Full 1:1 column remain
open.
## APP-1943 kinetic source transitions — November 19, 2026

The pinned Java reference is Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
Source review of `RotationPropagator.propagateNewSource` confirms that incompatible
nonzero conveyed speeds destroy the newly added position with drops. Horizon's
kinetic source generation is shared with network traversal, and a conflicting
new kinetic member is now removed; the surviving adjacent networks are then
republished so their saved capacity and stress reflect the split immediately.

`tools/test-kinetic-network-sources.py` covers two separated creative-motor line
networks at +16 and -16 RPM, idle save/reopen, and insertion of a three-shaft
connection whose final shaft must break for equal and weaker opposing sources.
It also checks a stronger opposing source, matching +16 sources merging to
capacity 524288, same-direction slower-source transitions, separation after
removal, and an active merged save/reopen. The headless regression passed on
freshly built Horizon `native-9f42064-b2e225daec86` (focused source regression rerun after rebase). The existing
small/large-waterwheel, loaded-stressometer, rotation-speed-controller-cascade,
rotation-speed-controller-competing and rotation-speed-controller-LAN checks
also passed on that exact build (6/6). Commands:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-b2e225daec86/horizon-ctl .local/patched-launcher/versions/native-9f42064-b2e225daec86/horizon-client .local/horizon-client/26.3 --jobs 1 --check kinetic-network-sources
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-03cb1f8496d1/horizon-ctl .local/patched-launcher/versions/native-9f42064-03cb1f8496d1/horizon-client .local/horizon-client/26.3 --jobs 1 --check small-waterwheel --check large-waterwheel --check loaded-stressometer --check rotation-speed-controller-cascade --check rotation-speed-controller-competing --check rotation-speed-controller-lan
```

These Horizon outcomes are integration regressions, not captured Java trace
equivalence. Branch layouts and LAN guest observation of this source-merge
case remain follow-ups. Full 1:1 remains Open.


### APP-1943 stress-capacity boundary — November 19, 2026

Extended the existing `tools/test-loaded-stressometer.py` rig; no new load
family or separate fixture. The small water wheel supplies 8 RPM and 256 SU.
Seven, eight and nine attached millstones produce 224, 256 and 288 SU. The
check observes every connected millstone plus the wheel, shaft, stressometer
and a connected speedometer. It then removes all mills and checks recovery.

Expected behavior comes from pinned Java `KineticNetwork.calculateCapacity`,
`calculateStress` and `getStressMultiplierForSpeed`,
`KineticBlockEntity.updateFromNetwork` (`capacity < stress`) and `getSpeed`,
`StressGaugeBlockEntity.updateFromNetwork`, and
`SpeedGaugeBlockEntity.onSpeedChanged`. The already captured Java
`fixtures/loaded_stressometer-java.csv` provides the same 256-SU source and
prior below/above/recovery samples; the strict at-capacity outcome follows
the pinned Java comparison (`256 < 256` is false). This case checks both the
stored theoretical ±8 RPM across the connected gear train and the effective
speedometer response: it stays active below/at capacity, reads zero at 288 SU,
and resumes after removing the load.

On fresh build `native-9f42064-b2e225daec86`, the 105-tick existing Java trace
and Goggles comparison passed, followed by the added boundary states:

| Load | Java expected capacity/stress | Connected stored RPM | Effective speedometer | Result |
| --- | --- | --- | --- | --- |
| 7 mills | 256 / 224 SU | Wheel/shaft/gauges +8; millstones alternate ±8 | Moving | Pass |
| 8 mills | 256 / 256 SU | Wheel/shaft/gauges +8; millstones alternate ±8 | Moving at equality | Pass |
| 9 mills | 256 / 288 SU | Theoretical values remain signed ±8 | 0 while overstressed | Pass |
| Mills removed | 256 / 0 SU | Wheel/shaft/gauges +8 | Moving again | Pass |

The overloaded effective-speed comparison uses Java `getSpeed()` (zero while
overstressed); the saved per-member `Speed` remains the theoretical signed
RPM, as in Java. The stressometer value was 0.875, 1.0 and 1.125 respectively,
then returned to zero on recovery. Command:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-b2e225daec86/horizon-ctl .local/patched-launcher/versions/native-9f42064-b2e225daec86/horizon-client .local/horizon-client/26.3 --jobs 1 --check loaded-stressometer
```

Branch layouts and direct LAN guest observation of this source merge remain
follow-ups; Full 1:1 stays Open.


### APP-2102 server configuration, permissions and persistence — November 19, 2026

On the available Horizon client `native-9f42064-6ce68a31b125` (Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, mixins
`5a64af938ec86b00d53d16a408aabc0038fb3e57`) with the content pack prepared
from Create `ac0c444d9828da3453ae8cc65338e8de063286fb` (SHA-256
`9a84fcfb00af7a5ffd52d1fe61a0ef853af78e197e557f192f5842cd8c383f0e`), the
dedicated baseline check passed these bounded cases:

- A generated `server.properties` retained the default `spawn-protection=16`;
  setting `difficulty=hard` was observable from the connected operator.
- The operator executed `/give`; the nonoperator's same command did not grant
  an item. The server's `ops.json` retained the operator at permission level 4.
- A guest received paper, disconnected, rejoined with the same identity, and
  retained the item.
- The existing LAN Hand Crank check passed guest reversal: shaft speed changed
  from +32 to −32 RPM. Its idle and active save/reopen cases passed; the active
  16 RPM motor and shaft resumed after reopening.

## Bogeys and train assembly (APP-2047)

The pinned Java reference is Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
`StationBlockEntity.refreshAssemblyInfo()` takes its axis from the selected
track edge and target direction, starts one block along that axis, and checks
bogeys at the track's up normal. Its default bogey limit is 20.
`isValidBogeyOffset()` rejects positions less than three blocks from an existing
bogey. During `assemble()`, each captured carriage must contain its ordered
second bogey at the next discovered bogey position when it has one. The rig
follows those rules: target `[9,112,-8]`,
direction `+X`, track at `y=112`, and bogeys at `[10,113,-8]`,
`[13,113,-8]`, `[17,113,-8]`, and `[20,113,-8]`. Two independent Glue regions
connect each pair to its own plank body, controls and barrel.

The first Horizon fixture attempt showed four placed bogeys but a disabled
assembly button. Instrumentation confirmed target `[9,112,-8]`, direction `+X`,
and a 24-block track scan. The station had cached a zero count on the first
assembly-mode tick, before the fixture placed the bogeys; frozen game time then
prevented another scan before the UI was reopened. Stepping one game tick after
placement makes the station discover all four bogeys before the menu opens. No
station direction or scan change was needed. The registered
[multi-carriage replay](tools/test-train-multi-carriage.py) now checks assembly
and all four bogey offsets, host save/reopen, guest convergence on the assembled
and restored blocks, cargo restoration for both carriages, and a separate
40-tick manual drive where all eight track points move.

On `native-9f42064-4d9ec02143c5` (Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`), with pack SHA-256
`cb9a737fce8e9f26c0b0f4f0a8fc2af332959c39f1d4cb3ca06f9a3583e28fcc`, the
multi-carriage test and affected `train-bogeys`, `manual-train`,
`train-disassembly`, and `train-standing-disassembly` regressions passed. The
multi-carriage movement assertion verifies movement and all eight track-point
updates, not Java-equivalent multi-carriage speed timing. Broader layouts,
curved multi-carriage movement, and full Java parity remain open.

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-4d9ec02143c5/horizon-ctl .local/patched-launcher/versions/native-9f42064-4d9ec02143c5/horizon-client .local/horizon-client/26.3 --jobs 2 --check train-multi-carriage --check train-bogeys --check manual-train --check train-disassembly --check train-standing-disassembly
```

Final client SHA-256: `6e33963a1eeae1b6e0344f22ee9af92aa4acb9f740343a3ad4465e31b2e290f0`;
control tool SHA-256: `1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`.

## APP-1978 Super Glue and assembly selection

The pinned Java reference is Create `ac0c444d9828da3453ae8cc65338e8de063286fb`.
`SuperGlueSelectionHandler` cancels an active selection on sneak, while
`SuperGlueSelectionPacket` creates the selected region and calls
`SuperGlueSelectionHelper.collectGlueFromInventory` once for availability and
again for consumption. Despite its `simulate` argument, that helper calls
`hurtAndBreak` in both invocations and scans the selected slot followed by the
remaining inventory. Super Glue durability is 99 (`AllItems.SUPER_GLUE`).

The baseline mismatch was reproduced on `native-9f42064-59c1049d0f04` with the
new isolated spare-stack case: start with damage-99 Glue in hotbar slot 0 and a
fresh Glue in slot 1, then select two connected blocks. The region was created
and slot 0 broke, but Horizon left slot 1 at damage 0. Java consumes one point
from slot 1 during the second helper call. The original check log was replaced
by the final run; the observed baseline command, state and failed assertion are
preserved in `.local/parity/super-glue-selection-baseline-spare-stack-failure.txt`.

Horizon now searches Glue in Java's selected-then-inventory order. It swaps a
spare stack through the selected slot while calling the ordinary durability
path, preserving wear handling and break effects, then restores the changed
stack to its original slot. Guest actions mark the inventory for resend. Glue
use remains main-hand only, matching Java's client handler. Removal now accepts
a left-click on a block whose center lies inside a Glue region, when main-hand
Glue is held and the acting player is within Java's 32-block range. It removes
the nearest matching region and cancels breaking the underlying block. This
block-hit route is a usable approximation: the marker has no Java entity
hitbox, so exact entity ray picking, hit plane presentation, particles and
sound remain unverified.

On `native-9f42064-8cc365d013ad`, the isolated solo check passed selection,
saved-region reopen, damage-97/98 last-charge edges, spare-stack final-charge
fallback, sneak cancellation, two overlapping regions and block-preserving
removal. The LAN guest check passed normal region/durability, spare-stack
consumption into slot 1 (damage 1), and guest removal with the block retained.
The existing train assembly check matched all 125 Java motion ticks, and the
multiplayer train check assembled on the dedicated server and observed 37
Java-matching guest motion ticks. These train checks are representative
integration coverage; they do not establish every glue configuration or full
train parity. The suite output is in `.local/parity/`.

Runtime identity: client SHA256
`d78524837d9c33c4d7790a8ce9febcacb7c58679ff1543a98e8958d0714267c2`; control
tool SHA256 `1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`;
content pack SHA256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The unchanged train structure fixture used for the isolated worktree has SHA256
`ff7048a951a87371c5cbe6fc7b98a2f087a6137be85d73b21d43975003cd5c58`.

Commands:

```sh
python3 tools/test-server-baseline.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --pack .local/create.hmod
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check hand-crank-lan --check hand-crank-persistence
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-8cc365d013ad/horizon-ctl .local/patched-launcher/versions/native-9f42064-8cc365d013ad/horizon-client .local/patched-launcher/versions/native-9f42064-8cc365d013ad/.local/horizon-client/26.3 --jobs 1 --check super-glue-selection
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-8cc365d013ad/horizon-ctl .local/patched-launcher/versions/native-9f42064-8cc365d013ad/horizon-client .local/patched-launcher/versions/native-9f42064-8cc365d013ad/.local/horizon-client/26.3 --jobs 1 --check super-glue-selection-lan
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-8cc365d013ad/horizon-ctl .local/patched-launcher/versions/native-9f42064-8cc365d013ad/horizon-client .local/patched-launcher/versions/native-9f42064-8cc365d013ad/.local/horizon-client/26.3 --jobs 1 --check manual-train --check multiplayer-train
```

The new dedicated check is registered as `server-baseline` in
`tools/test-parity.py`. This scoped config case exercises Minecraft's
`server.properties`; it does not establish Create `create-server.toml`
loading/import, network synchronization or migration. The existing hand-crank
restart check is a local world reopen, while the multiplayer check exercises a
dedicated LAN world. Those broader cases and Full 1:1 remain open.


## Item Vault gameplay baseline (APP-2015)

On `native-9f42064-6ce68a31b125` (Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`) with pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`, the
registered [bounded vault replay](tools/test-vault-groups.py) passed these
state and interaction cases:

- A Hopper inserted paper through the first member of a two-block group; a
  second Hopper extracted it through the other member. Both blocks then read
  empty.
- Removing one empty member split the group and left its neighbor usable.
- A surviving member was filled to all 20 slots (64 paper plus 19 stacks of
  stone). Two additional paper remained in its Hopper across save/reopen; after
  one slot was freed, the transfer completed without loss or duplication.
- A LAN guest opened that output Hopper, retrieved its paper, and the host saw
  the emptied slot after state convergence. This proves the resulting state,
  not Java-equivalent packet arrival timing.
- A complete 3×3×9 horizontal group reached the large state. This matches the
  pinned `ItemVaultBlockEntity` width limit of 3 and length limit of
  `width * 3`.

The sampled checks use command-driven setup and state observation rather than
a new Java tick trace. The behavior follows the pinned
`ItemVaultBlock.java`, `ItemVaultBlockEntity.java`, and
`ConnectivityHandler.java` rules. Existing Java comparisons remain the 69-tick
comparator, 151-tick storage, and 20-tick fuel protection fixtures. The
[survival recipe replay](tools/test-machine-crafting.py) also covers the
original Item Vault recipe among 12 matching recipes. Existing mounted cargo
comparisons cover guest Hopper insertion and extraction with a mounted Vault.

Run the bounded group replay with:

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check vault-groups --check vault-groups-lan
```

Other dimensions, storage groupings and material combinations remain follow-up
coverage; Full 1:1 stays Open.

APP-1978 bounded outcomes do not claim exact Java packet timing or exhaustive
connectivity, inventory, rendering or effect parity. Full 1:1 remains Open.


## Millstone gameplay baseline (APP-1958)

On `native-9f42064-c9fa0f927bed` (Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`) with the pinned Create source
`ac0c444d9828da3453ae8cc65338e8de063286fb` and prepared pack SHA-256
`8c375b36ab5485aad9e4e2793bc416182c9971428107e4df3269622c80553557`, all six
registered checks passed:

- `wheat-milling`: all 81 samples (ticks 0–80) matched the upstream fixture,
  including RPM, timer and item transfers.
- `milling-recipes`: clay, wool and bone each matched 106 fixture rows.
- `millstone-lifecycle`: stopped idle contents/timer and a partway active wheat
  cycle survived world reopen; the resumed result was within the pinned recipe's
  guaranteed and chance-output bounds.
- `millstone-backpressure`: a full result slot paused processing without
  consuming the input, and freeing capacity let the wheat cycle complete.
- `millstone-lan`: a survival guest supplied wheat and collected the flour;
  host and guest inventories converged after the LAN interaction.
- `milling-lookup`: clay and wheat recipes opened in solo and LAN lookup.

The lifecycle and backpressure replays are source-aligned Horizon gameplay
checks, not exact Java save/reload trace comparisons. The LAN check establishes
eventual inventory state, not packet timing. These representative cases do not
establish exhaustive recipe, chance distribution, layout, rendering or effect
parity; Full 1:1 remains Open.

Run the six checks together with:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-c9fa0f927bed/horizon-ctl .local/patched-launcher/versions/native-9f42064-c9fa0f927bed/horizon-client .local/patched-launcher/versions/native-9f42064-c9fa0f927bed/.local/horizon-client/26.3 --jobs 1 --check wheat-milling --check milling-recipes --check millstone-lifecycle --check millstone-backpressure --check millstone-lan --check milling-lookup
```

## Smart Observer gameplay baseline (APP-2040)

The pinned Java Create `ac0c444d9828da3453ae8cc65338e8de063286fb` observes the
unsided inventory capability of its target. In a double chest, either half
exposes the combined inventory. The detector now uses Horizon's chest pairing
to include the far half.

The [Java GameTest](tools/java-smart-observer-double-chest.patch) produced
[four samples](fixtures/smart-observer-double-chest-java.csv) after configuring a
three-stone filter sample. Eight dirt in the attached half did not qualify. One
stone in the far half sustained the six-tick countdown and powered the lamp.
Removing that stone let the signal and lamp turn off, and replacing it restored
both. GameTest tick 8 is the trace origin. In a disposable pinned checkout,
run `git apply --unidiff-zero /path/to/tools/java-smart-observer-double-chest.patch`
and then `./gradlew --offline --no-daemon --max-workers=2 runGameTestServer`
with JDK 21. Extract the fields after `SMART_OBSERVER_DOUBLE_CHEST,`.
The capture passed in 3m 14s. The patch and CSV SHA-256 hashes are
`23e274596631537f54aaa0edde379613126464f15b05f0351ff1fe806318e4c7` and
`5541fdf862d94163ab456b624d073a628478f2d0f5c52f305a68a740b1d07f0c`.

The [lifecycle replay](tools/test-smart-observer-lifecycle.py) also configures a
filtered barrel that stays idle and cold reopens both setups. The LAN variant
applies both filters through guest survival input, then rejoins the cold
reopened host and checks that the guest sees the same powered and idle states.
The reload checks use Horizon saves. Guest checks assert convergence.

Before the fix, both the solo and LAN lifecycle runs matched the rejection
control and then failed the first matching-item sample on
`native-9f42064-6ce68a31b125`: filter sample 3 and far-half count 1 agreed
with Java, while the countdown was 0 and both the Observer and lamp stayed
off. On that archived client, the existing storage, filtered storage,
solo/LAN filter input, world, chute motion, belt/funnel and Display Link
replays passed in 315 seconds.

The incremental private launcher 0.2.67 build on Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` produced
`native-9f42064-9d5ee01041b7` in 264 seconds. The client SHA-256 was
`5b4e7bab7264ed05e78a49f9f26e2457bb79aa0203235104063d2eff5add5aea`
and the pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Both `observer-lifecycle` and `observer-lifecycle-lan` matched all four Java
samples and passed their cold-reopen checks in 78 seconds together. The LAN
guest restored its view of both observers and lamps after reconnecting. The
full ten-check batch passed on a rebuilt candidate after rebasing onto
`036972379bc9b35b3fc371ae6755abcbb79f3f9f` (Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`). The rebuilt client
`native-9f42064-9669a74fb4bf` has SHA-256
`f504c88fadca21613d4e9a13436ee8686872791287e74c7d49e581637b05a9be`.

The same candidate passed all eight selected regressions.

| Check | Matching Java coverage |
| --- | --- |
| `observer-storage`, `observer-filtered-storage` | 46 unfiltered samples and 92 filtered samples across two lanes |
| `observer-filter-input`, `observer-filter-input-lan` | 56 observations in each role, including filter changes and clearing |
| `observer-world` | 72 samples across two block lanes and 46 chute samples |
| `observer-chutes` | 18 ticks of chute item motion and the downstream piston |
| `observer-belt-funnel` | 180 ticks of Observer output, item movement, pistons and Gantry |
| `display-link` | 146 ticks of single and double chest counts and redstone gating |

Run the focused batch with Python 3.10 or newer and the prepared resources:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 2 \
  --check observer-lifecycle --check observer-lifecycle-lan \
  --check observer-storage --check observer-filtered-storage \
  --check observer-filter-input --check observer-filter-input-lan \
  --check observer-world --check observer-chutes --check observer-belt-funnel \
  --check display-link
```

Full 1:1 remains Open, including broader target and filter combinations and
Java-equivalent packet timing.

# APP-2021 Packager gameplay baseline

The finite APP-2021 baseline covers survival placement beside a stocked Barrel,
addressed package dispatch on a redstone pulse, unpacking, full-target handling,
and idle and in-flight save/reopen. The Java replay covers package creation,
cargo and address retention, pickup, unpacking and a second pulse in solo and
LAN. Stock Link dispatch is covered by the linked Packager checks below. Full
1:1 remains Open for other inventory capabilities, multi-source ordering,
effects, and exact Java packet and reload timing.

The focused Packager checks passed on pinned Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` in client build
`native-9f42064-99eb016dfcb1`. The Packager pack SHA-256 was
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.

| Check | Evidence |
| --- | --- |
| `packager-placement` | Survival placement faced the stocked Barrel; a pulse sent five iron and two redstone with the sign address. |
| `packager-lifecycle` | Orientation and stock persisted through idle reopen; an addressed in-flight package resumed after reopen and was retrievable; a full 27-slot Barrel rejected dispatch without changing the held package and accepted it after capacity opened. |
| `packager`, `packager-lan` | Both roles matched all 67 Java Packager state and wire samples; visual pose sampling covered 11 poses in each role. Guest convergence was observed. |
| `stock-link-packager`, `stock-link-packager-lan` | Solo and LAN each matched 26 Java Stock Link snapshots. |

Run the focused gameplay checks with the compatible launcher and prepared
resources. `test-parity.py` uses the repository's `.local/create.hmod`; place
the verified Packager HMOD there (SHA-256 above) before invoking this batch.
The two new checks also accept `--pack` when run directly:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 2 \
  --check packager-placement --check packager-lifecycle \
  --check packager --check packager-lan \
  --check stock-link-packager --check stock-link-packager-lan
```

The isolated lifecycle cases verify Horizon reopen behavior; they do not claim
exact Java save/reload parity. Guest convergence does not establish exact
packet-arrival or interpolation parity.
# APP-1971 Chute and Smart Chute gameplay baseline

The finite APP-1971 baseline covers survival acquisition, representative
vertical transfer, Smart Chute controls, backpressure, persistence, and LAN
guest interaction. Full 1:1 remains Open for airflow, branch and mounted
layouts and exact Java save/network timing.

`tools/test-chute-crafting.py` verifies the pinned survival recipes: four
Chutes from iron sheets and an iron ingot, then one Smart Chute from a brass
sheet, Chute and Electron Tube. `tools/test-creative-crate-chute.py` matches 13
Java cargo ticks for ordinary downward and upward delivery in solo and LAN.
`tools/test-item-filter-chute.py` matches all 20 Java Smart Chute snapshots at
tick 16 in solo and LAN; the lifecycle cases exercise filter edits, rejected
input, powered stop/resume, and cold reopen with idle and in-flight cargo.
`tools/test-clipboard-copy.py --chute` checks exact Clipboard transfer for
filter, amount and mode settings, including List Filter installation and the
filter-only case, in solo and LAN. The upward full-Chest capacity cases match
all 19 Java samples in both modes and verify delivery resumes when capacity
opens.

The focused batch passed 11/11 registered checks on the fresh client built
from port commit `1da56f2a0e33936df8e007e3c188e09fd20057e0` and pinned Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. Client SHA-256:
`322cad6d76f2c9c3f9d9f18ab68252035d39e0457ad50c3c4f8a161839ac9ebf`; pack
SHA-256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Checks: `chute-survival-crafting`, `item-filter-chute`,
`item-filter-chute-lan`, `smart-chute-clipboard`,
`smart-chute-clipboard-lan`, `creative-crate-chute`,
`creative-crate-chute-lan`, `creative-crate-chute-upward`,
`creative-crate-chute-upward-lan`, `upward-chute-capacity`, and
`upward-chute-capacity-lan`. Runs used isolated fixture worlds; LAN cases
included a guest. The exact focused command is:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 2 \
  --check chute-survival-crafting --check item-filter-chute \
  --check item-filter-chute-lan --check smart-chute-clipboard \
  --check smart-chute-clipboard-lan --check creative-crate-chute \
  --check creative-crate-chute-lan --check creative-crate-chute-upward \
  --check creative-crate-chute-upward-lan --check upward-chute-capacity \
  --check upward-chute-capacity-lan
```

These representative cases establish the finite gameplay baseline. They do
not claim exhaustive Java parity for every inventory, airflow, branch,
mounted, visual, effect or packet-timing combination.

## Redstone Contact gameplay baseline (APP-2000)

The pinned Java `RedstoneContactBlock.hasValidContact` accepts either a
Redstone Contact or an Elevator Contact when their facing values oppose.
Before the fix, the old Horizon client powered the Redstone-to-Redstone pair
and kept a mismatched pair off, but failed the Redstone-to-Elevator pair. The
preserved reproduction is `.local/evidence/app-2000/pre-fix-redstone-contacts.log`.
`native/contact.rs` now reads facing from both registered contact IDs for
placement adjacency, neighbor updates and the scheduled contact tick.

The finite baseline cases passed:

- A player placed a contact against a support block; its facing matched the
  pinned Java look-direction default. A matching pair, a nonmatching pair,
  and a mixed Redstone/Elevator pair produced the expected static output.
- Both connected states survived idle save/reopen. Removing each paired
  contact deactivated the remaining Redstone Contact.
- The original vertical Gantry trace matched all 111 samples, ticks 0–110,
  for carriage height (tolerance `1e-6`), three powered states (exact), and
  diamond-block height (exact). Trace origin is the first fixture sample.
- An active Gantry/contact save at fixture tick 12 reopened and matched the
  Java trace at tick 20 after server startup advanced the saved world.
- On a dedicated server, host and guest agreed on matching, mismatched, mixed
  pairs and deactivation. This confirms guest convergence, not packet-arrival
  timing equivalence.

The Java fixture is `fixtures/redstone_contacts-java.csv` from Create
`ac0c444d9828da3453ae8cc65338e8de063286fb`; the capture patch hash is
`9746209a1df14aa1c3907c22d3e5f7c2529cb447b1608b943fc8bf44c6fa8419`.
No Java recapture was needed. The final Horizon build is
`native-9f42064-395b15d09945` on pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`; its client SHA-256 is
`e7fce2430c800def29c42730261f9b79030c52bff3cf361522357956c3403145` and
the pack SHA-256 is
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The solo trace output is `.local/redstone_contacts-horizon.csv` (112 rows
including its header). The test log is `.local/parity/redstone-contacts.log`.

Run the scoped checks with the pinned client and prepared 26.3 resources:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 \
  --check redstone-contacts --check redstone-contacts-lan
```

Both checks passed. `py_compile` for the two test scripts and runner, plus
`git diff --check`, passed. Work time: setup/evidence reuse about 5 minutes;
implementation and debugging about 25 minutes; private first build 533 seconds
and incremental build 169 seconds; syntax/diff checks under a second; focused
integration runs about 8 minutes across final-main reruns. The latest-main sync
after those checks required no engine rebuild.
No exhaustive contraption layouts, cosmetic timing or Java packet timing was
claimed. Full 1:1 remains Open.


## APP-2008 Dispensers, droppers and mounted actors

The bounded comparison reused the pinned Create `ac0c444d9828da3453ae8cc65338e8de063286fb` references. The mounted dispenser implementation in this checkout is byte-identical to its source at `7f44b58c28df6a797c73e187dced78fe8575741e`; source review covered `MountedDispenseBehavior`, `DefaultMountedDispenseBehavior`, `DropperMovementBehaviour`, and `DispenserMovementBehaviour`. No consequential source mismatch appeared in the bounded cases, so no runtime edit was warranted.

The following checks passed on `native-9f42064-d6dc2ad18d3f` (Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, client SHA-256 `006bfe15a198b29d6af7633d353dcadaa07039121ae66c2081927299835a8811`) with the freshly prepared pinned pack (SHA-256 `ec0ee28f53e79af557cf6de5777d6f7c96497333be277d1aa005bbd606870e61`):

| Case | Java comparison / outcome |
| --- | --- |
| Mounted arrow dispenser on a moving bearing | All 142 observations matched, including actor pose, ammo decrement, projectile count and launch direction across four successive launches. |
| Two Gantry dispensers | All 68 samples matched for actor ordering and no duplicate/fighting effects. |
| Refilled Gantry dispensers | All 68 samples matched for ammo refill from mounted cargo and subsequent firing. |
| Dropper into Creative Crate, solo and LAN | Both 26-observation replays passed. |
| Dropper into Chute, solo and LAN | Both registered cargo-transfer checks passed. |

The focused command was `python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 --check arrow-dispenser --check dispensers-dont-fight --check dispensers-refill --check creative-crate-dropper --check creative-crate-dropper-lan --check package-dropper-chute --check package-dropper-chute-lan`. The first three outputs are `.local/arrow_dispenser-horizon.csv`, `.local/dispensers_dont_fight-horizon.csv`, and `.local/dispensers_refill-horizon.csv`; individual logs are in `.local/parity/`.

The Dropper LAN cases establish guest operation and convergence for those adjacent item-transfer paths. The mounted Gantry/bearing cases above were solo only. The follow-up mounted-actor gate below covers the remaining representative guest and persistence cases; host/guest timing equivalence and all other payload/mounting combinations remain unverified. Full 1:1 remains Open.

The follow-up harness `tools/test-mounted-dispenser-gates.py` now assembles a
real Dropper fixture before the bearing actor is created, with a five-item
cobblestone stack. On the pinned `native-9f42064-d6dc2ad18d3f` runtime, the
mounted Dropper decremented and ejected one item, the LAN guest converged, and
both idle and active `/save-all`/reopen checks conserved stack plus dropped-item
counts. The mounted dispenser launched an arrow, conserved ammo and projectile
count through idle and active reopen, and the rendered guest screenshot visibly
contains the launched arrow. The `horizon-ctl entities` API is deliberately not
used as a projectile oracle because it reports mobs, item drops and XP only;
the guest screenshot is the replication assertion. Fresh artifacts are kept
under `.local/app-2008-dispenser-fix/`, and the latest full run is recorded in
`/private/tmp/app2008-mounted-full-no-diagnose.log`.

The checks are registered as `mounted-dispenser-gates` and
`mounted-dispenser-dropper` in `tools/test-parity.py`. This is representative
coverage, not exhaustive payload, mounting or packet-timing parity; keep the
family Partial and Full 1:1 Open.

# APP-1981 Mechanical Saw gameplay baseline

The bounded pass for APP-1981 keeps the existing generated Spruce Trapdoor
trace and adds the gameplay cases that were missing from the matrix. It ran on
Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, native build
`native-9f42064-06476b4a74cb`, Create Java reference
`ac0c444d9828da3453ae8cc65338e8de063286fb`, and pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`.
The rebuilt client is `native-9f42064-6a56a7b08e28`; its
`horizon-client` SHA-256 is
`849467cabc3e7ae6c013fe321fb0bcab843f37185074c883ea18eb9b941a7751`.
It was built with `main` at `10b9850`. The later `main` updates through
`4c28752` contain no `native/` changes, so the saw runtime source is unchanged.

The focused seven-check batch passed 7/7 on this build:

- `mechanical-saw`: the existing bamboo plank cut and horizontal log cut
  matched all 96 sampled Java ticks, including the invalid Diamond pass-through.
- `runtime-saw`: the generated Spruce Trapdoor cut matched all 96 Java ticks.
- `mechanical-saw-placement`: placement and the filter configuration UI passed.
- `electronics-crafting`: the survival Mechanical Saw recipe passed.
- `mechanical-saw-output-recovery`: a full Depot held the saw's Bamboo Mosaic;
  clearing the Depot delivered the buffered output without loss.
- `mechanical-saw-tree-bearing`: an idle filter survived save/reopen; the
  powered bearing-mounted saw then cut a representative three-log oak trunk,
  survived active save/reopen, removed its attached leaves, and retained all
  three logs in mounted storage.
- `mechanical-saw-lan`: with the host tick loop running, the guest collected
  the actual filtered Bamboo Mosaic output from the powered saw; the host
  observed no duplicated Bamboo Planks.

Run with the exact built client and prepared resources:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 \
  --check mechanical-saw --check runtime-saw \
  --check mechanical-saw-placement --check electronics-crafting \
  --check mechanical-saw-tree-bearing \
  --check mechanical-saw-output-recovery --check mechanical-saw-lan
```

Two earlier exploratory guest fixtures did not establish transfer: one left a
guest-dropped item at a stale pre-teleport spawn height, and another had the
guest close enough to pick up the input before the saw. Their diagnostics are
preserved in `.local/parity/mechanical-saw-lan.log`; the final fixture avoids
both setup errors and passes. Broader tree species, other cutting outputs and
exact moving-contraption tick timing remain follow-ups. Full 1:1 remains Open.
# APP-2084 Potato Cannon gameplay baseline

The bounded APP-2084 pass reuses the pinned Create Java traces and checks the finite gameplay gates in the issue. Java source is Create 6.0.10 at
ac0c444d9828da3453ae8cc65338e8de063286fb; the cannon item callback reviewed
for ammunition rejection is
src/main/java/com/simibubi/create/content/equipment/potatoCannon/PotatoCannonItem.java
(SHA-256 828a2f94493104651ad6d6beb0c3225cec8512fb42662b804b3f4c9428cd19cb).
Unsupported ammunition is rejected by getAmmo when the selected item has no
registered projectile type; use returns PASS before consumption, wear,
cooldown, or projectile creation. The updated existing launch fixture checks
this with three sticks, retaining all three and the cannon's durability with no
projectile, in solo and LAN.

| Gate | Bounded cases and result |
| --- | --- |
| Acquisition, ammo and cooldown | mechanical-tools-crafting produced the original cannon recipe. potato-cannon checked an empty click, rejected sticks, then an accepted potato shot, consumption, cannon wear, launch pose/velocity, and the first three Java flight ticks within 1e-6, solo and LAN. potato-cannon-priority covered eight supported-ammo selection/consumption cases in each mode. potato-cannon-ammo-cooldown matched Java player-tick cooldown boundaries for potato, carrot, apple, beetroot, melon slice and golden carrot in each mode. |
| Crop action and special ammunition | potato-cannon-carrot-farmland matched the Java upward-face crop action control: a vanilla carrot shot removed the projectile but left farmland and the crop space unchanged through tick 5, solo and LAN. potato-cannon-cure matched golden-apple cure initiation for weakened and ordinary zombie villagers through ticks 0–4 in both modes. Other crop-action implementations and cure completion remain follow-ups. |
| Player impact and multiplayer | potato-cannon-honey-guest-to-host and potato-cannon-honey-host-to-guest matched Java damage and Slowness II on an actual LAN player in both firing directions. The launch, ammo-priority, cooldown, Backtank, cure, crop-action, and projectile-save cases also ran as solo/LAN pairs. Guest convergence is established; packet arrival/interpolation timing is not claimed. |
| Backtank and persistence | potato-cannon-backtank matched the six Java air-charge outcomes, ammunition use, cannon wear and projectile creation in solo and LAN. APP-2081's completed Copper Backtank baseline also checked charged/partially depleted save/reopen. potato-projectile-save retained an in-flight apple's source stack, projectile UUID and shooter UUID across save/reopen for a solo shooter and a LAN guest. Continued post-reopen flight and other recovery paths remain open. |

The 17 focused checks passed: mechanical-tools-crafting, potato-cannon and
potato-cannon-lan, potato-cannon-priority and its LAN variant,
potato-cannon-ammo-cooldown and its LAN variant,
potato-cannon-backtank and its LAN variant,
potato-cannon-carrot-farmland and its LAN variant,
potato-cannon-cure and its LAN variant, both Honeyed Apple LAN directions,
and potato-projectile-save and its LAN variant. The original 17-check batch
passed; after adding the unsupported-stick assertion to the existing launch
fixture, both updated launch checks passed again (2/2). The initial socket
denial and first LAN fixture-timing failure are preserved under
.local/parity-app-2084-sandbox-denied/ and
.local/parity-app-2084-stick-first-run/; the LAN fixture now waits three
player ticks after the rejected click.

The run used Horizon 9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0, native build
native-9f42064-6bdf8691aa42 (prepared with main at 781c0ef), client SHA-256
703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe, pinned
Create Java above, and pack SHA-256
a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b.
Current main at verification is c8e0638. The Potato Cannon Rust module and its
selected engine patches are unchanged between 781c0ef and 8e4d539. Newer main
does include other native modules and mixin entries, so a fresh combined-build
run is still needed before integration is considered complete.

Commands:

```sh
python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 \
  --check mechanical-tools-crafting --check potato-cannon \
  --check potato-cannon-lan --check potato-cannon-priority \
  --check potato-cannon-priority-lan --check potato-cannon-ammo-cooldown \
  --check potato-cannon-ammo-cooldown-lan --check potato-cannon-backtank \
  --check potato-cannon-backtank-lan --check potato-cannon-carrot-farmland \
  --check potato-cannon-carrot-farmland-lan --check potato-cannon-cure \
  --check potato-cannon-cure-lan --check potato-cannon-honey-guest-to-host \
  --check potato-cannon-honey-host-to-guest --check potato-projectile-save \
  --check potato-projectile-save-lan

python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 \
  --check potato-cannon --check potato-cannon-lan
```

The build script was attempted from an isolated APP-2084 worktree using a
private copy-on-write launcher cache; the compatible launcher stopped before
compilation when it could not resolve
api.github.com/repos/horizon-rust/horizon/commits/9f42064 in this offline
environment. No current-main native build was produced. The bounded gameplay
baseline is supported by the identified run above; combined-build validation
remains required after this PR. Full 1:1 remains Open.

Reused Java capture patch SHA-256 values:

| Capture patch | SHA-256 |
| --- | --- |
| tools/java-potato-cannon-trace.patch | abd17e22e40fe93b800f7aeedf3f527c8171cd7508a5edd10b59517c8b7b6cce |
| tools/java-potato-cannon-ammo-batch.patch | 9176e13ec02e027252f38b86b4b70b9550ce89050764178d38b88dacc2c8e7a7 |
| tools/java-potato-cannon-priority.patch | 5dcf16858c49c9f07c7033a4bf0e90b103498df24a1147f5715d428e432cf224 |
| tools/java-potato-cannon-backtank.patch | 35659521871485e9dd6dc7c485f5736dfc44b44f4653b85133562801d1b6b8f8 |
| tools/java-potato-cannon-carrot-farmland.patch | ab6d4fb9dd65fcb683efb8d89a7e6fd67424c5ac82391460701b73d91e1345ab |
| tools/java-potato-cannon-cure.patch | 4c9678d92f0bd9cf7cd77432fea0db0c8696905141fa1f7f0729832273c2610e |
| tools/java-potato-cannon-honey-player.patch | 6c1d67e4d2a19d1154828058a89b220f55ef4ba79446a44382c0df3c5230fa21 |
| tools/java-potato-projectile-save.patch | 532c819b8da18f3b7ba03e03cf9a1894d533915c8362ca412be803765786acca |

## APP-2007 Mechanical Roller gameplay baseline
The finite checks completed on the pinned Create reference
`ac0c444d9828da3453ae8cc65338e8de063286fb` and Horizon pin
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`:

- Existing Java comparisons `roller_filling` and `roller_paving_and_clearing`
  passed on the final combined client. Together they compare 262 captured ticks for
  fill, paving and clearing behavior, including the recorded material cases.
- `roller-mode-ui` crafted a Roller from its pinned survival recipe, placed it
  on a full floor, and confirmed the crafted item was consumed. It selected
  Tunnel Pave, Straight Fill and Wide Fill as host; a LAN guest selected Wide
  Fill and the host observed the server value. The selected mode persisted
  through `/save-all flush` and fixture restart. This
  proves guest convergence and idle mode persistence, not packet-arrival timing
  parity.
- The Java `RollerBlockEntity` assigns separate value boxes to filtering
  (`hOffset=3`) and mode (`hOffset=-3`). Its filter predicate rejects air,
  block entities, stairs, shapes that are not full-block outlines, and empty
  collision shapes. `FilteringBehaviour.onShortInteract` returns on an invalid
  item before consuming it; ordinary valid block materials are stored without
  consumption. These rules were checked against Create reference commit
  `ac0c444d9828da3453ae8cc65338e8de063286fb`.
- `roller-mode-ui` now checks one supported stone and one unsupported chest in
  solo and LAN. Chest clicks at the filter box retained the count of one,
  created no chest block, and left the existing filter unchanged. Stone was
  stored with its count still one. LAN assertions read both the guest inventory
  prediction and the host's authoritative `RollerGuest` inventory and block
  entity. The stone filter and host inventory remained after save/reopen.
  This verifies the filter value-box dispatch as well as item conservation; it
  does not claim exact packet timing.
- `roller-filling-reopen` matched all 80 Java ticks, saved and reopened at tick
  40, compared carriage position, material stock and world blocks at the
  boundary, then confirmed subsequent work resumed without duplication or
  skips. `roller_paving_and_clearing` matched all 181 Java ticks. Shared Gantry
  Shaft/Carriage regressions remain additional transport evidence.
- Final candidate build: `native-9f42064-5bee4a761065`, pinned Horizon
  `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`; client SHA-256
  `8b75ead5d110227f15b5ae07a708d368bad6524841ca8e16550a9f90ed5484f7`; test
  Create pack SHA-256
  `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
- Exact scoped command:

  ```sh
  python3 tools/test-parity.py "$ctl" "$client" "$resources" --jobs 1 \\
    --check roller-filling --check roller-paving-and-clearing \\
    --check roller-mode-ui
  ```

The new `native/roller.rs` work adds the mode setter, Roller placement redirect,
full-block filter validation, and the Java slab-to-double-block filter state.
`native/speed_controller_controls.rs` exposes the three mode choices through the
existing Roller value board. `tools/test-roller-mode-ui.py` is the LAN/mode and
idle-reopen check registered by the parity runner.

The finite APP-2007 gameplay gates pass on this build. Shared `gantry-lan-reload`
and `mounted-drill-gantry-lan-reload` checks additionally cover guest motion,
active save/reopen, and conserved payload output. They are shared Gantry
transport evidence rather than a claim of exact packet-timing parity for every
Roller actor case. Additional terrain patterns, drum visuals, animation and
exact network timing remain follow-ups; Full 1:1 stays Open.
## Creative Crate gameplay baseline — APP-2016

The finite baseline reuses the supply, filter refund, Hopper, Dropper, Funnel,
and Chute Java comparisons above and in the feature matrix. `creative-tabs`
checks creative availability. The persistence replay configures a tagged filter
through the crate's value box, saves and reopens the world, then verifies the
unchanged filter and continued bottomless Hopper extraction with item components
intact. The crate is a static source, so persistence is checked before and after
reopen rather than requiring an internal active-processing state. Host/guest
configuration and extraction evidence is supplied by the existing LAN cases;
guest convergence is not claimed as Java packet-timing parity. Other filter
variants, automation targets, and cosmetic/visual fidelity remain open.

On `native-9f42064-6bdf8691aa42`, the APP-2016 persistence replay and
`create-creative-tabs` passed. The persistence case used the APP-2017 evidence
pack (`create.hmod`, SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`) and
prepared 26.3 resources. It configures the filter with an actual player click,
reopens the saved world, and checks extraction for 40 ticks. Focused LAN
regressions for supply, Hopper extraction, Dropper insertion, and Funnel
insertion also passed on that build. Command:

```sh
python3 tools/test-parity.py "$CTL" "$CLIENT" "$RESOURCES" --jobs 2 \
  --check creative-crate-persistence --check create-creative-tabs \
  --check creative-crate-supply-lan --check creative-crate-hopper-lan \
  --check creative-crate-dropper-lan --check creative-crate-funnel-insert-lan
```

The Java behavior references remain pinned to Create
`ac0c444d9828da3453ae8cc65338e8de063286fb`; earlier per-family sections record
their capture patches and sampled counts. The persistence case checks ordinary
Horizon save/reopen and does not claim Java reload parity.

## APP-1967 sequenced assembly baseline

The existing Java-backed checks remain valid starting evidence: `precision-mechanism` compares 108 ticks in the four-belt, three-deployer factory; `track-crafting` compares 190 samples of the three-stage track recipe; and `sturdy-sheet` compares 67 ticks through fluid filling and two press strokes. The Precision Mechanism fixture seeds only its weighted-result roll. These checks preserve concrete item IDs, counts, assembly steps, progress-bearing belt cargo, deployer state, and final outputs where applicable.

The Mechanical Press prerequisite (APP-1960) and Deployer prerequisite (APP-1966) are Done. The APP-1967 completion gates still need a player-driven survival chain using legitimate ingredients, a wrong-step and blocked-output recovery case, representative host/guest agreement, and idle plus partway sequence save/reopen. The Java checkout and compatible Horizon runtime are not present in this worktree, so no fresh replay or resulting build identity is claimed here. Keep Full 1:1 Open; broader recipe combinations and unseeded weighted-roll coverage remain follow-ups.

## APP-2005 Contraption Controls

The existing `contraption-controls` check compares all 105 Java ticks for the
representative rotating harvester and plough fixture. It also toggles both
moving controls, checks their disabled settings after disassembly and a world
save/reopen, then reassembles and confirms the disabled actor filters return
without changing the sampled crop or soil state. The native bearing now copies
saved control settings into the moving assembly at start and writes the moving
settings back to each control block before disassembly, following
`Contraption.startMoving` and `ContraptionControlsMovement.stopMoving` in the
pinned Java source.

This passed on `native-9f42064-5c89103ca2f5` with `create.hmod` SHA-256
`825e822d982dc624a691f0cced1ca2db370d030bea0899f46432021c7036642b` and
prepared 26.3 resources:

```sh
python3 tools/test-parity.py "$CTL" "$CLIENT" "$RESOURCES" --jobs 1 \
  --check contraption-controls
```

The deployed actor effect and host input are covered by the replay. The related
Deployer regressions also pass on the same build and pack: the six-lane
application replay passes in solo and LAN, including item applications over 25
ticks, and the Deployer baseline verifies Wrench mode changes, hand exchange,
filter replacement, and exact 65-item conservation. The LAN baseline has the
guest perform those actions and confirms host/guest inventory convergence. The
idle and active Deployer save/reopen cases retain filters and held items and
resume one application with a single consumed item.

```sh
python3 tools/test-parity.py "$CTL" "$CLIENT" "$RESOURCES" --jobs 1 \
  --check deployer-applications --check deployer-applications-lan
python3 tools/test-deployer-baseline.py "$CTL" "$CLIENT" "$RESOURCES" \
  --pack .local/create.hmod --persistence
python3 tools/test-deployer-baseline.py "$CTL" "$CLIENT" "$RESOURCES" \
  --pack .local/create.hmod --lan
```

These checks use `native-9f42064-5c89103ca2f5`, prepared 26.3 resources and
pack SHA-256 `825e822d982dc624a691f0cced1ca2db370d030bea0899f46432021c7036642b`.
The Deployer behavior remains shared with APP-1966; this ticket adds no
duplicate Deployer implementation. Full 1:1 remains Open for broader actor
types, settings, effects and packet timing.

## APP-2052 train schedules, conductor and condition editor

This finite baseline reuses the pinned Java schedule and conductor captures
above. The accepted cases are schedule creation and copying; destination,
delay and one stock/passenger condition; start, pause, cancel and looping;
conductor assignment and retrieval; guest editing; and idle or active reopen
without duplicate dispatch. The editor replays cover the exact serialized
components and save/reopen state in solo and LAN. The conductor replay covers
the controlling-seat acceptance, non-controlling-seat rejection, paused
resume, returned timetable component and guest convergence. The scheduled
station replays cover destination matching, reversal, cargo-idle and mounted
item/fluid threshold behavior through the existing Java tick traces.

The evidence uses Create `ac0c444d9828da3453ae8cc65338e8de063286fb`, Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, and the compatible 0.2.67
launcher builds identified in the preceding fixture sections. Representative
editor and conductor runs compare exact components and nine hand/assignment
observations; scheduled routing runs compare 123 Java ticks in solo and LAN,
including a five-tick delay, cargo-idle reset, passenger-count alternatives,
and mounted stock/fluid thresholds. Ordinary save/reopen is covered by the
entry, multi-entry, progress, condition and conductor replays. Exact packet
arrival timing, exhaustive condition/layout combinations, cross-dimension
routes and cosmetic presentation remain Full 1:1 follow-ups rather than
baseline blockers.

For this checkout, the focused runtime verification used
`native-9f42064-6bde2ea90cf2` with prepared 26.3 resources and the isolated
Create pack (`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`):

```sh
python3 tools/test-parity.py "$CTL" "$CLIENT" "$RESOURCES" --jobs 1 \
  --check train-schedule-progress --check train-schedule-progress-lan \
  --check train-conductor --check train-conductor-lan \
  --check scheduled-reverse-trip-reopen
```

All five checks passed. The progress and conductor checks passed in solo and
LAN; the reverse-trip replay reopened parked and moving trains at its Java
trace ticks and passed the active mid-entry persistence/no-duplicate-dispatch
case. The client and fixture bundle were provisioned outside Git under the
worktree `.local` directory.

## APP-2053 scheduled routing and arrival

This bounded pass covers the compact two-station route, one branch choice,
arrival/departure/wait, missing and unreachable destinations, canceled-route
recovery, host/guest state, and en-route/dwelling reopen. It reuses the APP-2052
active and parked reverse-trip reopen evidence; those cases were not rerun for
this ticket. Full 1:1 remains Open for broader route selection, network size,
cross-dimension movement and interactions.

The pinned references are Create `ac0c444d9828da3453ae8cc65338e8de063286fb`
and Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. The runtime was
`native-9f42064-6bdf8691aa42` (client SHA-256
`703e42791612c8c1673a37cdd73385a588854e6e3d4c9a71f22fbfd39e98e1fe3`,
pack SHA-256
`a6d1b163171988886f3650e42edab3fe623ced56a9ca60856ba59a28d9b3e33b`;
prepared 26.3 resources). Existing `scheduled-station-approach` and
`scheduled-station-approach-lan` each matched 123 Java samples for arrival,
departure and dwell. `scheduled-wildcard-route-red-lan` matched 198 Java
samples for a guest-assigned wildcard timetable selecting the farther route
with the short branch forced red. `scheduled-reverse-trip-reopen` passed in
APP-2052 on build `native-9f42064-6bde2ea90cf2`, including parked wait and
active mid-entry reopen without duplicate dispatch.

The new `scheduled-route-recovery` integration check passed on the identified
runtime. It verified that an unavailable named destination leaves the train
parked and the schedule unpaused, restoring the station causes a retry and
arrival, taking Train Controls cancels the route and clears transit state, and
resuming the conductor timetable redispatches and arrives. The source-aligned
Java paths are `ScheduleRuntime`, `DestinationInstruction`,
`Navigation.cancelNavigation`, `CarriageContraptionEntity.startControlling`,
and `ScheduleItemEntityInteraction`.

The matching LAN recovery check remains unverified: the isolated guest launch
could not open its control socket because `/private/tmp` ran out of space. The
failed setup log is `.local/parity/scheduled-route-recovery-lan.log`; earlier
sandbox-denied socket attempts are also invalid setup, not gameplay failures.
The separate station-approach and forced-red branch LAN checks passed, so host
and guest route state is covered for the accepted arrival and branch cases, but
not yet for canceled-route recovery. No exhaustive route or packet-timing claim
is made.

## APP-2059 train display, prompts and arrival audio

On `native-9f42064-76138ca65acb`, the [bounded feedback pass](TRAIN-FEEDBACK-PARITY.md)
adds station Train Schedule Status, the named driving HUD, manual station
prompts and a mounted bell/note/whistle arrival queue. Six controlled Java delay
strings and blank-status boundaries pass. Solo and LAN drivers see the HUD and
receive the three muted playback events; configured idle links/countdowns and
active named trains retain state through reopen. Seven neighboring checks pass,
including 198 Java manual-approach samples and 183 title/throttle samples in each
role. The initial LAN fixture used an unsupported synchronous remote chat API;
the corrected full LAN replay passes, and its failed log is retained.

This preserves the earlier observed-name and schedule evidence. It does not
establish exact Java moving-audio, packet, physical speaker, waveform or reload
phase equivalence. Station Summary predictions, broader status conditions,
manual honking, continuous carriage mixing and exact HUD art/animation remain
follow-ups; the feature matrix's Full 1:1 stays Open.

## APP-2058 Train door integration gameplay baseline

The [bounded acceptance record](APP-2058-EVIDENCE.md) retains the existing Java
station, paired interaction and stopped/moving reopen comparisons. The new
[passage check](tools/test-train-door-passage.py) uses real Survival walking:
closed mounted Train Doors stop the player, manually opened paired leaves
permit crossing onto the landing, and a solid column beyond the open doorway
stops the player without changing the door states. Both host and LAN guest
positions are checked against the authoritative server. This is scoped gameplay
collision evidence; exact Java player motion and packet arrival are unverified.
APP-2051 and APP-2057 are completed prerequisites. Full 1:1 remains Open.

## APP-2093 — Schematicannon survival baseline

This pass preserves the existing 233-tick Java flight fixture and cites the Done
APP-2092 acquisition/capture/import pass as its schematic prerequisite. It adds
player controls and repairs target eligibility, atomic multi-item extraction and
unsafe source-container copying. Full 1:1 remains Open.

Pinned Java source reviewed: `SchematicannonBlockEntity.tickPrinter`,
`shouldPlace`, `shouldIgnoreBlockState`, `refillFuelIfPossible`,
`ConfigureSchematicannonPacket.handle`, `SchematicPrinter.shouldPlaceBlock`,
`ItemRequirement.defaultOf`, and `BlockHelper.prepareBlockEntityData`, at
`ac0c444d9828da3453ae8cc65338e8de063286fb`. Important source expectations are:
matching target states and unbreakable targets are skipped; protected block
entities are retained; double slabs require two items; all requirements must be
available before extraction; one gunpowder supplies 400 shots. Printing prepares
safe block-entity data instead of cloning saved container inventories.

Pre-fix live probes on `native-9f42064-de4782e18b5b` reproduced one consumed stone
and shot for an already-present block. The six-cell probe consumed one slab for
a double slab, replaced bedrock with stone, and cloned seven source diamonds.
Logs: `/private/tmp/horizon-app-2093/.local/probe-before-socket.log` and
`probe-safety-before.log`. Earlier missing-resource and sandbox-socket attempts
in `probe-before.log` are invalid setup runs, not gameplay evidence.

The finite acceptance fixture uses one six-cell existing schematic: existing
stone, missing double slab, a newly printed chest, bedrock, a stocked target
chest, and one ordinary stone target. It exercises real survival schematic and
fuel insertion; missing-material pause with one slab; exact two-slab resupply;
manual pause while a block is in flight; resume and completion; ammo exhaustion
and adjacent-gunpowder resupply; and an exact 256-block invalid anchor. The main
build must spend two slabs, one chest, one stone and three of 400 shots, retain
the stocked chest's five copper ingots, leave bedrock intact, and never clone the
seven source diamonds. Idle, active and completed reopen checks retain the plan, settings and
exact item/ammo conservation. Idle and completed snapshots compare saved fields
exactly. The active printer may legitimately advance during startup before the
control tool freezes ticks; it must retain its queue or finish with the exact
expected output and costs. This does not claim exact Java reload timing. LAN repeats guest actions and observes host/guest block convergence;
it does not establish Java packet arrival timing.

The new screen exposes Start, Pause, Stop, skip-missing, replace mode and
container replacement, plus ammo, status and the current missing stack/count.
Original Java checklist/book printing, entity printing, full safe-NBT writers,
configured-block merges, multi-block/optional-mod planning, transforms and exact
presentation remain unverified follow-ups, not exhaustive parity claims.

### Final verification

The reference capture patch SHA256 is
`9a7f1551a40113b15e2227795ff7af0806740d0b5ee8368c42aaa0c7bb30db90`;
the unchanged 233-row Java CSV SHA256 is
`f14bc77a711f17775848150dce7feba0470c871a2d8043cf0946f9a02d824da1`.
The prepared pack SHA256 is
`00d37a5973ed7a104433f59ceb7744d7a9fffafeaf8a9bd92024af7587bef3bb`,
created with `python3 tools/prepare.py /path/to/pinned/Create` and the added
five-slot `create:schematicannon` menu registration. The resource directory is
Minecraft 26.3, and the native source pin remains `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`.

Build `native-9f42064-f172164a2087` passed the survival/reopen and LAN checks,
the original 233-tick Java replay, and the Schematic Table regression. The Java
import regression also passed on the prior `native-9f42064-fd19c1af93b8` build;
the final five-check batch and combined-main verification are recorded below.
The survival fixture explicitly steps 194 ticks and the LAN fixture 169, besides
measured startup ticks. The original Java comparison covers ticks 0–232 with
zero differences in its discrete fields, six-decimal progress and flight counters.
Guest checks establish convergence, not exact Java packet arrival/interpolation.

Failed diagnostic results remain under `/private/tmp/horizon-app-2093/.local/`:
`baseline-first.log` and the labeled `baseline-*-sneak.log`/`baseline-mouse.log`
loading diagnostics; `baseline-memory-only-template.log` for the invalid
memory-only Structure Block persistence fixture; and `baseline-startup-ticks.log`
/`baseline-active-queue.log` for overstrict assumptions about startup aging.
The corrected fixture uses the APP-2092 production capture/export backend to seed
an actual saved file and checks conservation while normal startup ticks run.
Visual QA found a clipped title, stale status/ammo and a missing visible required
count; the final screen fits the viewport and synchronizes only its relevant NBT
fields and flying blocks, without broadcasting the full queued structure.

Builds used the compatible official launcher 0.2.67 and a private APFS-cloned
compiler cache in the ticket worktree. The original successful build took 447 s;
intermediate builds took 208 s and 129 s, and the synchronized-screen build 296 s.
Source/fixture authoring and debugging overlapped those builds. Setup/reference
review and pre-fix captures occupied about 5 minutes; authoring/debugging about
25 minutes; final integration/CI took about 10 minutes. After rebasing onto
`2b929215292973f625d55248cbc1940435557da3`, the PR-head build
`native-9f42064-edcfe16aa867` completed in 321 s using the same pinned launcher,
pack hash and isolated worktree cache. Its three directly affected checks all
passed: `schematicannon-baseline`, `schematicannon-baseline-lan`, and
`schematicannon`. The preceding synchronized-screen build passed the five-check
batch (`schematicannon`, both baselines, `schematic-table`, and
`schematic-java-import`); the small follow-up UI change only adds the visible
required count, and the three directly affected checks were rerun on the final
build. `python3 tools/check-source.py` and `git diff --check` passed. The
original Java replay covers ticks 0–232 with zero differences in its discrete
fields, six-decimal progress and flight counters. No full-suite or desktop-game
run was used. After main advanced to `16696be` (APP-2086 symmetry-wand
implementation and APP-2052/2055 documentation), the PR merged that source and
rebuilt as `native-9f42064-352ad233a46a` in 193 s. All ten selected checks
passed together: `schematicannon`, both Schematicannon baselines, and all seven
`symmetry-wand-*` checks. Source checks passed with 489 JSON, 45 JSONL, 893
Python, two shell and three TOML files. This is the combined-source integration
result; it does not expand APP-2093's bounded gameplay claim.

## APP-2086 Wand of Symmetry gameplay baseline

The bounded pass retains the earlier powered-crafter acquisition, XY/YZ plane,
Survival mining and Creative mining evidence. It adds ordinary Shift-use mode
configuration, both double-plane alignments and triple-plane mirroring. Java
calls these reflections rather than a separate rotational mode; their composed
reflections produce the corresponding repeated patterns around the vertical axis.

Pinned Java remains `ac0c444d9828da3453ae8cc65338e8de063286fb`; Horizon remains
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. The real headless Java GameTest patch
is `tools/java-symmetry-wand-modes.patch`, with source/capture metadata in
`fixtures/symmetry_wand_modes-java.metadata.json` and 13 discrete target/facing/
stair-shape samples in `fixtures/symmetry_wand_modes-java.csv`. The source is
north-facing straight Oak Stairs at `(12,170,25)` around origin `(10,169,22)`.
The CSV coordinates are offsets from that origin, in Java map iteration order.
The patch adds a probe and client-only annotations to render methods, without
changing gameplay rules. Initial capture passed in 27 seconds; the world-origin
refresh passed in 47 seconds.

Required cases: both additional double-plane alignments and triple-plane with
all destinations valid, one blocked by Bedrock, and supplies for only one mirror;
correct material consumption, source/mirrored loot and pickaxe damage; 13 stair
state transforms; ordinary mode/orientation UI and origin placement; disabled and
enabled item/settings save/reopen followed by resumed mirroring. Run the same
cases with a real LAN guest and host-authoritative observations. This instantaneous
feature has no active processing timer: saved enabled state plus subsequent
placement is the meaningful active substitute. Guest checks prove convergence,
not exact Java packet arrival timing. Preserve Full 1:1 Open.

Build environment: isolated worktree `/private/tmp/horizon-app-2086`, branch
`codex/app-2086-wand-of-symmetry`, private writable launcher/cache under `.local/`.
The supplied launcher cache source was already patched and failed reapplication;
retain `build-pinned.log` and `build-clean.log`. Fetching the exact pinned official
source and materializing its `CLAUDE.md` documentation symlink restored staging.
The source archive SHA-256 is
`a2549acc67393bc7e388531f59afb4a827d7427923f44b2777f05545f2495ffa`.
The official launcher 0.2.67 is used through `tools/build-native.sh`. Cursor fix
`16af87f` is an ancestor of the build source. No shared compiler cache, worlds or
user desktop game were changed. The initial sandboxed baseline attempt could not
open a control socket; `before-modes-runtime.log` is invalid gameplay evidence.
The permitted existing-client run (`native-9f42064-d6dc2ad18d3f`) timed out opening
the missing wand screen; see `before-modes-permitted.log`.

The unchanged runtime pack SHA-256 is
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
Runtime resources are the prepared pinned Nightly's `.local/horizon-client/26.3`.
All test worlds and sockets are temporary, render clients use hidden `--offscreen`,
and pure hosts are headless. Raw build, capture and integration evidence remains
under `/private/tmp/horizon-app-2086/.local/`; portable fixture and summaries are
committed.

Nonblocking follow-ups: exact preview effects, world mirror rendering and sounds,
localized selector labels, additional block/geometry/material cross-products,
custom server range configuration, and exact Java reload/network timing. The
screen uses the original panel texture and an item icon; it does not claim the
original rotating 3D mirror preview. Full 1:1 remains Open.

Final candidate: `native-9f42064-33dee4e7bb07`, client SHA-256
`a251e83f3225e484e903cd8d7b5733f537ee15f33cfe56909b3793d95562da5f`,
control tool SHA-256
`1cca267a26d8e85ed00e07fa9148fa6d3c5125313cca4b8eed8dd00bc3d0b1d8`.
Native and patch inputs are identical before/after rebasing from `40fa2fb` onto
`cd18c0f`; the intervening main commit only changes train tests/documentation.
The clean first build took 586 seconds, final incremental build 379 seconds.
Source/syntax checks passed (488 JSON, 45 JSONL, 891 Python, 2 shell and 3 TOML).
Targeted native Rust compiled as part of both complete builds; no standalone
Clippy inputs changed.

The first added implementation build `native-9f42064-c7f605d58ff4` passed the
orthogonal clear/blocked cases but reproduced a wrong first target when only one
extra stone was available. The final implementation preserves Java's 16-bucket
BlockPos HashMap traversal (including stable insertion order within collisions),
after collapsing repeated symmetry-axis positions. The initial screen screenshot
was visually inspected: both selectors and confirmation are legible on the
original panel. Raw screenshot: `.local/symmetry-settings.png` (solo) and
`.local/symmetry-settings-lan.png` (guest).

Preserved invalid harness attempts: `modes-initial.log` used an out-of-reach
activation block; `modes-initial-reach-fixed.log` and
`modes-initial-setup-debug.log` attempted a rejected direct custom-component item
command and left a previous diagonal setting active. The corrected rig configures
every mode through the actual UI. `modes-initial-ui-rig.log` is the valid pre-fix
insufficient-supply reproduction. `modes-lan-invalid-name.log` and its client log
used an overlength guest name and never exercised gameplay; the corrected guest
name is `SymmetryModes`. The initial final-suite run passed all six other checks;
only that LAN setup case needed a retry.

The Java capture origin is one block below the clicked Horizon origin. This is
a justified equivalence class: all included mirrors operate exclusively on X/Z
and preserve source Y, so the same absolute source/target blocks and Java hash
order apply. Both origins remain well inside the unchanged default 50-block range.
There is no claim about vertical reflection, exact range-boundary parity or
per-tick network timing. Integration checks are event/state assertions after
convergence, with zero tolerance for discrete blocks, components, counts and
wear; they are not tick-timing traces.

Reproduction:

```sh
sh tools/build-native.sh /path/to/launcher-0.2.67/horizon-launcher /path/to/private-launcher-data
python3 tools/test-parity.py /path/to/native-9f42064-33dee4e7bb07/horizon-ctl /path/to/native-9f42064-33dee4e7bb07/horizon-client /path/to/prepared/26.3 --jobs 2 --check 'symmetry-wand-*'
python3 tools/test-parity.py /path/to/native-9f42064-33dee4e7bb07/horizon-ctl /path/to/native-9f42064-33dee4e7bb07/horizon-client /path/to/prepared/26.3 --jobs 1 --check symmetry-wand-modes-lan
python3 tools/check-source.py
```

Pack is the worktree-local `.local/create.hmod` snapshot identified above. To
recapture Java, clone the pinned Create revision into a disposable checkout,
apply `tools/java-symmetry-wand-modes.patch`, and run
`JAVA_HOME=/path/to/jdk21 ./gradlew --offline runGameTestServer`. Extract the 13
`CREATE_SYMMETRY_MODE` rows; no Rust output is used to generate their expectations.

All seven targeted checks passed on the candidate: existing plane solo/LAN,
Survival break solo/LAN, Creative break, and the new modes solo/LAN. Final modes
logs are `final-solo-held-mouse.log`, `final-lan-held-mouse.log` and their
`.local/parity/symmetry-wand-modes*.log` case output. Across solo and guest this
covers 18 Survival placement/mining groups, 26 sampled stair transforms, four
world reopen checks, and two resumed seven-copy placements. Material/drop/wear
expectations compose the unchanged Java apply/remove per-target rules and retained
plane probes over the newly captured mirror targets.

Additional invalid fixture runs are preserved as `modes-*-staged-sneak-invalid.log`,
`modes-*-action-released-shift.log`, `modes-lan-before-input-send.log`,
`modes-lan-reopen-failure.log` and `modes-lan-forced-gamemode.log`. Inspection of
Horizon `TaskKind::releases_input` showed deferred interact/use-item tasks release
held movement keys at completion, unlike `Wait`. The final rig holds Shift through
four ticks and uses a direct mouse click until the screen opens, matching the
existing Worldshaper helper. It also explicitly returns a forced LAN rejoin from
the Creative host's mode to Survival before checking costs. An idempotent
`/gamemode` returns no chat, so setup reads the command reply rather than indexing
an empty chat list. None of these fixture corrections changed production code.

### Combined-source verification

After rebasing onto main `2b92921` (including the portable minecart cargo fix),
`native-9f42064-14bf8b98c5e3` built successfully in 242 seconds. Its client SHA-256
is `2df9b896c8f534d5404fae55eff772a956a68a727358606ebe2706368383224c`;
its control tool and pack hashes remain those recorded above. All seven registered
`symmetry-wand-*` checks passed together with `--jobs 2` in approximately 143
seconds. This includes both complete new mode/lifecycle runs and all five existing
regressions. Raw summary: `.local/combined-suite.log`; individual outputs:
`.local/parity/symmetry-wand-*.log`; build: `.local/build-combined.log`.
Verification ran on the rebased PR head before protected-branch integration.

Approximate overlapping work times: setup/cache recovery 9 minutes;
source review, implementation and fixture authoring 9 minutes; Java captures
74 seconds; complete native builds 586 + 379 + 242 seconds; syntax checks a few
seconds per pass; integration and fixture debugging about 18 minutes, plus the
combined run above. These categories overlap and are not an elapsed-time sum.

## APP-2100 Localization and UI gameplay baseline

The finite acceptance set reuses existing Java-backed fixtures for English UI,
one supported secondary locale (`de_de`), settings and text entry, a text-length
boundary, keyboard close/back behavior, guest interaction, and saved settings.
The reference is Create 6.0.10 at
`ac0c444d9828da3453ae8cc65338e8de063286fb`; Horizon is
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`.

| Case | Check and result |
| --- | --- |
| English/German settings labels and guest interaction | `clockwork-settings` passed. English and German option names matched, including `Stundenzeiger zuerst`, `Minutenzeiger zuerst`, and `24-Stunden-Zeiger zuerst`; option spacing and six-tick hold/release behavior matched Java. The host cycled settings and a Survival LAN guest changed the authoritative mode twice. |
| Text entry, keyboard close, overflow and persistence | `track-station-name` and `track-station-name-lan` passed all five Java rows: default name, regular name, whitespace-only rejection, padded Unicode, and the 25-unit maximum with excess input ignored. Enter committed edits and Escape closed the editor. The host's final name survived world restart; guest edits reached the host. |
| Menu text input, guest use and saved settings | `train-schedule-entry` passed. A host and LAN guest entered `Main Platform *`, confirmed the five-second delay action, reopened the card, and retained the exact Java item component. The host's component survived world restart. |
| Selected-item and gauge text | `goggles-gauges` matched all 78 Java readout samples across ten gauge cases, including text, colors and strikethrough. |

All five checks passed on the identified client
`native-9f42064-6ce68a31b125` with the matching prepared pack. Horizon client
SHA-256 is `bdbafe5289f2c05ef76009c17070e0320a7c606e042dd5202b142e0e6d123fc9`;
Create pack SHA-256 is
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The first two station-name attempts stopped before launching because the fresh
worktree lacked the ignored local Java structure fixture; after that single
817-byte fixture was copied into the isolated worktree, both station checks
passed. Raw final logs are in `.local/parity/` in the APP-2100 worktree.

The batch command was `HORIZON_NO_AUDIO=1 python3 tools/test-parity.py
<horizon-ctl> <horizon-client> <prepared-26.3> --jobs 2 --check
clockwork-settings --check track-station-name --check track-station-name-lan
--check train-schedule-entry --check goggles-gauges`. Station checks were also
rerun together with `--jobs 1` after staging the missing ignored fixture.

This establishes the bounded gameplay baseline only. Other locales, additional
text fields and overflow limits, accessibility, broad menu coverage, and exact
typographic/pixel parity remain unverified; Full 1:1 stays Open.


No production defect appeared in this bounded pass, so no native/UI code or Java
capture changed. Approximate effort: setup and source/evidence review 8 minutes;
documentation 4 minutes; Java capture and native build 0 minutes; targeted
integration checks 1 minute elapsed; fixture setup/debugging 3 minutes.
