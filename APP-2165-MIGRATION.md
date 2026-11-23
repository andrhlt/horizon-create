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
step (`rpm * 360 / 60 / 20`), captures a chest in the bearing's immediate
glued footprint, rounds its Y-axis transform to world blocks, and carries the
captured rider by the same discrete delta. A zero motor setting terminates at
the current rotated position and uses the existing safe-dismount path. The
linear no-motor path remains unchanged as a regression. The focused runtime
fixture is `tools/test-typed-bearing-rotation.py`; it is a bounded one-chest
rotation check, not full glue graph, actor, guest, or legacy `MovedBlocks`
parity.

The typed client seam now also has a continuous render bridge: the bearing's
`block_entity_submit` reads synchronized angle/RPM, applies the partial-tick
angular phase with `BlockEntityDrawContext::rotate_about`, and submits the
captured chest model through `block`. This is the smallest supported visual
closure for the retained slice. The public surface does not expose arbitrary
moving-payload collision geometry or a server-side contraption entity graph to
the client renderer, so collision/restoration remains authoritative and
discrete until that broader bridge exists.

## Evidence and remaining work

- Pure lifecycle: assembly, motion, rider landing, and conservation pass.
- Existing legacy fixtures remain the source-matched acceptance set for bearing,
  piston, pulley, elevator, and train behavior.
- Not yet verified on the frozen post-API runtime: block/entity registration,
  actual world payload capture, host/guest convergence, save/reopen, collision
  against moving payloads, train boarding, passenger restoration, or offscreen
  moving render output.
- `native/fake_track.rs` changes from the coordinator checkout were not copied.

This is an intentionally partial checkpoint. It identifies the concrete
payload contract and testable conservation gate without claiming exhaustive
Create parity.
