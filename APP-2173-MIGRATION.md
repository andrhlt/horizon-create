# APP-2173 kinetic and transmission delivery

## Production entry point

The production native mod is `migration/create` with package ID `create`.
`Hooks::register` in `migration/create/src/lib.rs` registers the Create raw recipe
serializers, then calls `kinetic_adapter::register(registrar)` and
`kinetic_controls::register(registrar)`. The flat native package includes the
normalized Create content at its root; it cannot load a second content-only mod
with the same `create` ID. `tools/prepare-create-native.py` stages this package
from the checked-in Rust sources and APP-2172's content artifact.

The kinetic adapter owns the `create:simple_kinetic` block-entity type used by
shafts, cogwheels, Gearbox, Clutch, Gearshift, chain drives and Flywheel. The
controls adapter registers Sequenced Gearshift and Rotation Speed Controller
parts and handles their real menu input through `ScreenClickEvent` and
`MenuButtonEvent`. That menu callback mutates the event's live block entity so
the setting is saved and synchronized. APP-2172 confirmed the canonical
`migration/create/` package ID and `Hooks::register` contract, including these
adapter registration calls. APP-2172 will reconcile this package in its own
branch; APP-2173 retains integration and acceptance ownership.

## Bounded acceptance cases

The production package passed the following cases on the pinned 0a runtime:

| Case | Observed result |
| --- | --- |
| Motor, shaft, clutch and Gearshift | +32 RPM transmission; powered Clutch stopped the output; unpowered recovery resumed; powered Gearshift reversed output to -32 RPM |
| Conflicting source | Opposing source rejected; established network stayed at +32 RPM |
| Cogwheel ratio | Large-to-small pair drove output at -64 RPM |
| Loop handling | Consistent four-cogwheel loop stayed driven at +32 RPM; inconsistent four-Gearbox loop resolved to 0 RPM |
| Overload and recovery | One Millstone after 13 large-to-small stages raised stress to 1,048,576 against 524,288 capacity and stopped the motor; removing the load restored +32 RPM and zero stress |
| Gearbox and Flywheel | Gearbox output and attached Flywheel ran at -32 RPM |
| Adjustable Chain Gearshift | Redstone signal 15 persisted and produced +16 RPM |
| Rotation Speed Controller | Client set the target to 64 RPM through its menu; connected output reached +64 RPM |
| Sequenced Gearshift | Client selected the reverse instruction through its menu; powered sequencer produced -32 RPM |
| Offline host and guest | Two distinct whitelisted UUIDs joined the same localhost server; both observed the Clutch power change |
| Save and reopen | Active +32/-64 transmissions, controller target/output and sequencer program/output survived server save, stop and reopen |

The complete route receipt is [migration/APP-2173-production-route.json](migration/APP-2173-production-route.json).
The repeatable headless route is
[tools/test-app-2173-production-route.py](tools/test-app-2173-production-route.py).
It requires the prepared pinned game resources, native build binaries, the
launcher, and APP-2172's `.hmod` as the content source. It uses an isolated
world, a two-name whitelist, offline localhost clients and cloned resources.

## Build and package evidence

Launcher 0.2.107 (`horizon-launcher 0.2.107`, SHA-256
`2b1cef3b1c36b5097b42447aee3abfb9f4459e5bbe3757d85e04fc8c2e06445c`)
successfully built the package against Horizon
`0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, Minecraft 26.3, mixins
`e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, Rust 1.99.1. Launcher 0.2.105
was checksum-checked but was not needed; 0.2.107 did not fail the cohort.
The production manifest contains only `create`, with no omitted mods. The
runtime registered 658 Create blocks, 711 items, four fluids and three entity
types, with an empty registry warning file.

The content normalizer records the 0a schema conversions in
[migration/APP-2173-content-normalization.json](migration/APP-2173-content-normalization.json): it removed 203 unsupported
block properties, translated nine fields, normalized one loot condition, added
two controller menus and removed duplicate generated fluid block/item
definitions. Runtime startup still skips 27 recipes whose
`neoforge:tag_empty` load conditions are unsupported, and reports two unknown
worldgen feature references (`create:striated_ores_overworld` and
`create:zinc_ore`). These imported content limitations are recorded separately
from the passed kinetic gameplay cases; they are not claims of complete Create
parity.

## Remaining nonblocking follow-ups

The finite APP-2173 gameplay cases above pass. Full 1:1 remains open in the
feature matrix. This pass does not establish exhaustive orientation/property
cross-products, Java-equivalent animation or packet timing, Adjustable Chain
Gearshift overspeed breaking, or survival acquisition through the skipped
worldgen and conditional recipes. Those remain explicit follow-up work rather
than blockers to the recorded kinetic transmission acceptance.
