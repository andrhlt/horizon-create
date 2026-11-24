# APP-2175: gauges and Turntable SDK migration

## Current disposition

This branch adds source-derived, host-independent gauge and Turntable math for
the frozen SDK adapter. It is a partial implementation; it does not yet make
these blocks work in the typed production package.

| Family row | Classification | Evidence and remaining work |
| --- | --- | --- |
| Speedometer and Stressometer | Adapted logic; SDK integration open | `native/gauge_logic.rs` carries Java's speed bands, stress bands, strict overload comparison, speed-to-dial scale, and 1/8 needle easing. `tools/test-gauge-turntable-logic.py` checks boundaries. Typed block-entity registration, saved/synchronized network readings, model submission, normal Goggles readout, overload observation, and idle/active reopen are not verified on the frozen SDK. |
| Turntable | Adapted math; SDK integration open | `native/turntable_motion.rs` carries Java's player camera falloff and edge-vector motion. The edge rotation uses standard `sin_cos`; Java's float sine-table approximation is not reproduced yet and needs comparison against the existing trace. Existing old-runtime Turntable traces remain useful regression inputs, but do not verify this SDK route. Typed kinetic graph registration, rotating model submission, player/mob contact, guest behavior, and idle/active reopen remain open. |

No row is classified as SDK gameplay verified. The historical matrix's “Pass”
entries refer to the earlier `native-9f42064` runtime and must not be read as
proof of this migration.

## Bounded acceptance cases

1. Gauge readings: idle; positive and negative RPM; 1, 30, and 100 RPM
   display boundaries; stress at 50%, 75%, exactly 100%, and above capacity;
   save/reopen idle and active readings.
2. Turntable: idle, positive drive, reversal, stop/removal, and loaded stress;
   player at center and edge; pig contact and removal; meaningful active
   save/reopen; host/guest convergence where the supported offline route allows.
3. Reuse the existing original Java traces and compare every sampled field.
   Re-run the affected fixtures on a single identified frozen-SDK build after
   typed package registration is available.

## Dependencies

The current `migration/kinetic-probe` registers only the Creative Motor,
shaft, cogwheels, and Millstone. It does not register either gauge or the
Turntable. The shared graph adapter also has no gauge or Turntable node yet.
APP-2173 owns network/transmission rules and APP-2172 owns production root and
registry integration. This branch leaves those shared roots untouched. Their
registration must attach these blocks to the completed adapter; the product
Goggles/render contracts must then consume the saved readings and visual state.

The typed runtime does not yet expose a verified Turntable player-camera hook
in the staged probe. Do not approximate the original camera contact by
teleporting a standing player. The existing `native/turntable_player_math.rs`
remains the source reference for the eventual supported contact callback.

## Commands and result

Run the source-only check with:

```sh
python3 tools/test-gauge-turntable-logic.py
```

This check exercises production math only. It does not prove block registration,
server authority, rendering, multiplayer, save/reopen, or compatibility with a
particular SDK/runtime artifact. Those gates remain pending the shared adapter
and package integration.

On 2026-11-23, `python3 tools/test-gauge-turntable-logic.py` passed 5/5 checks
with local `rustc 1.100.0 (0ef1bc386 2026-11-09)`. This is not the required
Rust/SDK 1.99.1 cohort. The worktree has no `.horizon/sdk` source tree or
matching Horizon runtime inputs, so no native build receipt or SDK gameplay
run was produced.
