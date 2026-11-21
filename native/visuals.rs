use std::sync::{Mutex, OnceLock};

use horizon_core::geometry::Direction;
use horizon_core::random::{LegacyRandom, RandomSource};
use horizon_world::nbt::{Compound, JavaString, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_arm::{self, ARM};
use super::create_belt::BELT;
use super::create_crushing::{MODEL as CRUSHING_MODEL, WHEEL as CRUSHING_WHEEL};
use super::create_fan::FAN;
use super::create_fluids::{PUMP, PUMP_MODEL};
use super::create_machines::{
    CLUTCH, COG, GEARBOX, GEARSHIFT, LARGE_COG, LARGE_WHEEL, SHAFT, SPEEDOMETER, STRESSOMETER, WHEEL,
    axis_index, facing_axis, float, gauge_axis, gearbox_multiplier, int, network_values, offset, reading, set_float,
};
use super::create_mixer::{self, MIXER};
use super::create_press::PRESS;
use super::create_sequencer::{self, SEQUENCER};
use super::create_spout::{self, SPOUT};
use super::create_steam::{self, ENGINE};
use super::create_cogwheel::{encased_size, CASED_COG_ENTITY, CASED_LARGE_COG_ENTITY};
use super::native_block_entity_draw::BlockEntityDraw;

const WHEEL_MODEL: &str = "create:block/water_wheel/wheel";
const DIAL_MODEL: &str = "create:block/gauge/dial";
const SPEED_HEAD: &str = "create:block/gauge/speedometer/head";
const STRESS_HEAD: &str = "create:block/gauge/stressometer/head";
const LARGE_WHEEL_MODEL: &str = "create:block/large_water_wheel/block";
const LARGE_WHEEL_EXTENSION: &str = "create:block/large_water_wheel/block_extension";
const SHAFT_MODEL: &str = "create:block/shaft";
const CHAIN_DRIVE: &str = "create:encased_chain_drive";
const COG_MODEL: &str = "create:block/cogwheel";
const CASED_COG_MODEL: &str = "create:block/cogwheel_shaftless";
const SHAFT_HALF_MODEL: &str = "create:block/shaft_half";
const LARGE_COG_MODEL: &str = "create:block/large_cogwheel_shaftless";
const COG_AXLE_MODEL: &str = "create:block/cogwheel_shaft";
const MODELS: [&str; 10] = [
    WHEEL_MODEL,
    LARGE_WHEEL_MODEL,
    LARGE_WHEEL_EXTENSION,
    DIAL_MODEL,
    SPEED_HEAD,
    STRESS_HEAD,
    SHAFT_MODEL,
    COG_MODEL,
    LARGE_COG_MODEL,
    COG_AXLE_MODEL,
];

pub(super) fn register_models(models: &mut Vec<String>) {
    super::create_sticker::models(models);
    models.extend(MODELS.map(String::from));
    models.extend([CRUSHING_MODEL, PUMP_MODEL].map(String::from));
    models.push(super::create_flywheel::ROTOR_MODEL.into());
    models.push(super::create_turntable::MODEL.into());
    models.push(super::create_bearing::WINDMILL_TOP.into());
    models.push(super::create_clockwork::TOP.into());
    models.extend([super::create_train_signal::INDICATOR_ON, super::create_train_signal::INDICATOR_OFF]
        .map(String::from));
    models.extend([CASED_COG_MODEL, SHAFT_HALF_MODEL].map(String::from));
    super::create_press::register_models(models);
    super::create_belt::register_models(models);
    super::create_fan::register_models(models);
    create_mixer::models(models);
    create_arm::models(models);
    super::create_ejector::models(models);
    super::create_funnel_flap::models(models);
    super::create_valve::models(models);
    super::create_hand_crank::models(models);
    super::create_speed_controller::models(models);
    create_spout::models(models);
    super::create_hose::models(models);
    super::create_rope::models(models);
    super::create_elevator::models(models);
    super::create_train_portable_visuals::models(models);
    super::create_elevator_indicator::models(models);
    super::create_track::models(models);
    super::create_bogey::models(models);
    create_steam::models(models);
    for base in [WHEEL_MODEL, LARGE_WHEEL_MODEL, LARGE_WHEEL_EXTENSION] {
        models.extend(super::create_wheel_material::WOODS.map(|wood| format!("{base}_{wood}")));
    }
}

const CENTER: [f32; 3] = [0.5; 3];
const X: [f32; 3] = [1.0, 0.0, 0.0];
const Y: [f32; 3] = [0.0, 1.0, 0.0];
const Z: [f32; 3] = [0.0, 0.0, 1.0];
const DIAL_PIVOT: [f32; 3] = [0.0, 5.75 / 16.0, 5.75 / 16.0];
const PREVIOUS: usize = 3;
const CURRENT: usize = 4;
const DIAL_TIME: usize = 5;

pub(super) fn speed_target(speed: f32) -> f32 {
    let rpm = speed.abs();
    if rpm < 30.0 {
        rpm / 30.0 * 0.45
    } else if rpm < 100.0 {
        0.45 + (rpm - 30.0) / 70.0 * (0.75 - 0.45)
    } else {
        0.75 + (rpm - 100.0) / 156.0 * (1.125 - 0.75)
    }
}

fn ease(current: f32, target: f32) -> f32 {
    current + (target - current) * 0.125
}

pub(super) fn tick_dial(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    target: f32,
    easing_target: f32,
    network_changed: bool,
) {
    let previous = reading(entity, CURRENT);
    let mut current = ease(previous, easing_target);
    let wobble = if current > 1.0 {
        wobble_fraction(game, pos, &entity.id)
    } else {
        0.0
    };
    current -= (current - 1.0) * wobble;
    let changed = float(&entity.nbt, "Value").unwrap_or(0.0) != target;
    set_float(&mut entity.nbt, "Value", target);
    entity.data.resize(DIAL_TIME + 2, 0);
    entity.data[PREVIOUS] = previous.to_bits() as i32;
    entity.data[CURRENT] = current.to_bits() as i32;
    let time = game.world.game_time;
    entity.data[DIAL_TIME] = time as i32;
    entity.data[DIAL_TIME + 1] = (time >> 32) as i32;
    if changed || network_changed || wobble != 0.0 {
        game.native_block_entity_sync(pos);
    }
}

fn wobble_fraction(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> f32 {
    fn roll(random: &mut impl RandomSource) -> f32 {
        if random.next_float() < 0.5 {
            random.next_float()
        } else {
            0.0
        }
    }

    // Seed only the stressometer addressed by the opt-in fixture trace.
    static FIXTURE_RANDOM: OnceLock<Option<Mutex<LegacyRandom>>> = OnceLock::new();
    if block == STRESSOMETER
        && game.dim.id() == "minecraft:overworld"
        && render_origin().is_some_and(|origin| pos == offset(origin, [3, 1, 3]))
        && let Some(random) = FIXTURE_RANDOM.get_or_init(|| {
            let seed = std::env::var("CREATE_STRESS_TRACE_SEED")
                .ok()?
                .parse()
                .ok()?;
            Some(Mutex::new(LegacyRandom::new(seed)))
        })
    {
        return roll(&mut *random.lock().expect("stress trace random mutex"));
    }
    roll(&mut game.world.random)
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Option<Compound> {
    if let Some(tag) = super::create_depot::update_tag(entity) {
        return Some(tag);
    }
    let mut tag = Compound::new();
    match entity.id.as_str() {
        CLUTCH | GEARSHIFT | GEARBOX => {
            set_float(&mut tag, "VisualSpeed", visual_transmission_rpm(entity));
            for key in ["ShaftInputSide", "ShaftInputDirection"] {
                if let Some(value) = entity.nbt.get(&key.into()) {
                    tag.insert(key.into(), value.clone());
                }
            }
        }
        SEQUENCER => {
            let (modifier, side, _) = create_sequencer::output(Some(entity));
            set_float(&mut tag, "VisualSpeed", float(&entity.nbt, "Speed").unwrap_or(0.0));
            tag.insert("ShaftInputSide".into(), Tag::Int(side));
            tag.insert("ShaftOutputModifier".into(), Tag::Int(modifier));
        }
        super::create_turntable::BLOCK => set_float(&mut tag, "VisualSpeed", reading(entity, 0)),
        "create:motor" => set_float(&mut tag, "VisualSpeed", reading(entity, 0)),
        "create:cuckoo_clock" => {
            for key in ["ClockHour", "ClockMinute", "ClockAnimation", "ClockAnimationProgress", "ClockAnimationStart"] {
                if let Some(value) = entity.nbt.get(&key.into()) {
                    tag.insert(key.into(), value.clone());
                }
            }
        }
        WHEEL | LARGE_WHEEL => {
            set_float(&mut tag, "VisualSpeed", reading(entity, 0));
            if let Some(material) = entity.nbt.get(&JavaString::from("Material")) {
                tag.insert("Material".into(), material.clone());
            }
        }
        super::create_portable_interface::ITEM | super::create_portable_interface::FLUID => {
            return Some(super::create_train_portable_visuals::update_tag(entity));
        }
        FAN => return Some(super::create_fan::update_tag(entity)),
        BELT => return Some(super::create_belt::update_tag(entity)),
        PRESS => return Some(super::create_press::update_tag(entity)),
        super::create_bearing::WINDMILL => return Some(super::create_bearing::windmill_update_tag(entity)),
        super::create_clockwork::CLOCKWORK => return Some(super::create_clockwork::update_tag(entity)),
        super::create_flywheel::FLYWHEEL => return Some(super::create_flywheel::update_tag(entity)),
        MIXER => return Some(create_mixer::update_tag(entity)),
        super::create_fluids::BASIN => return Some(create_mixer::basin_display_update_tag(entity)),
        ARM => return Some(create_arm::update_tag(entity)),
        super::create_ejector::EJECTOR => return Some(super::create_ejector::update_tag(entity)),
        super::create_hand_crank::CRANK => return Some(super::create_hand_crank::update_tag(entity)),
        super::create_speed_controller::CONTROLLER => return Some(super::create_speed_controller::update_tag(entity)),
        super::create_valve::VALVE => {
            set_float(&mut tag, "VisualSpeed", super::create_machines::saved_speed(&entity.nbt));
            if let Some(pointer) = entity.nbt.get(&JavaString::from("Pointer")) {
                tag.insert("Pointer".into(), pointer.clone());
            }
        }
        super::create_valve::HANDLE_ENTITY => {
            set_float(&mut tag, "VisualSpeed", reading(entity, 0));
            for key in [
                "TotalUseTicks",
                "StartAngle",
                "TargetAngle",
                "InUse",
                "Backwards",
                "ScrollValue",
            ] {
                if let Some(value) = entity.nbt.get(&key.into()) {
                    tag.insert(key.into(), value.clone());
                }
            }
        }
        SPOUT => return Some(create_spout::update_tag(entity)),
        super::create_hose::HOSE => return Some(super::create_hose::update_tag(entity)),
        super::create_rope::PULLEY => return Some(super::create_rope::update_tag(entity)),
        super::create_elevator::PULLEY => return Some(super::create_elevator::update_tag(entity)),
        super::create_track::TRACK => return Some(super::create_track::update_tag(entity)),
        ENGINE => return Some(create_steam::update_tag(entity)),
        PUMP | CRUSHING_WHEEL | CASED_COG_ENTITY | CASED_LARGE_COG_ENTITY | "create:encased_shaft" | "create:simple_kinetic" | super::create_chain_gearshift::ADJUSTABLE => {
            set_float(&mut tag, "VisualSpeed", reading(entity, 0))
        }
        SPEEDOMETER | STRESSOMETER => {
            for key in ["Speed", "Network"] {
                if let Some(value) = entity.nbt.get(&key.into()) {
                    tag.insert(key.into(), value.clone());
                }
            }
            set_float(
                &mut tag,
                "Value",
                float(&entity.nbt, "Value").unwrap_or(0.0),
            );
            set_float(&mut tag, "DialPrevious", reading(entity, PREVIOUS));
            set_float(&mut tag, "DialCurrent", reading(entity, CURRENT));
            let lo = entity.data.get(DIAL_TIME).copied().unwrap_or(0);
            let hi = entity.data.get(DIAL_TIME + 1).copied().unwrap_or(0);
            let time = (i64::from(hi) << 32) | i64::from(lo as u32);
            tag.insert("DialTime".into(), Tag::Long(time));
        }
        _ => return None,
    }
    Some(tag)
}

fn dial_at(nbt: &Compound, game_time: i64) -> (f32, f32) {
    let target = float(nbt, "Value").unwrap_or(0.0);
    let mut previous = float(nbt, "DialPrevious").unwrap_or(0.0);
    let mut current = float(nbt, "DialCurrent").unwrap_or(0.0);
    let Some(Tag::Long(time)) = nbt.get(&JavaString::from("DialTime")) else {
        return (previous, current);
    };
    // Between server snapshots, replay the same tick recurrence locally.
    // Past 256 steps the remaining difference is below visible precision.
    for _ in 0..game_time.saturating_sub(*time).clamp(0, 256) {
        let next = ease(current, target);
        previous = current;
        if next == current {
            break;
        }
        current = next;
    }
    (previous, current)
}

fn needle_angle(previous: f32, current: f32, partial: f32) -> f32 {
    -90.0 * (previous + partial * (current - previous))
}

pub(super) fn wheel_angle(time: i64, partial: f32, rpm: f32, phase: f32) -> f32 {
    (((time as f64 + f64::from(partial)) * f64::from(rpm) * 3.0 / 10.0 + f64::from(phase)) % 360.0)
        as f32
}

pub(super) fn draw_rotating(
    game: &Game<'_>,
    draw: &mut BlockEntityDraw,
    axis: usize,
    angle: f32,
    model: &str,
) {
    draw.push();
    draw.rotate_about([X, Y, Z][axis], angle, CENTER);
    match axis {
        0 => draw.rotate_about(Z, -90.0, CENTER),
        2 => draw.rotate_about(X, 90.0, CENTER),
        _ => {}
    }
    game.native_draw_model(draw, model, 0xFFFFFF);
    draw.pop();
}

fn render_encased_cog(
    game: &Game<'_>,
    pos: [i32; 3],
    large: bool,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(axis) = game.native_block_state_property(state, "axis").and_then(axis_index) else {
        return;
    };
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
    let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
    let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
    let model = if large { LARGE_COG_MODEL } else { CASED_COG_MODEL };
    let gear_phase = if large && phase == 0.0 { 11.25 } else { phase };
    let gear_angle = wheel_angle(draw.game_time, draw.partial, rpm, gear_phase);
    let first = draw.vertices_mut().len();
    draw_rotating(game, draw, axis, gear_angle, model);
    let gear = draw.vertices_mut().len() - first;

    // The half-shaft model projects south. Face each open end before rotating it.
    let mut shafts = [0; 2];
    for (end, key) in ["bottom_shaft", "top_shaft"].into_iter().enumerate() {
        if game.native_block_state_property(state, key) != Some("true") {
            continue;
        }
        let first = draw.vertices_mut().len();
        draw_shaft_half(game, draw, axis, end, angle);
        shafts[end] = draw.vertices_mut().len() - first;
    }

    static TRACE: OnceLock<Option<String>> = OnceLock::new();
    if TRACE.get_or_init(|| std::env::var("CREATE_CASED_COG_RENDER").ok())
        .as_deref().is_some_and(|target| target == format!("{},{},{}", pos[0], pos[1], pos[2]))
    {
        println!("CREATE_CASED_COG_FRAME {} {:.8} {rpm:.8} {phase:.8} {angle:.8} {gear} {} {} {gear_phase:.8} {gear_angle:.8}",
            draw.game_time, draw.partial, shafts[0], shafts[1]);
    }
}

fn draw_shaft_half(
    game: &Game<'_>,
    draw: &mut BlockEntityDraw,
    axis: usize,
    end: usize,
    angle: f32,
) {
    draw.push();
    draw.rotate_about([X, Y, Z][axis], angle, CENTER);
    match (axis, end) {
        (0, 0) => draw.rotate_about(Y, -90.0, CENTER),
        (0, 1) => draw.rotate_about(Y, 90.0, CENTER),
        (1, 0) => draw.rotate_about(X, 90.0, CENTER),
        (1, 1) => draw.rotate_about(X, -90.0, CENTER),
        (2, 0) => draw.rotate_about(Y, 180.0, CENTER),
        _ => {}
    }
    game.native_draw_model(draw, SHAFT_HALF_MODEL, 0xFFFFFF);
    draw.pop();
}

/// The original `CreativeMotorRenderer` draws a single `SHAFT_HALF` partial
/// facing the motor's `facing`, rotating about that axis at the standard kinetic
/// angle. The half-shaft always protrudes toward `facing`, matching
/// `CreativeMotorBlock.hasShaftTowards`.
fn render_motor(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(facing) = game.native_block_state_property(state, "facing") else {
        return;
    };
    let Some(direction) = super::machines::dir_from_name(&facing) else {
        return;
    };
    let Some(axis) = facing_axis(&facing) else {
        return;
    };
    let end = usize::from(direction.normal()[axis] > 0);
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
    let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
    let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
    let first = draw.vertices_mut().len();
    draw_shaft_half(game, draw, axis, end, angle);
    static TRACE: OnceLock<bool> = OnceLock::new();
    if *TRACE.get_or_init(|| std::env::var_os("CREATE_MOTOR_RENDER").is_some()) {
        let [x, y, z] = pos;
        let vertices = draw.vertices_mut().len() - first;
        let sign = if end == 1 { 1 } else { -1 };
        println!(
            "CREATE_MOTOR_FRAME {x},{y},{z},{facing},{axis},{sign},{},{:.8},{phase:.4},{rpm:.6},{angle:.8},{vertices}",
            draw.game_time, draw.partial
        );
    }
}

fn visual_transmission_rpm(entity: &ModBlockEntity) -> f32 {
    if let Some(speed) = float(&entity.nbt, "VisualSpeed") {
        return speed;
    }
    let [rpm, capacity, stress] = network_values(&entity.nbt);
    if stress > capacity { 0.0 } else { rpm }
}

fn render_split_shaft(
    game: &Game<'_>,
    pos: [i32; 3],
    block: &str,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let axis = if block == SEQUENCER && game.native_block_state_property(state, "vertical") == Some("true") {
        Some(1)
    } else {
        game.native_block_state_property(state, "axis").and_then(axis_index)
    };
    let Some(axis) = axis else {
        return;
    };
    let powered = game.native_block_state_property(state, "powered") == Some("true");
    let input = int(&entity.nbt, "ShaftInputSide").unwrap_or(0);
    let rpm = visual_transmission_rpm(entity);
    let modifier = match block {
        _ if input == 0 => 1,
        SEQUENCER => int(&entity.nbt, "ShaftOutputModifier").unwrap_or(0),
        CLUTCH if powered => 0,
        GEARSHIFT if powered => -1,
        _ => 1,
    };
    let output = rpm * modifier as f32;
    let speeds = if input == 1 { [output, rpm] } else { [rpm, output] };
    let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
    let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
    let mut vertices = [0; 2];
    let angles = speeds.map(|speed| wheel_angle(draw.game_time, draw.partial, speed, phase));
    for (end, angle) in angles.into_iter().enumerate() {
        let first = draw.vertices_mut().len();
        draw_shaft_half(game, draw, axis, end, angle);
        vertices[end] = draw.vertices_mut().len() - first;
    }
    static TRACE: OnceLock<bool> = OnceLock::new();
    if *TRACE.get_or_init(|| std::env::var_os("CREATE_SPLIT_SHAFT_RENDER").is_some()) {
        let [x, y, z] = pos;
        let [left, right] = speeds;
        let [left_angle, right_angle] = angles;
        let [left_vertices, right_vertices] = vertices;
        println!("CREATE_SPLIT_SHAFT_FRAME {x},{y},{z},{block},{axis},{powered},{input},{},{:.8},{phase:.4},{left:.6},{right:.6},{left_angle:.8},{right_angle:.8},{left_vertices},{right_vertices}", draw.game_time, draw.partial);
    }
}

fn render_gearbox(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(box_axis) = game.native_block_state_property(state, "axis").and_then(axis_index) else {
        return;
    };
    let source = int(&entity.nbt, "ShaftInputDirection")
        .and_then(|value| usize::try_from(value).ok())
        .and_then(|index| Direction::ALL.get(index))
        .map_or([0; 3], |face| face.normal());
    let speed = visual_transmission_rpm(entity);
    static TRACE: OnceLock<bool> = OnceLock::new();
    let trace = *TRACE.get_or_init(|| std::env::var_os("CREATE_GEARBOX_RENDER").is_some());
    for axis in (0..3).filter(|&axis| axis != box_axis) {
        let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
        let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
        for (end, direction) in [-1, 1].into_iter().enumerate() {
            let mut side = [0; 3];
            side[axis] = direction;
            let rpm = speed * gearbox_multiplier(source, side);
            let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
            let first = draw.vertices_mut().len();
            draw_shaft_half(game, draw, axis, end, angle);
            if trace {
                let [x, y, z] = pos;
                let [sx, sy, sz] = source;
                let vertices = draw.vertices_mut().len() - first;
                println!("CREATE_GEARBOX_FRAME {x},{y},{z},{box_axis},{axis},{direction},{sx},{sy},{sz},{},{:.8},{phase:.4},{rpm:.6},{angle:.8},{vertices}", draw.game_time, draw.partial);
            }
        }
    }
}

pub(super) fn submit(
    game: &Game<'_>,
    pos: [i32; 3],
    block: &str,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    if block == super::create_sticker::STICKER && entity.id == block {
        super::create_sticker::render(game,pos,state,entity,draw);
        return;
    }
    if super::create_chain_conveyor_visual::render(game, pos, entity, draw) {
        return;
    }
    super::create_funnel_flap::render(game, pos, block, state, entity, draw);
    if matches!(block, super::create_portable_interface::ITEM | super::create_portable_interface::FLUID)
        && entity.id == block
    {
        super::create_train_portable_visuals::render(game, pos, state, entity, draw);
        return;
    }
    if block == super::create_redstone_link::LINK {
        super::create_redstone_link::render(game, state, entity, draw);
        return;
    }
    if block == super::create_factory_gauge::BLOCK && entity.id == super::create_factory_gauge::ENTITY {
        super::create_factory_gauge::render(game, state, entity, draw);
        return;
    }
    if block == super::create_display_board::BOARD {
        super::create_display_board::render(game, state, entity, draw);
        return;
    }
    if block == ARM && entity.id == ARM {
        create_arm::render(game, pos, state, entity, draw);
        return;
    }
    if block == super::create_speed_controller::CONTROLLER && entity.id == block {
        super::create_speed_controller::render(game, pos, state, entity, draw);
        return;
    }
    if block == super::create_bearing::WINDMILL && entity.id == block {
        super::create_bearing::windmill_render(game, state, entity, draw);
        return;
    }
    if block == super::create_train_signal::SIGNAL && entity.id == block {
        super::create_train_signal::render(game, entity, draw);
        return;
    }
    if block == super::create_clockwork::CLOCKWORK && entity.id == block {
        super::create_clockwork::render(game, state, entity, draw);
        return;
    }
    if block == super::create_hand_crank::CRANK && entity.id == block {
        super::create_hand_crank::render(game, pos, state, entity, draw);
        return;
    }
    if block == super::create_valve::VALVE && entity.id == block {
        super::create_valve::render_pipe_valve(game, pos, state, entity, draw);
        return;
    }
    if super::create_valve::is_handle(block) && entity.id == super::create_valve::HANDLE_ENTITY {
        super::create_valve::render(game, pos, state, block, entity, draw);
        return;
    }
    if block == super::create_ejector::EJECTOR && entity.id == block {
        super::create_ejector::render(game, state, entity, draw);
        return;
    }
    if entity.id == super::create_bogey::ENTITY {
        super::create_bogey::render(game, state, block, draw);
        return;
    }
    if block == super::create_track::TRACK && entity.id == block {
        super::create_track::render(game, entity, draw);
        return;
    }
    if block == super::create_elevator::PULLEY && entity.id == block {
        super::create_elevator::render(game, pos, state, entity, draw);
        return;
    }
    if block == super::create_rope::PULLEY && entity.id == block {
        super::create_rope::render(game, pos, entity, draw);
        return;
    }
    if block == super::create_hose::HOSE && entity.id == block {
        super::create_hose::render(game, state, entity, draw);
        return;
    }
    if block == SPOUT && entity.id == SPOUT {
        create_spout::render(game, entity, draw);
        return;
    }
    if block == ENGINE && entity.id == ENGINE {
        create_steam::render(game, pos, entity, draw);
        return;
    }
    if block == super::create_fluids::BASIN && entity.id == block {
        create_mixer::draw_basin(game, entity, draw);
        return;
    }
    if block == MIXER && entity.id == MIXER {
        create_mixer::draw(game, entity, draw);
        return;
    }
    if block == PUMP && entity.id == PUMP {
        if let Some(axis) = game
            .native_block_state_property(state, "facing")
            .and_then(facing_axis)
        {
            let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
            let angle = wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
            draw_rotating(game, draw, axis, angle, PUMP_MODEL);
        }
        return;
    }
    if block == CRUSHING_WHEEL && entity.id == CRUSHING_WHEEL {
        if let Some(axis) = game
            .native_block_state_property(state, "axis")
            .and_then(axis_index)
        {
            let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
            let angle = wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
            draw_rotating(game, draw, axis, angle, CRUSHING_MODEL);
        }
        return;
    }
    if block == FAN && entity.id == FAN {
        super::create_fan::render(game, state, entity, draw);
        return;
    }
    if block == BELT && entity.id == BELT {
        super::create_belt::render(game, pos, state, entity, draw);
        return;
    }
    if block == super::create_turntable::BLOCK && entity.id == block {
        super::create_turntable::render(game, pos, entity, draw);
        return;
    }
    if block == super::create_flywheel::FLYWHEEL && entity.id == block {
        super::create_flywheel::render(game, pos, state, entity, draw);
        return;
    }
    if block == PRESS && entity.id == PRESS {
        super::create_press::render(game, pos, state, entity, draw);
        return;
    }
    if block == GEARBOX && entity.id == block {
        render_gearbox(game, pos, state, entity, draw);
        return;
    }
    if matches!(block, CLUTCH | GEARSHIFT | SEQUENCER) && entity.id == block {
        render_split_shaft(game, pos, block, state, entity, draw);
        return;
    }
    if matches!(entity.id.as_str(), CASED_COG_ENTITY | CASED_LARGE_COG_ENTITY)
        && let Some(large) = encased_size(block)
    {
        render_encased_cog(game, pos, large, state, entity, draw);
        return;
    }
    if (matches!(block, COG | LARGE_COG | SHAFT) && entity.id == "create:simple_kinetic")
        || (block == super::create_chain_gearshift::ADJUSTABLE && entity.id == block)
        || (block == CHAIN_DRIVE && entity.id == "create:encased_shaft")
        || (block == super::create_shaft::GIRDER_SHAFT && entity.id == "create:encased_shaft")
    {
        let Some(axis) = game
            .native_block_state_property(state, "axis")
            .and_then(axis_index)
        else {
            return;
        };
        let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
        let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
        let model = match block {
            COG => COG_MODEL,
            LARGE_COG => LARGE_COG_MODEL,
            _ => SHAFT_MODEL,
        };
        let mut phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
        if block == LARGE_COG {
            let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
            draw_rotating(game, draw, axis, angle, COG_AXLE_MODEL);
            if phase == 0.0 {
                phase = 11.25;
            }
        }
        let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
        let first = draw.vertices_mut().len();
        draw_rotating(game, draw, axis, angle, model);
        static CHAIN_DRIVE_TRACE: OnceLock<bool> = OnceLock::new();
        if block == CHAIN_DRIVE
            && *CHAIN_DRIVE_TRACE.get_or_init(|| std::env::var_os("CREATE_CHAIN_DRIVE_RENDER").is_some())
        {
            let game_time = draw.game_time;
            let partial = draw.partial;
            let vertices = draw.vertices_mut().len() - first;
            println!(
                "CREATE_CHAIN_DRIVE_FRAME {} {} {} {} {} {:.8} {:.8} {:.8} {:.8} {}",
                pos[0], pos[1], pos[2], axis, game_time, partial, rpm, phase, angle, vertices
            );
        }
        return;
    }
    if block == "create:creative_motor" && entity.id == "create:motor" {
        render_motor(game, pos, state, entity, draw);
        return;
    }
    if !matches!(block, WHEEL | LARGE_WHEEL | SPEEDOMETER | STRESSOMETER) || entity.id != block {
        super::create_depot::render(game, block, state, entity, draw);
        return;
    }
    if matches!(block, WHEEL | LARGE_WHEEL) {
        let axis = if block == WHEEL {
            game.native_block_state_property(state, "facing")
                .and_then(facing_axis)
        } else {
            game.native_block_state_property(state, "axis")
                .and_then(axis_index)
        };
        let Some(axis) = axis else {
            return;
        };
        let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
        let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
        let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
        let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
        draw.push();
        draw.rotate_about([X, Y, Z][axis], angle, CENTER);
        match axis {
            0 => draw.rotate_about(Z, -90.0, CENTER),
            2 => draw.rotate_about(X, 90.0, CENTER),
            _ => {}
        }
        let first = draw.vertices_mut().len();
        let model = match block {
            WHEEL => WHEEL_MODEL,
            _ if game.native_block_state_property(state, "extension") == Some("true") => {
                LARGE_WHEEL_EXTENSION
            }
            _ => LARGE_WHEEL_MODEL,
        };
        let material = super::create_wheel_material::material(&entity.nbt);
        let wood = material
            .strip_prefix("minecraft:")
            .and_then(|name| name.strip_suffix("_planks"));
        let wood = wood
            .filter(|wood| super::create_wheel_material::WOODS.contains(wood))
            .unwrap_or("oak");
        game.native_draw_model(draw, &format!("{model}_{wood}"), 0xFFFFFF);
        let vertices = draw.vertices_mut().len() - first;
        draw.pop();
        trace_frame(pos, block, draw, [rpm, phase, angle, rpm], vertices);
        return;
    }

    let Some(facing) = game.native_block_state_property(state, "facing") else {
        return;
    };
    let first_axis = game.native_block_state_property(state, "axis_along_first") == Some("true");
    let Some(axis) = gauge_axis(facing, first_axis) else {
        return;
    };
    let (previous, current) = dial_at(&entity.nbt, draw.game_time);
    let angle = needle_angle(previous, current, draw.partial);
    let mut needle_vertices = 0;
    for (face, opposite, face_axis, normal, yaw) in [
        ("east", "west", 0, [1, 0, 0], 0.0),
        ("west", "east", 0, [-1, 0, 0], 180.0),
        ("north", "south", 2, [0, 0, -1], 90.0),
        ("south", "north", 2, [0, 0, 1], -90.0),
    ] {
        if face_axis == axis || opposite == facing || (axis == 1 && face != facing) {
            continue;
        }
        let [x, y, z] = offset(pos, normal);
        let neighbor = game.world.block(x, y, z);
        if game.res.facts().get(neighbor).solid_render {
            continue;
        }
        draw.push();
        draw.rotate_about(Y, yaw, CENTER);
        let head = if block == SPEEDOMETER {
            SPEED_HEAD
        } else {
            STRESS_HEAD
        };
        game.native_draw_model(draw, head, 0xFFFFFF);
        draw.rotate_about(X, angle, DIAL_PIVOT);
        let first = draw.vertices_mut().len();
        game.native_draw_model(draw, DIAL_MODEL, 0xFFFFFF);
        needle_vertices += draw.vertices_mut().len() - first;
        draw.pop();
    }
    let target = float(&entity.nbt, "Value").unwrap_or(0.0);
    trace_frame(
        pos,
        block,
        draw,
        [previous, current, angle, target],
        needle_vertices,
    );
}

fn render_origin() -> Option<[i32; 3]> {
    static ORIGIN: OnceLock<Option<[i32; 3]>> = OnceLock::new();
    *ORIGIN.get_or_init(|| {
        let origin = std::env::var("CREATE_WHEEL_RENDER_ORIGIN").ok()?;
        let mut coordinates = origin.split(',').map(str::parse::<i32>);
        Some([
            coordinates.next()?.ok()?,
            coordinates.next()?.ok()?,
            coordinates.next()?.ok()?,
        ])
    })
}

fn trace_frame(
    pos: [i32; 3],
    block: &str,
    draw: &BlockEntityDraw,
    [a, b, angle, target]: [f32; 4],
    vertices: usize,
) {
    let Some(origin) = render_origin() else {
        return;
    };
    let (x, y) = if super::create_machines::trace_large_wheel() {
        (4, 2)
    } else {
        (3, 1)
    };
    let delta = match block {
        WHEEL | LARGE_WHEEL => [x, y, 2],
        SPEEDOMETER => [x, y, 1],
        STRESSOMETER => [x, y, 3],
        _ => return,
    };
    if pos == offset(origin, delta) {
        println!(
            "CREATE_WHEEL_FRAME {block} {} {:.8} {a:.8} {b:.8} {angle:.8} {vertices} {target:.8}",
            draw.game_time, draw.partial
        );
    }
}
