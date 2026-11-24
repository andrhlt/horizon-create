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
| Millstone | Typed adapter and pure timer module exist in `native/millstone_adapter.rs` and `native/millstone_processing.rs`. Legacy fixture covers recipe variants, backpressure, reopen and LAN. | Frozen-SDK production wheat milling passed with output persistence across reopen and full-output input conservation. Other listed Millstone variants and guest convergence remain open. |
| Mechanical Press | `native/press.rs` covers ground, belt, Depot and Basin endpoints. `native/press_processing.rs` is the shared cycle seam. Legacy traces and lifecycle check pass on 9f42064. | `native/press_adapter.rs` adds a typed ground-item endpoint and scheduled output spawn. The managed fixture passes with the readiness/freeze/tick ordering corrected: ground iron produced one Iron Sheet, consumed the ingot, and retained output across save/reopen. Belt, Depot, Basin, remaining metals, saturated-output recovery and LAN remain open. |
| Crushing Wheels | `native/crushing.rs` covers wheel processing and output handling. APP-1959 legacy trace/lifecycle evidence is recorded in `PARITY.md`. | `native/crushing_adapter.rs` registers a 16-slot typed controller endpoint, recipe lookup, timed processing, chance outputs and output backpressure. It compiles against the pinned SDK; no runtime recipe, arrangement, save/reopen or guest case has passed. Kinetic network integration remains open. |
| Basin compacting and mixing | `native/press.rs` and `native/mixer.rs` implement press compacting and mixing. APP-1961 traces/lifecycle evidence is recorded in `PARITY.md`. | No typed Basin/Mixer endpoint is registered; `native/basin_adapter.rs` is still a stub. |
| Blaze Burner | `native/burner.rs` contains fuel, cake, expiry, heat and state handling; legacy lifecycle evidence is recorded in `PARITY.md`. | No typed Burner endpoint is registered; `native/burner_adapter.rs` is still a stub. |

The kinetic probe entry point names generated/staged sibling modules. The source
staging step copies selected production modules from `native/` into the package;
the package folder alone is not a standalone Cargo project before staging.

## Build and evidence record

Target cohort: Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, MC 26.3,
SDK `sdk-0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, Rust 1.99.1. A migration pass
must also record its native-build receipt, package/dylib/content identities,
world/chunk setup, command, outcomes, and elapsed time here before claiming a
case passed.

Build: earlier Millstone candidate `native-0a875da-a73a5c37eb40`, generated from
`tools/prepare-processing-probe.py` and built by Horizon Launcher 0.2.107 with
the managed, unsigned developer base. Receipt `native-mods.json` records
Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, Rust 1.99.1, optimized
`prebuilt-api` target. Staged mod SHA-256 is
`9e3e3f1cb7ad95e2ea9fa7c6182410e67483adc38d89f02df85df09e7584e033`; dylib
SHA-256 is `fba78cfb124985751959058ae0b05e6035807c3ba52929b1871634da5bbf4fb1`.

The production Create content pack used for the passing Millstone fixture has
SHA-256 `9834792c2138959844d92f0442984ae41158286f1c11d6e90548c13303665dfd`.
The isolated fixture ran offline in a single-player managed instance for the
previously recorded Millstone wheat case and the Press ground-iron case. For
Press, use the candidate's own
`.local/horizon-client/26.3` resources; an older resource bundle failed during
startup because `fluid_state_definitions` was missing. The successful fixture
log is in `.local/sdk-check/evidence/press/managed-play.log` and the game log
is `.local/sdk-check/evidence/press/latest.log`. Current reconciled processing probe
candidate `native-0a875da-1375e30dd760` builds with Press and Crushing modules;
its mod SHA-256 is `a74f6c74a705d501754376d31e91b912437ce0c1b3dfa3a64ad3f1487eaaf277`,
and dylib SHA-256 is `b5102eb96771a6d7f37d43ae164e86156dc2f9307ed375c0673f149e44aca566`.
The fixture's sequencing issue is corrected. Developer offline mode is
single-player only; no guest/LAN cases were run. Basin/Mixer and Burner remain
unimplemented.

This remains an incomplete migration. It does not meet the ticket's family
coverage, integration, persistence or multiplayer gate and must not be marked
Done or closed.
