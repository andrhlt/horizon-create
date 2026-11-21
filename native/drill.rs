use std::sync::atomic::{AtomicI32, Ordering};

use horizon_core::{
    geometry::{Direction, Vec3},
    random::RandomSource,
};
use horizon_world::{
    level::{LevelAccess, PlacementContext},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use crate::containers::ModBlockEntity;

use super::create_bearing::{deposit, relative};
use super::create_depot::compound;
use super::create_machines::{float, int, offset, string};
use super::create_visuals::wheel_angle;
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const DRILL: &str = "create:mechanical_drill";
pub(super) const ENTITY: &str = "create:drill";
pub(super) const HEAD: &str = "create:block/mechanical_drill/head";
const LAZY_SLOT: usize = 3;
const BREAKER_SLOT: usize = 4;
static NEXT_BREAKER: AtomicI32 = AtomicI32::new(-1);

pub(super) fn new_tag() -> Compound {
    Compound::from([
        ("Progress".into(), Tag::Int(0)),
        ("NextTick".into(), Tag::Int(0)),
    ])
}

pub(super) fn neighbor_changed(entity: &mut ModBlockEntity) {
    entity.nbt.insert("NextTick".into(), Tag::Int(1));
}

fn state_at(game: &Game<'_>, pos: [i32; 3]) -> BlockStateId {
    game.world.block(pos[0], pos[1], pos[2])
}

fn advance_lazy_tick(entity: &mut ModBlockEntity) {
    if entity.data.len() <= BREAKER_SLOT {
        entity.data.resize(BREAKER_SLOT + 1, 0);
        entity.data[LAZY_SLOT] = 10;
    }
    if entity.data[LAZY_SLOT] == 0 {
        entity.data[LAZY_SLOT] = 10;
        if int(&entity.nbt, "NextTick") == Some(-1) {
            neighbor_changed(entity);
        }
    } else {
        entity.data[LAZY_SLOT] -= 1;
    }
}

fn crack(game: &mut Game<'_>, entity: &mut ModBlockEntity, target: [i32; 3], progress: i32) {
    if entity.data[BREAKER_SLOT] == 0 {
        entity.data[BREAKER_SLOT] = NEXT_BREAKER.fetch_sub(1, Ordering::Relaxed);
    }
    game.native_set_break_progress(entity.data[BREAKER_SLOT], target, progress);
}

fn remove_target(game: &mut Game<'_>, target: [i32; 3]) {
    let center =
        target.map(|c| f64::from(c) + 0.5 + (game.world.random.next_double() - 0.5) * 0.125);
    if let Some(drops) = game.native_machine_destroy_block(target, None, true) {
        for stack in drops {
            game.add_item_entity(stack, center, Some([0.0; 3]), 10);
        }
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    advance_lazy_tick(entity);
    if rpm == 0.0 {
        return;
    }
    let delay = int(&entity.nbt, "NextTick").unwrap_or(0);
    if delay < 0 {
        return;
    }
    entity.nbt.insert("NextTick".into(), Tag::Int(delay - 1));
    if delay > 0 {
        return;
    }
    let Some(facing) = super::create_fan::facing(game, state_at(game, pos)) else {
        return;
    };
    let target = offset(pos, facing.normal());
    let state = state_at(game, target);
    let properties = game.res.behaviours().facts(state);
    let hardness = properties.hardness;
    let current = int(&entity.nbt, "Progress").unwrap_or(0).clamp(0, 9);
    if hardness < 0.0
        || game.res.behaviours().is_air(state)
        || matches!(
            game.native_state_block(state),
            Some("minecraft:water" | "minecraft:lava")
        )
        || game
            .native_state_block(state)
            .is_some_and(|block| game.block_in_tag("create:non_breakable", block))
    {
        if current != 0 {
            entity.nbt.insert("Progress".into(), Tag::Int(0));
            crack(game, entity, target, -1);
        }
        return;
    }

    let speed = rpm.abs() / 100.0;
    let added = ((speed / hardness) as i32).clamp(1, 10 - current);
    let progress = current + added;
    if progress == 10 {
        remove_target(game, target);
        entity.nbt.insert("Progress".into(), Tag::Int(0));
        entity.nbt.insert("NextTick".into(), Tag::Int(-1));
        crack(game, entity, target, -1);
    } else {
        entity.nbt.insert("Progress".into(), Tag::Int(progress));
        entity
            .nbt
            .insert("NextTick".into(), Tag::Int((hardness / speed) as i32));
        crack(game, entity, target, progress);
    }
}

fn actor_pos(block: &Compound, key: &str) -> Option<[i32; 3]> {
    match block.get(&key.into()) {
        Some(Tag::IntArray(pos)) => pos.as_slice().try_into().ok(),
        _ => None,
    }
}

fn set_actor_pos(block: &mut Compound, key: &str, pos: [i32; 3]) {
    block.insert(key.into(), Tag::IntArray(pos.to_vec()));
}

fn actor_int(block: &Compound, key: &str) -> Option<i32> {
    match block.get(&key.into()) {
        Some(Tag::Int(value)) => Some(*value),
        _ => None,
    }
}

fn actor_set_int(block: &mut Compound, key: &str, value: i32) {
    block.insert(key.into(), Tag::Int(value));
}

fn actor_breaker(block: &mut Compound) -> i32 {
    if let Some(id) = actor_int(block, "BreakerId") {
        return id;
    }
    let id = NEXT_BREAKER.fetch_sub(1, Ordering::Relaxed);
    actor_set_int(block, "BreakerId", id);
    id
}

fn can_break(game: &Game<'_>, pos: [i32; 3]) -> bool {
    let state = state_at(game, pos);
    let facts = game.res.facts().get(state);
    facts.hardness >= 0.0
        && !game.res.behaviours().is_air(state)
        && !game.native_block_collision(pos).is_empty()
        && game.native_state_block(state) != Some("minecraft:moving_piston")
        && !game.native_state_block(state).is_some_and(|block| {
            matches!(block, "minecraft:water" | "minecraft:lava")
                || game.block_in_tag("create:non_breakable", block)
                || game.block_in_tag("create:tracks", block)
        })
}

/// Permit a linear contraption to enter a cell only when its forward-facing
/// drill can reach that cell and the pinned breaker rules allow it.
pub(super) fn allows_obstruction(
    game: &Game<'_>,
    blocks: &[Compound],
    next_anchor: [i32; 3],
    blocked: [i32; 3],
    motion: [i32; 3],
) -> bool {
    blocks.iter().any(|block| {
        let Some(state_tag) = compound(block, "BlockState") else {
            return false;
        };
        if string(state_tag, "Name").as_deref() != Some(DRILL) {
            return false;
        }
        let Some(state) = game.state_from_nbt(&Tag::Compound(state_tag.clone())) else {
            return false;
        };
        let Some(face) = super::create_fan::facing(game, state) else {
            return false;
        };
        let normal = face.normal();
        if normal != motion {
            return false;
        }
        let local = relative(block);
        let target = std::array::from_fn(|i| {
            (f64::from(next_anchor[i] + local[i]) + 0.5 + f64::from(normal[i]) * 0.65)
                .floor() as i32
        });
        target == blocked && can_break(game, blocked)
    })
}

/// Run the pinned DrillMovementBehaviour rules for a drill mounted on a
/// translating contraption. The block compound is the actor's persistent
/// MovementContext data, so progress survives a stalled step and save/reopen.
pub(super) fn translate(
    game: &mut Game<'_>,
    blocks: &mut [Compound],
    previous: [f64; 3],
    current: [f64; 3],
    minimum_speed: f32,
) -> bool {
    let motion = std::array::from_fn::<_, 3, _>(|i| current[i] - previous[i]);
    let mut stalled = false;
    for index in 0..blocks.len() {
        let (before, actor_and_after) = blocks.split_at_mut(index);
        let Some((block, after)) = actor_and_after.split_first_mut() else {
            continue;
        };
        let Some(state_tag) = compound(block, "BlockState") else {
            continue;
        };
        if string(state_tag, "Name").as_deref() != Some(DRILL) {
            continue;
        }
        let Some(state) = game.state_from_nbt(&Tag::Compound(state_tag.clone())) else {
            continue;
        };
        let Some(face) = super::create_fan::facing(game, state) else {
            continue;
        };
        let breaker = actor_breaker(block);
        let normal = face.normal();
        let local = relative(block);
        let target = std::array::from_fn(|i| {
            (current[i] + f64::from(local[i]) + 0.5 + f64::from(normal[i]) * 0.65).floor() as i32
        });
        set_actor_pos(block, "LastDrillCell", target);
        let forward = motion
            .into_iter()
            .zip(normal)
            .map(|(step, sign)| step * f64::from(sign))
            .sum::<f64>();
        if motion.into_iter().all(|step| step == 0.0) {
            if let Some(break_at) = actor_pos(block, "BreakingPos") {
                block.remove(&"BreakingPos".into());
                block.remove(&"Progress".into());
                block.remove(&"TicksUntilNextProgress".into());
                game.native_set_break_progress(
                    breaker,
                    break_at,
                    -1,
                );
            }
            continue;
        }
        if actor_pos(block, "BreakingPos").is_none() && forward > 0.0 && can_break(game, target) {
            set_actor_pos(block, "BreakingPos", target);
            actor_set_int(block, "Progress", 0);
            actor_set_int(block, "TicksUntilNextProgress", 0);
        }
        let Some(break_at) = actor_pos(block, "BreakingPos") else {
            continue;
        };
        if !can_break(game, break_at) {
            block.remove(&"BreakingPos".into());
            block.remove(&"Progress".into());
            block.remove(&"TicksUntilNextProgress".into());
            game.native_set_break_progress(
                breaker,
                break_at,
                -1,
            );
            continue;
        }
        let wait = actor_int(block, "TicksUntilNextProgress").unwrap_or(0);
        if wait > 0 {
            actor_set_int(block, "TicksUntilNextProgress", wait - 1);
        } else {
            let motion_length = motion
                .into_iter()
                .map(|v| v * v)
                .sum::<f64>()
                .sqrt();
            let signed_length = -motion_length;
            let animation_speed = ((
                (signed_length * 1000.0 + 100.0 * signed_length.signum()) as i32 / 100
            ) * 100) as f32;
            let speed = (animation_speed.abs() / 500.0).clamp(minimum_speed, 16.0);
            let hardness = game.res.facts().get(state_at(game, break_at)).hardness;
            let progress = actor_int(block, "Progress").unwrap_or(0)
                + ((speed / hardness) as i32)
                    .clamp(1, 10 - actor_int(block, "Progress").unwrap_or(0));
            if progress >= 10 {
                game.native_set_break_progress(breaker, break_at, -1);
                if let Some(drops) = game.native_machine_destroy_block(break_at, None, true) {
                    let mut rest = drops;
                    for stack in rest.drain(..) {
                        let limit = game
                            .items()
                            .get(&stack.item)
                            .map_or(64, |item| item.max_stack);
                        if let Some(left) = deposit(before, stack, limit)
                            .and_then(|left| deposit(after, left, limit))
                        {
                            game.pop_resource(break_at, left);
                        }
                    }
                }
                block.remove(&"BreakingPos".into());
                block.remove(&"Progress".into());
                block.remove(&"TicksUntilNextProgress".into());
            } else {
                actor_set_int(block, "Progress", progress);
                actor_set_int(
                    block,
                    "TicksUntilNextProgress",
                    (hardness / speed).max(0.0) as i32,
                );
                game.native_set_break_progress(breaker, break_at, progress);
            }
        }
        stalled |= actor_pos(block, "BreakingPos").is_some();
    }
    stalled
}

pub(super) fn placement(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    if level.native_state_block(state) != Some(DRILL) {
        return None;
    }
    let mut preferred: Option<Direction> = None;
    for side in Direction::ALL {
        let [x, y, z] = side.normal();
        let Some(block) = level
            .registry
            .state(level.block_state(context.pos.offset(x, y, z)))
        else {
            continue;
        };
        let axis = if x != 0 {
            "x"
        } else if y != 0 {
            "y"
        } else {
            "z"
        };
        let rear = super::create_fluids::name(side.opposite());
        let connects = match block.name.as_str() {
            "create:shaft" | "create:andesite_encased_shaft" | "create:brass_encased_shaft" => {
                block
                    .properties
                    .get("axis")
                    .is_some_and(|value| value == axis)
            }
            "create:creative_motor" => block
                .properties
                .get("facing")
                .is_some_and(|value| value == rear),
            "create:mechanical_drill" | "create:hand_crank" => block
                .properties
                .get("facing")
                .is_some_and(|value| value == super::create_fluids::name(side)),
            _ => false,
        };
        if !connects {
            continue;
        }
        if preferred.is_some_and(|old| old != side && old.opposite() != side) {
            preferred = None;
            break;
        }
        preferred = Some(side);
    }
    let [x, y, z] = super::view_vector(context.yaw, context.pitch);
    let looking = Direction::approximate_nearest(Vec3::new(x, y, z));
    let facing = if context.sneaking {
        looking
    } else {
        preferred.unwrap_or(looking).opposite()
    };
    let water = level
        .registry
        .state(level.block_state(context.pos))
        .is_some_and(|block| {
            block.name == "minecraft:water"
                && block
                    .properties
                    .get("level")
                    .is_none_or(|value| value == "0")
        });
    let state =
        level.native_state_with_property(state, "facing", super::create_fluids::name(facing))?;
    level.native_state_with_property(state, "waterlogged", if water { "true" } else { "false" })
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(facing) = super::create_fan::facing(game, state) else {
        return;
    };
    let rpm = float(&entity.nbt, "Speed").unwrap_or(0.0);
    let (yaw, pitch) = match facing {
        Direction::East => (90.0, 0.0),
        Direction::West => (270.0, 0.0),
        Direction::North => (180.0, 0.0),
        Direction::Up => (0.0, -90.0),
        Direction::Down => (0.0, 90.0),
        _ => (0.0, 0.0),
    };
    let negative = facing.normal().iter().sum::<i32>() < 0;
    let angle = wheel_angle(
        draw.game_time,
        draw.partial,
        if negative { -rpm } else { rpm },
        0.0,
    );
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], pitch, [0.5; 3]);
    draw.rotate_about([0.0, 0.0, 1.0], angle, [0.5; 3]);
    game.native_draw_model(draw, HEAD, 0xffffff);
    draw.pop();
}
