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
60 blocks of the destination. The HUD supplies usable textual feedback; Java's
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
station Train Schedule Status source (`.local/feedback-before-retry.log`). The
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
