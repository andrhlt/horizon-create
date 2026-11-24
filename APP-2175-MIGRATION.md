# APP-2175: gauges and Turntable SDK migration

## Bounded gameplay disposition

Speedometer, Stressometer, and Turntable are integrated on the frozen Horizon
SDK and passed the ticket's practical offline gameplay baseline. This evidence
is specific to the final `native-0a875da-d99bfac77285` build and does not
replace the historical Java comparison evidence for the family.

| Family row | Baseline result | Evidence and remaining work |
| --- | --- | --- |
| Speedometer and Stressometer | Pass | Both gauges joined a powered millstone network and reported `Speed: 16.0 RPM` and `Stress: 64.0 / 262144.0` in the live HUD; persisted block data held the same speed, stress, and capacity. Offscreen screenshots show usable dials and readable overlays. The network was saved and cold-reopened; both values remained and continued updating. |
| Turntable | Pass | A powered table rotated a grounded host player and a LAN guest player. Setting motor speed to zero stopped both; the final repeated yaw samples remained unchanged while table speed, capacity, and stress were zero. Active save/reopen preserved the powered table's `16 RPM`, `64 SU` load, and `262144 SU` capacity, and host movement resumed after reopen. |

The bounded baseline passed with the offline account route only; no Microsoft
sign-in was used. Multiplayer evidence demonstrates representative guest action
and state convergence on a local host/guest session. It does not claim packet
arrival or interpolation parity. The matrix's **Full 1:1** column remains Open.

## Runtime and commands

The final native build used Horizon SDK
`0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, Minecraft 26.3, launcher 0.2.107,
Rust 1.99.1, and mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`. The
isolated prepared client assets and game data lived under
`/private/tmp/horizon-app2175`; the final mod version was
`native-0a875da-d99bfac77285`.

The logic check passed 15/15:

```sh
python3 tools/test-gauge-turntable-logic.py
```

The exact SDK probe was staged and built with the compatible launcher:

```sh
python3 tools/prepare-kinetic-probe.py --output /private/tmp/horizon-app2175/project
HORIZON_LAUNCHER_HOME=/private/tmp/horizon-app2175/launcher-home \
HORIZON_HOME=/private/tmp/horizon-app2175/game-home \
/Applications/Horizon.app/Contents/MacOS/horizon-launcher native-build \
  /private/tmp/horizon-app2175/project --instance app-2175-build \
  --version native-0a875da-d99bfac77285 --trust-native-code
```

Gameplay used `horizon-ctl` against isolated offline host and guest clients.
The final build loaded the resource pack (35,903 block states and 1,677 items),
then exercised the powered network, readouts, stop state, active save/quit/cold
reopen, and a local LAN guest on a separately powered Turntable. On reopen,
the host gauge and table values were still `16 RPM`, `64 SU`, and `262144 SU`;
the host then resumed motion. On the guest table, yaw changed while powered and
remained fixed over two later samples after power was removed.

## Remaining comparison scope

The runtime cases above establish ordinary playability for the requested
baseline. Negative RPM, exact 1/30/100 RPM display boundaries, stress at 50%,
75%, exactly 100% and above capacity, center-versus-edge velocity, pig contact,
and all removal variants were not run on this frozen-SDK build. Existing pinned
Java traces remain useful reference evidence, but were not replayed as a full
cross-product here. The gauge pointer currently uses a redstone-torch model;
exact cosmetic parity, Java float sine-table output, and Goggles-only readout
gating remain follow-ups. These limits do not prevent ordinary powered reading
or player motion. No failure was observed in the original scoped probe checks.

## Production-package merge follow-up

After main advanced through APP-2173, this branch was merged with commit
`88bcb60f1d642bb66e6c49f8f6a64747cd45aa13`. The gauge and Turntable adapter is
now also staged in the combined `migration/create` production package. The
combined package compiled against the same pinned SDK as
`native-0a875da-ffa02e1d76d0`, using the APP-2173-normalized content pack. The
17 source logic cases pass on the combined source. The live gauge/Turntable
cases above were run on the earlier `native-0a875da-d99bfac77285` probe build;
they have not been repeated on the combined production package.

The APP-2173 production-route regression was also attempted on the combined
build. It reached its overload case but observed `16 RPM` and `0` stress where
that route expects `32 RPM` and overload. The repository's prior APP-2173 route
receipt records the expected overloaded state. This mismatch remains an open
regression result; it is not counted as a pass by this ticket.
