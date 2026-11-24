# APP-2177 Fan and Nozzle migration

## Delivered scope

The pinned 0a content schema rejected `waterloggable` as a block property and
`place_block` on block items. Waterlogging remains represented by supported
`waterlogged` state properties (including their false defaults), and placeable
items use the supported `block` target. `tools/test-app2177-content-schema.py`
checks all 52 affected block definitions and five item definitions.

`native/create_fan_nozzle_adapter.rs` registers the production Nozzle part and
implements powered Fan airflow, saved processing state, recipe output,
obstruction/range queries, and Nozzle item/living-player impulses through the
typed SDK. The Fan is registered as a terminal on the existing
`create:simple_kinetic` part. Its signed RPM is supplied by APP-2173's kinetic
graph; fan processing and airflow advance from that Fan's own block-entity
server tick, so a multi-motor graph cannot multiply the per-Fan work. Fan
processing state and Nozzle range/entity tracking are stored on their block
entities for normal synchronization and saves.

## Pinned production verification

Built through the typed `horizon-launcher native-build` route with optimized
profile against Horizon `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`, Rust 1.99.1,
and the prebuilt API. The selected build was `native-0a875da-ee0f9e377c6f`.
No legacy mixin tool bundle was used. The combined Create package loaded with
no omitted mods, registry warnings, or unknown feature references. Compiled
package tree SHA-256:
`75d8cc987d88b8ac5f8b2e8c7eef35011d38d6dc9f19b8b9360bb6298f755ede`.

`tools/test-app2177-production-offline-route.py` ran two distinct whitelisted
offline UUIDs on an isolated localhost dedicated server and offscreen clients.
The run passed these gameplay checks:

- A 32 RPM Fan registered as a kinetic terminal with 64 stress and moved a
  representative item forward; -32 RPM reversed its item motion; zero RPM
  stopped the Fan.
- A crushed raw zinc item in the water lane became a zinc nugget through the
  production recipe path.
- The supported Nozzle pushed and pulled both host and guest players under
  positive and reversed Fan RPM. Both clients observed the Nozzle facing state.
- The Fan's speed and item tracking, the Nozzle's active range and tracked
  entities, the processed output, and a signed geared output survived server
  save/reopen. The reopened server retained `Speed: 32.0f`, `Stress: 64.0f`,
  `CreateNozzleRange: 5.125f`, and `create:zinc_nugget`.

Run receipt for the pinned package is available at
`/private/tmp/app2177-production-rebased-final/two-client-proof.json` in the
verification environment. The run used content hash
`252cddb41a7acd475012a3e482ec6225030384f44889f40057b6d1bb05d4d06d` and two
separate offline identities. The committed route script is the reproducible
record of setup and assertions.

## Bounded remaining parity

The production runtime route covers representative item processing and player
movement. The broader legacy Fan/Nozzle suites remain useful evidence, but this
pass does not claim every recipe, mob/item Nozzle combination, visual effect,
or exact Java timing. Those details remain Full 1:1 follow-ups in the feature
matrix; they do not block the practical gameplay scope delivered here.
