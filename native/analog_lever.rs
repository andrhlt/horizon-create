use horizon_client::first_person::Hand;
use horizon_client::particles::{ParticleOptions, ParticleType};
use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};

use super::create_machines::{float, int, mod_entity, set_float};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const LEVER: &str = "create:analog_lever";
const HANDLE: &str = "create:block/analog_lever/handle";
const INDICATOR: &str = "create:block/analog_lever/indicator";
const DELAY: i32 = 15;

pub(super) fn new_tag() -> Compound {
    Compound::from([
        ("State".into(), Tag::Int(0)),
        ("ChangeTimer".into(), Tag::Int(0)),
    ])
}

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([HANDLE, INDICATOR].map(String::from));
}

pub(super) fn strength(nbt: &Compound) -> i32 {
    int(nbt, "State").unwrap_or(0).clamp(0, 15)
}

fn connected(face: &str, facing: Direction) -> Direction {
    match face {
        "floor" => Direction::Up,
        "ceiling" => Direction::Down,
        _ => facing,
    }
}

fn read_facing(facing: &str) -> Direction {
    match facing {
        "south" => Direction::South,
        "east" => Direction::East,
        "west" => Direction::West,
        _ => Direction::North,
    }
}

pub(super) fn source(level: &GameLevel<'_>, state: BlockStateId, result: &mut bool) {
    *result |= level
        .registry
        .state(state)
        .is_some_and(|state| state.name == LEVER);
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    face: Direction,
    direct: bool,
    result: &mut i32,
) {
    let Some(state) = level
        .registry
        .state(state)
        .filter(|state| state.name == LEVER)
    else {
        return;
    };
    let attach = state.properties.get("face").map_or("floor", |p| p.as_str());
    let facing = read_facing(
        state
            .properties
            .get("facing")
            .map_or("north", |p| p.as_str()),
    );
    let correct_side = !direct || face == connected(attach, facing).opposite();
    *result = match level.world.block_entities.get(&(pos.x, pos.y, pos.z)) {
        Some(BlockEntity::Mod(entity)) if correct_side => strength(&entity.nbt),
        _ => 0,
    };
}

pub(super) fn tick(game: &mut Game<'_>, pos: (i32, i32, i32)) {
    let at = [pos.0, pos.1, pos.2];
    let Some(timer) = mod_entity(game, at)
        .filter(|entity| entity.id == LEVER)
        .and_then(|entity| int(&entity.nbt, "ChangeTimer"))
        .filter(|&timer| timer > 0)
    else {
        return;
    };
    game.native_with_mod_block_entity(at, |entity| {
        entity.nbt.insert("ChangeTimer".into(), Tag::Int(timer - 1));
    });
    if timer != 1 {
        return;
    }
    let attach = game.native_block_property(at, "face");
    let facing = game.native_block_property(at, "facing");
    let [dx, dy, dz] = connected(
        attach.as_deref().unwrap_or("floor"),
        read_facing(facing.as_deref().unwrap_or("north")),
    )
    .opposite()
    .normal();
    let state = game.world.block(at[0], at[1], at[2]);
    let lever = BlockPos::new(at[0], at[1], at[2]);
    game.with_level(|behaviours, level, ticks| {
        let block = behaviours.block(state);
        behaviours.update_neighbors_at(level, ticks, lever, block);
        behaviours.update_neighbors_at(level, ticks, lever.offset(dx, dy, dz), block);
    });
    super::create_machines::flush_chain_gearshifts(game);
    super::create_controller_rail::flush(game);
}

fn chase(from: f32, target: f32) -> f32 {
    if (f64::from(from) - f64::from(target)).abs() < 1e-5 {
        target
    } else {
        (f64::from(from) + f64::from(0.2_f32) * (f64::from(target) - f64::from(from))) as f32
    }
}

