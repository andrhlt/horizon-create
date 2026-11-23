# APP-2165 moving assembly/train migration

## Scope and ownership

This lane owns moving payload identity and lifecycle: bearing/piston/pulley and
gantry assemblies, attached blocks and inventories, moving collision, rider
carry/dismount, train carriage state, and moving-world rendering. Stationary
machine algorithms remain in APP-2163; menus and shared input remain in
APP-2164. Central registration/build changes remain with APP-2136.

The current source already contains the legacy behavior in `native/bearing.rs`,
`native/mechanical_piston.rs`, `native/train.rs`, `native/elevator_collision.rs`
and the related actor/seat/render modules. The post-API seam is represented by
`native/moving_slice.rs`: assembly owns the payload, movement changes only its
pose, and disassembly returns blocks and inventories together.

## First retained slice

The first bounded implementation is an assembled bearing payload with a chest
and one rider. `migration/motion-probe` registers a typed
`BlockEntityPart` for `create:mechanical_bearing`; its load callback persists a
payload, its server tick advances the motion offset and records a collision
query, and its terminal state records safe rider dismount/disassembly. The
pure lifecycle checks are in `tools/test-moving-slice.py` and run without a
game window or input.

The typed-Part base is PR #192 at `9009897f5461d3e0662b7114dd2a87ac42d417f4`.
Its verified SDK boundary supplies block-entity save/load, server ticks, client
draw submission, and collision queries. This probe is the minimal compile/runtime
candidate for binding the existing bearing capture/restore path; it does not
claim train, passenger, or LAN parity yet.

## Retained bearing acceptance mapping

The existing `tools/test-bearing-player-collision.py` is the world-level
acceptance fixture. It checks the real legacy fields and entities: `MovedBlocks`
and `Angle` while active, seven copper ingots after save/reopen and disassembly,
host/guest players remaining on ground through rotation, and restoration after
power removal. It is not silently counted as proof for the new Part.

The new `migration/motion-probe` has a deliberately smaller bridge: it captures
one real chest directly above a bearing into `PayloadPos` and `PayloadEntity`,
moves that chest one block per server tick after the pinned collision query,
merges its saved block-entity data at the destination, and records a safe
terminal state. Its `PayloadBlocks`/`PayloadItems` fields are probe evidence;
the old `MovedBlocks`/`MountedItems` path remains the production bridge still
to be reconciled for arbitrary glued payloads, rider entities, rotation, and
train carriage state.

The rider bridge uses the pinned API's real server handles: a player standing
in the captured chest footprint is recorded by UUID, transported with each
successful payload step, and teleported to the old payload footprint when
collision or the motion bound ends the run. `RiderCaptured`,
`RiderLastPosition`, and `RiderSafeDismount` are probe-owned acceptance state,
not a claim that the legacy bearing's complete passenger-attachment contract
has been migrated. The coordinated headless build must still establish that
the typed hook compiles and that a world fixture observes the same host/guest
safety behavior as `tools/test-bearing-player-collision.py`.

## Powered rotation slice

The next bounded slice reads `ScrollValue` from a creative motor directly
below an up-facing bearing. When present, the probe uses the legacy angular
step (`rpm * 360 / 60 / 20`), captures a bounded adjacent payload footprint,
rounds each block's Y-axis transform to world blocks, and carries the captured
rider by the first block's discrete delta. Each captured block keeps its
canonical typed state string and block-entity NBT (including container items),
and restore writes all target states only after duplicate/occupied-target
checks. A zero motor setting terminates at the current rotated position and
uses the existing safe-dismount path. The linear no-motor path remains
unchanged as a regression. The focused runtime fixture is
`tools/test-typed-bearing-rotation.py`; it now uses a chest plus barrel and
checks both inventories, but it is still not full glue graph, actor, guest, or
legacy `MovedBlocks` parity.

