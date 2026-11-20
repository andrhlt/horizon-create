# APP-2036 Pulse Repeater, Extender and Timer

## Bounded case list and outcome

| Gate | Cases | Result |
| --- | --- | --- |
| Java timing | Six configurations: Extender 2 and 5 ticks; Repeater 2 and 7; Timer 20; inverted Timer 2. Source-on/off events at recorded ticks 4, 9, 13, 14, 30 and 36. Compare `powered`, `powering`, `inverted`, `State`, interval, output wire and side wire at every sample, ticks 0–44 inclusive. | Existing Java trace: 270/270 states matched, zero differences. LAN replay observes guest output convergence. |
| Player actions | Survival recipes and placement; empty/sneaking/held-item clicks; short click inversion and held timer value-board input. | Existing bounded action results: 12 Java states matched. Timer value board: eight recorded choices matched in solo and LAN; guest edits reached the authority without changing polarity. |
| Persistence | Idle configured Extender, Repeater and Timer with interval 200 and inversion on; then sustained input on all three, save/reopen, and continue one tick. | Passed on the identified headless client. Interval and polarity retained while idle; active configuration did not regress and operation advanced after reopen. Timer phase is allowed to advance while idle. |
| Regression | Pulse-only checks above; no native gameplay source changed in this ticket. | Persistence replay passed. Existing timing/action comparisons were retained as valid family evidence. |

## Source and runtime

- Java Create: `ac0c444d9828da3453ae8cc65338e8de063286fb` (Minecraft 1.21.1 / NeoForge 21.1.219).
- Horizon: `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0` (Minecraft 26.3).
- Save/reopen check client and control tool: `native-9f42064-6bdf8691aa42`, preserved under `.local/app-2017-evidence`; its record identifies the build synchronized to main commit `781c0ef`.
- Create pack SHA-256 used for the persistence run: `e0027300944fde1c6f1e31f74f25b9e79b01a9334062db2b2ab9a060135ac4d7`.
- Java timing trace SHA-256: `578e49a38ed20e4d12eab3a574be12688bc90df0022615d1603a85918b893b63`.
- Java timer settings SHA-256: `f1a1e7861c01213ea05d658bd8ea4703e723596aec8bc03c2a79ab33b4dc8b38`.
- Java action reference SHA-256: `7c59cb1fad30d224a2132f6e935ee5cffd1b25da895b7e1361ece40566db20bf`.

Reproduction for the new persistence gate (use the matching local executables and prepared resources):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/test-brass-diode-persistence.py \
  /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 \
  --pack /path/to/create.hmod
```

Result: `Pulse Extender, Repeater, and Timer idle settings survived save/reopen; active input state was retained and operation resumed.` The raw control log is in `.local/app-2036-pulse-diodes/horizon-brassdiodepersistence.log`.

The first persistence assertion attempted to preserve the Timer's internal `State` while idle. That counter is a live phase and naturally advances in an unpowered Timer, so that assertion was too strict. The final check compares the durable interval and polarity while idle, then verifies saved active configuration and resumed progress. This was a harness correction, not a gameplay defect.

## Follow-ups

Full 1:1 remains Open. Exact indicator animation and sound timing, all interval combinations, additional orientations and packet arrival/interpolation timing remain unverified and do not block this gameplay baseline.
