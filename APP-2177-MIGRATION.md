# APP-2177 fan and Nozzle migration

## Starting state and finite case list

The legacy runtime already has broad Encased Fan coverage: four processing
types, speed interruption, loose-item traces, obstruction/distance boundaries,
idle and active item reopen, and a LAN Depot output flow. Nozzle placement,
item impulses, support removal and survival crafting also have legacy evidence.
Those results remain valid for that runtime; they do not verify the frozen SDK
adapter.

This ticket's bounded SDK pass is:

| Area | Cases | Current result |
| --- | --- | --- |
| Shared airflow rules | RPM 0, ±16, ±256 and over-range; axis sign; 3–20 block reach | Pure production helper, 4 focused tests pass |
| Depot processing | Washing, smoking, blasting and haunting; 16/17-item timer boundary; output conservation and full-output recovery | Existing legacy checks; SDK adapter open |
| Loose item airflow | Positive/reversed flow, velocity easing and obstruction/distance boundary | Existing legacy checks; SDK adapter open |
| Nozzle entities | Item, mob and player push/pull; 1.5-block pull exclusion; crouching, line of sight and 20-block cap | Impulse kernel tested; SDK query/effect adapter open |
| Persistence | Idle and active Fan/Nozzle save and reopen, retaining operation and affected inventory/entities | SDK runtime check open |
| Multiplayer | Host action and guest observation of processing and Nozzle movement | SDK host/guest check open |

Exact particles, animation phase, exhaustive recipes and packet-arrival timing
remain outside this pass unless they expose a gameplay defect.

## Changes in this checkpoint

`native/fan_airflow_math.rs` extracts the small numerical rules needed by both
adapters: fan reach and direction, batched Depot timer transitions, loose-item
velocity easing, and Nozzle impulses for items, mobs or players. The legacy Fan,
loose-item and Nozzle item paths now call that shared module, so the existing
runtime and the next typed adapter can use the same equations.

This is a preparation checkpoint, not the gameplay migration. No production
typed-Part registration, real fan/entity query, recipe transfer, save/reopen,
offscreen render, or LAN result is claimed here. The production package owner
(APP-2172) owns the shared package registration seam, and the kinetic/transmission
adapter owner (APP-2173) owns fan speed integration. The pinned 0a875da API
surface includes [`LevelRef::entities_in`](https://github.com/arismoko/horizon/blob/0a875da91dbb0fdcb7ba8c42c11341aa229af51a/crates/horizon-mod-vocab/src/host/levels.rs),
[`entity_set_velocity`](https://github.com/arismoko/horizon/blob/0a875da91dbb0fdcb7ba8c42c11341aa229af51a/crates/horizon-mod-vocab/src/host/entities.rs)
and [`player_set_velocity`](https://github.com/arismoko/horizon/blob/0a875da91dbb0fdcb7ba8c42c11341aa229af51a/crates/horizon-mod-vocab/src/host/players.rs),
so entity effects can be implemented through the selected SDK; no API gap has
been established.

## Reproduction

Source baseline: Create `ac0c444d9828da3453ae8cc65338e8de063286fb`; repository
baseline `cc12664`. The focused production-rule test is dependency-free:

```sh
rustc --edition=2024 --test native/fan_airflow_math.rs -o /tmp/app2177-fan-airflow-tests
/tmp/app2177-fan-airflow-tests
```

Result: 4 passed. This does not identify a Horizon native build or content-pack
hash. The frozen-SDK build, actual headless gameplay, persistence, host/guest and
render checks remain open.
