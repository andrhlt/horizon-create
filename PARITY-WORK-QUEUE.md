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
