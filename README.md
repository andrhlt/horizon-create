# Create for Horizon

A fresh port of Create for Minecraft 26.3 on Horizon. The gameplay reference
is Create 6.0.10 for NeoForge on Minecraft 1.21.1, commit
`ac0c444d9828da3453ae8cc65338e8de063286fb`. The native code targets Horizon
Nightly `9f42064`. Create and the artwork are by the Creators of Create.

## Build and play

```sh
python3 tools/prepare.py /path/to/Create
sh tools/build-native.sh /path/to/horizon-launcher /path/to/launcher-data
```

The build script expects the pinned Nightly and its source in the launcher
data directory. It applies the repository's Horizon patches to a copy of the
source under `.local/patched-launcher`, where the launcher installs the
resulting native client. The patch filters wheel axle directions before Horizon ranks
horizontal fluid paths. This lets the remaining routes participate in
water spread. The directional signal query lets a Display Link exclude
the redstone output from its own source.

The native build supplies server behavior and client animation. The
`.local/create.hmod` pack supplies block states, recipes, and locally
imported assets. For a normal launcher instance, copy the built version
directory from `.local/patched-launcher/versions/` into the launcher's
`versions/` directory and select that version for Create Parity Lab.
Place `.local/create.hmod` in the instance's `horizon-mods/` folder and
enable Create in Options → Mods.

The port includes the creative motor, small and large water wheels,
shafts, cogwheels, clutches, gearboxes, gearshifts, and speed and stress
gauges. Processing includes milling, depot pressing, fan processing,
crushing, mechanical mixing, mechanical crafting, and spouting. Items
move through chutes, belts, tunnels, arms, and vaults. The port also
supports branched pipes, steam engines, stockpile switches, and Smart
Observers.

Display Links send item counts and depot names to Nixies and powered
Display Boards. Redstone Contacts send pulses from moving Gantries,
and wireless Redstone Links carry analog power. The native build
runs as a dedicated multiplayer server.
The original train tracks can be produced through sequenced assembly.
Two-click survival placement lays straight, diagonal, and Bézier spans,
including crossings, S-curves, rises, and extended turns. The native
client draws curved rails with the original segment and tie models.
Mechanical Crafters pass grids between linked machines, and heated basins
brew potions that can be piped to a spout. Hose Pulleys transfer water
between bodies of fluid. A Sequenced Gearshift drives the Rope Pulley,
which lays rope and a magnet at rest and exposes its height to the
Threshold Switch. It also moves a glued platform and preserves its cargo.
Train Stations can be placed in survival after targeting
track. The station assembly screen places and resizes bogeys with Train
Casing, using the original small and large bogey models. Glue a single
carriage to one or two bogeys, add forward-facing Train Controls, and
assemble it at the station. The original controls and rotating bogeys
are visible during manual travel on straight rails and through bends.
Routing, schedules, conductors, seats, mounted doors, and selected
contraption actors have playable paths and repeatable comparisons. The
feature matrix records the remaining layouts, interactions, presentation,
and lifecycle cases; these paths do not yet establish full 1:1 parity.

The [timed Sticker source-port experiment](STICKER-SOURCE-PORT.md) records a
second bounded trial of translating upstream logic before batch verification.
The [Sticker checklist](STICKER-PARITY.md) records the broader timed completion
pass and distinguishes implemented behavior from full parity verification.

See the [feature matrix](FEATURE-MATRIX.md) for family coverage and [Create parity](PARITY.md) for the Java-to-Horizon fixture results.

## Test

The suite covers all 64 active GameTests at the pinned Java Create revision
and includes additional rendering, player interaction, and multiplayer
checks. It replays the original structure files and compares the recorded
gameplay state tick by tick. See the individual fixture sections for the
fields compared and the Java trace capture commands.

Run the repeatable checks with the stock Nightly control tool, the built
client, and the prepared 26.3 resources. The suite writes a log for each
check under `.local/parity/`. Java reference traces live in `fixtures/`.
The Horizon runs write their traces under `.local/`.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Use repeatable `--check` patterns during development to run just the
affected checks. The full suite is still available by omitting them.

Tank logic also has a fast loop using the same connectivity implementation
as the game, compared with original Java through shared action scripts:

```sh
python3 tools/test-tank-script.py --backend core
```

This uses cached Rust dependencies and does not launch Minecraft. Real headless
integration checks still verify the world adapter. See the
[architecture audit](ARCHITECTURE-AUDIT.md), the current
[tank evidence matrix](TANK-PARITY.md), and [tank script instructions](fixtures/tank-scripts/README.md) for measured costs,
coverage limits and reference capture commands.

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3 --check 'brass-diode-*' --check 'redstone-latches*'
```

The early fixtures can also run individually.

```sh
python3 tools/smoke-cogwheel.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-wheat-milling.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-small-waterwheel.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-small-waterwheel.py --visual /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

The tests install the pack in a temporary game directory. The cogwheel
smoke test places the block as a player, reopens the world, and captures
the original static model and textures in `.local/cogwheel.png`.

The wheat test places the unchanged upstream `wheat_milling.nbt`, toggles
the fixture lever while frozen, and steps the server 80 times. It compares
ticks 0 through 80 to [the Java trace](fixtures/wheat_milling-java.csv)
and writes `.local/wheat_milling-horizon.csv`. Both traces include the
mill RPM and timer, the wheat in the source barrel, and flour in the
hopper and output chest. The expected mill start is tick 12. Flour
reaches the chest at ticks 46, 72, and 80.

The small water wheel test places the unchanged upstream
`small_waterwheel.nbt` and operates the fixture's levers in the same
sequence as the Java test. It compares ticks 0 through 31 to
[the Java trace](fixtures/small_waterwheel-java.csv) and writes
`.local/small_waterwheel-horizon.csv`. It checks the water levels, the
dry axle edges, the wheel's flow score, wheel and speedometer RPM, and the
stressometer's capacity and applied stress. The opposing flows cancel
at tick 25. The wheel reaches 8 RPM and 256 SU capacity at tick 31.

With Java 21, run `./gradlew runGameTestServer` in a disposable checkout of
the pinned Create commit. Apply `tools/java-wheat-trace.patch` there and
rerun to reproduce the trace. The patch keeps the original fixture and
assertion, records the sampled values, and seeds only this fixture's milling
rolls. The Horizon runner uses the same seed for the fixture mill. Standard
gameplay uses the level RNG.

Apply `tools/java-small-waterwheel-trace.patch` to a clean checkout at the
same revision and run the same Gradle task to record the `CREATE_WHEEL`
rows. The patch selects the original small wheel test and records the
sampled values alongside its original assertions.

