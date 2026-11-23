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
and one rider. It covers start, motion, safe dismount, and one-shot disassembly
with inventory conservation. The pure lifecycle checks are in
`tools/test-moving-slice.py` and run without a game window or input.

The typed-Part base is PR #192 at `9009897f5461d3e0662b7114dd2a87ac42d417f4`.
Its verified SDK boundary supplies block-entity save/load, server ticks, client
draw submission, and collision queries. The next integration patch must bind
the existing bearing capture/restore path to those callbacks; this PR does not
claim train, passenger, or LAN parity yet.

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
