# APP-2184 redstone controls on Horizon 0a

## Scope and result

This pass adds a native SDK adapter for selected redstone controls to the
production Create package path. It registers Analog Lever, Redstone Contact,
Elevator Contact, Desk Bell, Rose Quartz Lamp, Powered Latch, Powered Toggle
Latch, Pulse Repeater, Pulse Extender, and Pulse Timer. The Analog Lever uses a
0–15 content state and delayed server update; contact, bell, latch, diode, and
lamp callbacks provide initial power behavior.

This is **not a gameplay-complete APP-2184 pass**. The module does not yet
implement Redstone Link wireless channels, Linked Controller bindings,
Peculiar/Haunted Bell behavior, Stockpile Switch configuration, Smart Observer
inventory detection, Display Link/Board data flow, or Nixie text. Settings and
full Create interactions for the diode family are incomplete. Existing
FEATURE-MATRIX rows describe the legacy native build and its evidence; that
evidence does not transfer to the new 0a SDK package.

## Build evidence

- Horizon: `0a875da91dbb0fdcb7ba8c42c11341aa229af51a`.
- Rust/SDK: `1.99.1`; mixins `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`.
- Content archive: `/private/tmp/app2184-create-0a.hmod`, SHA-256
  `af8788600eb8159179cf04f94cebe03065184b104718c215a223583bae6ed949`.
- Content was regenerated with `tools/prepare.py` from pinned Create
  `ac0c444d9828da3453ae8cc65338e8de063286fb`, then converted with
  `tools/prepare-0a-content-pack.py`. The converter report is
  `.local/app2184-0a-content-report.json`; it records 202 removed unsupported
  properties and the optional-recipe/worldgen conversions.
- `prepare-create-native.py` staged the complete package at
  `/private/tmp/app2184-create-stage-v2` and `cargo check --offline` passed
  against the pinned SDK. Three warnings are in the pre-existing kinetic
  modules (`next_active` assignment and unused motor-setting helpers).

## Open acceptance gates

The fresh package has not been built into the Horizon runtime or exercised in
gameplay. No redstone Java trace, host/guest agreement, save/reopen, or affected
regression is claimed for this SDK adapter. Before APP-2184 can pass its finite
gameplay baseline, migrate the remaining scoped families, restore complete
configuration and interaction paths, then run the applicable existing
comparison cases on the fresh package: Analog Lever 0/7/15 and debounce;
matching/mismatched contacts; powered latch and diode edge/held/boundary
settings; bell pulse/facing; and lamp neighbor power. Include host and guest
actions plus representative idle/active save/reopen for stateful controls.

The broader families listed above remain linked blockers. Cosmetic and
exhaustive Full 1:1 work can remain open after the finite gameplay gates pass.
