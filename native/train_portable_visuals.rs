use glam::{Quat, Vec3};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use super::Game;
use super::create_machines::{float, int, set_float};
use super::create_portable_interface::{FLUID, ITEM};
use super::native_block_entity_draw::BlockEntityDraw;
use super::native_entities::NativeDisplay;
use crate::containers::ModBlockEntity;

const FLAGS: i32 =
    horizon_world::level::flags::UPDATE_CLIENTS | horizon_world::level::flags::UPDATE_KNOWN_SHAPE;
const EXTENDED: &str = "extended";
const PREVIOUS: &str = "ExtensionPrevious";
const CURRENT: &str = "ExtensionProgress";
const LIT: &str = "ExtensionLit";

pub(super) fn models(out: &mut Vec<String>) {
    for name in ["portable_storage_interface", "portable_fluid_interface"] {
        for part in ["block_middle", "block_middle_powered", "block_top"] {
            out.push(format!("create:block/{name}/{part}"));
        }
    }
}

fn set_model(game: &mut Game<'_>, pos: [i32; 3], extended: bool) -> bool {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let old_extended = game.native_block_state_property(state, EXTENDED) == Some("true");
    if old_extended == extended {
        return false;
    }
    game.native_set_block_property_with(
        pos,
        EXTENDED,
        if extended { "true" } else { "false" },
        FLAGS,
    );
    true
}

fn set_pose(entity: &mut ModBlockEntity, previous: f32, current: f32, lit: bool) {
    set_float(&mut entity.nbt, PREVIOUS, previous);
    set_float(&mut entity.nbt, CURRENT, current);
    entity.nbt.insert(LIT.into(), Tag::Byte(i8::from(lit)));
}

pub(super) fn start_bearing_connection(entity: &mut ModBlockEntity, distance: f32) {
    let previous = float(&entity.nbt, CURRENT).unwrap_or_default();
    set_float(&mut entity.nbt, "Distance", distance);
    set_pose(entity, previous, 1.0, true);
}

pub(super) fn show_bearing_connection(game: &mut Game<'_>, pos: [i32; 3]) {
    set_model(game, pos, true);
    game.native_block_entity_sync(pos);
}

pub(super) fn update(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    freeze_retraction_start: bool,
) {
    let current = float(&entity.nbt, CURRENT).unwrap_or(0.0);
    let previous = float(&entity.nbt, PREVIOUS).unwrap_or(0.0);
    let old_lit = int(&entity.nbt, LIT) == Some(1);
    let timer = int(&entity.nbt, "Timer").unwrap_or(0);
    let lit = (4..=64).contains(&timer);
    let value = if freeze_retraction_start {
        current
    } else if lit {
        1.0
    } else {
        timer.clamp(0, 4) as f32 / 4.0
    };
    let model_changed = set_model(game, pos, current > 0.0 || value > 0.0);
    if previous != current || current != value || lit != old_lit || model_changed {
        set_pose(entity, current, value, lit);
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    ["Distance", PREVIOUS, CURRENT, LIT]
        .into_iter()
        .filter_map(|key| {
            entity
                .nbt
                .get(&key.into())
                .cloned()
                .map(|value| (key.into(), value))
        })
        .collect()
}

pub(super) fn retracted_display(state: &mut Compound) {
    if matches!(
        super::create_machines::string(state, "Name").as_deref(),
        Some(ITEM | FLUID)
    ) && let Some(Tag::Compound(properties)) = state.get_mut(&"Properties".into())
        && properties.contains_key(&EXTENDED.into())
    {
        properties.insert(EXTENDED.into(), Tag::String("false".into()));
    }
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    if game.native_block_state_property(state, EXTENDED) != Some("true") {
        return;
    }
    let name = match entity.id.as_str() {
        ITEM => "portable_storage_interface",
        FLUID => "portable_fluid_interface",
        _ => return,
    };
    let Some((yaw, pitch)) = rotation(game.native_block_state_property(state, "facing")) else {
        return;
    };
    let previous = float(&entity.nbt, PREVIOUS).unwrap_or(0.0);
    let current = float(&entity.nbt, CURRENT).unwrap_or(0.0);
    let distance = float(&entity.nbt, "Distance").unwrap_or(0.0);
    let progress = (previous + draw.partial * (current - previous)).powi(2) * distance * 0.5;
    let lit = int(&entity.nbt, LIT) == Some(1);
    let middle = if lit {
        "block_middle_powered"
    } else {
        "block_middle"
    };
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], pitch, [0.5; 3]);
    let middle_offset = progress * 0.5 + 0.375;
    let mut vertices = [0; 2];
    for (index, (part, offset)) in [(middle, middle_offset), ("block_top", progress)]
        .into_iter()
        .enumerate()
    {
        let start = draw.vertices_mut().len();
        draw.push();
        draw.translate([0.0, offset, 0.0]);
        game.native_draw_model(draw, &format!("create:block/{name}/{part}"), 0xFFFFFF);
        draw.pop();
        vertices[index] = draw.vertices_mut().len() - start;
    }
    draw.pop();
    static TRACE: std::sync::OnceLock<Option<String>> = std::sync::OnceLock::new();
    if TRACE
        .get_or_init(|| std::env::var("CREATE_TRAIN_PORT_RENDER").ok())
        .as_deref()
        .is_some_and(|target| target == format!("{},{},{}", pos[0], pos[1], pos[2]))
    {
        println!(
            "CREATE_TRAIN_PORT_FRAME {} {:.8} {previous:.8} {current:.8} {distance:.8} {yaw} {pitch} {lit} {middle_offset:.8} {progress:.8} {} {}",
            draw.game_time, draw.partial, vertices[0], vertices[1]
        );
    }
}

