# APP-2164 lane handoff

This lane is based on the frozen APP-2136 adapter contract at PR #192,
commit `9009897f5461d3e0662b7114dd2a87ac42d417f4`. APP-2136 owns the typed
adapter, package-root registration, and central manifest. APP-2164 owns the
player-facing board/input path and the ordinary interaction families below.

## Current ownership

| Family | APP-2164 files/evidence | Boundary |
| --- | --- | --- |
| Creative Motor settings board | `migration/kinetic-probe/src/motor_board.rs`, `native/motor_board.rs` | Server mutation remains authoritative; `menu_button` resolves the acting player level and calls the typed adapter setter. |
| Host/guest board action | `migration/kinetic-probe/data/create/horizon/menu/creative_motor.json` | The menu declaration and server button mapping are compiled. The pinned SDK still lacks a supported content-id to opaque `MenuKey` lookup, so ordinary empty-hand opening is an explicit seam for APP-2136 integration. |
| Menus, filters, tools, static content | Existing `native/*screen*`, `native/*editor*`, `native/wrench.rs`, `content/` | Stationary processing state stays with APP-2163; moving targets and train lifecycle stay with APP-2165. |

## Finite acceptance cases

The board pass is bounded to signed `-24`, `0`, `64`, and `256` settings,
including host and guest actions, rejection of a non-motor target, and the
existing active/idle save/reopen checks. The board's zero detent must remain
zero; it must not become `+1` through a lower-bound clamp.

Exact pixel and packet-arrival parity remain follow-ups. The typed board/menu
module compiles against the pinned prebuilt API using the 9009897 adapter
sources. Runtime board opening and screen clicks remain blocked by the missing
supported `String -> MenuKey` lookup: `PlayerRef::open_mod_menu` requires an
opaque `MenuKey`, while `KeysHost::menu_keys` does not expose names and the
only name helper is hidden. Do not index or zip opaque keys to ids. APP-2136
must supply the narrow central resolution seam (or expose a supported
content-menu key) before board-open/host64/guest24/zero acceptance. The compile
candidate still proves the server-side target identity, player-level selection,
signed button mapping, and shared setter call.