The `--visual` run uses the offscreen Horizon client and steps the same
fixture through tick 47 so the speedometer has time to move. It verifies
that the rotating mesh and both needles submit geometry and compares their
angles against [the Java visual trace](fixtures/small_waterwheel-visual-java.csv).
The comparison uses each Horizon frame's partial tick and aligns wheel
phase across the two clocks and fixture positions. The original fixture
leaves the stressometer unloaded, so its needle stays at zero throughout.
The Horizon frame samples are in `.local/small_waterwheel-visual-horizon.csv`.

Apply `tools/java-small-waterwheel-visual-trace.patch` to a clean checkout
in place of the gameplay trace patch and run `./gradlew runGameTestServer`
to reproduce the `CREATE_WHEEL_VISUAL` rows. The patch samples Java's
actual dial state and applies Create's renderer math at a partial tick of
0.5. It preserves the original assertions and delays success to tick 47.

## Large water wheel fixture

```sh
python3 tools/test-small-waterwheel.py --large --visual /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

The runner places the byte-for-byte upstream `large_waterwheel.nbt`,
checks for all eight rim blocks, and operates the two levers. The Java
trace reaches 4 RPM and 512 SU on tick 42, while water is still present
on both sides. The cut-off stream disappears on tick 61. The runner
compares gameplay through tick 61 and rendered poses through tick 68.

Apply `tools/java-large-waterwheel-trace.patch` in a clean checkout of
the pinned Java Create revision and run `./gradlew runGameTestServer`.
The patch retains the original assertions and records the `CREATE_WHEEL`
and `CREATE_WHEEL_VISUAL` samples. The references are
[gameplay](fixtures/large_waterwheel-java.csv) and
[animation](fixtures/large_waterwheel-visual-java.csv). The corresponding
Horizon traces are written under `.local/`.

## Loaded stressometer fixture

```sh
python3 tools/test-loaded-stressometer.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

The test builds a vertical small water wheel connected to a stressometer,
lets the water settle for 70 ticks, and samples ticks 0 through 104.
It connects four millstones after tick 0 and removes them after tick 12.
Java publishes the 128 SU load and 0.5 dial target at tick 1 and advances
the needle at tick 2. The target and needle both drop at tick 13.
The test repeats the cycle with two millstones (64 SU) after ticks 24
and 36, while the needle is still settling from the first unload. A
third cycle applies 288 SU after tick 48 and removes it after tick 96.
Both tests seed only the fixture gauge's RNG with 2 to compare Create's
overload wobble. Normal gameplay uses the level RNG.
The runner checks the capacity, stress, and target reported by Horizon's
server plus the needle pose drawn by its client.

To regenerate [the Java reference](fixtures/loaded_stressometer-java.csv),
apply `tools/java-loaded-stressometer-trace.patch` to a clean checkout of
the pinned Create revision and run `./gradlew runGameTestServer` on Java 21.
The patch adds a separate GameTest using the same arrangement and timings.
Its `CREATE_LOADED_DIAL` lines contain the seven CSV fields in order. The
Horizon runner writes `.local/loaded_stressometer-horizon.csv` with its
render partial tick and needle angle.

Add `--goggles` to compare the client's overlay at every sampled tick. The
reference at [goggles-stress-load-java.json](fixtures/goggles-stress-load-java.json)
was captured by passing the Java GameTest's capacity and stress values through
the real Java client's gauge formatter. The [Java probe](tools/java-goggles-gauge-trace.patch)
runs in a disposable client connected to a local Java Create server. Set the
client JVM property `create.goggles.fixture` to the reference CSV's absolute
path for the loaded run. With that JVM property omitted, the probe emits
twenty independent speed and stress cases. Replay them with
`tools/test-goggles-gauges.py` using the same Horizon arguments.

## Water-wheel materials fixture

```sh
python3 tools/test-waterwheel-materials.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Both wheels accept planks by hand and through a rotating deployer. The
fixture uses an original clutch and gearbox to power two deployers fed by
straight chutes. It checks the ordered 11 Java plank species, both wheel
materials, and both deployers' state, timer, and RPM through tick 126.
Deployer item interactions currently cover wheel recoloring. The client
draws the original rotors with the selected wood textures.

Apply `tools/java-waterwheel-materials-trace.patch` to the pinned Java
checkout and run `./gradlew runGameTestServer`. The `CREATE_MATERIAL_ORDER`
and `CREATE_MATERIAL` records produce the item order and CSV in `fixtures/`.

### Depot comparator and Nixie tube

`depot_comparator_output` uses Create's original structure with a half-full
ender-pearl stack, a full pearl stack, diamonds, and a sword. The trace extension
empties the first depot at tick 0 and inserts four pearls at tick 8. The comparator
updates two ticks later and the Nixie one tick after that. All eight readings
match Java for 17 ticks. The Nixie uses the original housing with a text overlay.
Create's layered font poses and flicker are pending.

```sh
python3 tools/test-depot-comparator.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Threshold switch

The original item `threshold_switch` fixture compares chest stock, capacity,
the threshold comparison, delayed output, and the lamp for 61 ticks. The trace
also configures 128/64 item limits, removes the stock, and restores it in
two stages to measure both edges. Supports item counting with a simple item
filter. The configuration screen, fluid targets, and complex filters are pending.

```sh
python3 tools/test-threshold-switch.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Smart Observer storage

The original `smart_observer_storage` and `smart_observer_filtered_storage`
fixtures exercise smart chutes feeding chests. The Java and Horizon traces
include the inventories, Observer output and countdown, and both lamps for
46 ticks each. Each test also removes and restores a matching item to measure
when the signal falls and returns. The filtered fixture checks that gold ore
doesn't trigger a filter set to gold blocks.

```sh
python3 tools/test-smart-observer.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-smart-observer.py --filtered /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Milling recipe coverage

The content pack imports all 47 standard milling recipes from the pinned Create
checkout. Three variants of the wheat milling structure run clay, magenta wool
through the wool tag, and bone using the same seed on both engines. Each variant
matches 106 ticks of the barrel, mill, hopper, and output inventory.

```sh
python3 tools/test-milling-recipes.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Shaft and cogwheel gear trains

The test drives small and large cogwheels from a motor through shafts. It
compares opposite rotation, 2:1 and 1:2 ratios, bevel gears, and power removal
and restoration. All ten shaft and gear speeds match Java for 36 ticks. The
small cogwheel, shaft, and separate large cogwheel gear and axle use the
original Java meshes in the client renderer.

```sh
python3 tools/test-shaft-and-cogwheel.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Smart Observer blocks and chutes