fn rotation(facing: Option<&str>) -> Option<(f32, f32)> {
    Some(match facing? {
        "up" => (0.0, 0.0),
        "down" => (0.0, 180.0),
        "north" => (180.0, 90.0),
        "south" => (0.0, 90.0),
        "west" => (-90.0, 90.0),
        "east" => (-270.0, 90.0),
        _ => return None,
    })
}

const ACTOR_TARGET: &str = "MovingPortTarget";

pub(super) fn has_bearing_pose(block: &Compound) -> bool {
    block.contains_key(&ACTOR_TARGET.into())
}

pub(super) fn chase_carriage_port(block: &mut Compound, target: Option<f32>, now: i64) -> bool {
    chase_moving_port(block, target, now, true)
}

pub(super) fn chase_bearing_port(block: &mut Compound, target: Option<f32>, now: i64) {
    chase_moving_port(block, target, now, false);
}

fn chase_moving_port(block: &mut Compound, target: Option<f32>, now: i64, train: bool) -> bool {
    let previous = float(block, PREVIOUS);
    let current = float(block, CURRENT).unwrap_or_default();
    let old_target = float(block, ACTOR_TARGET).unwrap_or_default();
    let target = target.unwrap_or(old_target);
    // The unpowered fixed interface refreshes its nearby actors before they tick.
    let step_target = if train && old_target == 0.0 && target > 0.0 {
        target
    } else {
        old_target
    };
    let next = current + (step_target - current).clamp(-0.25, 0.25);
    if previous == Some(current) && current == next && target == old_target {
        return false;
    }
    set_float(block, PREVIOUS, current);
    set_float(block, CURRENT, next);
    set_float(block, ACTOR_TARGET, target);
    if train && std::env::var_os("CREATE_TRAIN_MOVING_PORT_TRACE").is_some() {
        println!(
            "CREATE_TRAIN_MOVING_PORT {now} {current:.8} {next:.8} {target:.8} {}",
            current == target && next == target,
        );
    }
    true
}

pub(super) fn draw_carriage_port(
    kind: &str,
    block: &Compound,
    mut state: Compound,
    carriage: Quat,
    show: &mut impl FnMut(i32, &Compound, NativeDisplay),
) {
    let Some(Tag::Compound(properties)) = state.get_mut(&"Properties".into()) else {
        return;
    };
    let Some((yaw, pitch)) =
        rotation(super::create_machines::string(properties, "facing").as_deref())
    else {
        return;
    };
    properties.insert(EXTENDED.into(), Tag::String("true".into()));
    let previous = float(block, PREVIOUS).unwrap_or_default();
    let current = float(block, CURRENT).unwrap_or_default();
    let target = float(block, ACTOR_TARGET).unwrap_or_default();
    let lit = previous == target && current == target;
    let middle = if lit {
        "block_middle_powered"
    } else {
        "block_middle"
    };
    let center = Vec3::splat(0.5);
    show(
        0,
        &state,
        NativeDisplay {
            left_rotation: carriage.to_array(),
            interpolation: 1,
            teleport: 1,
            ..NativeDisplay::default()
        },
    );
    let rotation = carriage
        * Quat::from_rotation_y(yaw.to_radians())
        * Quat::from_rotation_x(pitch.to_radians());
    let name = kind.trim_start_matches("create:");
    for (index, (part, offset)) in [(middle, current * 0.5 + 0.375), ("block_top", current)]
        .into_iter()
        .enumerate()
    {
        let state = Compound::from([(
            "Name".into(),
            Tag::String(format!("create:carriage_{name}_{part}").as_str().into()),
        )]);
        show(
            1 + index as i32,
            &state,
            NativeDisplay {
                translation: (carriage * center + rotation * (Vec3::Y * offset - center))
                    .to_array(),
                left_rotation: rotation.to_array(),
                interpolation: 1,
                teleport: 1,
                ..NativeDisplay::default()
            },
        );
    }
}
