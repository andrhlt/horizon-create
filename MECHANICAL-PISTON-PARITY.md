# Mechanical piston comparison

Reference: Create 6.0.10, commit `ac0c444d9828da3453ae8cc65338e8de063286fb`.
The Java captures are generated GameTests, separate from the original four-tick
`ploughing` fixture. The capture patches and metadata are in `tools/` and
`fixtures/` with the prefix `mechanical-piston` (the Java patches begin
`java-mechanical-piston`).

The comparison covers 24 sampled ticks for each of six scenarios: the three
movement modes with an extended Sticker and attached stone; the non-sticky
piston; an immovable bedrock obstruction; and a glued payload including the
extended Sticker, stone, mechanical plough and harvester. The replay compares
piston offset, speed and state, nearby block states, moving payload names, and
Sticker extension and power; the actor scenario also compares the cells above
the piston. Run the named checks with `tools/test-parity.py --check
'mechanical-piston-*'` after supplying the usual binary and resource paths.

On November 19, the selected suite passed 13/13 checks on
`native-9f42064-a5156e57df79`, including all six 24-tick Java comparisons,
the original ploughing fixture, LAN state checks for the Sticker and multi-actor
payload, a Horizon reload, offscreen rendering on host and guest, and the
host/guest mode control board. The earlier build exposed a missing screen
registration; its failed result is retained in
`.local/mechanical-piston/suite-before-ui-fix.log`.

The LAN checks compare the authoritative host on each server step to Java and
wait for guest block states to converge on each step. They do not establish
Java network packet timing or client interpolation parity. The reload check
compares a restarted Horizon world to an uninterrupted Java trace; it is not
a Java save/reload comparison. A separate hidden offscreen rendering check
exercises the moving Sticker head. The control board uses Java's option labels;
its interaction and visual details have not been exhaustively compared to Java.

Full piston parity remains open: these six traces do not cover every
orientation, pole length, payload, block interaction, speed transition,
collision, lifecycle, sound, or multiplayer presentation. The existing
gearbox piston fixture uses vanilla pistons and is not evidence of mechanical
piston behavior.

## APP-1982 finite gameplay pass, November 20, 2026

The existing captures and November 19 results above remain valid. This pass
uses the finite gates in `COMPLETION-STANDARD.md`; it does not require every
orientation/length/payload cross-product before delivery.

| Required bounded case | Evidence and current result |
| --- | --- |
| Facing classes and pole lengths | `test-mechanical-piston-boundaries.py` runs six one-pole sticky rigs and one east-facing four-pole rig. It checks endpoints, payload retention, direction changes and source-derived motion boundaries. These are Horizon gameplay assertions, not newly captured per-facing Java traces. The existing Gearbox direction reference separately supplies 48 exact west/up samples; see `GEARBOX-PARITY.md`. |
| Sticky versus normal return | Preserve the six original 24-tick traces, including normal-piston return and all three movement modes. The additional Gearbox references supply 120 samples for direct push-only blocks versus pullable stone; their already integrated `PushReaction::Push` handling is preserved. |
| Representative payload | Preserve the extended Sticker/stone and glued plough/harvester captures, including their host/guest checks. A separate container-payload cross-product is not required for this pass. |
| Zero, reversal and speed change | Existing captures reverse at signed 64 RPM. The boundary runner additionally stops an assembled mode-2 payload, resumes return at 128 RPM, and uses 4 RPM for the active reopen case. Its tolerances and assertions are source-derived gameplay checks; exact Java stop/reversal interpolation and all fractional offsets remain unverified. |
| Obstruction | Existing bedrock trace covers rejected extension. A newly captured Java test proves retraction away from an immovable pull target; the pre-fix Horizon build fails this case. See below. |
| Idle and moving reopen | The boundary runner saves/reopens both retracted, stopped mode-0 rigs and genuinely moving mode-2 rigs, checking settings, cargo and subsequent operation. Server startup advances before `fixture_world` can freeze it, so active offsets may advance. This is a Horizon lifecycle check, not exact Java reload timing. |
| LAN and regression | Reuse the prior representative host/guest mode and payload actions. After rebuilding the fix, rerun `mechanical-piston-*`, `ploughing`, and `gearbox-mechanical-piston*` on the identified candidate. Old-build results do not verify the new native fix. |

### Immovable pull-target regression

Pinned source review covered `MechanicalPistonBlockEntity.getMovementSpeed`,
`LinearActuatorBlockEntity.tick/onSpeedChanged/tryDisassemble`,
`PistonContraption.collectExtensions/addToInitialFrontier`, and the piston/pole
placement paths. Java deliberately stops collecting the retraction frontier
when the first block is immovable; it still retracts the piston apparatus.
Horizon instead propagated `saved_block(...)?` failure, preventing the entire
assembly. The narrow fix skips that pull target during retraction while
retaining rejection during extension.

