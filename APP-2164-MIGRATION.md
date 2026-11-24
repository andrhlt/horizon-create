# APP-2164 lane handoff

This lane is based on the current APP-2136 adapter contract at PR #192,
commit `90ef89c182726d2be03ae592a610054519b6a664`. APP-2136 owns the typed
adapter, package-root registration, and central manifest. APP-2164 owns the
player-facing board/input path and the ordinary interaction families below.

## Current ownership

| Family | APP-2164 files/evidence | Boundary |
| --- | --- | --- |
| Creative Motor settings board | `migration/kinetic-probe/src/motor_board.rs`, `native/motor_board.rs` | Server mutation remains authoritative; `menu_button` resolves the acting player level and calls the typed adapter setter. |
| Host/guest board action | `migration/kinetic-probe/data/create/horizon/menu/creative_motor.json` | Canonical menu-key resolution and server button mapping compile. The pinned prebuilt client surface still lacks the global screen-click hook needed to submit the board buttons. |
| Existing presentation fallback | `native/speed_controller_controls.rs`, `native/speed_controller_input_draw.rs`, `native/speed_controller_input_server.rs` | The existing native route already owns the Creative Motor screen id, draw/input loop, and LAN action channel. It remains the only runnable board-opening path until the typed content-menu key seam exists. |
| Menus, filters, tools, static content | Existing `native/*screen*`, `native/*editor*`, `native/wrench.rs`, `content/` | Stationary processing state stays with APP-2163; moving targets and train lifecycle stay with APP-2165. |

## Finite acceptance cases

The board pass is bounded to signed `-24`, `0`, `64`, and `256` settings,
including host and guest actions, rejection of a non-motor target, and the
existing active/idle save/reopen checks. The board's zero detent must remain
zero; it must not become `+1` through a lower-bound clamp.

Exact pixel and packet-arrival parity remain follow-ups. The typed board/menu
module compiles against the pinned prebuilt API using the 90ef89c adapter
sources. The server can now resolve the canonical `create:creative_motor`
menu key and open the board without indexing opaque keys. The pinned
prebuilt client surface does not expose the newer global `screen_click` hook,
and its available mouse hook requires a mutable client host while the hook
provides a read-only host, so it cannot submit `menu.click_button`. The
existing native screen/input route remains the supported runnable fallback;
typed board-open is compile-verified, while typed screen-click and host64 /
guest24 / zero runtime acceptance remain pending the client hook surface.
