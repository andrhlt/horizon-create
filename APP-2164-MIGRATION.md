# APP-2164 lane handoff

This lane is based on the frozen APP-2136 adapter contract at PR #192,
commit `9009897f5461d3e0662b7114dd2a87ac42d417f4`. APP-2136 owns the typed
adapter, package-root registration, and central manifest. APP-2164 owns the
player-facing board/input path and the ordinary interaction families below.

## Current ownership

| Family | APP-2164 files/evidence | Boundary |
| --- | --- | --- |
| Creative Motor settings board | `native/speed_controller_controls.rs`, `native/speed_controller.rs`, `tools/test-creative-motor.py` | Server mutation remains authoritative; the typed adapter's `set_motor_setting(host, level, pos, setting)` is the migration target. |
| Host/guest board action | `native/speed_controller_input_server.rs`, `tools/test-multiplayer-creative-motor.py` | Guest sends the existing action once; APP-2136 owns typed transport and graph sync. |
| Menus, filters, tools, static content | Existing `native/*screen*`, `native/*editor*`, `native/wrench.rs`, `content/` | Stationary processing state stays with APP-2163; moving targets and train lifecycle stay with APP-2165. |

## Finite acceptance cases

The board pass is bounded to signed `-24`, `0`, `64`, and `256` settings,
including host and guest actions, rejection of a non-motor target, and the
existing active/idle save/reopen checks. The board's zero detent must remain
zero; it must not become `+1` through a lower-bound clamp.

Exact pixel and packet-arrival parity remain follow-ups. A typed SDK menu/screen
adapter will be supplied as a small integration patch against APP-2136's
central package once the board route is connected to the shared adapter.
