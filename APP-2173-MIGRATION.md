# APP-2173 kinetic and transmission migration

## Starting classification

This pass starts from merged checkpoint PR #192 (`48ae3d2`), which provides a
typed kinetic adapter for Creative Motor, Shaft, Cogwheel, Large Cogwheel, and
the Millstone load used by its processing checkpoint. The checkpoint's
`APP-2136-MIGRATION.md` records those component receipts; they are not a single
production-package or full-family acceptance run.

| Assigned matrix row | Starting state | This pass |
| --- | --- | --- |
| Kinetic propagation, speed, stress, overload | Adapted motor/shaft/cogwheel graph; source and load subset only | Directional transmission rules extended; full load, loop, overload, reconnect/split gates remain open |
| Small/large/encased cogwheels | Small/large cogwheel typed path in checkpoint | Encased cogwheels remain open |
| Shafts and encased shafts | Straight Shaft typed path in checkpoint | Andesite/Brass encased shaft paths remain open |
| Gearbox and Vertical Gearbox | Legacy implementation only | Typed block-entity registration and axis node added; runtime cases remain open |
| Clutch and Gearshift | Legacy implementation only | Typed registrations and powered output-side transfer rules added; runtime/reconnect cases remain open |
| Encased Chain Drive and Adjustable Chain Gearshift | Legacy implementation only | Typed registration, link-axis/end-point connection rules, and signal ratio translation added; signal update scheduling, overspeed break behavior, and runtime remain open |
| Sequenced Gearshift | Legacy implementation only | Open |
| Creative Motor | Adapted in PR #192; signed setting and save/reopen receipts are recorded there | Reused; no new claim |
| Rotation Speed Controller | Legacy implementation only | Open |
| Flywheel | Legacy implementation only | Typed registration and axis node added; runtime, stress, and lifecycle cases remain open |

## Implemented rule slice

`native/kinetic_slice.rs` now models Flywheel, Gearbox, Clutch, Gearshift, and
Chain Drive nodes in addition to the checkpoint's nodes. Gearbox faces connect
perpendicular to its declared axis. Its outgoing direction modifier follows
the existing `machines.rs::gearbox_multiplier` rule. A powered Clutch cuts
only the output side after its incoming face; a powered Gearshift negates only
that output. Chain links follow the legacy axis/endpoint rules, and adjustable
links translate their saved signal to the source speed modifier. The typed
adapter recognizes these blocks, walks their directed edges, and registers the
corresponding existing Create block-entity IDs.
`tools/prepare-kinetic-probe.py` includes the corresponding block definitions
in its isolated probe pack.

The direct production-logic check is:

```sh
rustc --edition=2024 --test native/kinetic_slice.rs -o /private/tmp/app2173-kinetic-slice-tests
/private/tmp/app2173-kinetic-slice-tests
```

Result: 7 passed, including the existing cogwheel ratio, signed source,
capacity/stress, and arbitration cases plus the new directional transmission
cases. `python3 tools/prepare-kinetic-probe.py --output
/private/tmp/app2173-probe-project` staged the bounded probe pack. These are
source-level checks; no APP-2173 typed-package build or Horizon gameplay case
has passed in this worktree yet.

## Bounded delivery cases and remaining gates

The finite integration cases for the full ticket remain: a connected
motor-to-shaft-to-Gearbox-to-gearshift/clutch-to-Flywheel path; straight and
turned Gearbox outputs; powered/unpowered Clutch stop/resume; powered/unpowered
Gearshift signed output; source conflict and loop rejection; connected
overload below/at/above capacity and recovery; reconnect/split; representative
Sequenced/Adjustable Chain operation; active save/reopen; and a supported host
and guest converging on a representative transmission change. Preserve axis,
orientation, waterlogging, ordinary configuration, and block contents where
applicable.

The typed package currently registers only the selected checkpoint types plus
Flywheel, Gearbox, Clutch, Gearshift, Encased Chain Drive, and Adjustable Chain
Gearshift. The latter's signal update scheduling and overspeed breaking are not
migrated. Sequenced Gearshifts, Rotation Speed Controllers, encased cogwheels
and shafts, and their content/presentation integration are not migrated by
this slice. The current adapter also lacks the complete legacy load table,
Sequenced/Chain state, speed-controller cross-network links, inconsistent-loop
resolution, and all production registry/package wiring. Those gaps block
APP-2173 gameplay completion; the source-level checks do not establish
multiplayer, persistence, or the ticket's Horizon/SDK build cohort.

## Build cohort

Target is Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, SDK
`sdk-0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, Minecraft 26.3, mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, Rust 1.99.1, and launcher
0.2.105. The preparation-only manifest in `cohort/APP-2137-cohort.json`
records the immutable inputs. APP-2172 owns a reproducible full package and
supported offline two-client route; until its package/runtime inputs are
available, no production build, multiplayer, or final save/reopen result is
claimed here.
