# APP-2174 frozen SDK migration

## Source and baseline

This branch starts from `origin/main` at `48ae3d2d17385ab72eaefcd2b1160f230d4bbfe0`, which includes the reviewed APP-2136 typed kinetic slice. The assigned legacy entry points remain `native/hand_crank.rs`, `native/valve.rs`, `native/water_wheel_placed.rs`, `native/large_wheel.rs`, `native/steam.rs`, and `native/steam_whistle.rs`; their central behavior also runs through `native/machines.rs`.

The Java reference is Create `ac0c444d9828da3453ae8cc65338e8de063286fb` (Create 6.0.10, Minecraft 1.21.1, NeoForge 21.1.219). The target is Minecraft 26.3, Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, SDK/Rust 1.99.1, and mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`; use only an approved matching fork cohort when required. No APP-2174 build or runtime check has been run yet. The current checkout does not contain the pinned SDK, launcher, or matching runtime assets.

## Family classification

Historical `FEATURE-MATRIX.md` and `PARITY.md` results are useful source-derived regression inputs. They were produced on Horizon `9f42064` and do not demonstrate that these families work on the frozen SDK. The new typed adapter in `native/kinetic_adapter.rs` currently handles Creative Motor, shaft, cogwheel, large cogwheel, and Millstone only. `migration/kinetic-probe/src/power_sources.rs` now contains the extracted source-output rules for crank/handle direction, dyed-handle recolor drive, wheel flow sign/capacity, boiler efficiency, and Powered Shaft RPM/capacity. This pure production module is ready for the APP-2173 network adapter to consume; until the graph and registration paths call it, it does not establish runtime behavior.

| Assigned family | Existing behavior/evidence | Frozen SDK classification |
| --- | --- | --- |
| Hand Crank | Legacy click, stroke timer, reversal/source arbitration, coast, placement and LAN checks; Java motor matrix has 448 samples across 16 cases. | Open: no typed registration, crank input route, saved stroke transition, or new-cohort gameplay check. |
| Copper Valve Handle and dyed handles | Legacy placement, dyeing, signed angle/stroke, support loss and LAN checks. | Open: no typed handle state, interaction route, or new-cohort persistence/network check. |
| Small and Large Water Wheels | Legacy material/placement, axis/shaft preference, generation and save/reopen cases. | Open: no typed wheel registration, fluid/rotation integration, or new-cohort gameplay check. |
| Steam Engine, boiler and Powered Shaft | Legacy heat/water sampling, efficiency/output and Java boundary trace; pump interruption/restart and cold reopen are recorded. | Open: no typed boiler intake, engine/shaft production, or new-cohort resource/persistence check. |
| Steam Whistle and extension | Legacy attachment, growth, wrench propagation, redstone and muted audio checks. | Open: no typed whistle/extension registration, boiler activation, or new-cohort gameplay check. |

No assigned row is classified as adapted and verified or working unchanged on the frozen SDK.

The focused rules check covers inactive/active and reversed crank/handle output, recolor disconnect, small/large wheel sign/capacity, missing engines, tank-size and 10 mB supply boundaries, passive/active heat, zero-power shaft output, signed RPM, and capacity. It passes under the pinned Rust 1.99.1 compiler. These are algorithm checks only, not Horizon gameplay checks.

## Finite case matrix

Use the pinned Java sources and existing capture helpers where their observations cover the case. The required sample is deliberately bounded:

1. **Hand Crank:** survival placement and supported face; ordinary and sneaking click; ten-tick stroke expiration; forward/reverse output; compatible source join, slower opposing source rejection, and equal/faster opposing source break; crank-to-shaft/cogwheel consumer; idle and mid-stroke save/reopen; host/guest reversal if the approved runtime supports two clients.
2. **Valve Handles:** ordinary plus one dyed handle and verify the dye family registration; valid support and support removal; forward/reverse rotation; connect to an axial shaft consumer; idle and powered save/reopen; host/guest interaction if supported.
3. **Water Wheels:** small and large wheel, horizontal and vertical axle, one valid flow and one rejected/insufficient flow; survival placement/material use; drive a shaft/cogwheel consumer; removal and idle/active reopen; host/guest convergence if supported.
4. **Steam:** one passive-heat case and one active-heat case, zero/one engine, below/at the minimum water boundary, water intake and supply interruption/restart, actual Powered Shaft consumer output, and cold plus running reopen. Include pump-driven stop/restart as the bounded fluid-to-boiler path.
5. **Whistle:** tank-side and tank-top attachment, first extension growth and wrench size propagation, redstone on/off, and removal; verify it contributes to boiler activation without producing engine power by itself.

For each case record source revision, exact build/package/content hashes, dimension and chunk setup, tick origin and observed fields. Compare exact discrete state and item/fluid conservation. Distinguish guest convergence from packet-arrival timing. Cosmetic curve, pixel, audio backend and exhaustive layout comparisons remain open follow-ups.

## Adapter handoff and blockers

The source families need the complete network/transmission adapter owned by APP-2173: source registration and per-block output, topology rebuild after placement/removal, consumer propagation, opposing-source arbitration, stress/overload, reconnect and saved network state. The current APP-2136 slice is intentionally limited to the Creative Motor/shaft/cogwheel/Millstone graph, so claiming a power-source runtime case against it would be misleading.

APP-2172 owns the production package/registry integration and an approved offline two-client route. Its current issue description says the managed offline route is single-player-only and direct client launch cannot be used to bypass leases. Host/guest gameplay must remain unverified until APP-2172 provides a supported route. APP-2174 can provide small registration/source patches without taking ownership of those shared files.

The main checkout contains only the older `9f42064` build tools. The isolated APP-2174 worktree has no `.horizon` SDK package or pinned launcher/runtime assets, and the referenced APP-2136 temporary `.sdk` directory is not present. Therefore there is no valid frozen-cohort build receipt to attach to this assessment yet. Do not reuse historical binaries or another worker's selected build as APP-2174 evidence.
