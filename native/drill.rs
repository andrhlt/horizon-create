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

use super::create_machines::{float, int, offset};
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
