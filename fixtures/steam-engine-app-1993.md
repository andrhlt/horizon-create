# Steam Engine APP-1993 bounded evidence

Reference: Create 6.0.10 at `ac0c444d9828da3453ae8cc65338e8de063286fb`.
The existing [steam trace](steam_engine-java.csv) remains the 13-sample passive
two-engine baseline. It does not cover the cases below.

## New Java boundary trace

`tools/java-steam-engine-boundaries-trace.patch` filters the Java GameTest run
to one source test, `TestFluids.steamEngineBoundaries`, and emits actual Java
block-entity readings at every test tick from 0 through 220. It retains the
upstream `steam_engine` structure and performs this finite sequence:

| Relative ticks | Action | Java observations |
| --- | --- | --- |
| 0–1 | Pumped boiler starts with two engines, then the second is removed | Water supply, attachment count, both shaft speeds/power |
| 8 | Restore the second engine | Reconnection and shaft output |
| 20 | Replace one passive heater with a `KINDLED` burner | One active heat level, below the two-engine heat demand |
| 23–27 | Remove, then restore the second engine while water is flowing | One-engine and two-engine shaft output under limited heat |
| 30 | Raise that heater to `SEETHING` | Two active heat levels for the 2×2×2 boiler |
| 40 | Restore the lit campfire | Passive heat stage |
| 50–165 | Stop then restart the pump via the fixture lever | Pump RPM, ten-sample water-supply decay and recovery |
| 0–220 | Sample each tick | Boiler supply, pump RPM, engine count, heat, both powered shafts, speedometer RPM, stress capacity |

The heater state transitions exercise Java's real boiler heat evaluator but
do not simulate player fueling. Player refueling and an active insufficient-
water threshold remain follow-ups; cold idle/running reopen and guest actions
are covered by separate Horizon integration checks below.

To capture the reference in a disposable checkout of the pinned Java source,
apply the patch and run the existing GameTest server task with Java 21. Preserve
the test log, then extract its rows:

```sh
python3 tools/parse-steam-engine-boundary-trace.py /path/to/java-gametest.log fixtures/steam-engine-boundaries-java.csv
```

The Horizon replay takes that CSV with `--reference` and writes its trace under
`.local/app-1993/`:

```sh
python3 tools/test-steam-engine-boundaries.py /path/to/horizon-ctl /path/to/horizon-client /path/to/prepared/26.3 --reference fixtures/steam-engine-boundaries-java.csv
```

## Save/reopen replay

`tools/test-steam-engine-reopen.py` uses isolated worlds for a cold idle reopen
and a running reopen after the original pump fixture has filled the boiler.
It checks engine count and supply before/after reopen and checks that the
powered shaft is idle or resumes operation as appropriate. This is a
source-aligned Horizon persistence check, not a Java reload comparison.

## Multiplayer boundary

`tools/test-steam-engine-lan.py` reuses `tools/test-multiplayer.py`'s dedicated
server and two-client helpers. A guest toggles the steam fixture's pump lever
to stop supply; host and guest must both observe the powered state. The host
then restarts the pump and both clients must observe the restored state. This
proves representative guest control and block-state convergence, not packet
arrival timing or exact remote shaft animation. It requires the prepared
structure at `--structure` and the identified branch build.

## Run record

Reference build: Create 6.0.10 at `ac0c444d9828da3453ae8cc65338e8de063286fb`.
Horizon build: `native-9f42064-6a3da367a9bb`, using the ticket-local launcher,
the prepared `26.3` resources and `.local/create.hmod` (SHA-256
`bc1b75b415cd3616253b27464f1178c7bd24bd46fb465c4e1ecd4700d812a9a7`). The
Java capture ran on the isolated copy with `/opt/homebrew/opt/openjdk@21`;
shared Java sources, native caches and other worktrees were not modified.

The Java GameTest passed and emitted 221 observations for relative ticks 0–220.
The parser wrote `fixtures/steam-engine-boundaries-java.csv`. The corrected
capture uses absolute world positions for all GameTest block writes. An earlier
diagnostic capture used template-relative positions and did not produce the
intended heater/engine transitions; it is excluded from the portable fixture.
An earlier idle-reopen attempt left the lever unpowered, so the pump refilled
the boiler during reopen; that invalid setup was corrected by powering the
lever and checking both pump shafts are zero before save.

The replay applies engine attach/detach mutations before the matching Horizon
step because Java updates its boiler attachment callback immediately, while
Horizon recomputes engine attachments in its tank tick. Heater and pump actions
remain after-step, matching the captured Java timing. The replay checks every
field at all 221 samples and permits only these captured differences:

* Ticks 12–16: supply is 57.6 in Java and 51.2 in Horizon (6.4 units), with
  every other field equal. Both compute water stage 5 (`ceil(supply) / 10`),
  exceeding this size-2 boiler's two active heat stages; shaft speeds, power,
  RPM and stress are equal. The trace does not show a stage or output effect.
* Tick 23 and ticks 27–29: only the listed shaft speed/power, speedometer and
  stress observations differ while kinetic state refreshes after engine
  attachment changes. All fields converge again at the next stable sample;
  engine count, water, heat and pump speeds remain exact.

The water amount difference remains open for source-level investigation. Java's
`FluidNetwork` uses 16 propagation cycles per tick and a simulated then executed
fill, while `BoilerData` averages gathered supply in five-tick samples. No
native gameplay change is justified by this trace: both values stay in the same
water stage and output is unchanged. The pump-off trace reaches zero water at
tick 148, where passive shaft output also stops; after restart, supply/output
recover. This establishes sufficient supply and zero-water stop/recovery, but
does not sample the active stage's exact insufficient-water threshold.

The registered checks use the exact identified client build and run sequentially;
outputs and worlds are ticket-local or temporary. Reproduce the complete bounded
suite with:

```sh
python3 tools/test-parity.py .local/patched-launcher/versions/native-9f42064-6a3da367a9bb/horizon-ctl .local/patched-launcher/versions/native-9f42064-6a3da367a9bb/horizon-client .local/horizon-client/26.3 --jobs 1 --check 'steam-engine*'
```

The complete registered run passed all four checks: the original 13-sample
passive trace, the 221-sample Java boundary replay, cold idle and running
save/reopen, and the two-client dedicated-server LAN interaction. The guest
stopped the pump and both clients observed the lever state; the host restarted
it and both clients observed the restored state. The first LAN harness attempt
used a single-player tick-control method against the dedicated server and was
invalid; the corrected harness exercises guest and host actions directly over
the running server. Final check logs are under `.local/parity/`, with LAN
artifacts under `.local/app-1993/`.

Still open: exact pump supply amount, true active fuel/refuel stages, active
insufficient-water threshold, and cosmetic boiler effects. These are bounded
follow-ups; they do not expand this evidence pass into exhaustive parity.
