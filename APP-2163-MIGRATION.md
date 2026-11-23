# APP-2163 processing and logistics migration

## Current lane boundary

This lane owns stationary processing, recipe execution, block inventories,
item transfer endpoints, fluid storage/transport, and persistence. The typed
kinetic adapter and central registration remain owned by APP-2136. The usable
adapter handoff is PR #192 commit `9009897f5461d3e0662b7114dd2a87ac42d417f4`.

The first implementation seam is the existing Millstone path. Its pure timer
transition is now factored as `millstone_processing::tick` in
`native/millstone_processing.rs`; the legacy world/inventory code remains authoritative for
item movement, recipes, chance rolls, NBT migration, and sync. The future typed
Part should call this transition after reading the connected `Speed` from the
APP-2136 entity NBT rather than calculating kinetic state itself.

## Bounded case matrix

| Family | Existing implementation | Required bounded evidence | Status |
| --- | --- | --- | --- |
| Millstone processing | `native/machines.rs::tick_mill` | Wheat speed/tick trace, output conservation, idle/active reopen, backpressure | Timer seam implemented; runtime migration open |
| Millstone inventory/logistics | `block_entity_container`, chute/hopper paths | Host/guest insertion and extraction through the wheat fixture | Existing legacy path; typed endpoint migration open |
| Crushing and pressing | `native/crushing.rs`, `native/press.rs` | Existing representative recipe/output checks | Reuse existing logic; adapter migration open |
| Mixing/heating | `native/mixer.rs`, burner/fan paths | Heated acceptance/rejection and interruption/restart | Reuse existing logic; adapter migration open |
| Fluids | `native/fluid_tank.rs`, `native/create_fluids.rs` | Pump/pipe/tank transfer, filling/draining and reopen | Existing legacy path; typed endpoint migration open |
| Item logistics | belts, funnels, chutes, depots, vaults, arms and crafters | Representative transport and capacity/filter negatives | Existing family checks; typed endpoint migration open |

This is a finite first pass, not an exhaustive variant cross-product. Cosmetic
parity, exact packet timing, and untested machine combinations remain separate
follow-ups unless they expose item loss, duplication, broken guest authority,
or corrupt saves.

## Adapter contract requested from APP-2136

The processing lane needs only these shared capabilities:

1. Read the connected authoritative `Speed` for a stationary block entity.
2. Register a typed block-entity part without changing the existing block IDs.
3. Expose the entity's typed item slots to ordinary container input/output rules.
4. Merge saved NBT and publish an entity sync after recipe completion or a
   transfer that changes observable inventory.
5. Resolve the pinned recipe list and item ingredient/result conversion.

No kinetic graph walk, source arbitration, or duplicate speed calculation is
needed in this lane. The first Millstone adapter can preserve the existing ten
slots (`0` input, `1..9` output), `Timer`, `InputInventory`, and
`OutputInventory` save keys while the typed entity stores the live item slots.

### Registration handoff (not applied here)

The shared manifest owner should add this lane-owned source alongside the
existing `machines` module:

```toml
[[module]]
id = "millstone_processing"
file = "crates/horizon-client/src/game.rs"
name = "create_millstone_processing"
source = "millstone_processing.rs"
```

`machines.rs` already references the file with an explicit `#[path]`, so the
generated module can use the same source without a second implementation.

## This checkpoint

Source base: `origin/main` at `87ae37f`. Adapter reference: PR #192 at
`9009897f5461d3e0662b7114dd2a87ac42d417f4`. The pure Millstone transition was
compiled and run as an isolated Rust test harness: 2/2 tests passed, covering
zero-speed idle, cycle start, speed-dependent decrement, clamping and invalid
or empty inputs. `git diff --check` passes. A full pinned native build and
runtime wheat/LAN/reopen replay are still required after the typed Part and
central registration are integrated by APP-2136; this checkpoint does not claim
the migration or the APP-2163 lane complete.
