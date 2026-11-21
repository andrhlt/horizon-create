# Sticker implementation and verification

This tracks the complete base-Create Sticker source checklist separately from
claims of exhaustive parity. Reference: Java Create 6.0.10 commit
`ac0c444d9828da3453ae8cc65338e8de063286fb`; Horizon `9f42064` / Minecraft 26.3.
The pass translates the audited Sticker methods and key inherited behavior. Verification remains
bounded by the cases below; the family is not marked fully 1:1 verified.

## Checklist

| Java behavior | Implemented | Verification | Remaining evidence |
| --- | --- | --- | --- |
| Default state and physical properties | Yes | Original Java runtime default and physical-property recording; real native default/property probe | More contextual collision cases |
| Placement facing, sneaking and initial power | Yes | Existing real powered survival placement and pulse regression; six-direction block-world comparisons | More real placement/sneak angles |
| Rising-edge toggle; held/falling power | Yes |36 Java world records; host/guest pulses | Broader redstone circuit interactions |
| No weak-power conduction through Sticker | Yes |6 Java decisions plus6 real directional isolation rigs | Other powered-neighbor combinations |
| Piston tick/update ordering and interpolation | Yes |192 tick records and960 frame offsets bit-exact against actual Java StickerBE/LerpedFloat | Java network delivery timing |
| Bounce living/nonliving, suppression and signed zero | Yes, shared callback core and existing legacy engine bindings |384 combined bounce/step callback cases; existing20 pig trajectory ticks | Wider whole player/item/other-entity trajectories |
| Slow-horizontal-motion drag | Yes, player/mob/item paths |384 combined callback cases;15 actual pig movement ticks with stone/sideways controls | Other entities and player/item trajectories |
| Fall damage, including redundant super-call path | Yes |120 original Java health/alive/callback-count comparisons | Whole-fall trajectories and other damage modifiers |
| Support-face checks and original brittle/movable tags | Yes |480 decisions over 80 original states and6 directions | Wider connected tank/vault/bogey layouts and cross-block combinations |
| Extended neighbor capture | Yes |18 original collector/assembly comparisons | Actual player-operated moving assemblies |
| Wrench rotation and pickup | Yes |36 original rotations, actual held-wrench rotation and survival sneak pickup | Additional survival interactions |
| Inherited structure rotation/mirroring | Existing shared engine path | Not separately verified in this pass | Original Java structure-transform comparisons |
| Original head/base models and textures | Yes |6 assets byte-identical to Java;12 facing/endpoint vertex-bound checks in actual offscreen rendering | Java GPU pixel comparison, lighting/UV equivalence and identity-based nudge |
| Scene/fake-world endpoint rendering | Yes | Source-reviewed supplied-state/live-instance handling | Live moving-contraption visual comparison |
| Attach/detach events and sound parameters | Yes | Java event bits and actual client attachment/detachment events; original sound-event alias | Java sound waveform/timing comparison |
| Forty attachment slime fragments | Yes | Source reviewed against actual Ponder rotation bytecode | Seeded Java particle output comparison |
| Upright landing/running slime particles | Yes | Source reviewed, including world nextFloat RNG, original position and motion formulas | Exact particle production/RNG-phase comparison |
| Runtime state excluded from saved NBT | Yes | Actual dedicated save/reopen and region inspection | Broader clone/move lifecycle |
| Empty/unchanged client updates | Yes | Two real unchanged-target updates observed by each of two headless clients | Controlled Java client packet-delivery comparison |
| Late join, chunk unload/reload, reconnect, restart | Yes | Dedicated server and two headless clients, recorded lifecycle cases | Java network tick-for-tick comparison |
| Survival crafting recipe | Yes | Original Java recipe read directly; actual crafting output and ingredient consumption | More tag ingredient substitutions |
| Optional ComputerCraft peripheral | No | Outside base-Create runtime in this port | Separate dependency/integration work |

## Evidence and execution

- [Original client animation oracle](tools/java-sticker-source.patch) factors
  the original client routine for dedicated-server execution using the actual
  Java dependency. It is not a Java GPU client.
- [Remaining behavior oracle](tools/java-sticker-remaining.patch) invokes actual
  Java block callbacks and support APIs. Its trajectory pigs have AI enabled
  with goals removed; all rigs stay inside one ticking chunk. Face probes have
  a supporting floor and assert the requested block survived placement.
- [Interaction oracle](tools/java-sticker-interactions.patch) invokes the original
  wrench-state and weak-power methods.
- [Fast callback comparison](tools/test-sticker-callback-core.py) compiles the
  exact production engine callback source, checked against the canonical patch,
  with standalone rustc. It compares384 physics cases bit-for-bit and120
  fall-call counts without launching or rebuilding Horizon; the measured final
  run took0.779seconds, including compilation.
- [Native batch](tools/test-sticker-remaining.py) compares999 Java records:
 384 callbacks,120 fall-health/count results,480 faces and15 actual movement
  ticks. Expected outputs are not sent to the native probe. Movement uses an
  explicit 1e-7 tolerance; callback vectors use exact double bits, including-0.
  The fixture adapter explicitly maps Java `minecraft:chain` to26.3
  `minecraft:iron_chain` while retaining its properties.
