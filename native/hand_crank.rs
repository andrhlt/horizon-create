use std::sync::OnceLock;

use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use horizon_client::first_person::Hand;

use super::create_fan::facing;
use super::create_machines::{crank_input_rpm, float, int, reading, set_float};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const CRANK: &str = "create:hand_crank";
const BASE_MODEL: &str = "create:block/hand_crank/block";
const HANDLE_MODEL: &str = "create:block/hand_crank/handle";
const USE_TICKS: i32 = 10;
const RPM: f32 = 32.0;
const ANGLE: usize = 3;
const ANGULAR_VELOCITY: usize = 4;
const CENTER: [f32; 3] = [0.5; 3];
const X: [f32; 3] = [1.0, 0.0, 0.0];
const Y: [f32; 3] = [0.0, 1.0, 0.0];
const Z: [f32; 3] = [0.0, 0.0, 1.0];

pub(super) fn preferred_direction(level: &GameLevel<'_>, pos: BlockPos) -> Option<Direction> {
    preferred_in_directions(level, pos, Direction::ALL)
}

pub(super) fn preferred_in_directions(
    level: &GameLevel<'_>,
    pos: BlockPos,
    directions: impl IntoIterator<Item = Direction>,
) -> Option<Direction> {
    let mut preferred_axis = None;
    let mut preferred = None;
    for direction in directions {
        let delta = direction.normal();
        let [x, y, z] = delta;
        let axis = delta.iter().position(|component| *component != 0)?;
        let neighbor = level.world.block(pos.x + x, pos.y + y, pos.z + z);
        let Some(state) = level.registry.state(neighbor) else {
            continue;
        };
        let name = |key| state.properties.get(key).map(String::as_str);
        let axis_value = ["x", "y", "z"][axis];
        let neighbor_facing = name("facing").and_then(super::machines::dir_from_name);
        let can_connect = match state.name.as_str() {
            "create:shaft"
            | super::create_flywheel::FLYWHEEL
            | "create:cogwheel"
            | "create:large_cogwheel"
            | "create:andesite_encased_shaft"
            | "create:brass_encased_shaft"
            | "create:large_water_wheel"
            | "create:crushing_wheel"
            | "create:powered_shaft"
            | "create:encased_chain_drive"
            | super::create_chain_gearshift::ADJUSTABLE
            | "create:gearshift"
            | "create:clutch"
            | super::create_speed_controller::CONTROLLER
            | "create:rope_pulley" => name("axis") == Some(axis_value),
            super::create_sequencer::SEQUENCER => {
                if name("vertical") == Some("true") {
                    axis == 1
                } else {
                    name("axis") == Some(axis_value)
                }
            }
            "create:creative_motor" => neighbor_facing == Some(direction.opposite()),
            CRANK | "create:encased_fan" | "create:mechanical_bearing" => neighbor_facing == Some(direction),
            name if super::create_valve::is_handle(name) => neighbor_facing == Some(direction),
            "create:water_wheel" => neighbor_facing.is_some_and(|face| face.normal()[axis] != 0),
            "create:gearbox" => name("axis").is_some_and(|value| value != axis_value),
            _ => false,
        };
        if can_connect {
            if preferred_axis.is_some_and(|selected| selected != axis) {
                return None;
            }
            preferred_axis = Some(axis);
            preferred = Some(direction.opposite());
        }
    }
    preferred
}

pub(super) fn generated(nbt: &Compound, face: Direction) -> f32 {
    if int(nbt, "InUse").unwrap_or(0) == 0 {
        return 0.0;
    }
    let backwards = int(nbt, "Backwards") == Some(1);
    let negative_face = matches!(face, Direction::Down | Direction::West | Direction::North);
    if backwards ^ negative_face { -RPM } else { RPM }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != CRANK || game.spectator() {
        return false;
    }
    // A client without a local use handler sends both hands. A normal
    // vanilla right-click stops at the crank's successful main-hand use.
    if game.hand != Hand::Main {
        return true;
    }
    let backwards = game.native_sneaking();
    let changed_rotation = game.native_with_mod_block_entity(pos, |crank| {
        let previous = int(&crank.nbt, "Backwards") == Some(1);
        let stopped = int(&crank.nbt, "InUse").unwrap_or(0) == 0;
        crank.nbt.insert("InUse".into(), Tag::Int(USE_TICKS));
        crank
            .nbt
            .insert("Backwards".into(), Tag::Byte(i8::from(backwards)));
        stopped || previous != backwards
    });
    if changed_rotation == Some(true)
        && let Some(face) = facing(game, game.world.block(pos[0], pos[1], pos[2]))
    {
        // A faster source drives the crank. Java breaks the crank if it
        // tries to turn against that source.
        let external = crank_input_rpm(game, pos);
        let negative_face = matches!(face, Direction::Down | Direction::West | Direction::North);
        if external.abs() > RPM && (external < 0.0) != (backwards ^ negative_face) {
            game.native_machine_destroy_block(pos, None, false);
        }
    }
    if let Some(player) = game.player.as_mut() {
        player.cause_food_exhaustion(RPM * 0.01);
    }
    game.swing_arm();
    true
}

