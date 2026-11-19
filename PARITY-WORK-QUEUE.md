# Parity work queue

The first 10 feature families are assigned through standalone Todo issues in the
[Blockmas project](https://linear.app/appstu/project/blockmas-02b108813887).
Claim an issue before starting and read [the worker workflow](PARITY-WORKER.md).
The [feature matrix](FEATURE-MATRIX.md) remains the evidence summary.
These tickets track remaining full-family parity, not work already completed.

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