The original block fixture matches 36 ticks of piston motion, filter
matching, observer timers, and lamps. The original chute fixture matches 46
ticks of item handoffs, observer output, and the piston moving its diamond
block.

```sh
python3 tools/test-smart-observer-world.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Survival crafting

The starter crafting recipes use Create's original patterns and ingredient
tags. The survival test crafts andesite alloy from andesite and iron nuggets,
applies one alloy to a stripped log to make casing, then crafts shafts and
both cogwheel sizes from the remaining alloy and planks. It uses Horizon's
inventory and block interaction controls.

```sh
python3 tools/test-survival-crafting.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Decorative stone palettes

Asurine, Crimsite, Limestone, Ochrum, Scoria, Scorchia, and Veridium
each provide 19 blocks with Java's original IDs, models, textures, loot,
shaping recipes, and stonecutting. They appear in the
`Create's Building Blocks` creative tab. Horizon's native stair, slab, wall,
and pillar templates supply placement behavior.

The fixture places all 133 blocks and compares their default states against
the Java registry. It cuts a pair of slabs from each family in a survival
Stonecutter, places and merges each pair, places a horizontal pillar, and
connects adjacent walls.
Pass `--java-source /path/to/Create` to also check the packed assets, loot,
tags, and recipes against the pinned source. Natural generation of the
base stones and connected textures on the Layered blocks and Pillars remain
open.

```sh
python3 tools/test-stone-palettes.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Apply `tools/java-stone-palette-trace.patch` to the pinned Java checkout and
run `./gradlew runGameTestServer` with Java 21 to capture its
`CREATE_STONE_PALETTE` rows.

### Mechanical press and depot

A Java fixture runs the original mechanical press and depot with two iron
ingots and interrupts power during the first cycle. Horizon matches all 71
ticks of press speed, cycle state, depot input and output, and head travel
derived from the press state. The renderer uses the original press head and
shaft. Depot pressing recognizes iron, copper, gold, and sugar cane.

In the survival inventory, hover over a pressing result such as an Iron Sheet
and press R to see its input, or hover over an input such as an Iron Ingot and
press U to see its pressing uses. The panel shows the Mechanical Press; Back
closes it. The same keys show Millstone recipes, such as clay into four Clay
Balls or wheat into Flour and seeds, including each output's chance. Crushing
Wheel recipes include non-overlapping Milling recipes; the tabs let you choose
between machines when both can process the same item. Bulk Washing recipes
show the Fan behind Flowing Water and the chance of each output. The
Sawing category covers Create cutting recipes such as Bamboo Planks into
Bamboo Mosaic; the separate automatic stonecutting category is not yet listed.
Mixer recipes show item inputs, Mixer and Basin, and heat requirements. Exact
water inputs such as the 1,000 mB used for Dough have a fluid slot and tooltip.
When an item matches several categories, their machine tabs switch between
those recipes; for example U over Copper Ingot offers Pressing and Mixing.
U over a Honey Block, Chocolate Bar or Mossy Cobblestone also shows its heated
Honey or Chocolate, or superheated Lava output. Tagged fluid inputs and
fluid-focused lookup are not yet listed.

```sh
python3 tools/test-depot-pressing.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Mechanical press and basin

A supplemental Java GameTest runs four presses through two compacting cycles
each. The recipes cover snow blocks into ice, iron ingots into iron blocks,
flint and gravel with lava into andesite, and honey bottles into honey blocks.
The Horizon replay compares all 33 ticks per press, including start and
completion state, input and output counts, lava use, and press head travel.
It also checks the absence of returned glass bottles, as in the pinned Java run.

The content pack includes the seven original Create compacting recipes.
The press can also compact uniform four- or nine-ingredient crafting recipes
from Horizon's recipe table. Broader press interactions remain open.

```sh
python3 tools/test-basin-compacting.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Apply `tools/java-basin-compacting-trace.patch` to a disposable checkout of
the pinned Java revision and run `./gradlew runGameTestServer` with Java 21.
The `CREATE_COMPACTING`, `CREATE_COMPACTING_LAVA` and
`CREATE_COMPACTING_BOTTLES` lines supply the data in
`fixtures/basin_compacting-java.csv`.

### Dedicated server test

Both clients and the dedicated server use the same native build and content
pack. The repeatable test starts the server on loopback with two test
players. It checks that both clients see the casing one player creates
and that eight ender pearls move through a depot from one player's inventory
to the other's.

```sh
python3 tools/test-multiplayer.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Horizontal belt and andesite tunnel

Connect two aligned shafts with a Mechanical Belt item to form a horizontal
belt. The reversal fixture compares 66 ticks of speed, item spacing, and
handoffs, including an occupied depot. Create's original
`andesite_tunnel_split` fixture compares 30 ticks from the chute through each
split and ends with one, one, and three brass ingots in the three depots.
Positions are compared within 0.000001 blocks. Slopes, rider movement, and
full belt dismantling and tunnel flap behavior remain open.

```sh
python3 tools/test-horizontal-belt.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-andesite-tunnel.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Encased fan on depots and loose items

Four lanes run the pinned Java recipes for washing magenta wool, smoking
beef, haunting sand, and blasting raw iron. The fans stop for eight ticks
and resume their original countdowns. Horizon matches all 175 ticks across
the four lanes. The client draws the original propeller.

The original `fan_processing` fixture matches all 172 ticks across five
lanes. The comparison checks supply and chute inventories, processed item
IDs and counts, and receiving barrels and lamps. A shared recipe RNG seed
gives the gravel lane the same six flint in both games. This trace measures
the item handoffs. It does not measure every loose item's rendered motion.

```sh
python3 tools/test-fan-depot.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-fan-processing.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```


### Sand washing on belts

The original `sand_washing` structure runs with its Java lever sequence and
a fixed recipe RNG seed. Horizon matches all 190 sampled ticks of funnel
cooldown, item counts, and fan countdowns. Belt positions match within
0.000001 blocks, reflecting the SNBT trace precision. Both engines deliver six
clay balls on tick 189. The fixture exercises pushing and extended brass belt
funnels with a Creative Crate as the source.

```sh
python3 tools/test-sand-washing.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Item vaults and funnels

The original `vault_comparator_output` fixture matches all 69 ticks of bread
intake, comparator strength, and Nixie readings across the 1×1, 2×2, and
3×3 vaults. Each vault part holds 20 slots. A vault exposes the combined
inventory from its faces, so a funnel can fill more than one part from
one input. The test spawns bread through the same post-tick callbacks as
Java. Funnel placement and filters currently cover the core item transfers.