pub(super) fn retain_support(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some(face) = facing(game, game.world.block(pos[0], pos[1], pos[2])) else {
        return true;
    };
    let rear = super::create_machines::offset(pos, face.opposite().normal());
    if game.world.loaded(rear[0], rear[2]) && game.native_block_collision(rear).is_empty() {
        game.native_machine_destroy_block(pos, None, false);
        return false;
    }
    true
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
) -> bool {
    let actual = rpm * 360.0 / 60.0 / 20.0;
    let previous_velocity = reading(entity, ANGULAR_VELOCITY);
    let velocity = previous_velocity + (actual - previous_velocity) / 4.0;
    let angle = reading(entity, ANGLE) + velocity;
    entity.data.resize(ANGULAR_VELOCITY + 1, 0);
    entity.data[ANGLE] = angle.to_bits() as i32;
    entity.data[ANGULAR_VELOCITY] = velocity.to_bits() as i32;

    let remaining = int(&entity.nbt, "InUse").unwrap_or(0);
    if remaining > 0 {
        entity.nbt.insert("InUse".into(), Tag::Int(remaining - 1));
        if game.world.game_time % 10 == 0 {
            let at = pos.map(|value| f64::from(value) + 0.5);
            let volume = remaining as f32 / 2.5;
            let pitch = (0.65 + (USE_TICKS - remaining) as f32 / 10.0) * 0.5;
            game.native_play_sound_in_place("create:cranking", at, 4, volume * 0.075, pitch);
            game.native_play_sound_in_place(
                "create:cranking_compounded_1",
                at,
                4,
                volume * 0.025,
                pitch,
            );
        }
    }
    if remaining > 0 || velocity.abs() > 1e-6 {
        game.native_block_entity_sync(pos);
    }
    remaining == 1
}

fn traced(pos: [i32; 3]) -> bool {
    static POSITION: OnceLock<Option<[i32; 3]>> = OnceLock::new();
    POSITION.get_or_init(|| {
        let value = std::env::var("CREATE_HAND_CRANK_TRACE").ok()?;
        let values = value
            .split(',')
            .map(str::parse)
            .collect::<Result<Vec<i32>, _>>()
            .ok()?;
        values.try_into().ok()
    }) == &Some(pos)
}

pub(super) fn trace_tick(game: &Game<'_>, pos: [i32; 3], entity: &ModBlockEntity) {
    if !traced(pos) {
        return;
    }
    eprintln!(
        "CREATE_HAND_CRANK_TICK {},{},{},{:.9},{:.9},{:.9},{:.9}",
        game.world.game_time,
        int(&entity.nbt, "InUse").unwrap_or(0),
        int(&entity.nbt, "Backwards") == Some(1),
        reading(entity, 0),
        reading(entity, 1),
        reading(entity, ANGLE),
        reading(entity, ANGULAR_VELOCITY),
    );
}

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([BASE_MODEL, HANDLE_MODEL].map(String::from));
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    set_float(&mut tag, "VisualAngle", reading(entity, ANGLE));
    set_float(
        &mut tag,
        "VisualAngularVelocity",
        reading(entity, ANGULAR_VELOCITY),
    );
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(face) = facing(game, state) else {
        return;
    };
    let (axis, base_pitch, base_yaw, handle_pitch, handle_yaw) = match face {
        Direction::Up => (Y, 0.0, 0.0, 90.0, 0.0),
        Direction::Down => (Y, 180.0, 0.0, -90.0, 0.0),
        Direction::North => (Z, -90.0, 0.0, 0.0, 0.0),
        Direction::East => (X, -90.0, -90.0, 0.0, -90.0),
        Direction::South => (Z, -90.0, 180.0, 0.0, 180.0),
        Direction::West => (X, -90.0, 90.0, 0.0, 90.0),
    };
    let perpendicular = pos
        .iter()
        .zip(axis)
        .filter(|(_, axis)| *axis == 0.0)
        .map(|(coordinate, _)| coordinate)
        .sum::<i32>();
    let phase = if perpendicular % 2 == 0 { 22.5 } else { 0.0 };
    let visual = |index, key| {
        if entity.data.get(index).is_some() {
            reading(entity, index)
        } else {
            float(&entity.nbt, key).unwrap_or(0.0)
        }
    };
    let rpm = visual(0, "VisualSpeed");
    let base_angle = super::create_visuals::wheel_angle(draw.game_time, draw.partial, rpm, phase);
    let angle = visual(ANGLE, "VisualAngle");
    let velocity = visual(ANGULAR_VELOCITY, "VisualAngularVelocity");

    let start = draw.vertices_mut().len();
    draw.push();
    draw.rotate_about(axis, base_angle, CENTER);
    draw.rotate_about(Y, base_yaw, CENTER);
    draw.rotate_about(X, base_pitch, CENTER);
    game.native_draw_model(draw, BASE_MODEL, 0xffffff);
    draw.pop();

    let handle_start = draw.vertices_mut().len();
    draw.push();
    let handle_angle = angle + draw.partial * velocity;
    draw.rotate_about(axis, handle_angle, CENTER);
    draw.rotate_about(Y, handle_yaw, CENTER);
    draw.rotate_about(X, handle_pitch, CENTER);
    game.native_draw_model(draw, HANDLE_MODEL, 0xffffff);
    draw.pop();
    if traced(pos) {
        let base_vertices = handle_start - start;
        let handle_vertices = draw.vertices_mut().len() - handle_start;
        eprintln!(
            "CREATE_HAND_CRANK_FRAME {},{:.9},{:.9},{:.9},{base_vertices},{handle_vertices}",
            draw.game_time, draw.partial, angle, handle_angle,
        );
    }
}
