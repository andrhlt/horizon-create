# Water Wheel gameplay baseline (APP-1957)

This bounded pass preserves the existing flow, material, stress and award references. Full 1:1 remains Open. The ticket gates follow [COMPLETION-STANDARD.md](COMPLETION-STANDARD.md).

## Bounded cases and reference

Pinned Java: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`, 6.0.10, Minecraft 1.21.1 / NeoForge 21.1.219. The source was inspected read-only.

| Cases | Reference / assertion | Check |
| --- | --- | --- |
| Survival crafting small then large wheel | `crafting/kinetics/water_wheel.json` and `large_water_wheel.json`: eight planks around shaft / small wheel; one output; exact ingredient consumption | `waterwheel-gameplay-crafting` |
| Small X and horizontal Y placement, shaft preference and sneak override | `DirectionalKineticBlock.getStateForPlacement`; test verifies the observed axis against the Java placement rule | `waterwheel-gameplay-axes` |
| Aligned small pair and rejected side-by-side pair; occupied large rim | `WaterWheelBlock.canSurvive`, `LargeWaterWheelBlock.getStateForPlacement` and block item: reject without consumption | `waterwheel-gameplay-placement` |
| Both sizes: survival placement, idle oak and active birch plank use | `WaterWheelBlockEntity.applyMaterialIfValid`: change material without shrinking the held stack; inherited by large wheel | `small/large-waterwheel-gameplay-reopen` |
| Both sizes: idle and active reopen | `read`/`write` persist Material and FlowScore; source-aligned flow, generated RPM, axial shaft state/RPM and inventory compare before/after restart, with 65 stepped ticks for lazy resampling | same |
| Both sizes: guest placement, host oak then guest birch use, active shaft | Authoritative material/RPM, survival plank stacks retained; guest local wheel and shaft states converge | `small/large-waterwheel-gameplay-lan` |
| Start, cancellation from opposing streams, stop/recovery, RPM and capacity | Original small and large water-wheel Java traces and structures, retained unchanged | existing `small-waterwheel`, `large-waterwheel` |
| At/beyond capacity and overload recovery | Existing loaded-stressometer Java trace and boundary cases, retained unchanged | `loaded-stressometer` |
| Ordered 11 plank species/deployer use; ownership/awards | Original material and award references, retained unchanged | `waterwheel-materials`, `*-waterwheel-award*` |

The reopen checks use Java source invariants, not a new Java reload capture. Generated speed is `clamp(flowScore, -1, 1) * 8 / size`. Each size has two world restarts. Reopen checks step 193/208 world ticks; LAN checks step 57/72 ticks, besides asynchronous replication waits. These counts do not imply exact Java timing parity.

## Final build and results

- Horizon pin: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` (Minecraft 26.3).
- Final native build: `native-9f42064-78cd07b754c9`, built with the documented compatible launcher and isolated worktree cache.
- Create pack SHA-256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
- Prepared 26.3 resource manifest SHA-256: `42d0494870e78ed6d74aa79162a60279aaccdedf82bdfc3f3b5f0851ed167a09`.
- Scoped gameplay gates: **7/7 pass**.
- Affected regressions: **19/19 pass**.
- `python3 tools/check-source.py`, `python3 -m py_compile tools/test-waterwheel-gameplay.py tools/test-waterwheel-advancement.py tools/test-parity.py` and `git diff --check` pass.

The placement harness makes real offscreen mouse clicks. Before each click it checks the ray hit block position and face, measured eye-to-hit distance, held item, sneak state, and synchronized yaw/pitch. Representative inputs include support `(12, 105, -11)`, south face, 3.67 blocks, held small wheel, no sneak; X support `(13, 110, -10)`, west face, 3.68 blocks; Y support `(12, 109, -10)`, up face, 3.96 blocks; and sneak support `(12, 110, -11)`, south face, 3.58 blocks, sneak true. The support selected by the wheel-pair case is the first wheel itself (south face, 2.74 blocks). The client is allowed to process each click before reading resulting state. The advancement fixture removes its adjacent stressometer before testing the intended no-neighbor placement direction; it had previously been influencing shaft preference.

The seven scoped runner checks are `waterwheel-gameplay-placement`, `waterwheel-gameplay-axes`, `waterwheel-gameplay-crafting`, `small-waterwheel-gameplay-reopen`, `large-waterwheel-gameplay-reopen`, `small-waterwheel-gameplay-lan`, and `large-waterwheel-gameplay-lan`. The 19 regression checks cover small/large flow and visual cases, awards and ownership, host/guest awards, reopen, magma-wheel awards, material use and loaded stressometer. Outputs are preserved under `.local/parity/`; reopen snapshots are `.local/waterwheel-gameplay-{small,large}-reopen.json`.

The LAN checks establish representative host/guest actions, inventory convergence, authoritative material/generation, and guest block-state convergence. They do not establish exact guest block-entity rendering, animation, packet arrival or interpolation parity. Exact Java save/reload comparison is also unverified. Broader fluid layouts, all material/orientation cross-products, long-run cases and cosmetic sound/animation remain follow-ups; Full 1:1 stays Open.

## Commands

```sh
python3 -m py_compile tools/test-waterwheel-gameplay.py tools/test-waterwheel-advancement.py tools/test-parity.py
python3 tools/check-source.py
git diff --check
python3 tools/test-parity.py CTL CLIENT RESOURCES --jobs 2 --check '*waterwheel-gameplay*'
python3 tools/test-parity.py CTL CLIENT RESOURCES --jobs 2 --check 'small-waterwheel*' --check 'large-waterwheel*' --check '*magma-wheel-award*' --check 'waterwheel-materials' --check 'loaded-stressometer'
```
