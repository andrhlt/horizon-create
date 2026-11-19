# Timed source-first Sticker experiment

A subsequent [completion pass](STICKER-PARITY.md) expands this bounded trial
with physics, support tags, interactions, presentation and lifecycle checks.

This is a bounded second trial after fluid tanks: translate the upstream
subsystem before batch verification. Sticker remains **Partial**, with the
limits below. The existing build and normal Create Parity Lab were preserved.

## Reference and implementation

Java reference: Create 6.0.10, commit
`ac0c444d9828da3453ae8cc65338e8de063286fb`, Minecraft 1.21.1,
NeoForge 21.1.219, actual cached Ponder 1.0.82 dependency.
Horizon reference: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`.
The content pack was unchanged, SHA-256
`036218cf690405199aa24e67e63433bc138cfd3272742d435f7ec602992ccc85`.

Read StickerBlock, StickerBlockEntity, StickerRenderer, StickerVisual,
Contraption's Sticker traversal, BlockMovementChecksImpl, SuperGlueEntity's
face check and SuperGlueItem's attachment particles before translating.
The optional ComputerCraft peripheral was outside this experiment.

| Upstream behavior | Horizon implementation | Evidence |
| --- | --- | --- |
| Tick chaser before applying received target; float storage and double interpolation | [Shared production animation core](native/sticker_animation.rs) | 192 Java animation records; 960 partial-frame offset values match by float bits |
| Rising-edge toggle, held/falling power and attachment in six directions | [World adapter](native/sticker.rs) | 36 original Java block-world records |
| Extended Sticker adds its facing neighbor unless unsupported | [Collector](native/sticker.rs), called by [common bearing traversal](native/bearing.rs) | 18 direct original bearing collector/assembly comparisons, including a nonsupportive drill face; not a player-operated moving-bearing test |
| Original partial head model, quadratic 0–0.25 block displacement | [Renderer](native/sticker.rs) and [visual registration](native/visuals.rs) | Actual offscreen Horizon rendering: 40 head vertices, intermediate extension/retraction offsets |
| Client initialization and transient piston state | Native block-entity factory and unsaved runtime state | Real client tick traces, checked against transitions present in the Java oracle |
| Attachment/detachment feedback | Source-derived local sound dispatch and forty slime fragments | Exact logical event bits compared; client events observed; audio/pixel/particle equality not established |
| Existing placement and restitution | Existing code retained | Powered survival placement, two rising/falling pulses and four five-tick pig trajectories pass |

[The Java patch](tools/java-sticker-source.patch) factors the original client
algorithm into a method called both by the original tick and a dedicated-server
GameTest. It uses the real StickerBlockEntity and LerpedFloat. The probe covers
initial extended/retracted states, an unchanged initial notification, interrupted
movement and repeated target notifications, with attached and unattached cases.
This avoids launching a Java GUI, but is **not** an unmodified Java client,
network synchronization, sound waveform or pixel comparison.

The pure replay includes the same Rust file used in the game. It contains no
second fitted animation implementation. The real-world checks call production
redstone/attachment and collector paths; their control bridge is opt-in through
`CREATE_STICKER_TEST`. No visible window was used. The offscreen client uses
hidden rendering and disables audio output.

## Reproduce

```sh
python3 tools/capture-sticker-java.py
python3 tools/test-sticker-source.py /absolute/path/horizon-ctl /absolute/path/horizon-client /absolute/path/26.3
python3 tools/test-sticker.py /absolute/path/horizon-ctl /absolute/path/horizon-client /absolute/path/26.3
python3 tools/test-sticker-bounce.py /absolute/path/horizon-ctl /absolute/path/horizon-client /absolute/path/26.3
```

The main suite registers this batch as `sticker-source`. The capture runs in a
disposable checkout and leaves the pinned Java reference untouched.
[Recorded Java data](fixtures/sticker-source-java.jsonl) and its
[revision/patch receipt](fixtures/sticker-source-java.metadata.json) are checked
in the comparison. Local logs and timing are under `.local/sticker-benchmark/`.

## Measured timing

Timing starts at **2026-11-19 13:40:10 UTC / 08:40:10 EST**, including system
selection. The observed first source-write boundary was 13:49:25 UTC: 9m15s
for selection, source audit and first-draft preparation. The first core
comparison had passed before the second build started at 13:53:55 UTC:
**within 13m45s of starting**, including the first Java capture.

Final verification was observed complete at **14:22:53 UTC / 09:22:53 EST**:
**42m43s from selection through final verification**. The final candidate is
`native-9f42064-abde3add95e2`. All three repeatable test commands above passed
on that candidate. Four successful native builds took 109, 96, 93 and 87
seconds; two additional attempts failed compilation. The total includes all
six build attempts, fixture development and debugging, Java captures,
integration checks and initial evidence documentation. Final report cleanup
follows that boundary.

The Java capture itself took 20.9 seconds. The final batch compared all 246
Java records, including the unchanged initial notification, and all 960 frame
values. The final offscreen receipt is in
`.local/sticker-benchmark/client-summary.json`; detailed pass logs are
`test-sticker-source-final.log`, `test-sticker-final.log` and
`test-sticker-bounce-final.log` in the same directory. The timing receipt is
`.local/sticker-benchmark/timing.json`.

These are wall-clock observations, not a controlled benchmark against tanks
or a projection for all of Create. This trial did not demonstrate an order of
magnitude reduction in total time. It demonstrated a short exact core loop
and the remaining cost of adapters and trustworthy integration evidence.

## Remaining boundaries

Full Sticker parity is not claimed. Remaining work includes wider support-face
classification and cross-block combinations, all-facing visual transforms and
model nudge, live mounted contraption behavior, lifecycle/duplicate network
packet semantics and host/guest timing, horizontal drag, player/nonliving bounce
and fall-damage cases, landing/running particles, recipe use, and audiovisual
comparison. The new particle geometry and sound parameters were translated from
source; they have not been compared with Java client output.

## What this trial says about speed

Source translation got the small animation core matching in the first batch.
The larger cost was making the game actually use it: a missing Sticker native
block entity, Rust adapter compile errors, the control bridge's Send boundary,
and an offscreen fixture whose player fell off its viewing platform. An
additional transition assertion exposed an oracle coverage gap for an unchanged
initial update, which was then captured from Java. These costs are part of
shipping a working port. The next trial should reuse this batch and client
harness, keep the subsystem boundary explicit, and measure total integration
time as well as core implementation time.