- [Interactions](tools/test-sticker-interactions.py),
  [presentation](tools/test-sticker-presentation.py),
  [crafting](tools/test-sticker-crafting.py), and
  [multiplayer lifecycle](tools/test-sticker-lifecycle.py) exercise the real
  engine/client paths. Geometry uses a source-derived transform comparison
  with 1e-4 block tolerance, not a Java rendered-image comparison. All rendering
  is offscreen; all other clients/server run headless and audio output is off.

The callback control bridge is opt-in through `CREATE_STICKER_TEST`. The fall
component comparisons use fresh clones of a real pig and the same callback
count helper/damage method as production; they are not 120 complete physical
falls. The actual movement tests separately exercise production collision,
restitution, drag, gravity and friction.

The content pack corrects the default facing to the measured Java north value
and adds the original `brittle`, `movable_empty_collider` and `corals` tags; the pack-diff receipt records every changed entry. The current
build was preserved before editing, including its binary, resources, source
snapshot and pack, under
`.local/baselines/2026-11-19-sticker-abde3add95e2/`.
Normal Create Parity Lab has not been replaced.

## Timed completion pass

Start: **2026-11-19 15:41:07 UTC /10:41:07 EST**, including audit and preservation.
One implementation worker and one independent Java/lifecycle/review worker.
The first native999-record comparison and12 geometry checks were observed
passing by16:09:54 UTC. Final verification timing, build attempts, candidate
and pack hashes are in `.local/sticker-completion/timing.json`.
Final candidate: `native-9f42064-b2405826c686`, pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
All seven registered Sticker checks passed through the normal parity runner,
plus all 18 cases of the separate two-client lifecycle run on that exact
candidate/pack. Total recorded Java observations: **1,288** across the246,
999,42 and1-record oracles; the960 frame values are included in the animation
records and are not another 960 scenarios.

Finished: **2026-11-19T16:19:25Z**, total **38m18s**, including source review, fixtures,
failed builds, final verification and documentation.

## APP-2011 gameplay baseline

The Mechanical Piston prerequisite is integrated by APP-1982 (PR #68). On its
identified build, `native-9f42064-7dd44073fdc4`, the APP-2011 worktree reran all
8 registered `sticker*` checks against the pinned Create pack
(`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`):
the 7/8 initial batch exposed a shared Wrench test-helper coordinate bug, then
the corrected survival crafting check passed independently. The other seven
checks, including all 18 host/guest lifecycle cases, passed in the initial
batch. The fix makes the helper validate the block under its supplied aim point.

Integrated payload checks on that same build passed `mechanical-piston-actors-lan`
and `mechanical-piston-reload`. The LAN guest retained the extended Sticker in
the moving multi-actor payload and converged on its state for all 24 Java
reference ticks. The moving save/reopen case retained the payload and extension
state and matched the uninterrupted Java trace at the sampled ticks. This is a
Horizon persistence check; it does not claim Java reload or packet-arrival timing
parity.

Commands (run from the APP-2011 worktree):

```sh
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 --jobs 2 --check 'sticker*'
python3 tools/test-parity.py /path/to/horizon-ctl /path/to/horizon-client /path/to/26.3 --jobs 1 --check mechanical-piston-actors-lan --check mechanical-piston-reload
python3 tools/test-sticker-callback-core.py
```

The Sticker implementation files and pack match the cited candidate; the
APP-2011 code change adjusts the shared Wrench test helper and evidence. The
candidate predates later `origin/main` changes for mounted-drill handling in
Mechanical Pistons (APP-1971) and Mechanical Saw actors on Bearings (APP-1981).
The recorded piston fixture contains no drill or saw actor, but a current-tip
combined build has not been verified. A private
`sh tools/build-native.sh /path/to/horizon-launcher /path/to/private-launcher-data`
attempt stopped before compilation: the copied Horizon source already contained
applied patches and rejected reapplication of `horizon-advancement-initial-inventory.patch`.
Resolve the local source-cache state and rerun the focused checks before closing
the ticket.

Full 1:1 remains Open: current-tip combined-build verification, inherited
structure transforms, wider connected-face/player-item combinations, exact
Java packet timing, pixels, sound and seeded particle equivalence, and the
optional ComputerCraft peripheral remain open.

Six native build attempts were made: two failed compilation and four
succeeded (108,102,100 and100 seconds). The total timer includes those failures,
fixture fixes, independent review, Java captures, native integration and
initial documentation. Successful final Java captures took about21–32seconds per batch;
these are separate from the0.779second cached Rust callback replay.

Repeat the registered integration checks with:

```sh
python3 tools/test-parity.py /absolute/path/horizon-ctl /absolute/path/horizon-client /absolute/path/26.3 --jobs 3 --check 'sticker*'
python3 tools/test-sticker-callback-core.py
```

The primary suite receipt is `.local/sticker-completion/suite-final.log`;
per-check logs live under `.local/parity/sticker*.log`. Final lifecycle traces,
pack hashes and saved-region inspection are under
`.local/sticker-completion/lifecycle/`.
The native movement fixtures keep AI enabled and set movement speed to zero
to remove movement intent while retaining physics; Java removes the pig's
goals instead. The comparison isolates the same initial physical motion.


This trial compares a larger scope and uses two workers; it is not a controlled
speedup measurement against the earlier 42m43s animation/attachment experiment.
