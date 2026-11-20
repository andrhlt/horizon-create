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
order. The [headless replay](tools/test-create-creative-tabs.py) checked
both memberships, Palettes order, and both first live pages on
`native-9f42064-89e551a852ca`. The 16-color seat search also passed.
Base keeps the port’s existing relative order pending a Java client
capture of its 3D-first sort. Search-only entries and attribution
still need comparison.

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

## Metal bars

The [original Java probe](tools/java-metal-bars-trace.patch) captures
Andesite, Brass, and Copper Bars' Stonecutter recipes and 24 connection
states. Each ingredient yields four bars. The [Horizon replay](tools/test-metal-bars.py)
places the bars in survival, compares their connections to stone, iron
bars, glass panes and oak fences, then waterlogs them. The host and a live
LAN guest matched all 24 states. The models and textures use the original
Create assets.

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

The [three-lamp Java fixture](fixtures/rose-quartz-lamp-java.csv) matched
39 ticks in solo and LAN on `a52e5e190a8d`. It covers a rising pulse on
each lamp, the one-tick activation, held latching after power is removed,
both comparator directions, and two survival Wrench actions. Verified
emission is 15 when lit and zero when off. Placement beside an existing
power source sets the input state while leaving the lamp off. The
survival recipe and six byte-identical blockstate, model and texture
files are included.

## Window palettes

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
original block and item models and textures. Pipe brackets remain open.

`tools/java-kinetic-brackets-trace.patch` records
`fixtures/kinetic-brackets-java.csv`.

```sh
python3 tools/test-kinetic-brackets.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-kinetic-brackets.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --craft
python3 tools/test-multiplayer-kinetic-brackets.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
```

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

```sh
python3 tools/test-creative-motor.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-creative-motor-placement.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-multiplayer-creative-motor.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
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
Wall and ceiling power, restart timing, visual tick timing, audio playback,
ambient particles, and Wrench behavior still need comparison.

```sh
python3 tools/test-analog-lever.py --visual /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --removal --destroy /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --removal /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
python3 tools/test-analog-lever.py --craft /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3
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

The [vertical Depot replay](tools/test-depot-drop-press.py) on build
`beea127aa56c` matched all [41 original Java ticks](fixtures/depot-drop-press-java.csv).
A loose ingot landed in the center of the Depot on tick 7, played the
original plop at volume .25 and pitch 1.25, and became an iron sheet on
tick 15. The earlier solo and LAN deposit and retrieval checks also passed.

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
and LAN on `693db180302a`. The open barrel accepted three ingots on tick 13.
The powered Funnel held its items through tick 18 and resumed on tick 19.
The partly full barrel accepted one on tick 13 and the other two on tick
21 after space cleared. The guest retrieved the eight remaining ingots
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

## Desk Bell

The [pinned Java probe](tools/java-desk-bell.patch) records pre-press state,
three presses including an in-flight retrigger, powered removal, and the
weak and directional direct signal over [55 ticks](fixtures/desk-bell-pulse-java.csv).
It also records the three original [sound events](fixtures/desk-bell-sound-java.csv)
and placement states for [all six faces](fixtures/desk-bell-placement-java.csv).
The [Horizon replay](tools/test-desk-bell.py) matches the two physical dust
circuits and the bell state every tick in solo and live LAN on
`native-9f42064-d1574c09aec5`. Both connected clients played all three
events with the original ID, category, center, gain and pitch. A solo
player crafted the original recipe. Solo and guest survival placement
matched all six Java facings in dry blocks and
[source water](fixtures/desk-bell-water-java.csv). The dry placement replay
also compared the outer outline plane hit by a center ray from each face.
The complete collision shape and exact animation remain open.

## Powered redstone latches

The [pinned Java fixture](tools/java-create-latches.patch) records
[41 ticks](fixtures/create-latches-java.csv) of Powered Latch and Powered
Toggle Latch state, rear and side redstone inputs, and output read by
adjacent dust. It includes short pulses, manual interactions and a
sneaking interaction. The [physical Horizon replay](tools/test-create-latches.py)
matched all 41 ticks in solo and with a guest operating both latches on
`native-9f42064-e6e755d336c6`. Both survival recipes were exercised in
solo. This replay covers the tested orientation and wire layout.

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

## Dyed Nixie Tubes

The [Java dye trace](fixtures/nixie-dye-java.csv) and
[Horizon replay](tools/test-nixie-colors.py) match all 16 colors in headless
solo and live LAN on `cbcf3690ed2f`. Dye recolors the mixed row, keeps the
held stack and existing text, and leaves a differently mounted neighbor
alone. A purple tube dropped the original orange item when mined. The
[redstone trace](fixtures/nixie-power-java.csv) matched the four power-on
and power-off ticks with the other tube retaining its text. The existing
Display Link fixture still matched all 146 Java ticks.

All 16 original blockstate definitions and their direct models match by
file bytes. The declared geometry matches the
[16 Java mount/facing combinations](fixtures/nixie-shapes-java.csv), and
the muted offscreen client emitted the original
[base palettes](fixtures/nixie-colors-java.csv). Per-frame flicker,
pixel parity, all placement paths, and save/reopen still need checks.

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

Train station attachment, train delivery, full world reload, the
animated flag and remaining presentation checks are open. This work
used isolated builds and muted offscreen menu replays.


## Nozzle placement and dropped-item airflow

