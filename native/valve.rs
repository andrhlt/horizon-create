use std::sync::OnceLock;

use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_machines::{facing_axis, float, int, rpm_at, set_float};
use super::create_speed_controller::setting_feedback;
use super::create_speed_controller_controls::Selection;
use super::native_block_entity_draw::BlockEntityDraw;
use horizon_world::registry::BlockStateId;

pub(super) const VALVE: &str = "create:fluid_valve";
const POINTER: &str = "create:block/fluid_valve/pointer";
pub(super) const HANDLE_ENTITY: &str = "create:valve_handle";
pub(super) const ANGLE_TITLE: &str = "Rotation when used";
const ROTATION: f32 = 32.0;
const RECOLOR_DRIVE: &str = "RecolorDrive";
const DYES: [&str; 16] = [
    "white",
    "orange",
    "magenta",
    "light_blue",
    "yellow",
    "lime",
    "pink",
    "gray",
    "light_gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
];

pub(super) fn is_handle(block: &str) -> bool {
    block
        .strip_prefix("create:")
        .and_then(|name| name.strip_suffix("_valve_handle"))
        .is_some_and(|name| name == "copper" || DYES.contains(&name))
}

pub(super) fn setting(entity: Option<&ModBlockEntity>) -> i32 {
    entity
        .and_then(|entity| int(&entity.nbt, "ScrollValue"))
        .unwrap_or(45)
        .clamp(-180, 180)
}

pub(super) fn box_center(game: &Game<'_>, pos: [i32; 3], side: [i32; 3]) -> Option<[f64; 3]> {
    let direction = facing(game, game.world.block(pos[0], pos[1], pos[2]))?;
    if direction.normal() != side
        || int(&super::create_machines::mod_entity(game, pos)?.nbt, "InUse").unwrap_or(0) > 0
    {
        return None;
    }
    Some(side.map(|component| 0.5 - f64::from(component) * 0.21875))
}