```sh
python3 tools/test-vault-comparator.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```


### Storage transfer through a vault, barrel, and depot

`tools/test-item-inventories.py` with the `storages` scenario replays
the original storage chain. The Java and Horizon runs both give the
placed structure 20 ticks to initialize before the lever is toggled.
The chest, vault, barrel, depot, and shulker inventories match on all 151
measured ticks. Apply `tools/java-item-inventories-trace.patch` to regenerate
the Java reference.

### Mounted dispensers

A dispenser on a bearing or gantry uses its own slots and can refill the
last item of a stack from matching cargo. Its direction follows the
payload and its launch includes the payload's motion. A dropper ejects
an item stack. Supported projectiles use Horizon's projectile simulation.

The original `arrow_dispenser` fixture compares 142 ticks of bearing
position and angle, ammunition, projectile count, and launch direction.
The projectile's random spread varies between Java runs. Each original
gantry dispenser fixture compares 68 ticks of carriage motion, lower and
upper supplies, barrel contents, and ordinary or spectral arrow counts
through disassembly.

Run `tools/test-arrow-dispenser.py` or `tools/test-gantry-dispensers.py`.
Apply `tools/java-farming-and-dispenser-trace.patch` or
`tools/java-gantry-dispensers-trace.patch` to capture the Java samples.

### Cart Assembler and furnace minecart fuel

Power a Cart Assembler to pick up the structure above the rail onto
a passing minecart. On an unpowered regular assembler the cart can set
its structure back down. A mounted furnace minecart takes coal or
charcoal from attached chests and barrels when it runs low. Item vaults
keep their contents protected from the cart's furnace.

`tools/test-vault-fuel.py` replays the original `vaults_protect_fuel`
scenario. It compares 20 ticks of cart position and fuel, both lamp and
comparator states, and the pickup and restoration of each container.
The replay restores the comparator output saved in the Java structure
because Horizon's template loader omits that vanilla block entity data.
Apply `tools/java-elevator-and-vault-fuel-trace.patch` to record the Java
reference. Cart coupling, configuration, and behavior on curved tracks
are pending.

### Cart-mounted Mechanical Harvester

Attach a Mechanical Harvester to a cart assembly facing the direction
of travel. The harvester cuts mature crops, saves one seed for replanting,
and sends the remaining drops to the assembly's storage. A portable
item interface can supply a funnel from the mounted chest minecart when
the two interfaces face each other.

`tools/test-crop-farming.py` replays the original `crop_farming` test.
All 72 ticks compare the cart's position and motion, mounted assembly
position, crop ages, and harvested item types in the output chest.
Random drop counts vary between Java runs. Apply
`tools/java-crop-cart-trace.patch` to capture the Java trace. Transfer into a docked cart is pending.

### Rotating contraption controls

A vertical Sequenced Gearshift can turn a Mechanical Bearing through a
programmed angle. The bearing can hold the assembly between turns.
Right-click a mounted Contraption Controls block to enable or disable
the actors selected by its item filter.

`tools/test-contraption-controls.py` replays the original `controls`
structure for 105 ticks. It presses the stone button and clicks the
moving controls, then compares the gearshift, bearing angle, enabled
actors, soil and wheat through all four turns. Apply
`tools/java-controls-trace.patch` to regenerate the Java reference.

### Elevator Pulley

Right-click a powered Elevator Pulley to assemble the cabin below it.
Other pulleys above that cabin follow the primary pulley. Pair its
moving Redstone Contact with stationary contacts along the shaft to
create floors. Redstone at a floor calls the cabin. Right-click a converted
Elevator Contact to enter its short and long names. Look at mounted
Contraption Controls, scroll to the destination, then right-click to select
it. Right-click a White Seat to board and crouch to dismount. Reassemble
cabins built on an earlier release to give them collision for standing
players.

`tools/test-elevator.py` replays the original `elevator` GameTest.
It compares the two floor lamps, lever, mirror-pulley link, cabin and
cow Y positions over all 67 ticks. Apply `tools/java-elevator-phase-trace.patch`
to record the Java samples. The `--visual` replay also checks both pulley belt
lengths against the Java cabin trace and captures the original belts, coils and
magnets moving in the Horizon client. Use `--reload-at 35 --reload-idle` to
check the same trip across a restart and again when stopped at the top floor.
The cabin's position after startup identifies the Java trip tick before the
replay continues. The reload test then calls the cabin back down with a lever,
compares the descent against `fixtures/elevator-return-java.csv`, and verifies
that clicking the pulley disassembles the cabin and restores its seat. To
capture the descent, apply `tools/java-elevator-return-trace.patch` after
`tools/java-elevator-phase-trace.patch` and use the `ELEVATOR_TRACE` rows
starting at tick 90.

`tools/test-multiplayer-elevator.py` opens a real Horizon LAN session. The
host and guest name two floors, board separate seats, and use the moving
controls to select the upper floor. Apply
`tools/java-elevator-passengers-trace.patch` in a clean pinned Java checkout
and run `./gradlew runGameTestServer` to capture the 92
`ELEVATOR_PASSENGERS` rows. Java injects a sneak packet into two embedded
server players. The Horizon replay uses server-side dismount to capture the
same operation without creative-flight motion from a held crouch key. It
also checks the position and lamps in both live Horizon clients.

The door selector in the floor contact editor applies to the cabin doors
facing that side. Use All, one compass direction, or None. A matching
landing door next to the cabin opens with it. Contraption Controls show the
selected floor on the panel. Scroll to preview it and right-click to confirm.
Players can stand on the cabin or sit in a seat.

`tools/test-elevator-service.py` sets the lower floor to South and the upper
floor to None, carries a LAN host and guest up the cabin, then changes the
upper floor to South. It compares both halves of the cabin and landing
doors, contact modes, lamps, cabin position, and server sound events
against the 101-tick Java trace. Apply
`tools/java-elevator-service-trace.patch` after the passenger patch and run
the same Java GameTest task to record the `ELEVATOR_SERVICE` rows.
The test also checks both Horizon clients against the indicator trace from
`tools/trace-java-elevator-indicator.py`, which uses the upstream animation
code and Catnip's Java interpolation.