The [Java probe](tools/java-nozzle-trace.patch) ran twice at the pinned
Create revision. It captured six [placement directions](fixtures/nozzle-placement-java.csv),
rejection on stone and on a backwards Fan, support removal and one item
drop, the original crafting result, and seven [radial airflow impulses](fixtures/nozzle-airflow-java.csv).
The airflow cases cover push, pull, the pull dead zone, maximum reach,
positions outside the scan range, obstruction, and a stopped Fan.

The [Horizon replay](tools/test-nozzle.py) passed in solo and LAN on
`native-9f42064-70205eb8ade6`. All eight placements or rejections
matched Java, including applicable shape planes and the ordinary Wrench
result. Removing the support dropped one Nozzle. The original recipe was
crafted in solo survival. The seven dropped-item inputs showed no early
motion on the first five Horizon ticks and matched the forced Java
impulse at the scan tick. The guest observed item movement and removal.
Continuous Java airflow cadence, player and mob movement, configurable
range, saturation, and presentation effects remain open.

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
draw their own random directions. Orb collection timing, complete
harvesting and loot replay, and ambient block particles remain open.

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
the seeded placement, deposit and close fixtures. The port uses
Horizon sided insertion. Unusual inventory handlers, visuals and exact
sound playback remain open.

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

## Basin materials and cooking

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
in solo and as a LAN guest. Longer runs, mixed support, ascending
controls and visual parity remain open.

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
Exact support collision, scaling for displayed block items, sounds
and particles need coverage.

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

The [survival replay](tools/test-cuckoo-clock.py) on
`native-9f42064-633fa4658824` and `create-clock-whistle-grip.hmod`
placed both original variants, consumed their block items, and
transmitted 16 RPM from each rear shaft. The clocks share the original
block entity type. The timed display, recipes in survival, audio,
Display Link source and the mysterious trigger remain open.

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
`create-factory-gauge-block.hmod`. Java's timed redstone path, attached
inventory behavior and the sparse crafting pattern remain open.

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

## Crafter Slot Cover

The [survival replay](tools/test-crafter-slot-cover.py) on
`native-9f42064-673f99e57bfa` with `create-track-observer.hmod`
crafted the original brass-nugget recipe, installed a cover on an
empty crafter and recovered it by clicking with an empty hand. The
preceding candidate crafted the same recipe but failed to install the
cover. Covered-grid processing, drop, visual and LAN checks remain
open.

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

On `native-9f42064-673f99e57bfa` with `create-track-observer.hmod`,
[the crafting and placement replay](tools/test-track-observer.py)
crafted two observers from each of the five original pressure plates and
placed it linked to a selected track. The [moving-train replay](tools/test-track-observer-train.py)
recorded a rail observer and adjacent wire going from unpowered to
powered at tick 38 and clearing at tick 60. This is the Horizon trace
for a straight, assembled train. Java timing, LAN, curves, diagonal
track and cargo filters remain open.

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

## Shopping List

The [survival replay](tools/test-shopping-list-discard.py) on
`native-9f42064-5add64cfcfc1` with `create-shopping-list.hmod`
retained the list during ordinary use and discarded it when the player
sneak-used it in air or on a block. The item is absent from the Create
creative tab, matching the original. List creation, entries, pricing,
tooltip summaries, purchases and LAN remain open.

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

The [survival replay](tools/test-tree-fertilizer.py) crafted two,
rejected stone without consumption, and grew oak with one fertilizer.
The pinned [Java obstruction probe](tools/java-tree-fertilizer-obstructions-trace.patch)
called the original item twice with identical scoped outcomes.
Its [recorded results](fixtures/tree_fertilizer_obstructions-java.csv)
show one item consumed, oak replacing stone in the trunk path while
bedrock stays, and all four base spruce logs from a 2×2 cluster with
no podzol. The Horizon replay passed those same two cases on
`native-9f42064-2bf765040d26` with `create-ponder-assets.hmod`.
A [survival LAN guest](tools/test-multiplayer-tree-fertilizer.py)
passed both cases on the same build, and the host verified the
original consumption and block outcomes. Other saplings, exact
random geometry and particles remain open.

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

## Creative Search membership

The [Java tab capture](fixtures/creative-tabs-java.csv) has 265 Base and 392
Palettes search entries. The pack lists all 657, and the pinned Horizon
candidate `native-9f42064-f30286a3e7ee` honors that membership in global Search.
The [offscreen replay](tools/test-create-creative-search.py) matched both lists
and verified that Blaze Cake Base appears and Chromatic Compound is excluded.
The existing tab replay passed the Base and Palettes display membership checks,
Palettes ordering, and the first live page of each. Java client Base ordering
and the remaining search interactions are open.

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

## Intermediate survival crafts

Six [Java-captured recipes](fixtures/intermediate-crafting-java.csv) matched the
[Horizon survival crafting grid](tools/test-machine-crafting.py) on
`native-9f42064-f30286a3e7ee`. The six outputs were Electron Tube, Transmitter,
Rose Quartz, Sand Paper, Red Sand Paper and Andesite Alloy using an iron nugget.
The [Java probe](tools/java-intermediate-crafting-trace.patch) checked recipe
IDs, outputs, counts and crafting remainders.

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

Commands:

```sh
python3 tools/test-server-baseline.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --pack .local/create.hmod
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --jobs 1 --check hand-crank-lan --check hand-crank-persistence
```

The new dedicated check is registered as `server-baseline` in
`tools/test-parity.py`. This scoped config case exercises Minecraft's
`server.properties`; it does not establish Create `create-server.toml`
loading/import, network synchronization or migration. The existing hand-crank
restart check is a local world reopen, while the multiplayer check exercises a
dedicated LAN world. Those broader cases and Full 1:1 remain open.
