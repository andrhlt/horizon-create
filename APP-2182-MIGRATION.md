# APP-2182 family migration

## Scope and finite acceptance cases

This is the bounded first migration pass for Chain Conveyor, Frogport,
Postboxes, and Table Cloths. Existing Java-derived legacy checks are retained
as regression inputs; they do not establish behavior on the Horizon 0a SDK.

| Family | Required cases |
| --- | --- |
| Chain Conveyor and Frogport | Address a package, deliver it through a running conveyor to a Frogport, reject a nonmatching endpoint, interrupt and resume a transfer, and save/reopen an active and idle route. Check conservation of package contents. |
| Postboxes | Place two differently addressed boxes away from stations, route a matching parcel to each, retain unmatched parcels, open/configure as host and guest, break a stocked box, and save/reopen both idle and stocked boxes. Check package and block drops for conservation. |
| Table Cloth | Issue an order from an owner-configured cloth through a stocked network, refuse an empty-stock order, return displayed items in their existing order, and save/reopen the configured endpoint and any pending list. Check item and currency conservation. |

Train-side station routing is outside this pass. Endpoint IDs and transfer
semantics must remain compatible with the train migration.

## Family status

| Family | Status on the 0a SDK | Evidence and remaining work |
| --- | --- | --- |
| Chain Conveyor | Open | Legacy chain connection, package routing, riding, LAN and save/reopen checks remain useful regression evidence. `migration/create` has no chain endpoint or transfer adapter; none of those cases has run on the 0a production package. |
| Frogport | Open | Legacy address, inventory, delivery, control, visual cue and restart evidence remains. The 0a production package has no Frogport inventory/menu/tick adapter. |
| Postboxes | Adapted, runtime verification open | `src/postbox.rs` registers all 16 block IDs with `create:package_postbox` and transfers every occupied native item slot into the SDK's pre-removal drops. Two unit checks cover empty slots and ordered, once-only item conservation. The frozen native build, actual stocked-box break, LAN authority, address behavior, transport and save/reopen remain unverified. |
| Table Cloths and shop | Open | Legacy tests cover all 19 cloth IDs, crafting, placement, display storage/reset, and a bounded configured shop flow. That shop fixture injects configuration directly; guest issuance was not stable, and checkout/payment/fulfillment remain open in the legacy notes. No cloth or shop behavior has been migrated into the 0a production package. |

## Build and verification record

- Source baseline: `origin/main` `306b6ee` (Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`).
- Language check: Rust 1.99.1, `cargo test --offline` in the production-staged crate against the exact local Horizon source tree at `/private/tmp/app2173-launcher-02107/native/source/0a875da91dbb0fdcb7ba8c42c11341aa229af51a` (revision marker matches the pinned Horizon SHA): 13 passed, 0 failed. This includes 11 existing kinetic tests and the two postbox conservation tests.
- Official launcher build: attempted with launcher 0.2.105, the explicit pinned `native-0a875da-fafbebe41f0f` version, Rust 1.99.1, and a private launcher/game home. First attempt stopped on `No space left on device`; after freeing only the APP-2182 temporary compile target and retrying, the CLI stopped before compilation with `The launcher is offline and the mod tools for the Nov 20 update aren't downloaded yet.` The pinned mixin executable is present in the isolated home, but the CLI still reports the tools unavailable. No shared cache was changed.
- No official 0a native-build receipt, package/dylib identity, runtime world, host/guest replay, or save/reopen result is claimed. These remain required before the migrated families can be marked gameplay verified.
