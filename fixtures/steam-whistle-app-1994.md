# Steam Whistle APP-1994 bounded evidence

## Scope and source

Create 6.0.10 Java reference: `ac0c444d9828da3453ae8cc65338e8de063286fb`.
The ticket worktree prepared its content pack and GameTest fixtures from the
read-only primary checkout at that exact revision using `tools/prepare.py`.
The pack passed ZIP integrity and its generated Steam Whistle blockstates and
item entries loaded in the Horizon runs.

Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` (Nightly
`9f42064`), Minecraft 26.3. Reused compatible build
`native-9f42064-d6dc2ad18d3f` from the primary checkout. Its
`native-mods.json` pins the Horizon commit above, and its `horizon-prepare
--check` passed for its bundled `.local/horizon-client/26.3` resource tree.
The Java replay, audio replay, cold reopen and dedicated-server LAN checks all
loaded the same rebuilt pack, SHA-256
`979e715441e3771b25a819364075894133e689d271348e7a5fc5f7e8e7ffaa79`.

## Bounded cases and results

| Gate | Cases and result |
| --- | --- |
| Java-backed gameplay | `steam-whistle` passed the pinned trace for tank attachment on side and top faces, 12 growth actions across the first three extension blocks, wrench octave propagation, redstone transitions, support loss and removal. It also confirmed powered floor placement. Discrete states matched exactly. |
| Activation, pitch and deactivation | `steam-whistle-audio` passed with muted audio requests: silence without boiler heat; passive-heat onset; one-extension pitch `2^(-1/12)`; fade to zero on redstone off; large-octave sound selection; redstone retrigger. |
| Guest-visible and sound state | `steam-whistle-lan` used offscreen host and guest clients on a dedicated server. The guest grew a single extension and wrenched the whistle to large; both clients observed extension shape and octave. Both clients recorded the boiler onset, tuned-pitch request, redstone fade/retrigger, fade to zero when boiler heat was removed, and a fresh cue when heat returned. This checks muted event requests, not speaker output or waveform parity. |
| Idle and active persistence | `steam-whistle-persistence` cold-reopened separate idle and boiler-powered worlds. Both retained large octave, pitch 3, a double segment followed by a single segment, and the expected redstone state. The active world retained `Steam: 1` and restarted its muted sound cue after reopen; switching redstone off then faded the cue to zero. |

The no-heat/active transition and octave behavior use the existing Java-backed
and audio checks. Persistence is a source-aligned Horizon save/reopen check,
not an exact Java reload comparison. LAN convergence establishes resulting
state and cues on both clients, not Java packet-arrival timing.

## Reproduction

Run sequentially to keep worlds, ports and output isolated:

```sh
python3 tools/test-parity.py \
  /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/horizon-ctl \
  /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/horizon-client \
  /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/.local/horizon-client/26.3 \
  --jobs 1 \
  --check steam-whistle \
  --check steam-whistle-audio \
  --check steam-whistle-persistence \
  --check steam-whistle-lan
```

Run the LAN case again after adding the boiler heat-loss and heat-restoration
assertions:

```sh
python3 tools/test-parity.py \
  /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/horizon-ctl \
  /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/horizon-client \
  /Users/andrewholt/dev/horizon-create/.local/patched-launcher/versions/native-9f42064-d6dc2ad18d3f/.local/horizon-client/26.3 \
  --jobs 1 --check steam-whistle-lan
```

Final logs and host/guest sound-request traces are retained in the ignored
worktree outputs `.local/parity/` and `.local/app-1994/`. The first sandboxed
attempts could not create Unix control sockets or bind the LAN test port; the
same checks passed with the normal elevated local-network execution.

## Remaining follow-ups

Exact chiff waveform and audio-backend playback, Java reload equivalence,
maximum-height layouts, and visual particle/animation comparisons remain open.
They do not block this bounded gameplay baseline.

## Time record (approximate)

- Source and runtime setup, pinned-pack preparation and compatibility checks: 15 min.
- Harness changes and evidence notes: 25 min.
- Build or new Java capture: not needed; the family implementation and fixture
  already existed, and the reusable Java trace was retained.
- Python syntax/runner checks: under 1 min.
- Horizon integration: about 1 min 25 sec total for the four-check pass and the
  follow-up LAN run.
- Sandbox diagnosis and elevated rerun: about 5 min.