The typed client seam now also has a continuous render bridge: the bearing's
`block_entity_submit` reads synchronized angle/RPM, applies the partial-tick
angular phase with `BlockEntityDrawContext::rotate_about`, and submits the
captured chest model through `block`. This is the smallest supported visual
closure for the retained slice. The public surface does not expose arbitrary
moving-payload collision geometry or a server-side contraption entity graph to
the client renderer, so collision/restoration remains authoritative and
discrete until that broader bridge exists.

## Arbitrary payload bridge boundary

The legacy capture path is intentionally not replaced by another chest-specific
case. `native/bearing.rs` follows super glue and chassis/sticker attachment
edges, snapshots each `BlockState`, block-entity NBT and mounted item/entity
state, and captures the same shapes for rotated collision. The pinned typed SDK
can read `LevelRef::block`, `LevelRef::block_state`,
`HostBlockStates::block_state_string`, `BlockEntityRef::data`,
`LevelRef::collision_boxes`, and `LevelRef::entities_in`; it can write a
specific `BlockState` with `LevelRef::set_block` and restore NBT with
`BlockEntityRef::merge_data`.

That surface has no public glue-area/attachment graph, arbitrary moving
contraption actor owner, mounted-item snapshot/restore contract, or captured
rotated collision-shape handle. A bounded scan could discover neighboring block
states, but it would be a new heuristic and would miss the legacy glue and
chassis rules. The smallest production bridge is therefore a server-side
attachment snapshot/actor layer that supplies the existing `MovedBlocks`,
`MountedItems`, rider and collision records to the typed Part; extending the
probe with more hard-coded block cases would not establish arbitrary payload
parity.

The retained Java flow gives that bridge a finite shape: seed the controller and
attached source, breadth-first follow chassis/sticker edges and glue-area
contacts, snapshot each relative block state, block-entity/item data and
vanilla entity data, then snapshot each block's local collision boxes. On
restore, rotate and round every relative position, reject occupied targets,
write the rotated state, merge block-entity NBT/items, restore vanilla entity
data, and remove temporary display/control entities. The typed Part currently
has the individual block/state/NBT/collision reads and writes, but no operation
that owns this graph as one moving actor or preserves its temporary entities
and rotated collision shapes. This is the exact next bridge, not a reason to
broaden the current chest probe.

## Evidence and remaining work

- Pure lifecycle: assembly, motion, rider landing, and conservation pass.
- Existing legacy fixtures remain the source-matched acceptance set for bearing,
  piston, pulley, elevator, and train behavior.
- The focused fixture passed independently on frozen candidate
  `native-0a875da-615d7c802370` using moving-probe source SHA
  `952f6218d064463c758f4afdc1dad915f9a812c2b6c95a64791e0b85940d570e`:
  chest+barrel state/NBT and 7+3 inventory conservation, 90-degree angular
  advancement, rider transport, MotionOffset-based save/reopen continuity,
  zero-power dismount, and occupied-target collision/safe-dismount. The exact
  candidate mod hashes were `native-mods.json`
  `44e32db0bd00c33025cb62364ed5f8432c4ff1c073a87f36740eefd88d596604` and
  `libmod_create_kinetic_probe.dylib`
  `692e5c82d749294fcc1a760db1e3a615979987a61a385231294aae4e39ff1c6f`.
- The pre-multi-block `0728db6` single-chest fixture also passed against that
  candidate with its collision target moved outside the new adjacent capture
  footprint; the unmodified historical obstacle coordinate is now itself an
  attached neighbor under the bounded capture rule.
- Still outside this checkpoint: arbitrary glued payload capture, host/guest
  convergence, train boarding, passenger restoration beyond the retained rider,
  and pixel-level offscreen render comparison.
- `native/fake_track.rs` changes from the coordinator checkout were not copied.

This is an intentionally partial checkpoint. It identifies the concrete
payload contract and testable conservation gate without claiming exhaustive
Create parity.