`tools/test-elevator-grounded.py` checks that two survival riders can crouch
out of their seats and stay grounded. `tools/test-elevator-standing.py`
checks standing support, on both clients and the server, on every sample
of the ascent and return. Each rider jumps independently at the lower
landing. For a live Java standing trace, apply
`tools/java-elevator-live-client-trace.patch` after the passenger patch
in a disposable pinned Java checkout. With Java 21, run
`python3 tools/capture-java-elevator-standing.py /path/to/Create`.
It starts two local Java clients and records their ascent and descent
at 20 ticks per second in `.local/elevator-service/`. Apply
`tools/java-elevator-standing-collider-trace.patch` as well to record the
collision callback and the previous cabin pose, including force-sync
resets. Run `python3 tools/trace-java-elevator-standing.py` to verify the
committed Java fixture independently of Horizon.
Run `tools/test-elevator-standing.py --live` with the same three Horizon
arguments to compare both local rider streams to the Java collision
calculation at the received cabin poses. Add `--delay` to test recovery
after a brief break in cabin updates.
`tools/test-elevator-walkthrough.py` checks that both survival players can
walk while the cabin moves, are stopped by closed doors, and exit when
both landing leaves open. It verifies opening and closing in both clients.

### Mechanical Roller

Mount a Mechanical Roller facing the direction of travel on a Gantry
Carriage assembly and supply paving blocks through attached storage.
Right-click the roller with a paving block to select its material.
Tunnel paving clears obstructions and pauses travel while the roller
works. Straight fill and wide fill read the mode from the block entity.

`tools/test-rollers.py` replays the original `roller_filling` and
`roller_paving_and_clearing` structures for 81 and 181 ticks. It checks
carriage position, paving stock, and the block at each of 48 positions
under or in front of the roller. Drops from cleared material vary between
Java runs. Apply `tools/java-rollers-trace.patch` to regenerate the traces.
The mode selector, drum animation, and paver profiles for trains are pending.

### Mechanical Piston and Plough

The mechanical piston has three movement modes. Additional Java captures and
headless comparisons cover a moving extended Sticker, blocked and normal
pistons, a glued multi-actor payload, and host/guest replication. The precise
coverage and remaining gaps are in [mechanical piston parity](MECHANICAL-PISTON-PARITY.md).

The original `ploughing` fixture checks payload position and soil for all
four Java ticks. The Horizon replay also extends the piston to its last
pole, reverses the motor, and checks that the sticky head brings the
plough back. Run `tools/test-ploughing.py`. Apply
`tools/java-farming-and-dispenser-trace.patch` to collect the Java trace.

Add extension poles behind the piston and connect its shaft to a source
of rotation. Attach a Mechanical Plough facing along its path, with the
blade above the soil. The moving plough tills suitable soil as it enters
each new block. The original plough's entity interactions and other
block-breaking behavior are pending.

### Mounted storage

The original `mounted_item_extract` and `mounted_fluid_drain` fixtures
replay a mechanical bearing docking two portable interfaces. The item
replay checks 253 ticks of bearing movement and every item type in the
mounted barrel, hopper, and chest. The fluid replay checks 65 ticks of
bearing movement and water in both tanks. The bearing restores the empty
storage at disassembly. Run either scenario with
`tools/test-mounted-storage.py`, or apply
`tools/java-mounted-storage-trace.patch` to capture the Java samples again.

Glue a portable interface and its matching storage to the bearing's
payload. Place a matching interface along its path, facing the moving
interface. The two interfaces dock automatically. Hoppers exchange
items with the moving inventory, and pressurized pipes exchange water
with its tanks. Both blocks use Create's retracted geometry. Head
extension is still pending.

### Schematicannon

The original `schematicannon` fixture compares 233 ticks of state, fuel,
progress, blocks in flight and their remaining travel time, and every
output cell. Horizon captures the original source volume with a structure
block and launches all 21 blocks. Apply
`tools/java-schematicannon-trace.patch` to regenerate the Java reference.

Use an Empty Schematic on a named structure block with a saved template.
Use the filled schematic on the face beside the desired output origin,
then on the cannon to load and start it. A neighboring Creative Crate
supplies unlimited blocks and fuel. The cannon also draws supplies from
adjacent inventories and accepts gunpowder by hand. The original cannon
interface, Schematic Table, and entity printing remain in development.

### Deployer mining

The original `issue9615_efficient_deployers` GameTest compares 77 ticks
of both deployers’ timers, speeds, targets, and Smart Observer signals.
The Efficiency V pickaxe breaks its deepslate diamond ore on tick 68.
The observer releases the piston, which moves the lime stained glass
into place on tick 76. Apply `tools/java-efficient-deployers-trace.patch`
to regenerate the Java reference.

### Netherite diving suit

The original `netherite_backtank` GameTest equips a zombie from the armor
stand in the template. Horizon matches all 181 Java ticks for the zombie’s
presence, health, fire timer, immunity, lava contact, height, and remaining
air. Apply `tools/java-netherite-backtank-trace.patch` to regenerate the
reference. Player diving and backtank refilling are still in development.

### Belt coaster

The original `belt_coaster` GameTest compares both chest inventories for
all 128 Java ticks. The fixture uses the upstream structure and pulls its
original lever. Inclined belts transfer items across their full length,
belt funnels queue stacks at occupied chutes, and upward chutes lift
stacks into the final belt. Belt connectors place inclined runs between
shafts separated by the same horizontal and vertical distance.

### Crushing wheels and upward chutes

The original `stone_cobble_sand_crushing` fixture matches all 146 ticks
of the two crushing stages, belt stacks, and four upward chutes. With the
same recipe seed, the final chest gets five sand and one flint. Wheel pairs
create their controllers automatically and use the original rotating mesh.
A separate player test places a brass funnel and checks that it feeds sand
from a Creative Crate onto the belt.

```sh
python3 tools/test-stone-crushing.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-funnel-placement.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Mechanical pump and open pipes

The original `in_world_pumping_in` and `in_world_pumping_out` fixtures match
69 ticks combined. The comparison includes pump RPM, fluid front progress
on both sides of the pump and glass pipe, the open-end buffer, the basin
contents, and the water block in the world. At 96 RPM the fully primed
pump transfers 48 millibuckets per tick, with the same open-end startup
and source refresh behavior as Java.

```sh
python3 tools/test-world-pump.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

The original `open_pipes` fixture matches 21 measured Java ticks.
The trace compares ignition, fire resistance, extinguishing, milk curing,
and the fluid amounts in all four tanks. The replay aligns the world clock
with Java's five-tick effect cycle and loads the original white seat geometry.
Seat mounting remains pending.

```sh
python3 tools/test-open-pipes.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Apply `tools/java-open-pipes-trace.patch` to capture the Java reference.

### Three-way fluid networks

The original `3_pipe_split` and `3_pipe_combine` GameTests compare all 402
ticks of pump speed and water levels in the four tanks. The split reaches
the three destinations at different ticks, then rebalances the flow. In
both directions the total remains 11,000 millibuckets. The fluid tank
groups use the original block models.

```sh
python3 tools/test-branched-pipes.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

