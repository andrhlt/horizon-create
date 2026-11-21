# APP-2059 train feedback gameplay pass

Reference: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`, Horizon
`9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`. Prerequisites APP-2049
(Stations/names/dispatch) and APP-2041 (Display Links/Boards) are Done.

## Finite case list

- Retain existing moving observed-train-name and schedule title/throttle traces.
- Select station Train Schedule Status from the Display Link screen, including a
  LAN guest. Compare six Java delay-format boundaries, and blank without a
  schedule, paused, in transit and at the last noncyclic stop.
- Show the current train's identity, speed, throttle and manual arrival/departure
  station prompts on the controls HUD, for the host and guest driver.
- Play one mounted bell, note block and small whistle during approach. Preserve
  source ordering and the half-rate queue progression; check actual muted client
  playback events. A physical speaker/waveform comparison is outside this pass.
- Reopen an idle configured station/link/countdown and a moving named train.
  Reuse the existing stopped/active manual-train reopen check for motion/control
  continuation and neighboring regressions for moving train names and schedules.

## Source rules and reference limits

`TrainStatusDisplaySource`, `ScheduleRuntime.getWaitingStatus` and
`TimedWaitCondition` define eligibility, first-alternative-group progress,
minute flooring and five-second rounding. `CarriageContraptionEntity.control`
defines the manual station prompts. `ArrivalSoundQueue`,
`CarriageContraption.capture` and `CarriageContraptionEntity.tickArrivalSound`
define playable mounted sources, longitudinal offsets, reverse order, volume 5
in the neutral category and one queue position every two ticks, triggered inside
60 blocks of the destination. The status adapter polls authoritative state each tick rather than reproducing
Java's display-update notification/packet timing. The HUD supplies usable textual feedback; Java's
artwork and smoothing are not reproduced here.

[Java capture patch](tools/java-train-feedback.patch) and
[capture runner](tools/capture-train-feedback-java.py) produce
[11 controlled observations](fixtures/train-feedback-java.json). They exercise
actual Java source methods with a controlled station/train/runtime, not a moving
Java train, real Java network delivery or Java audio playback. The fixture's
initial cyclic schedule made the intended last-stop negative invalid; the final
capture explicitly sets `cyclic=false`. Both logs remain under `.local`.
The Horizon fixture seeds selected runtime boundaries through commands, while
its ordinary countdown starts from a real Schedule given to a seated conductor.

## Environment and initial failures

Worktree `/private/tmp/horizon-app-2059`, branch
`codex/app-2059-train-feedback`, started from `6b060e2`. Builds use compatible
launcher 0.2.67 and a private APFS-cloned Rust target cache. The original shared
Horizon source already contained patches; the build base was replaced with a
fresh pinned GitHub tarball. Its `CLAUDE.md` symlink was materialized to meet the
launcher's staged-input restriction. No shared source/cache was modified.

The prechange offscreen client `native-9f42064-a5156e57df79` reproduced the missing
station Train Schedule Status source (`.local/feedback-before-valid.log`). Earlier probes opened the newly placed
link before ticking its block entity; those are invalid UI fixtures, retained
as `.local/feedback-before-retry.log` and `.local/feedback-status-initial.log`. The
first sandboxed attempt could not create its control socket; it is not gameplay
failure evidence. Early build attempts failed on an already-applied engine patch
and the archive symlink; their logs remain in `.local/feedback-build*.log`.
All worlds and ports are isolated, and all visual clients are hidden/offscreen.

## Remaining scope

Full 1:1 remains Open. Station Summary prediction boards, optional display
sources, full condition-specific status formatting, HUD texture/animation and
scroll throttle, manual honking, continuous carriage sound mixing, custom-head
note sounds, multi-carriage audio offsets and exact Java audio/network/reload
phase equivalence need further checks. Broader mounted-source layouts and
reverse audio sequences are source translations rather than measured moving
Java traces. These do not establish exhaustive family parity.

## Validation identity and commands

Final native build: `native-9f42064-76138ca65acb`; launcher 0.2.67,
performance profile, cursor fix included through current engine patches.
Pack SHA256: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
The branch was rebased onto `b1ee807`; that intervening main change touches
Worldshaper tests/docs only and leaves native code and engine patches unchanged.

```sh
B=.local/patched-launcher/versions/native-9f42064-76138ca65acb
python3 tools/test-parity.py "$B/horizon-ctl" "$B/horizon-client" "$B/.local/horizon-client/26.3" --jobs 2 \
  --check train-feedback --check train-feedback-lan \
  --check observed-train-display --check observed-train-display-lan \
  --check scheduled-title-throttle --check scheduled-title-throttle-lan \
  --check manual-train-reopen --check manual-station-approach \
  --check display-board-lifecycle
python3 tools/capture-train-feedback-java.py
python3 tools/check-source.py
```

Raw logs: `.local/feedback-final-checks.log`, `.local/parity/*.log`,
`.local/feedback-lan-retry.log`, `.local/java-feedback-capture-final.log`.
The first LAN fixture attempted a synchronous remote `command` chat return,
which the harness does not support. It failed with `KeyError: chat`; the
corrected fixture checks the guest's local block visibility and its source
configuration action against authoritative output. It does not claim to inspect
guest-local Nixie text. Actual guest HUD drawing and sound receipt are checked
on that client. The invalid log is preserved at
`.local/train-feedback-lan-first-invalid.log`.

Offscreen screenshots `.local/train-feedback-hud-solo.png` and
`.local/train-feedback-hud-lan.png` were visually inspected. The HUD was moved
above the existing controls-help overlay. Command-feedback chat in those
fixture screenshots is harness output, not the train HUD.

Timing (overlapping work, approximate): source/setup/implementation and fixture
debugging about 15 minutes; Rust builds 304 + 126 + 88 = 518 seconds;
Java captures 38 + 19 seconds; syntax checks under two seconds each. Runtime
integration duration and final outcomes are recorded with delivery below.

## Delivery results

All nine selected paths pass on the final native build: solo and LAN feedback,
solo and LAN observed names, solo and LAN title/throttle schedules, manual
station approach, manual idle/active reopen, and Display Board lifecycle.
The first grouped run reports 8/9 because of the invalid LAN remote-chat
assumption described above; the corrected complete LAN feedback replay passes
in `.local/feedback-lan-retry.log`. No production changes were needed for that
fixture correction. Integration took about six minutes for the grouped run,
with the focused LAN retry overlapping it.

The new source matches all six recorded Java delay strings. Four blank-state
eligibility cases pass. Each driver role runs 65 moving ticks and receives one
bell, harp note and small whistle playback event. The solo fixture reopens the
configured idle link/countdown and the active named train, retaining its name
and resumed wheel movement. Existing manual reopen separately checks resumed
control. The manual approach regression matches 198 Java observations, and each
title/throttle schedule replay matches 183. Guest configuration is checked
against authoritative output; the HUD trace and playback counters are sampled
on the actual guest. Replication convergence is not Java packet-timing parity.

`tools/check-source.py` passes for 487 JSON, 45 JSONL, 889 Python, two shell and
three TOML files. Native compilation passes. No standalone Rust/Clippy target
was changed. The combined native/engine source digest is
`635d77ec3baed1dbf87127db92a09bc10859447a29f973f7a276b76b455899ba`;
`.local/feedback-source-identity.json` records its file count for integration
verification. Full 1:1 remains Open.
