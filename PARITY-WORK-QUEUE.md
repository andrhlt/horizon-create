# Parity work queue

Feature families are tracked through standalone issues in the
[Blockmas project](https://linear.app/appstu/project/blockmas-02b108813887).
Claim an issue before starting and read [the worker workflow](PARITY-WORKER.md).
The [feature matrix](FEATURE-MATRIX.md) remains the evidence summary.
These tickets deliver finite gameplay completion passes under
[the completion standard](COMPLETION-STANDARD.md). Existing titles saying full
parity do not require exhaustive equivalence before delivery.

| Family | Linear issue |
| --- | --- |
| Kinetic network propagation, speed, stress and overload | [APP-1943](https://linear.app/appstu/issue/APP-1943/create-full-parity-kinetic-network-propagation-speed-stress-and) |
| Shafts, andesite and brass encased shafts | [APP-1944](https://linear.app/appstu/issue/APP-1944/create-full-parity-shafts-andesite-and-brass-encased-shafts) |
| Small and large cogwheels, encased cogwheels | [APP-1945](https://linear.app/appstu/issue/APP-1945/create-full-parity-small-and-large-cogwheels-encased-cogwheels) |
| Gearbox and Vertical Gearbox | [APP-1946](https://linear.app/appstu/issue/APP-1946/create-full-parity-gearbox-and-vertical-gearbox) |
| Clutch and Gearshift | [APP-1947](https://linear.app/appstu/issue/APP-1947/create-full-parity-clutch-and-gearshift) |
| Encased Chain Drive and Adjustable Chain Gearshift | [APP-1948](https://linear.app/appstu/issue/APP-1948/create-full-parity-encased-chain-drive-and-adjustable-chain-gearshift) |
| Sequenced Gearshift | [APP-1949](https://linear.app/appstu/issue/APP-1949/create-full-parity-sequenced-gearshift) |
| Creative Motor | [APP-1950](https://linear.app/appstu/issue/APP-1950/create-full-parity-creative-motor) |
| Rotation Speed Controller | [APP-1951](https://linear.app/appstu/issue/APP-1951/create-full-parity-rotation-speed-controller) |
| Hand Crank | [APP-1952](https://linear.app/appstu/issue/APP-1952/create-full-parity-hand-crank) |

All workers start from committed main and deliver a PR. Coordinate shared network
and build-cache changes; separate worktrees alone do not isolate the build cache.

## Batch 2: survival factory gameplay

These 20 standalone Todo issues prioritize obtaining materials, useful processing,
item handling and basic fluids. Follow COMPLETION-STANDARD.md; exhaustive parity
and cosmetic permutations are not delivery gates. Prerequisite links indicate
ordering for integrated survival checks; independent source work and existing
fixture checks can proceed in parallel. Do not duplicate prerequisite fixes.

| Family | Linear issue | Progression prerequisites |
| --- | --- | --- |
| Zinc Ore, deeper Zinc Ore, raw/zinc blocks and Zinc processing | [APP-1954](https://linear.app/appstu/issue/APP-1954/create-gameplay-baseline-zinc-ore-deeper-zinc-ore-rawzinc-blocks-and) | None within this batch |
| Andesite Alloy and Industrial/Weathered Iron blocks | [APP-1955](https://linear.app/appstu/issue/APP-1955/create-gameplay-baseline-andesite-alloy-and-industrialweathered-iron) | None within this batch |
| Andesite, Brass and Copper Casings | [APP-1956](https://linear.app/appstu/issue/APP-1956/create-gameplay-baseline-andesite-brass-and-copper-casings) | [APP-1955](https://linear.app/appstu/issue/APP-1955/create-gameplay-baseline-andesite-alloy-and-industrialweathered-iron), [APP-1961](https://linear.app/appstu/issue/APP-1961/create-gameplay-baseline-basin-compacting-and-mixing) |
| Water Wheels and Large Water Wheels | [APP-1957](https://linear.app/appstu/issue/APP-1957/create-gameplay-baseline-water-wheels-and-large-water-wheels) | [APP-1955](https://linear.app/appstu/issue/APP-1955/create-gameplay-baseline-andesite-alloy-and-industrialweathered-iron) |
| Millstone | [APP-1958](https://linear.app/appstu/issue/APP-1958/create-gameplay-baseline-millstone) | [APP-1955](https://linear.app/appstu/issue/APP-1955/create-gameplay-baseline-andesite-alloy-and-industrialweathered-iron) |
| Crushing Wheels and controller | [APP-1959](https://linear.app/appstu/issue/APP-1959/create-gameplay-baseline-crushing-wheels-and-controller) | [APP-1965](https://linear.app/appstu/issue/APP-1965/create-gameplay-baseline-mechanical-crafters) |
| Mechanical Press | [APP-1960](https://linear.app/appstu/issue/APP-1960/create-gameplay-baseline-mechanical-press) | None within this batch |
| Basin compacting and mixing | [APP-1961](https://linear.app/appstu/issue/APP-1961/create-gameplay-baseline-basin-compacting-and-mixing) | [APP-1962](https://linear.app/appstu/issue/APP-1962/create-gameplay-baseline-blaze-burner-fuels-and-blaze-cakes) |
| Blaze Burner, fuels and blaze cakes | [APP-1962](https://linear.app/appstu/issue/APP-1962/create-gameplay-baseline-blaze-burner-fuels-and-blaze-cakes) | None within this batch |
| Encased Fan | [APP-1963](https://linear.app/appstu/issue/APP-1963/create-gameplay-baseline-encased-fan) | None within this batch |
| Sandpaper and Red Sandpaper | [APP-1964](https://linear.app/appstu/issue/APP-1964/create-gameplay-baseline-sandpaper-and-red-sandpaper) | None within this batch |
| Mechanical Crafters | [APP-1965](https://linear.app/appstu/issue/APP-1965/create-gameplay-baseline-mechanical-crafters) | [APP-1960](https://linear.app/appstu/issue/APP-1960/create-gameplay-baseline-mechanical-press), [APP-1961](https://linear.app/appstu/issue/APP-1961/create-gameplay-baseline-basin-compacting-and-mixing), [APP-1964](https://linear.app/appstu/issue/APP-1964/create-gameplay-baseline-sandpaper-and-red-sandpaper) |
| Deployer | [APP-1966](https://linear.app/appstu/issue/APP-1966/create-gameplay-baseline-deployer) | [APP-1956](https://linear.app/appstu/issue/APP-1956/create-gameplay-baseline-andesite-brass-and-copper-casings), [APP-1964](https://linear.app/appstu/issue/APP-1964/create-gameplay-baseline-sandpaper-and-red-sandpaper) |
| Sequenced Assembly and unfinished ingredients | [APP-1967](https://linear.app/appstu/issue/APP-1967/create-gameplay-baseline-sequenced-assembly-and-unfinished-ingredients) | [APP-1960](https://linear.app/appstu/issue/APP-1960/create-gameplay-baseline-mechanical-press), [APP-1966](https://linear.app/appstu/issue/APP-1966/create-gameplay-baseline-deployer) |
| Mechanical Belt and Belt Connector | [APP-1968](https://linear.app/appstu/issue/APP-1968/create-gameplay-baseline-mechanical-belt-and-belt-connector) | None within this batch |
| Depot | [APP-1969](https://linear.app/appstu/issue/APP-1969/create-gameplay-baseline-depot) | [APP-1955](https://linear.app/appstu/issue/APP-1955/create-gameplay-baseline-andesite-alloy-and-industrialweathered-iron) |
| Andesite and Brass Funnels | [APP-1970](https://linear.app/appstu/issue/APP-1970/create-gameplay-baseline-andesite-and-brass-funnels) | [APP-1956](https://linear.app/appstu/issue/APP-1956/create-gameplay-baseline-andesite-brass-and-copper-casings) |
| Chute and Smart Chute | [APP-1971](https://linear.app/appstu/issue/APP-1971/create-gameplay-baseline-chute-and-smart-chute) | [APP-1956](https://linear.app/appstu/issue/APP-1956/create-gameplay-baseline-andesite-brass-and-copper-casings) |
| Fluid Pipe, Glass Fluid Pipe, Smart Fluid Pipe | [APP-1972](https://linear.app/appstu/issue/APP-1972/create-gameplay-baseline-fluid-pipe-glass-fluid-pipe-smart-fluid-pipe) | [APP-1960](https://linear.app/appstu/issue/APP-1960/create-gameplay-baseline-mechanical-press) |
| Mechanical Pump | [APP-1973](https://linear.app/appstu/issue/APP-1973/create-gameplay-baseline-mechanical-pump) | [APP-1972](https://linear.app/appstu/issue/APP-1972/create-gameplay-baseline-fluid-pipe-glass-fluid-pipe-smart-fluid-pipe) |

## Batch 3: remaining feature families

All 160 feature-matrix families now have standalone Linear issues: the 30 above
and the 130 below. These tickets complete bounded gameplay baselines under
COMPLETION-STANDARD.md; they do not claim exhaustive Java parity. Each description
contains its current matrix evidence, tailored acceptance cases, reference pins,
build/test workflow, multiplayer/persistence gates and PR delivery instructions.

Priorities favor survival blockers before optional/presentation work. Prerequisites
are also saved as Linear blocked-by relations. They order integrated acceptance;
independent source work and fixtures can proceed against working prerequisites.
Choose an unassigned issue with satisfied prerequisites and avoid duplicating
shared-module fixes. Linear owns live status; this table is an index, not a second
status tracker.

| Family | Linear issue | Priority | Integrated acceptance prerequisites |
| --- | --- | --- | --- |
| Copper Valve Handle and all dyed handles | [APP-1974](https://linear.app/appstu/issue/APP-1974/create-gameplay-baseline-copper-valve-handle-and-all-dyed-handles) | Medium | [APP-1943](https://linear.app/appstu/issue/APP-1943/create-full-parity-kinetic-network-propagation-speed-stress-and) |
| Speedometer and Stressometer | [APP-1975](https://linear.app/appstu/issue/APP-1975/create-gameplay-baseline-speedometer-and-stressometer) | High | [APP-1943](https://linear.app/appstu/issue/APP-1943/create-full-parity-kinetic-network-propagation-speed-stress-and) |
| Flywheel | [APP-1976](https://linear.app/appstu/issue/APP-1976/create-gameplay-baseline-flywheel) | Low | None |
| Turntable | [APP-1977](https://linear.app/appstu/issue/APP-1977/create-gameplay-baseline-turntable) | Low | None |
| Mechanical Saw | [APP-1981](https://linear.app/appstu/issue/APP-1981/create-gameplay-baseline-mechanical-saw) | High | [APP-1980](https://linear.app/appstu/issue/APP-1980/create-gameplay-baseline-mechanical-bearing) |
| Mechanical Drill | [APP-1983](https://linear.app/appstu/issue/APP-1983/create-gameplay-baseline-mechanical-drill) | High | [APP-1982](https://linear.app/appstu/issue/APP-1982/create-gameplay-baseline-mechanical-piston-sticky-mechanical-piston) |
| Nozzle | [APP-1984](https://linear.app/appstu/issue/APP-1984/create-gameplay-baseline-nozzle) | Medium | [APP-1963](https://linear.app/appstu/issue/APP-1963/create-gameplay-baseline-encased-fan) |
| Encased Fluid Pipe | [APP-1985](https://linear.app/appstu/issue/APP-1985/create-gameplay-baseline-encased-fluid-pipe) | High | [APP-1972](https://linear.app/appstu/issue/APP-1972/create-gameplay-baseline-fluid-pipe-glass-fluid-pipe-smart-fluid-pipe) |
| Fluid Valve | [APP-1986](https://linear.app/appstu/issue/APP-1986/create-gameplay-baseline-fluid-valve) | High | [APP-1972](https://linear.app/appstu/issue/APP-1972/create-gameplay-baseline-fluid-pipe-glass-fluid-pipe-smart-fluid-pipe), [APP-1973](https://linear.app/appstu/issue/APP-1973/create-gameplay-baseline-mechanical-pump) |
| Fluid Tank and Creative Fluid Tank | [APP-1987](https://linear.app/appstu/issue/APP-1987/create-gameplay-baseline-fluid-tank-and-creative-fluid-tank) | High | [APP-1973](https://linear.app/appstu/issue/APP-1973/create-gameplay-baseline-mechanical-pump) |
| Item Drain | [APP-1988](https://linear.app/appstu/issue/APP-1988/create-gameplay-baseline-item-drain) | High | [APP-1972](https://linear.app/appstu/issue/APP-1972/create-gameplay-baseline-fluid-pipe-glass-fluid-pipe-smart-fluid-pipe) |
| Hose Pulley | [APP-1989](https://linear.app/appstu/issue/APP-1989/create-gameplay-baseline-hose-pulley) | High | [APP-1973](https://linear.app/appstu/issue/APP-1973/create-gameplay-baseline-mechanical-pump) |
| Spout | [APP-1990](https://linear.app/appstu/issue/APP-1990/create-gameplay-baseline-spout) | High | [APP-1987](https://linear.app/appstu/issue/APP-1987/create-gameplay-baseline-fluid-tank-and-creative-fluid-tank) |
| Potion fluids and heated brewing | [APP-1991](https://linear.app/appstu/issue/APP-1991/create-gameplay-baseline-potion-fluids-and-heated-brewing) | Medium | [APP-1961](https://linear.app/appstu/issue/APP-1961/create-gameplay-baseline-basin-compacting-and-mixing), [APP-1990](https://linear.app/appstu/issue/APP-1990/create-gameplay-baseline-spout) |
| Honey, chocolate and tea | [APP-1992](https://linear.app/appstu/issue/APP-1992/create-gameplay-baseline-honey-chocolate-and-tea) | Medium | [APP-1961](https://linear.app/appstu/issue/APP-1961/create-gameplay-baseline-basin-compacting-and-mixing), [APP-1990](https://linear.app/appstu/issue/APP-1990/create-gameplay-baseline-spout) |
| Steam Engine, boiler and Powered Shaft | [APP-1993](https://linear.app/appstu/issue/APP-1993/create-gameplay-baseline-steam-engine-boiler-and-powered-shaft) | High | [APP-1987](https://linear.app/appstu/issue/APP-1987/create-gameplay-baseline-fluid-tank-and-creative-fluid-tank), [APP-1962](https://linear.app/appstu/issue/APP-1962/create-gameplay-baseline-blaze-burner-fuels-and-blaze-cakes), [APP-1973](https://linear.app/appstu/issue/APP-1973/create-gameplay-baseline-mechanical-pump) |
| Steam Whistle and extension | [APP-1994](https://linear.app/appstu/issue/APP-1994/create-gameplay-baseline-steam-whistle-and-extension) | Low | [APP-1993](https://linear.app/appstu/issue/APP-1993/create-gameplay-baseline-steam-engine-boiler-and-powered-shaft) |
| Super Glue and assembly selection | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection) | High | None |
| Linear, Secondary Linear and Radial Chassis | [APP-1995](https://linear.app/appstu/issue/APP-1995/create-gameplay-baseline-linear-secondary-linear-and-radial-chassis) | Medium | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection) |
| Mechanical Bearing | [APP-1980](https://linear.app/appstu/issue/APP-1980/create-gameplay-baseline-mechanical-bearing) | High | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection), [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Windmill Bearing and colored sails | [APP-1996](https://linear.app/appstu/issue/APP-1996/create-gameplay-baseline-windmill-bearing-and-colored-sails) | Medium | [APP-1980](https://linear.app/appstu/issue/APP-1980/create-gameplay-baseline-mechanical-bearing) |
| Clockwork Bearing | [APP-1997](https://linear.app/appstu/issue/APP-1997/create-gameplay-baseline-clockwork-bearing) | Medium | [APP-1980](https://linear.app/appstu/issue/APP-1980/create-gameplay-baseline-mechanical-bearing) |
| Cuckoo Clock and Mysterious Cuckoo Clock | [APP-1998](https://linear.app/appstu/issue/APP-1998/create-gameplay-baseline-cuckoo-clock-and-mysterious-cuckoo-clock) | Low | None |
| Mechanical Piston, Sticky Mechanical Piston, Extension Poles | [APP-1982](https://linear.app/appstu/issue/APP-1982/create-gameplay-baseline-mechanical-piston-sticky-mechanical-piston) | High | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection), [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Rope Pulley and moving payload | [APP-1999](https://linear.app/appstu/issue/APP-1999/create-gameplay-baseline-rope-pulley-and-moving-payload) | High | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection), [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Elevator Pulley, Elevator Contacts and cabin | [APP-2001](https://linear.app/appstu/issue/APP-2001/create-gameplay-baseline-elevator-pulley-elevator-contacts-and-cabin) | Medium | [APP-1999](https://linear.app/appstu/issue/APP-1999/create-gameplay-baseline-rope-pulley-and-moving-payload), [APP-2000](https://linear.app/appstu/issue/APP-2000/create-gameplay-baseline-redstone-contact) |
| Gantry Shaft and Gantry Carriage | [APP-2002](https://linear.app/appstu/issue/APP-2002/create-gameplay-baseline-gantry-shaft-and-gantry-carriage) | Medium | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection), [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Cart Assembler and Controller Rail | [APP-2003](https://linear.app/appstu/issue/APP-2003/create-gameplay-baseline-cart-assembler-and-controller-rail) | Medium | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection), [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Minecart Coupling, Anchor and portable contraption items | [APP-2004](https://linear.app/appstu/issue/APP-2004/create-gameplay-baseline-minecart-coupling-anchor-and-portable) | Medium | [APP-2003](https://linear.app/appstu/issue/APP-2003/create-gameplay-baseline-cart-assembler-and-controller-rail) |
| Contraption Controls | [APP-2005](https://linear.app/appstu/issue/APP-2005/create-gameplay-baseline-contraption-controls) | Medium | [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Harvester and Plough | [APP-2006](https://linear.app/appstu/issue/APP-2006/create-gameplay-baseline-harvester-and-plough) | High | [APP-1980](https://linear.app/appstu/issue/APP-1980/create-gameplay-baseline-mechanical-bearing) |
| Mechanical Roller | [APP-2007](https://linear.app/appstu/issue/APP-2007/create-gameplay-baseline-mechanical-roller) | Medium | [APP-2002](https://linear.app/appstu/issue/APP-2002/create-gameplay-baseline-gantry-shaft-and-gantry-carriage) |
| Dispensers, droppers and mounted actor behaviors | [APP-2008](https://linear.app/appstu/issue/APP-2008/create-gameplay-baseline-dispensers-droppers-and-mounted-actor) | Medium | [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Portable Storage and Fluid Interfaces | [APP-2009](https://linear.app/appstu/issue/APP-2009/create-gameplay-baseline-portable-storage-and-fluid-interfaces) | High | [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Seats and colored seats | [APP-2010](https://linear.app/appstu/issue/APP-2010/create-gameplay-baseline-seats-and-colored-seats) | Low | [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Sticker | [APP-2011](https://linear.app/appstu/issue/APP-2011/create-gameplay-baseline-sticker) | Medium | [APP-1982](https://linear.app/appstu/issue/APP-1982/create-gameplay-baseline-mechanical-piston-sticky-mechanical-piston) |
| General contraption rendering, collision and synchronization | [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) | High | [APP-1978](https://linear.app/appstu/issue/APP-1978/create-gameplay-baseline-super-glue-and-assembly-selection) |
| Weighted Ejector | [APP-2012](https://linear.app/appstu/issue/APP-2012/create-gameplay-baseline-weighted-ejector) | Medium | [APP-1969](https://linear.app/appstu/issue/APP-1969/create-gameplay-baseline-depot) |
| Andesite and Brass Tunnels | [APP-2013](https://linear.app/appstu/issue/APP-2013/create-gameplay-baseline-andesite-and-brass-tunnels) | High | [APP-1968](https://linear.app/appstu/issue/APP-1968/create-gameplay-baseline-mechanical-belt-and-belt-connector), [APP-1970](https://linear.app/appstu/issue/APP-1970/create-gameplay-baseline-andesite-and-brass-funnels) |
| Mechanical Arm | [APP-2014](https://linear.app/appstu/issue/APP-2014/create-gameplay-baseline-mechanical-arm) | High | [APP-1969](https://linear.app/appstu/issue/APP-1969/create-gameplay-baseline-depot), [APP-1962](https://linear.app/appstu/issue/APP-1962/create-gameplay-baseline-blaze-burner-fuels-and-blaze-cakes) |
| Item Vault | [APP-2015](https://linear.app/appstu/issue/APP-2015/create-gameplay-baseline-item-vault) | High | None |
| Creative Crate | [APP-2016](https://linear.app/appstu/issue/APP-2016/create-gameplay-baseline-creative-crate) | Low | None |
| Item Hatch | [APP-2017](https://linear.app/appstu/issue/APP-2017/create-gameplay-baseline-item-hatch) | Medium | None |
| List Filter, Attribute Filter and Package Filter | [APP-2018](https://linear.app/appstu/issue/APP-2018/create-gameplay-baseline-list-filter-attribute-filter-and-package) | High | None |
| Cardboard packages and rare variants | [APP-2020](https://linear.app/appstu/issue/APP-2020/create-gameplay-baseline-cardboard-packages-and-rare-variants) | Medium | [APP-2019](https://linear.app/appstu/issue/APP-2019/create-gameplay-baseline-cardboard-pulp-cardboard-block-and-bound) |
| Packager | [APP-2021](https://linear.app/appstu/issue/APP-2021/create-gameplay-baseline-packager) | Medium | [APP-2020](https://linear.app/appstu/issue/APP-2020/create-gameplay-baseline-cardboard-packages-and-rare-variants) |
| Repackager | [APP-2022](https://linear.app/appstu/issue/APP-2022/create-gameplay-baseline-repackager) | Medium | [APP-2021](https://linear.app/appstu/issue/APP-2021/create-gameplay-baseline-packager) |
| Stock Link | [APP-2023](https://linear.app/appstu/issue/APP-2023/create-gameplay-baseline-stock-link) | Medium | None |
| Redstone Requester | [APP-2024](https://linear.app/appstu/issue/APP-2024/create-gameplay-baseline-redstone-requester) | Medium | [APP-2021](https://linear.app/appstu/issue/APP-2021/create-gameplay-baseline-packager), [APP-2023](https://linear.app/appstu/issue/APP-2023/create-gameplay-baseline-stock-link) |
| Stock Ticker and Stock Keeper | [APP-2025](https://linear.app/appstu/issue/APP-2025/create-gameplay-baseline-stock-ticker-and-stock-keeper) | Medium | [APP-2021](https://linear.app/appstu/issue/APP-2021/create-gameplay-baseline-packager), [APP-2023](https://linear.app/appstu/issue/APP-2023/create-gameplay-baseline-stock-link) |
| Factory Gauge and Factory Panels | [APP-2026](https://linear.app/appstu/issue/APP-2026/create-gameplay-baseline-factory-gauge-and-factory-panels) | Medium | [APP-2024](https://linear.app/appstu/issue/APP-2024/create-gameplay-baseline-redstone-requester) |
| Chain Conveyor | [APP-2027](https://linear.app/appstu/issue/APP-2027/create-gameplay-baseline-chain-conveyor) | Medium | None |
| Frogport | [APP-2028](https://linear.app/appstu/issue/APP-2028/create-gameplay-baseline-frogport) | Medium | [APP-2027](https://linear.app/appstu/issue/APP-2027/create-gameplay-baseline-chain-conveyor), [APP-2020](https://linear.app/appstu/issue/APP-2020/create-gameplay-baseline-cardboard-packages-and-rare-variants) |
| Postboxes, 16 dyed blocks and items | [APP-2029](https://linear.app/appstu/issue/APP-2029/create-gameplay-baseline-postboxes-16-dyed-blocks-and-items) | Medium | [APP-2020](https://linear.app/appstu/issue/APP-2020/create-gameplay-baseline-cardboard-packages-and-rare-variants) |
| Table Cloths, 16 colors and 3 metal variants | [APP-2030](https://linear.app/appstu/issue/APP-2030/create-gameplay-baseline-table-cloths-16-colors-and-3-metal-variants) | Low | [APP-2020](https://linear.app/appstu/issue/APP-2020/create-gameplay-baseline-cardboard-packages-and-rare-variants) |
| Shopping List | [APP-2031](https://linear.app/appstu/issue/APP-2031/create-gameplay-baseline-shopping-list) | Low | [APP-2025](https://linear.app/appstu/issue/APP-2025/create-gameplay-baseline-stock-ticker-and-stock-keeper) |
| Redstone Contact | [APP-2000](https://linear.app/appstu/issue/APP-2000/create-gameplay-baseline-redstone-contact) | Medium | None |
| Redstone Link | [APP-2032](https://linear.app/appstu/issue/APP-2032/create-gameplay-baseline-redstone-link) | Medium | None |
| Linked Controller and Lectern Controller | [APP-2033](https://linear.app/appstu/issue/APP-2033/create-gameplay-baseline-linked-controller-and-lectern-controller) | Medium | [APP-2032](https://linear.app/appstu/issue/APP-2032/create-gameplay-baseline-redstone-link) |
| Analog Lever | [APP-2034](https://linear.app/appstu/issue/APP-2034/create-gameplay-baseline-analog-lever) | Medium | None |
| Powered Latch and Powered Toggle Latch | [APP-2035](https://linear.app/appstu/issue/APP-2035/create-gameplay-baseline-powered-latch-and-powered-toggle-latch) | Medium | None |
| Pulse Repeater, Extender and Timer | [APP-2036](https://linear.app/appstu/issue/APP-2036/create-gameplay-baseline-pulse-repeater-extender-and-timer) | Medium | None |
| Desk Bell | [APP-2037](https://linear.app/appstu/issue/APP-2037/create-gameplay-baseline-desk-bell) | Low | None |
| Peculiar Bell and Haunted Bell | [APP-2038](https://linear.app/appstu/issue/APP-2038/create-gameplay-baseline-peculiar-bell-and-haunted-bell) | Low | [APP-1963](https://linear.app/appstu/issue/APP-1963/create-gameplay-baseline-encased-fan) |
| Stockpile Switch | [APP-2039](https://linear.app/appstu/issue/APP-2039/create-gameplay-baseline-stockpile-switch) | Medium | None |
| Smart Observer (Content Observer) | [APP-2040](https://linear.app/appstu/issue/APP-2040/create-gameplay-baseline-smart-observer-content-observer) | Medium | None |
| Display Link and Display Board | [APP-2041](https://linear.app/appstu/issue/APP-2041/create-gameplay-baseline-display-link-and-display-board) | Medium | None |
| Nixie Tubes and dyed variants | [APP-2042](https://linear.app/appstu/issue/APP-2042/create-gameplay-baseline-nixie-tubes-and-dyed-variants) | Low | [APP-2041](https://linear.app/appstu/issue/APP-2041/create-gameplay-baseline-display-link-and-display-board) |
| Rose Quartz Lamp | [APP-2043](https://linear.app/appstu/issue/APP-2043/create-gameplay-baseline-rose-quartz-lamp) | Low | None |
| Controller Rail | [APP-2044](https://linear.app/appstu/issue/APP-2044/create-gameplay-baseline-controller-rail) | Medium | None |
| Train Track, curved spans and Railway Casing | [APP-2045](https://linear.app/appstu/issue/APP-2045/create-gameplay-baseline-train-track-curved-spans-and-railway-casing) | Medium | None |
| Fake Track | [APP-2046](https://linear.app/appstu/issue/APP-2046/create-gameplay-baseline-fake-track) | Low | [APP-2045](https://linear.app/appstu/issue/APP-2045/create-gameplay-baseline-train-track-curved-spans-and-railway-casing) |
| Track Observer | [APP-2048](https://linear.app/appstu/issue/APP-2048/create-gameplay-baseline-track-observer) | Medium | [APP-2045](https://linear.app/appstu/issue/APP-2045/create-gameplay-baseline-train-track-curved-spans-and-railway-casing), [APP-2047](https://linear.app/appstu/issue/APP-2047/create-gameplay-baseline-bogeys-and-train-assembly) |
| Bogeys and train assembly | [APP-2047](https://linear.app/appstu/issue/APP-2047/create-gameplay-baseline-bogeys-and-train-assembly) | Medium | [APP-2045](https://linear.app/appstu/issue/APP-2045/create-gameplay-baseline-train-track-curved-spans-and-railway-casing), [APP-1979](https://linear.app/appstu/issue/APP-1979/create-gameplay-baseline-general-contraption-rendering-collision-and) |
| Train Station, names and dispatch | [APP-2049](https://linear.app/appstu/issue/APP-2049/create-gameplay-baseline-train-station-names-and-dispatch) | Medium | [APP-2047](https://linear.app/appstu/issue/APP-2047/create-gameplay-baseline-bogeys-and-train-assembly) |
| Train Signals and occupancy | [APP-2050](https://linear.app/appstu/issue/APP-2050/create-gameplay-baseline-train-signals-and-occupancy) | Medium | [APP-2045](https://linear.app/appstu/issue/APP-2045/create-gameplay-baseline-train-track-curved-spans-and-railway-casing), [APP-2047](https://linear.app/appstu/issue/APP-2047/create-gameplay-baseline-bogeys-and-train-assembly) |
| Manual driving and Train Controls | [APP-2051](https://linear.app/appstu/issue/APP-2051/create-gameplay-baseline-manual-driving-and-train-controls) | Medium | [APP-2047](https://linear.app/appstu/issue/APP-2047/create-gameplay-baseline-bogeys-and-train-assembly) |
| Train Schedules, conductor and schedule condition editor | [APP-2052](https://linear.app/appstu/issue/APP-2052/create-gameplay-baseline-train-schedules-conductor-and-schedule) | Medium | [APP-2049](https://linear.app/appstu/issue/APP-2049/create-gameplay-baseline-train-station-names-and-dispatch) |
| Scheduled routing and arrival | [APP-2053](https://linear.app/appstu/issue/APP-2053/create-gameplay-baseline-scheduled-routing-and-arrival) | Medium | [APP-2052](https://linear.app/appstu/issue/APP-2052/create-gameplay-baseline-train-schedules-conductor-and-schedule), [APP-2050](https://linear.app/appstu/issue/APP-2050/create-gameplay-baseline-train-signals-and-occupancy) |
| Train passengers, seats and dismount | [APP-2054](https://linear.app/appstu/issue/APP-2054/create-gameplay-baseline-train-passengers-seats-and-dismount) | Medium | [APP-2051](https://linear.app/appstu/issue/APP-2051/create-gameplay-baseline-manual-driving-and-train-controls), [APP-2010](https://linear.app/appstu/issue/APP-2010/create-gameplay-baseline-seats-and-colored-seats) |
| Mounted train item and fluid storage | [APP-2055](https://linear.app/appstu/issue/APP-2055/create-gameplay-baseline-mounted-train-item-and-fluid-storage) | Medium | [APP-2051](https://linear.app/appstu/issue/APP-2051/create-gameplay-baseline-manual-driving-and-train-controls), [APP-2009](https://linear.app/appstu/issue/APP-2009/create-gameplay-baseline-portable-storage-and-fluid-interfaces), [APP-1987](https://linear.app/appstu/issue/APP-1987/create-gameplay-baseline-fluid-tank-and-creative-fluid-tank) |
| Train post routes, parcels and station buffers | [APP-2056](https://linear.app/appstu/issue/APP-2056/create-gameplay-baseline-train-post-routes-parcels-and-station-buffers) | Medium | [APP-2053](https://linear.app/appstu/issue/APP-2053/create-gameplay-baseline-scheduled-routing-and-arrival), [APP-2029](https://linear.app/appstu/issue/APP-2029/create-gameplay-baseline-postboxes-16-dyed-blocks-and-items) |
| Train door integration | [APP-2058](https://linear.app/appstu/issue/APP-2058/create-gameplay-baseline-train-door-integration) | Medium | [APP-2051](https://linear.app/appstu/issue/APP-2051/create-gameplay-baseline-manual-driving-and-train-controls), [APP-2057](https://linear.app/appstu/issue/APP-2057/create-gameplay-baseline-sliding-doors-and-train-side-door) |
| Train display sources, announcements and audio | [APP-2059](https://linear.app/appstu/issue/APP-2059/create-gameplay-baseline-train-display-sources-announcements-and-audio) | Low | [APP-2049](https://linear.app/appstu/issue/APP-2049/create-gameplay-baseline-train-station-names-and-dispatch), [APP-2041](https://linear.app/appstu/issue/APP-2041/create-gameplay-baseline-display-link-and-display-board) |
| Create stone world generation and Striated Ore | [APP-2060](https://linear.app/appstu/issue/APP-2060/create-gameplay-baseline-create-stone-world-generation-and-striated) | Low | None |
| Decorative stone palettes | [APP-2061](https://linear.app/appstu/issue/APP-2061/create-gameplay-baseline-decorative-stone-palettes) | Low | None |
| Rose Quartz and Polished Rose Quartz palettes | [APP-2062](https://linear.app/appstu/issue/APP-2062/create-gameplay-baseline-rose-quartz-and-polished-rose-quartz-palettes) | Low | [APP-1964](https://linear.app/appstu/issue/APP-1964/create-gameplay-baseline-sandpaper-and-red-sandpaper) |
| Glass windows and panes | [APP-2063](https://linear.app/appstu/issue/APP-2063/create-gameplay-baseline-glass-windows-and-panes) | Low | None |
| Train Trapdoor and Framed Glass Trapdoor | [APP-2064](https://linear.app/appstu/issue/APP-2064/create-gameplay-baseline-train-trapdoor-and-framed-glass-trapdoor) | Low | None |
| Copycat Panel, Step, base and Bars | [APP-2065](https://linear.app/appstu/issue/APP-2065/create-gameplay-baseline-copycat-panel-step-base-and-bars) | Low | None |
| Metal Bars | [APP-2066](https://linear.app/appstu/issue/APP-2066/create-gameplay-baseline-metal-bars) | Low | None |
| Metal Ladders | [APP-2067](https://linear.app/appstu/issue/APP-2067/create-gameplay-baseline-metal-ladders) | Low | None |
| Andesite, Brass and Copper Scaffolding | [APP-2068](https://linear.app/appstu/issue/APP-2068/create-gameplay-baseline-andesite-brass-and-copper-scaffolding) | Low | None |
| Metal Girders and encased Girder Shafts | [APP-2069](https://linear.app/appstu/issue/APP-2069/create-gameplay-baseline-metal-girders-and-encased-girder-shafts) | Low | [APP-1944](https://linear.app/appstu/issue/APP-1944/create-full-parity-shafts-andesite-and-brass-encased-shafts) |
| Wooden and Metal Brackets | [APP-2070](https://linear.app/appstu/issue/APP-2070/create-gameplay-baseline-wooden-and-metal-brackets) | Low | None |
| Copper Shingles and Tiles, slabs, stairs, wax/oxidation variants | [APP-2071](https://linear.app/appstu/issue/APP-2071/create-gameplay-baseline-copper-shingles-and-tiles-slabs-stairs) | Low | None |
| Placard | [APP-2072](https://linear.app/appstu/issue/APP-2072/create-gameplay-baseline-placard) | Low | None |
| Sliding Doors and train-side door interactions | [APP-2057](https://linear.app/appstu/issue/APP-2057/create-gameplay-baseline-sliding-doors-and-train-side-door) | Low | None |
| Shadow Steel and Refined Radiance family | [APP-2073](https://linear.app/appstu/issue/APP-2073/create-gameplay-baseline-shadow-steel-and-refined-radiance-family) | Low | None |
| Common parts and metal intermediates | [APP-2074](https://linear.app/appstu/issue/APP-2074/create-gameplay-baseline-common-parts-and-metal-intermediates) | High | None |
| Experience Nugget and Experience Block | [APP-2075](https://linear.app/appstu/issue/APP-2075/create-gameplay-baseline-experience-nugget-and-experience-block) | Low | None |
| Wrench | [APP-2076](https://linear.app/appstu/issue/APP-2076/create-gameplay-baseline-wrench) | High | None |
| Engineer's Goggles | [APP-2077](https://linear.app/appstu/issue/APP-2077/create-gameplay-baseline-engineers-goggles) | High | [APP-1975](https://linear.app/appstu/issue/APP-1975/create-gameplay-baseline-speedometer-and-stressometer) |
| Clipboard | [APP-2078](https://linear.app/appstu/issue/APP-2078/create-gameplay-baseline-clipboard) | Medium | None |
| Cardboard, Pulp, Cardboard Block and Bound Cardboard | [APP-2019](https://linear.app/appstu/issue/APP-2019/create-gameplay-baseline-cardboard-pulp-cardboard-block-and-bound) | Medium | None |
| Cardboard armor and disguise | [APP-2079](https://linear.app/appstu/issue/APP-2079/create-gameplay-baseline-cardboard-armor-and-disguise) | Low | [APP-2019](https://linear.app/appstu/issue/APP-2019/create-gameplay-baseline-cardboard-pulp-cardboard-block-and-bound) |
| Cardboard Sword | [APP-2080](https://linear.app/appstu/issue/APP-2080/create-gameplay-baseline-cardboard-sword) | Low | [APP-2019](https://linear.app/appstu/issue/APP-2019/create-gameplay-baseline-cardboard-pulp-cardboard-block-and-bound) |
| Copper Backtank, Copper Diving Helmet and Copper Diving Boots | [APP-2081](https://linear.app/appstu/issue/APP-2081/create-gameplay-baseline-copper-backtank-copper-diving-helmet-and) | Medium | None |
| Netherite Backtank and Netherite diving gear | [APP-2082](https://linear.app/appstu/issue/APP-2082/create-gameplay-baseline-netherite-backtank-and-netherite-diving-gear) | Low | [APP-2081](https://linear.app/appstu/issue/APP-2081/create-gameplay-baseline-copper-backtank-copper-diving-helmet-and) |
| Toolbox, 16 colors | [APP-2083](https://linear.app/appstu/issue/APP-2083/create-gameplay-baseline-toolbox-16-colors) | High | None |
| Potato Cannon | [APP-2084](https://linear.app/appstu/issue/APP-2084/create-gameplay-baseline-potato-cannon) | Low | [APP-2081](https://linear.app/appstu/issue/APP-2081/create-gameplay-baseline-copper-backtank-copper-diving-helmet-and) |
| Extendo Grip | [APP-2085](https://linear.app/appstu/issue/APP-2085/create-gameplay-baseline-extendo-grip) | Low | [APP-1965](https://linear.app/appstu/issue/APP-1965/create-gameplay-baseline-mechanical-crafters) |
| Wand of Symmetry | [APP-2086](https://linear.app/appstu/issue/APP-2086/create-gameplay-baseline-wand-of-symmetry) | Low | None |
| Handheld Worldshaper | [APP-2087](https://linear.app/appstu/issue/APP-2087/create-gameplay-baseline-handheld-worldshaper) | Low | None |
| Tree Fertilizer | [APP-2088](https://linear.app/appstu/issue/APP-2088/create-gameplay-baseline-tree-fertilizer) | Low | None |
| Shears/deployer interactions | [APP-2089](https://linear.app/appstu/issue/APP-2089/create-gameplay-baseline-shearsdeployer-interactions) | Medium | [APP-1966](https://linear.app/appstu/issue/APP-1966/create-gameplay-baseline-deployer) |
| Create foods and Builder's Tea | [APP-2090](https://linear.app/appstu/issue/APP-2090/create-gameplay-baseline-create-foods-and-builders-tea) | Low | [APP-1961](https://linear.app/appstu/issue/APP-1961/create-gameplay-baseline-basin-compacting-and-mixing) |
| Crafting Blueprint and Blueprint display | [APP-2091](https://linear.app/appstu/issue/APP-2091/create-gameplay-baseline-crafting-blueprint-and-blueprint-display) | Low | None |
| Empty Schematic, Schematic and Quill, Schematic Table | [APP-2092](https://linear.app/appstu/issue/APP-2092/create-gameplay-baseline-empty-schematic-schematic-and-quill-schematic) | Medium | None |
| Schematicannon | [APP-2093](https://linear.app/appstu/issue/APP-2093/create-gameplay-baseline-schematicannon) | Medium | [APP-2092](https://linear.app/appstu/issue/APP-2092/create-gameplay-baseline-empty-schematic-schematic-and-quill-schematic) |
| Survival progression and advancement ownership | [APP-2094](https://linear.app/appstu/issue/APP-2094/create-gameplay-baseline-survival-progression-and-advancement) | High | None |
| Creative tabs, creative search and item attribution | [APP-2095](https://linear.app/appstu/issue/APP-2095/create-gameplay-baseline-creative-tabs-creative-search-and-item) | Medium | None |
| Crafting, Stonecutting, smelting, blasting, smoking and campfire recipes | [APP-2096](https://linear.app/appstu/issue/APP-2096/create-gameplay-baseline-crafting-stonecutting-smelting-blasting) | High | None |
| Machine recipe logic and registry integration | [APP-2097](https://linear.app/appstu/issue/APP-2097/create-gameplay-baseline-machine-recipe-logic-and-registry-integration) | High | None |
| Block, item and entity models, textures and animation | [APP-2098](https://linear.app/appstu/issue/APP-2098/create-gameplay-baseline-block-item-and-entity-models-textures-and) | Low | None |
| Sounds, particles and effects | [APP-2099](https://linear.app/appstu/issue/APP-2099/create-gameplay-baseline-sounds-particles-and-effects) | Low | None |
| Localization and UI | [APP-2100](https://linear.app/appstu/issue/APP-2100/create-gameplay-baseline-localization-and-ui) | Low | None |
| Ponder and tutorials | [APP-2101](https://linear.app/appstu/issue/APP-2101/create-gameplay-baseline-ponder-and-tutorials) | Low | None |
| Server configuration, permissions and persistence | [APP-2102](https://linear.app/appstu/issue/APP-2102/create-gameplay-baseline-server-configuration-permissions-and) | High | None |
| Java integration equivalents | [APP-2103](https://linear.app/appstu/issue/APP-2103/create-gameplay-baseline-java-integration-equivalents) | Low | [APP-2097](https://linear.app/appstu/issue/APP-2097/create-gameplay-baseline-machine-recipe-logic-and-registry-integration) |