### Brass mixing

The unchanged `brass_mixing` factory matches 186 ticks of ingredient delivery,
mixer RPM and cycle, basin contents, mixer head height and speed, and brass
in the receiver. The original creative Blaze Burner heats the basin. The
output belt delivers the first two brass ingots to the chest on tick 185.

Run `tools/test-brass-mixing.py` with the same three arguments as the suite.
Apply `tools/java-brass-mixing-trace.patch` to a clean Java checkout and run
`./gradlew runGameTestServer` to record the `CREATE_BRASS` rows.

### Heated honey, chocolate, and Blaze Cakes

The heated mixer matches 86 Java ticks each for honey from honey blocks,
chocolate from melted chocolate bars, and chocolate from sugar, cocoa,
and milk. The comparison includes mixer motion, ingredient use, and
millibuckets in the Basin tanks. A fourth lane matches 86 ticks of the
Spout using 250 mB of lava to fill a Blaze Cake Base on a Depot.

The survival interaction test pours milk into a Basin, checks the empty
bucket and full-tank behavior, and uses the milk to mix chocolate.

```sh
python3 tools/test-fluid-food.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
python3 tools/test-basin-milk.py /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Apply `tools/java-fluid-food-trace.patch` to the pinned Java Create checkout
and run `./gradlew runGameTestServer` with Java 21 to capture the
`CREATE_HEATED_FLUID` and `CREATE_CAKE_SPOUT` rows.

### Basin fluid rendering

The Basin displays the original liquid sprites in adjacent strips. Surface
height follows Create's fill curve, and the strips resize as liquid enters
or leaves each tank. The Java reference captures the four real tank
interpolators. The Horizon replay compares 48 ticks at three frame fractions
each, including a tank drained completely and then removed from view.

`--visual` captures three Horizon frames for inspection.

```sh
python3 tools/test-basin-liquid-display.py --visual /path/to/horizon-ctl /path/to/native/horizon-client /path/to/prepared/26.3
```

Apply `tools/java-basin-liquid-display-trace.patch` to the pinned Java Create
checkout and run `./gradlew runGameTestServer` with Java 21 to capture the
`CREATE_BASIN_LIQUID` rows.

### Steam engine startup

The original `steam_engine` fixture matches all 13 ticks of its startup.
The comparison checks boiler heat and sampled water supply, both pump
speeds, both powered shafts and their efficiencies, and the output gauges.
On tick 12 the two passive engines provide 2,048 stress units at 16 RPM.

Run `tools/test-steam-engine.py` with the same three arguments as the suite.
Apply `tools/java-steam-engine-trace.patch` to a clean Java checkout and run
`./gradlew runGameTestServer` to record the `CREATE_STEAM` rows.

### Arm-fed brass mixing

The unchanged `brass_mixing_2` factory matches all 248 ticks of mechanical
arm movement, ingredient pickup and deposit, mixer operation, and brass
delivery. The original structure includes a glue entity which joins the
basin to a chain-driven mechanical bearing. The bearing tips the basin
and deposits the pair of brass ingots on the depot on tick 247.
The arm test loads the original saved interaction points. A separate
player test selects a source and destination by right-clicking with the arm
in hand, then places the arm and checks the transfer. Horizon draws the original
arm sections and claw and animates them between pickup and deposit points.

The original `arm_multi_output` fixture matches all 75 ticks of arm position
progress, target selection, coal block pickup and delivery, and each of the nine
burner fuel timers. Run `tools/test-arm-burners.py` with the three suite
arguments. Add `--visual` to capture rendered frames.

Run `tools/test-arm-brass-mixing.py` with the same three arguments as the suite.
Apply `tools/java-arm-brass-mixing-trace.patch` to a clean Java checkout
and run `./gradlew runGameTestServer` to record the `CREATE_ARM` rows.

### Survival boiler and burner interactions

The player tests attach a steam engine and a shaft using ordinary placement
interactions. They also feed a burner coal and a Blaze Cake in survival,
checking the consumed items, heat state, and remaining fuel.
Run `tools/test-steam-placement.py` and `tools/test-blaze-burner.py` with the
same three arguments as the suite.

### Potion spout

The original `spout_crafting` factory matches all 94 ticks of belt speed,
pump speed, carried stacks, spout timing, fluid levels, and chest output.
The spout consumes 25 millibuckets of strength potion to turn cinder flour
into redstone. The pump replenishes the spout 8 millibuckets per tick until
full, and the redstone arrives at the chest on tick 93.

Run `tools/test-spout-crafting.py` with the same three arguments as the suite.
The optional `--visual` run captures the spout and factory at three ticks.
Apply `tools/java-spout-crafting-trace.patch` to a clean Java checkout and
run `./gradlew runGameTestServer` to record the `CREATE_SPOUT` rows.

### Fluid detection and water and lava spouting

The original `smart_observer_pipes` GameTest matches 47 ticks of the Smart
Observer’s pulse, the piston and diamond block, and the 2,000 millibucket
transfer between tanks. The observation begins when an inbound pipe front
finishes filling, before the water arrives at the destination.

The original `spouting` factory matches all nine spouts for 150 ticks. This
includes pump flow across the branches, each spout’s charge and cycle,
hydration of farmland, three types of dirt becoming mud, water and lava
cauldrons, and the bucket, water bottle, and grass block delivered on depots.
The Java and Horizon fixture runners disable random block ticks so that the
comparison measures spout hydration independently of farmland drying.

Run `tools/test-fluid-observer.py` and `tools/test-spouting.py` with the same
three arguments as the suite. Apply `tools/java-fluid-observer-trace.patch` or
`tools/java-spouting-trace.patch` to a clean Java checkout and run
`./gradlew runGameTestServer` to reproduce the corresponding trace.

### Two-arm item loop and railway track assembly

The original `arm_purgatory` fixture matches all 101 ticks of arm state and
transfer, with exactly one diamond across both arms and depots throughout.

The original `track_crafting` factory matches all 190 ticks of the two
deployers, the Mechanical Press, the belt cargo, and the output chest.
The factory consumes stone, smooth stone, and andesite slabs plus iron or zinc
nuggets. The sixth railway track reaches the chest on tick 189. Carried item
positions are compared within 0.000001 blocks. The fixture ignores transient
empty belt entries, which represent no items.

Run `tools/test-arm-loop.py` and `tools/test-track-crafting.py` with the usual
three arguments. Apply `tools/java-arm-loop-trace.patch` or
`tools/java-track-crafting-trace.patch` to a clean Java checkout to reproduce
the corresponding trace with `./gradlew runGameTestServer`.

### Rail placement, fluid valves, and bottle delivery

Fifteen Java placement cases cover original straight, diagonal, and uphill
track states, including vertical looks. The Horizon runner places and consumes
the actual track items through ordinary survival interactions. Use
`tools/test-track-placement.py --visual` with the three suite arguments
to capture the original models in Horizon.

The original fluid `threshold_switch` fixture matches all 337 measured ticks.
The runner starts each copper handle through a player click, then compares valve
state, all three tank amounts, switch state and readout, and redstone lamp.
The two reservoirs contribute four buckets each before the drain opens.

The original `water_filling_bottle` fixture matches all 60 measured ticks,
including clutch activation, the belt handoff, Spout timing, the Weighted
Ejector’s lid and flight timing, and bottle arrival in the correct barrel.
Horizon renders the original Weighted Ejector model and item trajectory.
The comparison covers item launch and delivery in this layout. Entity launch
and obstacle handling remain open.

Run `tools/test-fluid-threshold.py` and `tools/test-water-filling-bottle.py`
with the three suite arguments. The matching Java trace patches are in
`tools/java-fluid-threshold-trace.patch`, `tools/java-water-filling-trace.patch`,
and `tools/java-track-placement-trace.patch`.

### Precision Mechanism assembly

Create's original `precision_mechanism_crafting` factory matches all 108
sampled ticks across four belts and three representative deployers. Each
intermediate item carries the actual assembly recipe and step component
through five loops. Both versions use the same fixture-only seed for the
weighted assembly outcomes. The chest receives a Precision Mechanism and a
Golden Sheet from the first two items.

Run `tools/test-precision-mechanism.py` with the three suite arguments.
Apply `tools/java-precision-mechanism-trace.patch` to reproduce the Java
reference in a clean checkout.


### Mechanical Crafter processing

The unchanged upstream `crushing_wheel_crafting.nbt` compares 144 ticks to
[the Java trace](fixtures/crushing_wheel_crafting-java.csv). The fixture
samples the linked crafter inventories, phases, speeds, and handoffs. Two
crushing wheels arrive in the chest on tick 143. Apply
`tools/java-mechanical-crafter-trace.patch` to the pinned Java checkout to
reproduce the trace.

### Heated potion brewing

The unchanged upstream `potion_brewing.nbt` compares 394 ticks to
[the Java trace](fixtures/potion_brewing-java.csv). It traces the mixer,
both input and output tank pairs, and the Spout as a filtered pipe sends
Healing potion fluid to it. A bottle of Healing reaches the chest on
tick 393. Apply `tools/java-potion-brewing-trace.patch` to reproduce it.

### Track spans

`tools/test-track-line.py` compares seven two-click survival placements to
[the Java trace](fixtures/track_line-java.csv), including both diagonal
orientations, an existing endpoint, an obstacle gap, a crossing, and
insufficient inventory. It reads the placed shapes and remaining inventory
from the server. Apply `tools/java-track-line-trace.patch` to reproduce the
Java cases.


### Smart Observer chute pulse

The original `smart_observer_chutes.nbt` matches all 18 ticks in
[the Java trace](fixtures/smart_observer_chute_motion-java.csv). The observer
powers on at tick 14, the piston begins moving the diamond block at tick 15,
and the diamond reaches the output at tick 17. The trace includes the item
and vertical position in all three chutes. Reproduce it by applying
`tools/java-chute-observer-trace.patch` to the pinned Java checkout.


### Track curves

`tools/test-track-curve.py` compares ten survival curve placements to
[the Java trace](fixtures/track_curve-java.csv). It reads both saved
endpoints and checks the shape, Bezier handle length, arc length, sampled
positions, and track cost. The scenarios exercise ninety-degree and
diagonal turns, S-curves, rises, the sprint-key extension, and two
refused placements. Use `--visual` to capture the original rail and tie
models. Apply `tools/java-track-curve-trace.patch` to reproduce the cases.

### Hose Pulley

The unchanged upstream `hose_pulley_transfer.nbt` compares 301 ticks to
[the Java trace](fixtures/hose_pulley_transfer-java.csv). At 256 RPM, both
buffers and each of the 54 fluid cells match at every sampled tick. The
Horizon runner uses strict template placement to preserve the structure's
saved fluid cells, as Java's GameTest placement does. The original windows
form the walls of both reservoirs. The drain starts at tick 11, the first
source appears in the destination at tick 18, and all 27 buckets have moved
by tick 221. Apply `tools/java-hose-pulley-trace.patch` to reproduce it.

### Sequenced Gearshift and Rope Pulley

The unchanged upstream `threshold_switch_pulley.nbt` compares 56 ticks
to [the Java trace](fixtures/threshold_switch_pulley-java.csv). It measures
the instruction, timer, speed, rope offset, magnet block, and sampled
height. The offset reaches four blocks on tick 44, the magnet is placed
on tick 46, and the switch reports the final height on tick 55. Height is
reported relative to each template's origin. Apply
`tools/java-sequenced-pulley-trace.patch` to reproduce it.

### Train Station placement

`tools/test-track-station.py` compares six survival placements to
[the Java trace](fixtures/track_station-java.csv). It checks both
approach directions, the station's relative track target, item
consumption, and refusals for a missing target, a junction, and
a target outside the sixteen-block range. Apply
`tools/java-track-station-trace.patch` to reproduce the Java cases.

### Sturdy Sheet assembly

`tools/test-sturdy-sheet.py` records 67 ticks in a depot-based setup with
Create's unchanged Sturdy Sheet recipe. It traces the application of
500 mB of lava, the two press strokes, and the item component as the
sheet progresses. The first press advances the component at tick 47 and
the Sturdy Sheet is ready at tick 66. Reproduce the reference by applying
`tools/java-sturdy-sheet-trace.patch` to the pinned Java checkout. The
survival recipe applies the sheet to Brass Casing to make Train Casing.

### Train assembly bogeys

`tools/test-train-bogeys.py` opens the station in Horizon, enters assembly
mode, and compares six survival clicks against the pinned Java
[bogey trace](fixtures/train_bogeys-java.csv). It checks first-bogey
placement, spacing, size cycling, and Train Casing consumption. Apply
`tools/java-train-bogeys-trace.patch` to reproduce the Java cases.

### Assembled train and manual controls

`tools/test-simple-train.py` uses Super Glue and the station screen to
assemble a two-bogey carriage in survival. It drives with W and S and
checks the speed and four wheel positions through 125 ticks of forward
travel, braking, reverse, and a full stop. Apply
`tools/java-manual-train-trace.patch` to reproduce the
[reference trace](fixtures/manual_train-java.csv) with Java's actual
manual control handler. The Horizon trace uses a tolerance of 0.0000012
blocks for the serialized wheel positions. Run the same script with
`--disassemble` to verify the station restores the seven carriage
blocks and clears the moving carriage.

`tools/test-multiplayer-train.py` assembles the carriage in survival
on a dedicated server. It observes 37 Java-matching ticks from a second
client and saves that client's view of the moving carriage.

### Curved train travel

`tools/test-curved-train.py` lays a survival track with a 90-degree bend,
assembles a two-bogey carriage, and drives it through the bend to a full
stop. The fixture repositions the driver during the run to stay in
reach of the controls. It compares speed and all four three-dimensional axle positions
with Java across 160 consecutive ticks. The coordinate tolerance is
0.000007 blocks. Apply `tools/java-curved-train-trace.patch` to reproduce
the [Java trace](fixtures/curved_train-java.csv).

### Brass Tunnel routing

`tools/test-brass-tunnel.py --mode MODE` replays the original Java
GameTests for filtering, split, round robin, prefer nearest, and
synchronized input. Across 522 ticks it checks every source inventory,
all three tunnel buffers, and each output inventory. Apply
`tools/java-brass-tunnel-trace.patch` to the pinned Java checkout to
regenerate the references. The fixture applies selection and filter
settings through the original structure data and the command interface.

`tools/test-brass-tunnel-settings.py` also sets all seven modes through
the in-game settings panel, then places and clears an East-side filter
with real survival interactions.

### Attribute filters

`tools/test-item-inventories.py` with the `attribute_filters` scenario
loads the original configured filters and compares all nine destination
inventories for 87 ticks. It covers routing by item tag, food, fluid
container, enchantment, damage, equipment, fuel, and compostability.
Adjacent tunnels hand off items during the same tick. Apply
`tools/java-item-inventories-trace.patch` to regenerate the Java reference.

### Smart Observers, vanilla piston, and Gantry Carriage

`tools/test-observer-belt-funnel.py` replays the original
`smart_observer_belt_and_funnel` structure for 180 ticks. It compares
both Smart Observer signals, the source and destination inventory,
the piston and diamond block, and the Gantry Carriage's offset.
`tools/java-smart-observer-belt-and-funnel-trace.patch` regenerates
the Java reference.

### Display Link and Smart Observer counting

`tools/test-display-link.py` runs the original `smart_observer_counting`
structure. It compares a single chest and a double chest presentation
over 146 ticks, including passive updates and suppression while powered.
`--configure` tests selecting a Nixie, placing the link on a Smart Observer,
and choosing its item-count source in survival. Apply
`tools/java-display-link-trace.patch` to regenerate the Java trace.

### Depot-fed Display Board

`tools/test-depot-display.py` replays the original `depot_display`
structure for 121 ticks. It compares the two depot items, both display
rows, and both board rotation speeds. Loading the structure restores
the configured Display Links. `--configure` places a new link in
survival and selects the second display row with the real settings screen.
Apply `tools/java-depot-display-trace.patch`
to regenerate the Java reference.

### Sandpaper and electronics crafting

Polish Rose Quartz with Sand Paper or Red Sand Paper held in either
hand. Holding use for 32 player ticks creates Polished Rose Quartz
and spends one durability. Releasing early returns the quartz.
The `test-sandpaper.py` fixture compares 80 active and terminal Java
samples through both paths. `test-electronics-crafting.py` crafts nine
original recipes, including Electron Tubes, Brass Tunnels, Nixie Tubes,
Display Boards, Transmitters, and Display Links.

### Rope Pulley cargo

`tools/test-rope-payload.py` glues casing, planks, and a loaded chest into
one platform in survival. It compares all 66 ticks of lowering, stopping,
retracting, and restoring the full cargo. It checks the rope offset,
carriage position and speed, both structural blocks, and the copper
inventory. Run the same tool with `--detach` to remove the pulley at a
1.5-block extension. The platform lands three blocks below the pulley
with all seven copper ingots, as in Java. Apply
`tools/java-rope-payload-trace.patch` to run both Java cases.

### Redstone Contacts on a vertical Gantry

`tools/test-redstone-contacts.py` replays the original
`redstone_contacts` structure. It compares the carriage height, all
three contact pulses, and the diamond block's progress through the
piston column across 111 ticks. Apply
`tools/java-redstone-contacts-trace.patch` to regenerate the Java
reference.

### Redstone Links

Place a link on a support and sneak-click it with an empty hand to
switch modes. Right-click the two frequency positions with items.
A receiver matches the ordered pair and outputs the strongest
in-range transmission, including analog levels.

`tools/test-redstone-link.py` compares 83 ticks with Java. It tests
two transmitters, both frequency orders, channel changes, and the
resulting lamp. `--configure` verifies the two frequency slots and
mode switch in survival. Apply `tools/java-redstone-link-trace.patch`
to regenerate the Java trace.

`tools/test-multiplayer-redstone-link.py` uses two independent clients on
a dedicated server. Both configure real frequency slots, and one client
powers the other client's lamp. The receiving client changes and restores
its frequency to verify that the lamp follows the shared server state.


### Sheep shearing

`tools/test-shearing.py` loads the original pen and sheep. A player shears
the sheep in survival. The sheared state and presence of nearby white wool
match all 13 measured Java ticks. Apply `tools/java-shearing-trace.patch`
to regenerate the reference.

## Parallel parity work

Claim a family in [the Linear work queue](PARITY-WORK-QUEUE.md) and follow
[the worker workflow](PARITY-WORKER.md).

Gameplay tickets use [finite completion gates](COMPLETION-STANDARD.md); ticket
completion and exhaustive Java parity are tracked separately.

## Lightweight PR checks

GitHub runs one small Linux job for pull requests: tracked Python, JSON/JSONL,
TOML and shell syntax; five standalone Rust behavior tests for Frogport, Toolbox
and elevator motion; and Clippy correctness errors for the standalone tank
crate when its inputs change. It does not build Horizon, download game assets,
run game fixtures, or enforce repository-wide formatting. The injected mod is not a
standalone Cargo crate, so this Clippy check does not cover the entire port.
Run `python3 tools/check-source.py` locally (Python 3.11+). Gameplay evidence
remains part of each worker's focused verification. Duplicate PR runs cancel.