The new [Java patch](tools/java-mechanical-piston-immovable-retraction.patch)
first extends a one-pole sticky piston, then places bedrock directly on its
head and reverses at sample 10. Java assembles retraction at sample 11 and is
fully retracted at sample 19; bedrock remains in place. Its GameTest asserts
the initial extension and final retraction, so a stationary setup cannot pass.
The [24 samples](fixtures/mechanical-piston-immovable-retraction-java.jsonl)
compare offset, signed RPM, piston state and five line cells with zero tolerance.
[Metadata](fixtures/mechanical-piston-immovable-retraction-java.metadata.json)
records the source revision, patch/trace hashes, tick origin and runtime pins.

The disposable pinned Java checkout used JDK 21.0.13.1 and an isolated
clonefile copy of the populated Gradle cache. The first offline build and
capture passed in Gradle's reported 5m45s, including dependency preparation.
The reusable capture command is:

```sh
python3 tools/capture-mechanical-piston-immovable-retraction-java.py \
  --java-source /path/to/pinned/Create \
  --gradle-home /path/to/worker-private/populated-gradle-home \
  --java-home /opt/homebrew/opt/openjdk@21
```

The exact headless replay on existing build `native-9f42064-a5156e57df79`,
using pack SHA-256
`e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`,
failed 13 of 24 samples beginning at sample 11. That build retains its head
and never retracts. Before-fix receipts are preserved in the worker's
`.local/mechanical-piston/immovable-retraction-exact-before.json` and
`immovable-retraction-exact-before.log`; the bootstrap Java log is
`java-immovable-retraction.log`. The earlier direct extended-rig reproduction
is retained as `immovable-retraction-before.json`.

Both new checks are registered as `mechanical-piston-boundaries` and
`mechanical-piston-immovable-retraction`. Run them through `tools/test-parity.py`
with the candidate's `horizon-ctl`, `horizon-client` and prepared 26.3 resources.
The worker used the existing build's resources at
`<build>/.local/horizon-client/26.3`, with isolated temporary worlds and
worktree-local outputs. It did not rebuild or mutate shared compilation caches.

The strengthened boundary run passed all seven rigs and 63 observations across
nine phases on the same existing build and pack. It observed the four-pole
payload still moving after reopen: offset 3.6171875 before save, 3.390625 when
refrozen, and 3.3828125 after one further server tick at 4 RPM. All seven rigs
retained their settings and captured stone. All returned their stone before
the idle reopen. Results are in `boundaries-horizon.json` and
`boundaries-active-baseline.log` under the worker's `.local/mechanical-piston/`.
The first out-of-loaded-area layout was invalid (`boundaries-baseline.log`).
The initial strict paused-offset reload assertion was also invalid because
startup advances the world (`boundaries-grid-baseline.log` and
`boundaries-grid-exact-offset-invalid.json`). A successful intermediate run
completed its return before refreeze (`boundaries-completed-during-reopen.json`);
the final slower setup removes that ambiguity. These records are preserved.

The fast production-mode replay (`python3 tools/test-mechanical-piston-core.py`)
passed 24 endpoint decisions across all three modes. Integrity checks passed
for all six existing piston/Gearbox reference files: pinned revision, patch
hashes, record counts, contiguous 0–23 tick windows and available trace hashes
(336 stored samples, including the legacy 24-sample Sticker capture; the latter
is not an additional independent scenario).

Candidate build `native-9f42064-7dd44073fdc4` was built from this worktree with
an isolated launcher cache and the pinned Horizon revision. Its focused command
passed 18/18 checks:

```sh
python3 tools/test-parity.py <candidate>/horizon-ctl <candidate>/horizon-client \
  <candidate>/.local/horizon-client/26.3 --jobs 2 \
  --check 'mechanical-piston-*' --check ploughing \
  --check 'gearbox-mechanical-piston*'
```

This includes the new immovable-target replay and boundary runner, all prior
mechanical-piston checks, original ploughing, and gearbox piston regressions.
The native fix is verified for this bounded baseline. Measured work time was
5m45s for the Java capture, 17m20s for the isolated native build, under one
second for the fast core replay, and about 11 minutes for the 18-check focused
integration suite. Source review, implementation and recovery were not timed
separately. Full 1:1 remains Open. Broader collisions,
pole limit/custom-config combinations, all payload and fractional-transition
cross-products, Java save/reload, network arrival timing, exact visuals and
sound remain explicitly unverified.
