# APP-2164 lane handoff

This lane is based on the current APP-2136 adapter contract at PR #192,
commit `90ef89c182726d2be03ae592a610054519b6a664`. APP-2136 owns the typed
adapter, package-root registration, and central manifest. APP-2164 owns the
player-facing board/input path and the ordinary interaction families below.

The motor board is delivered in PR #194. It is intentionally kept open until
the APP-2136 central adapter/registration work lands ahead of it. The supported
offline developer Play route is single-player only; offline guest convergence
is therefore unverified and remains an explicit follow-up rather than an
authentication request or a claimed pass.

## Current ownership

| Family | APP-2164 files/evidence | Boundary |
| --- | --- | --- |
| Creative Motor settings board | `migration/kinetic-probe/src/motor_board.rs`, `native/motor_board.rs` | Server mutation remains authoritative; `menu_button` resolves the acting player level and calls the typed adapter setter. |
| Host/guest board action | `migration/kinetic-probe/data/create/horizon/menu/creative_motor.json` | Delivered in #194 for ordinary positive/negative/zero clicks and save/reopen. Offline managed Play reports single-player only, so distinct-UUID guest convergence is unverified. |
| Existing presentation fallback | `native/speed_controller_controls.rs`, `native/speed_controller_input_draw.rs`, `native/speed_controller_input_server.rs` | Preserved as the working container/UI path; typed screen hooks are now source-compatible in the recorded developer SDK, but remain separately gated from #194's runtime receipt. |
| Analog lever interaction | `migration/kinetic-probe/src/analog_lever.rs`, legacy reference `native/analog_lever*.rs` | Follow-up probe ports main-hand empty-use state mutation with exact block/entity targeting and saved `State`; redstone-neighbour propagation, animation timer and wrench/clipboard precedence remain to be wired and tested. |
| Menus and editors | `native/*screen*`, `native/*editor*`, `native/*menu*`, `native/elevator_floors_editor_*.rs`, `native/sequencer_editor.rs`, `native/stock_keeper_screen.rs`, `native/worldshaper_screen*.rs` | Inventory only; no broad completion claim. Migrate one ordinary editor at a time, keeping container state authoritative. |
| Filters and configuration | `native/attribute_filter_*.rs`, `native/list_filter_editor.rs`, `native/package_filter_*.rs`, `native/item_filters.rs`, `native/observer_filter_remove.rs` | Inventory only; preserve item conservation, rejection, save/reopen and host authority. |
| Tools and held/offhand use | `native/wrench.rs`, `native/use_item_on.rs`, `native/toolbox*.rs`, `native/clipboard*.rs`, `native/goggles*.rs` | Inventory only; preserve main/offhand and ordinary survival use. Wrench is shared with APP-2076 for broader parity. |
| Recipes, discovery and presentation | `native/recipe_*.rs`, `native/ponder*.rs`, `content/` | Inventory only; APP-2096/2097 and APP-2101 own related family follow-ups, while this lane supplies reusable player-facing bindings. |
| Static block/item presentation | `content/assets/`, `content/data/` | Existing assets remain loaded; missing model/sound/particle parity is a follow-up, not evidence of gameplay completion. |

## Finite acceptance cases

The board pass is bounded to signed `-24`, `0`, `64`, and `256` settings,
including host and guest actions, rejection of a non-motor target, and the
existing active/idle save/reopen checks. The board's zero detent must remain
zero; it must not become `+1` through a lower-bound clamp.

Exact pixel and packet-arrival parity remain follow-ups. The recorded source-
matched developer SDK exposes the typed screen/draw/click hooks, while the
older prebuilt artifact does not; do not mix those artifacts. PR #194's
runtime receipt uses the unchanged working container/UI route and proves
ordinary `-128`, `+128`, and `0` settings, connected shaft response, and
save/reopen. The supported offline runtime explicitly has no account features,
so representative distinct-UUID guest convergence remains unverified.
