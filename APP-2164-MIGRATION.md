# APP-2164 lane handoff

This lane is based on the current APP-2136 adapter contract at PR #192,
commit `90ef89c182726d2be03ae592a610054519b6a664`. APP-2136 owns the typed
adapter, package-root registration, and central manifest. APP-2164 owns the
player-facing board/input path and the ordinary interaction families below.

## Current ownership

| Family | APP-2164 files/evidence | Boundary |
| --- | --- | --- |
| Creative Motor settings board | `migration/kinetic-probe/src/motor_board.rs`, `native/motor_board.rs` | Managed offline Play opens the typed board; ordinary clicks set positive, negative, and zero RPM and update the connected shaft. A scheduled server task applies the setting because the menu callback's block entity is temporarily out of world. |
| Host/guest board action | `migration/kinetic-probe/data/create/horizon/menu/creative_motor.json` | Host-side menu click and save/reopen pass. Distinct-UUID guest convergence remains unverified because developer-offline Play is single-player-only and the approved route does not permit direct lease-bypassing client launch. |
| Menus, filters, tools, static content | Existing `native/*screen*`, `native/*editor*`, `native/wrench.rs`, `content/` | Stationary processing state stays with APP-2163; moving targets and train lifecycle stay with APP-2165. |

## Finite acceptance cases

The board pass is bounded to signed `-24`, `0`, `64`, and `256` settings,
including host and guest actions, rejection of a non-motor target, and the
existing active/idle save/reopen checks. The board's zero detent must remain
zero; it must not become `+1` through a lower-bound clamp.

The typed board/menu, screen rendering, and click path are runtime-verified on
the pinned matching candidate. `tools/test-typed-motor-board.py` exercised
+64, -24, zero, then +64 RPM; the motor and shaft agreed, and active +64
survived save/reopen. The menu stayed open and the offscreen client did not
capture the pointer. Exact pixel parity and distinct-player guest convergence
remain follow-ups. The latter needs a supported lease-compliant offline guest
route; no sign-in or cache-lease bypass was used.
