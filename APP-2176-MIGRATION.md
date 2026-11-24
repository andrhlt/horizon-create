# APP-2176 processing migration

## Scope and finite case list

This pass migrates the processing family into the frozen Horizon 0a875da / MC
26.3 package. It preserves the Create 6.0.10 algorithms and the existing
Press timing seam. The legacy 9f42064 checks below are regression inputs; they
do not establish behavior in the new SDK package.

Required cases:

1. Millstone regression: wheat, clay, wool-tag, and bone recipes; zero/positive/
   negative speed; output saturation and recovery; idle and active save/reopen;
   guest input/output convergence.
2. Mechanical Press: ground item, horizontal belt, and Depot input; iron, gold,
   copper, and brass pressing; non-recipe item ahead of valid input; one output
   per cycle; zero-speed pause/interruption; full output recovery; idle and
   active save/reopen; guest collection.
3. Crushing Wheels: valid/invalid wheel arrangement, equal/opposing/reversed
   speeds, stop/resume, two-stage multi-output recipe, saturated output and
   recovery, idle and active save/reopen, host processing with guest collection.
4. Basin compacting/mixing: dry compacting; dry mixing; heated brass acceptance
   and cold rejection; ingredient and fluid conservation; multiple outputs and
   chance-bearing results; full-output backpressure/recovery; power interruption;
   idle/active save/reopen; guest insertion and collection.
5. Blaze Burner: ordinary fuel and blaze cake, invalid fuel, fuel threshold,
   overflow/expiry, lava-bucket remainder, soul flame transition, heat supplied
   to a recipe, idle/active save/reopen, guest fueling with host-authoritative
   consumption.

## Family inventory

| Family | Existing source and legacy evidence | Frozen-SDK package status |
| --- | --- | --- |
| Millstone | Typed adapter and pure timer module exist in `native/millstone_adapter.rs` and `native/millstone_processing.rs`. Legacy fixture covers recipe variants, backpressure, reopen and LAN. | Reuse the valid frozen-SDK wheat milling case: output persisted across reopen and full-output input conservation passed. Other listed variants and guest convergence remain open. |
| Mechanical Press | `native/press.rs` covers ground, belt, Depot and Basin endpoints. `native/press_processing.rs` is the shared cycle seam. Legacy traces and lifecycle check pass on 9f42064. | Current-main production package passes a powered Press cycle: an ingot is consumed, an Iron Sheet is produced, and the guest collects it. Fixture waits for game time after `/tick step` before freezing; Press scheduled output is forwarded through production Hooks. Guest inventory persists across clean server save/stop/reopen. Belt, Depot, Basin inputs, other metals, saturated output, and active Press save/reopen remain open. |
| Crushing Wheels | `native/crushing.rs` covers wheel processing and output handling. APP-1959 legacy trace/lifecycle evidence is recorded in `PARITY.md`. | Current-main production package passes opposing powered wheels crushing Gravel to Sand. A full controller inventory retains Gravel, then produces Sand once output space is cleared. Output inventories survive clean save/stop/reopen. Arrangement/speed variants, two-stage outputs, and guest collection remain open. |
| Basin compacting and mixing | `native/press.rs` and `native/mixer.rs` implement the legacy operations. APP-1961 traces/lifecycle evidence is recorded in `PARITY.md`. | Current-main production package passes dry Andesite Alloy mixing, nine Snow Blocks to Ice compacting, cold Brass rejection, and heated Brass mixing over Blaze Cake heat. Full Basin output retains all nine Snow Blocks until space is cleared; recipes resume and outputs survive clean save/stop/reopen. Fluid recipes, chance/multi-output variants, guest insertion/collection, and power interruption remain open. |
| Blaze Burner | `native/burner.rs` contains fuel, cake, expiry, heat and state handling; legacy lifecycle evidence is recorded in `PARITY.md`. | Current-main production package consumes Coal as ordinary fuel, accepts Blaze Cake, supplies heat for Brass mixing, rejects cold Brass mixing, and preserves active fuel through clean save/stop/reopen. Fuel boundaries, invalid fuel, bucket remainder, soul flame, expiry, and guest fueling remain open. |

The kinetic probe entry point names generated/staged sibling modules. The source
staging step copies selected production modules from `native/` into the package;
the package folder alone is not a standalone Cargo project before staging.

## Build and evidence record

Target cohort: Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, MC 26.3,
SDK `sdk-0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, Rust 1.99.1. Tests used the
managed headless developer route with the candidate's matching 26.3 resources,
isolated state, and freeze-after-readiness followed by explicit tick steps.
No account state or lease configuration was changed.

Processing candidate: `native-0a875da-090983026484`, staged by
`tools/prepare-processing-probe.py`, built by Horizon Launcher 0.2.107 against
the optimized `prebuilt-api` target. The receipt records Horizon
`0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, and Rust 1.99.1. Staged mod
SHA-256 is `610e581ca8c4a11fc1186d8b9b83c8e9b6eb6d8b92d1de8f75fd21b81994b7e0`;
dylib SHA-256 is `b03ea23f5862641e878e918f1b1a38d2050885bc8649064afa77add44fef2bc9`.

The current-main production package is `native-0a875da-8f6188d7b79b`, staged
from `migration/create` with `tools/prepare-create-native.py`. The fixture
used the supported localhost offline dedicated-server route with two distinct
offscreen clients. It did not change authentication or lease settings and did
not launch a visible client. The exact run record is
[`migration/APP-2176-production-proof.json`](migration/APP-2176-production-proof.json);
it records build/binary hashes, Press guest collection, representative
processing and backpressure, plus inventory/fuel after clean server stop and
reopen. Millstone's valid frozen-SDK evidence is reused rather than rerun.

This is a representative production integration pass, not exhaustive family
parity. Full 1:1 remains Open. The finite follow-ups listed above cover other
Press input routes and recovery cases, Crushing layout and multi-output cases,
Basin fluid/chance recipes and interruptions, and Burner fuel/state edges.