pub(super) fn set_angle(game: &mut Game<'_>, pos: [i32; 3], selection: Selection) {
    let angle = selection.value.clamp(1, 180) * if selection.row == 0 { -1 } else { 1 };
    let changed = game.native_with_mod_block_entity(pos, |entity| {
        if entity.id != HANDLE_ENTITY || setting(Some(entity)) == angle {
            return false;
        }
        entity.nbt.insert("ScrollValue".into(), Tag::Int(angle));
        true
    });
    if changed == Some(true) {
        setting_feedback(game, pos);
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn place(
    level: &super::GameLevel<'_>,
    state: BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<BlockStateId> {
    use horizon_core::geometry::Vec3;
    use horizon_world::{fluid::FluidKind, level::LevelAccess};

    if level.registry.state(state)?.name != VALVE {
        return None;
    }
    let aim = context.nearest_looking_direction();
    let facing = if context.sneaking {
        aim
    } else {
        aim.opposite()
    };
    let shaft = |direction| {
        super::create_hand_crank::preferred_in_directions(level, context.pos, [direction]).is_some()
    };
    let pipe = |direction| prefers_pipe_neighbor(level, context.pos, direction);
    let first = match facing {
        Direction::Up | Direction::Down => {
            let [x, y, z] = super::view_vector(context.yaw, 0.0);
            let horizontal = Direction::approximate_nearest(Vec3::new(x, y, z));
            let mut preferred = None;
            for (side, clockwise) in [
                (Direction::North, Direction::East),
                (Direction::East, Direction::South),
                (Direction::South, Direction::West),
                (Direction::West, Direction::North),
            ] {
                if !shaft(side) && !pipe(clockwise) {
                    continue;
                }
                let along_x = side.normal()[0] != 0;
                if preferred.is_some_and(|axis| axis != along_x) {
                    preferred = None;
                    break;
                }
                preferred = Some(along_x);
            }
            preferred.unwrap_or(horizontal.normal()[0] != 0)
        }
        _ => {
            let along_x = facing.normal()[0] != 0;
            let across = if along_x {
                Direction::South
            } else {
                Direction::East
            };
            if shaft(Direction::Up)
                || shaft(Direction::Down)
                || pipe(across)
                || pipe(across.opposite())
            {
                along_x
            } else {
                !along_x
            }
        }
    };
    let fluid = level.behaviours.fluid(level.block_state(context.pos));
    let waterlogged = fluid.kind() == FluidKind::Water && fluid.is_source();
    let placed =
        level.native_state_with_property(state, "facing", super::create_fluids::name(facing))?;
    let placed = level.native_state_with_property(
        placed,
        "axis_along_first",
        if first { "true" } else { "false" },
    )?;
    level.native_state_with_property(
        placed,
        "waterlogged",
        if waterlogged { "true" } else { "false" },
    )
}

fn prefers_pipe_neighbor(
    level: &super::GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    direction: Direction,
) -> bool {
    use super::create_encased_fluid_pipe::BLOCK as ENCASED_PIPE;
    use super::create_fluids::{GLASS_PIPE, PIPE, PUMP, SMART_PIPE, name};
    use horizon_world::level::LevelAccess;

    let [x, y, z] = direction.normal();
    let Some(block) = level.registry.state(level.block_state(pos.offset(x, y, z))) else {
        return false;
    };
    let property = |key| block.properties.get(key).map(String::as_str);
    let axis = if x != 0 {
        "x"
    } else if y != 0 {
        "y"
    } else {
        "z"
    };
    let facing_axis = || property("facing").and_then(facing_axis);
    let direction_axis = if x != 0 {
        0
    } else if y != 0 {
        1
    } else {
        2
    };
    match block.name.as_str() {
        PIPE => true,
        GLASS_PIPE => property("axis") == Some(["x", "y", "z"][direction_axis]),
        ENCASED_PIPE => property(name(direction.opposite())) == Some("true"),
        PUMP => facing_axis() == Some(direction_axis),
        SMART_PIPE => {
            let pipe_axis = if property("face") == Some("wall") {
                Some(1)
            } else {
                facing_axis()
            };
            pipe_axis == Some(direction_axis)
        }
        "create:fluid_tank"
        | "create:creative_fluid_tank"
        | "minecraft:cauldron"
        | "minecraft:water_cauldron"
        | "minecraft:lava_cauldron" => true,
        _ => property("honey_level").is_some(),
    }
}

pub(super) fn pipe_axis(game: &Game<'_>, pos: [i32; 3]) -> Option<usize> {
    let vertical = facing_axis(&game.native_block_property(pos, "facing")?)?;
    let second = game.native_block_property(pos, "axis_along_first")? == "true";
    (0..3)
        .filter(|&axis| axis != vertical)
        .nth(usize::from(second))
}

pub(super) fn shaft_axis(game: &Game<'_>, pos: [i32; 3]) -> Option<usize> {
    let advertised = facing_axis(&game.native_block_property(pos, "facing")?)?;
    let pipe = pipe_axis(game, pos)?;
    (0..3).find(|&axis| axis != advertised && axis != pipe)
}

pub(super) fn enabled(game: &Game<'_>, pos: [i32; 3]) -> bool {
    game.native_block_property(pos, "enabled").as_deref() == Some("true")
}

pub(super) fn speed(nbt: &Compound, face: Direction) -> f32 {
    if int(nbt, "InUse").unwrap_or(0) <= 0 {
        return 0.0;
    }
    let backwards = int(nbt, "Backwards") == Some(1);
    let configured = int(nbt, "ScrollValue").unwrap_or(45);
    let negative_face = matches!(face, Direction::Down | Direction::West | Direction::North);
    if backwards ^ (configured < 0) ^ negative_face {
        -ROTATION
    } else {
        ROTATION
    }
}

pub(super) fn generator(
    game: &Game<'_>,
    pos: [i32; 3],
    nbt: &Compound,
    face: Direction,
) -> (f32, f32) {
    if let Some(rpm) = float(nbt, RECOLOR_DRIVE) {
        // Java clears the recolored entity's generator. A spinning rear
        // shaft can drive the same handle back at its previous speed.
        let connected = super::create_machines::valve_rear_link(game, pos, face);
        return (if connected { rpm } else { 0.0 }, 0.0);
    }
    (speed(nbt, face), 8.0)
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    let block = game.native_block(pos);
    if *canceled || !is_handle(&block) || !game.may_build() {
        return;
    }
    *canceled = true;
    if recolor(game, pos, &block) || rpm_at(game, pos) != 0.0 {
        return;
    }
    let Some(direction) = facing(game, game.world.block(pos[0], pos[1], pos[2])) else {
        return;
    };
    let backwards = game.native_sneaking();
    let Some(true) = game.native_with_mod_block_entity(pos, |handle| {
        let nbt = &mut handle.nbt;
        if int(nbt, "InUse").unwrap_or(0) > 0 || int(nbt, "Cooldown").unwrap_or(0) > 0 {
            return false;
        }
        let amount = int(nbt, "ScrollValue").unwrap_or(45).clamp(-180, 180);
        let degrees = amount.unsigned_abs() as f32;
        let ticks = (degrees / (ROTATION * 0.3)).ceil() as i32 + 2;
        let target = if degrees > 135.0 { 180 } else { 90 } * amount.signum();
        let start = int(nbt, "TargetAngle").unwrap_or(0).rem_euclid(90);
        nbt.remove(&RECOLOR_DRIVE.into());
        nbt.insert("StartAngle".into(), Tag::Int(start));
        nbt.insert("TargetAngle".into(), Tag::Int(start + target));
        nbt.insert("InUse".into(), Tag::Int(ticks));
        nbt.insert("TotalUseTicks".into(), Tag::Int(ticks));
        nbt.insert("Backwards".into(), Tag::Byte(i8::from(backwards)));
        nbt.insert("Cooldown".into(), Tag::Int(4));
        let rpm = speed(nbt, direction);
        set_float(nbt, "Speed", rpm);
        true
    }) else {
        return;
    };
    game.swing_arm();
    super::create_machines::refresh_connected_network(game, pos);
}

fn recolor(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> bool {
    let Some(color) = game
        .held()
        .and_then(|stack| stack.item.strip_prefix("minecraft:")?.strip_suffix("_dye"))
        .filter(|color| DYES.contains(color))
    else {
        return false;
    };
    let target = format!("create:{color}_valve_handle");
    if target == block {
        return false;
    }
    let Some(base) = game.native_default_state(&target) else {
        return false;
    };
    let Some(face) = game.native_block_property(pos, "facing") else {
        return false;
    };
    let Some(water) = game.native_block_property(pos, "waterlogged") else {
        return false;
    };
    let replacement = game.with_level(|_, level, _| {
        level
            .native_state_with_property(base, "facing", &face)
            .and_then(|state| level.native_state_with_property(state, "waterlogged", &water))
    });
    let Some(replacement) = replacement else {
        return false;
    };
    let mut retained = super::create_machines::mod_entity(game, pos).cloned();
    if let Some(entity) = retained.as_mut() {
        let actual = super::create_machines::reading(entity, 0);
        if int(&entity.nbt, "InUse").unwrap_or(0) > 0 && float(&entity.nbt, RECOLOR_DRIVE).is_none()
        {
            let connected = super::machines::dir_from_name(&face)
                .is_some_and(|face| super::create_machines::valve_rear_link(game, pos, face));
            set_float(
                &mut entity.nbt,
                RECOLOR_DRIVE,
                if connected { actual } else { 0.0 },
            );
        }
        entity.nbt.remove(&"Network".into());
        set_float(&mut entity.nbt, "Speed", 0.0);
        entity.data.clear();
    }
    if game.native_set_block(
        game.native_dimension(),
        pos,
        replacement,
        horizon_world::level::flags::UPDATE_ALL,
    ) && let Some(retained) = retained
    {
        game.native_with_mod_block_entity(pos, |entity| *entity = retained);
        game.native_block_entity_sync(pos);
    }
    true
}

pub(super) fn tick_handle(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
) -> bool {
    if float(&entity.nbt, RECOLOR_DRIVE).is_some_and(|speed| speed != 0.0)
        && let Some(face) = facing(game, game.world.block(pos[0], pos[1], pos[2]))
        && !super::create_machines::valve_rear_link(game, pos, face)
    {
        set_float(&mut entity.nbt, RECOLOR_DRIVE, 0.0);
    }
    let remaining = int(&entity.nbt, "InUse").unwrap_or(0);
    if remaining > 0 {
        entity.nbt.insert("InUse".into(), Tag::Int(remaining - 1));
    }
    if remaining <= 1 {
        let cooldown = int(&entity.nbt, "Cooldown").unwrap_or(0);
        if cooldown > 0 {
            entity.nbt.insert("Cooldown".into(), Tag::Int(cooldown - 1));
        }
    }
    if remaining > 0 || rpm != 0.0 {
        game.native_block_entity_sync(pos);
    }
    remaining == 1
}

fn valve_chase(rpm: f32) -> (f32, f32) {
    (
        if rpm > 0.0 { 1.0 } else { 0.0 },
        (rpm.abs() / 320.0).min(1.0),
    )
}

pub(super) fn retarget(entity: &mut ModBlockEntity, rpm: f32) {
    let mut pointer = compound(&entity.nbt, "Pointer")
        .cloned()
        .unwrap_or_default();
    let (target, step) = valve_chase(rpm);
    set_float(&mut pointer, "Target", target);
    set_float(&mut pointer, "Speed", step);
    entity.nbt.insert("Pointer".into(), Tag::Compound(pointer));
}

pub(super) fn tick_valve(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
) {
    let mut pointer = compound(&entity.nbt, "Pointer")
        .cloned()
        .unwrap_or_default();
    let old = float(&pointer, "Value").unwrap_or(0.0);
    let (target, step) = valve_chase(rpm);
    let next = old + (target - old).clamp(-step, step);
    let previous = float(&pointer, "Previous").unwrap_or(old);
    set_float(&mut pointer, "Previous", old);
    set_float(&mut pointer, "Value", next);
    set_float(&mut pointer, "Target", target);
    set_float(&mut pointer, "Speed", step);
    entity.nbt.insert("Pointer".into(), Tag::Compound(pointer));

    let (is_open, new_open) = (enabled(game, pos), next >= 1.0);
    if (new_open || next <= 0.0) && is_open != new_open {
        // The changed pipe schedules its network update for the next block
        // tick, then waits for pressure and flow directions to settle.
        if new_open {
            entity
                .nbt
                .insert("FlowReady".into(), Tag::Long(game.world.game_time + 3));
        }
        game.native_set_block_property(pos, "enabled", if new_open { "true" } else { "false" });
    }
    if new_open || is_open && next > 0.0 {
        super::create_fluids::tick(game, pos, entity);
    }
    if previous != old || old != next {
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn models(models: &mut Vec<String>) {
    models.push(POINTER.into());
    models.extend(
        DYES.into_iter()
            .chain(["copper"])
            .map(|color| format!("create:block/{color}_valve_handle")),
    );
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    block: &str,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(face) = facing(game, state) else {
        return;
    };
    let (pitch, yaw) = match face {
        Direction::Up => (0.0, 0.0),
        Direction::Down => (180.0, 0.0),
        Direction::North => (-90.0, 0.0),
        Direction::East => (-90.0, -90.0),
        Direction::South => (-90.0, 180.0),
        Direction::West => (-90.0, 90.0),
    };
    let nbt = &entity.nbt;
    let total = int(nbt, "TotalUseTicks").unwrap_or(0);
    let remaining = int(nbt, "InUse").unwrap_or(0);
    let start = int(nbt, "StartAngle").unwrap_or(0) as f32;
    let target = int(nbt, "TargetAngle").unwrap_or(0) as f32;
    let rpm = if entity.data.is_empty() {
        float(nbt, "VisualSpeed").unwrap_or(0.0)
    } else {
        super::create_machines::reading(entity, 0)
    };
    let face_sign = face.normal().iter().sum::<i32>() as f32;
    let backwards = if int(nbt, "Backwards") == Some(1) {
        -1.0
    } else {
        1.0
    };
    let angle = |partial: f32| {
        if remaining == 0 && rpm != 0.0 {
            let sum: i32 = pos
                .iter()
                .zip(face.normal())
                .filter_map(|(&coordinate, normal)| (normal == 0).then_some(coordinate))
                .sum();
            let phase = if sum % 2 == 0 { 22.5 } else { 0.0 };
            super::create_visuals::wheel_angle(draw.game_time, partial, rpm, phase) * face_sign
        } else if remaining > 0 && total > 0 {
            let t = (total - remaining) as f32 + partial;
            (start + (target - start) * (t / total as f32).clamp(0.0, 1.0)) * backwards
        } else {
            target * backwards
        }
    };
    let base_roll = angle(0.0) * face_sign;
    let rotation = angle(draw.partial);
    let before = draw.vertices_mut().len();
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], pitch, [0.5; 3]);
    draw.rotate_about([0.0, 1.0, 0.0], rotation, [0.5; 3]);
    if let Some(name) = block.strip_prefix("create:") {
        game.native_draw_model(draw, &format!("create:block/{name}"), 0xffffff);
    }
    draw.pop();
    if trace_motion(pos) {
        let vertices = draw.vertices_mut().len() - before;
        eprintln!(
            "CREATE_VALVE_FRAME {},{remaining},{:.9},{base_roll:.9},{:.9},{vertices}",
            draw.game_time,
            draw.partial,
            rotation * face_sign
        );
    }
}

pub(super) fn render_pipe_valve(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(face) = facing(game, state) else {
        return;
    };
    let (Some(pipe), Some(shaft)) = (pipe_axis(game, pos), shaft_axis(game, pos)) else {
        return;
    };
    let parity = pos[(shaft + 1) % 3].wrapping_add(pos[(shaft + 2) % 3]);
    let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let shaft_angle = super::create_visuals::wheel_angle(draw.game_time, draw.partial, rpm, phase);
    super::create_visuals::draw_rotating(game, draw, shaft, shaft_angle, "create:block/shaft");

    let yaw = match face {
        Direction::West => 90.0,
        Direction::North => 180.0,
        Direction::East => 270.0,
        _ => 0.0,
    };
    let pitch = match face {
        Direction::Up => 0.0,
        Direction::Down => 180.0,
        _ => 90.0,
    };
    let offset = if pipe == 1 || shaft == 0 { 90.0 } else { 0.0 };
    let (previous, current) = compound(&entity.nbt, "Pointer").map_or((0.0, 0.0), |pointer| {
        let current = float(pointer, "Value").unwrap_or(0.0);
        (float(pointer, "Previous").unwrap_or(current), current)
    });
    let angle = offset - 90.0 * (previous + draw.partial * (current - previous));
    let start = draw.vertices_mut().len();
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], pitch, [0.5; 3]);
    draw.rotate_about([0.0, 1.0, 0.0], angle, [0.5; 3]);
    game.native_draw_model(draw, POINTER, 0xFFFFFF);
    draw.pop();
    if std::env::var_os("CREATE_FLUID_VALVE_RENDER_TRACE").is_some() {
        let vertices = draw.vertices_mut().len() - start;
        eprintln!(
            "CREATE_FLUID_VALVE_FRAME {} {:.9} {previous:.9} {current:.9} {angle:.9} {vertices}",
            draw.game_time, draw.partial,
        );
    }
}

fn trace_motion(pos: [i32; 3]) -> bool {
    static PICK: OnceLock<Option<[i32; 3]>> = OnceLock::new();
    PICK.get_or_init(|| {
        std::env::var("CREATE_VALVE_TRACE")
            .ok()?
            .split(',')
            .map(str::parse)
            .collect::<Result<Vec<i32>, _>>()
            .ok()?
            .try_into()
            .ok()
    }) == &Some(pos)
}