fn animation(nbt: &Compound, now: i64) -> (f32, f32) {
    let target = strength(nbt) as f32;
    let Some(Tag::Long(start)) = nbt.get(&"AnimationTick".into()) else {
        return (target, target);
    };
    let mut current = float(nbt, "AnimationStart").unwrap_or(target);
    let mut previous = current;
    for _ in 0..now.saturating_sub(*start).clamp(0, 128) {
        previous = current;
        current = chase(current, target);
    }
    (previous, current)
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if *canceled || game.native_block(pos) != LEVER {
        return;
    }
    if game.hand != Hand::Main
        || game
            .held()
            .is_some_and(|item| item.item.as_ref() == "create:wrench")
    {
        return;
    }
    let change = if game.native_sneaking() { -1 } else { 1 };
    let now = game.world.game_time;
    let Some(value) = game.native_with_mod_block_entity(pos, |entity| {
        let old = strength(&entity.nbt);
        let next = (old + change).clamp(0, 15);
        if old != next {
            let (_, current) = animation(&entity.nbt, now);
            set_float(&mut entity.nbt, "AnimationStart", current);
            entity.nbt.insert("AnimationTick".into(), Tag::Long(now));
            entity.nbt.insert("State".into(), Tag::Int(next));
            entity.nbt.insert("ChangeTimer".into(), Tag::Int(DELAY));
        }
        next
    }) else {
        return;
    };
    game.native_block_entity_sync(pos);
    let center = pos.map(|n| f64::from(n) + 0.5);
    let pitch = 0.25 + ((value + 5) as f32 / 15.0) * 0.5;
    game.native_play_sound_in_place("minecraft:block.lever.click", center, 4, 0.2, pitch);
    let attach = game.native_block_property(pos, "face");
    let facing = game.native_block_property(pos, "facing");
    let facing = read_facing(facing.as_deref().unwrap_or("north"));
    let side = connected(attach.as_deref().unwrap_or("floor"), facing);
    let backward = facing.opposite().normal();
    let attachment = side.opposite().normal();
    let point = std::array::from_fn(|i| {
        center[i] + 0.1 * f64::from(backward[i]) + 0.2 * f64::from(attachment[i])
    });
    let mut dust = ParticleOptions::simple(ParticleType::Dust);
    dust.color = [1.0, 0.0, 0.0, 1.0];
    dust.scale = 1.0;
    if let Some(player) = game.native_acting_player() {
        game.native_send_particles_to(player.uuid, &dust, None, point, [0.0; 3], 0.0, 0, false);
    } else {
        game.native_add_particle(&dust, point, [0.0; 3]);
    }
    game.swing_arm();
    if game.lan_acting.is_some() && game.held().is_some() {
        game.guest_inventory_resend = true;
    }
    *canceled = true;
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(state) = game.pack.assets.registry.state(state) else {
        return;
    };
    let pitch = match state.properties.get("face").map(|value| value.as_str()) {
        Some("wall") => 90.0,
        Some("ceiling") => 180.0,
        _ => 0.0,
    };
    let yaw = match state.properties.get("facing").map(|value| value.as_str()) {
        Some("east") => 90.0,
        Some("south") => 0.0,
        Some("west") => 270.0,
        _ => 180.0,
    };
    let (previous, current) = animation(&entity.nbt, draw.game_time);
    let interpolated = (f64::from(previous)
        + f64::from(draw.partial) * (f64::from(current) - f64::from(previous)))
        as f32;
    let fraction = interpolated / 15.0;
    let color = (((44.0 + 161.0 * fraction) as u32) << 16) | (((3.0 - 3.0 * fraction) as u32) << 8);
    let x = [1.0, 0.0, 0.0];
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.rotate_about(x, pitch, [0.5; 3]);
    game.native_draw_model(draw, INDICATOR, color);
    draw.rotate_about(x, fraction * 90.0, [0.5, 1.0 / 16.0, 0.5]);
    game.native_draw_model(draw, HANDLE, 0xffffff);
    draw.pop();
}
