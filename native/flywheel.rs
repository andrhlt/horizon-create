use std::sync::OnceLock;

use horizon_world::level::PlacementContext;
use horizon_world::nbt::Compound;
use horizon_world::registry::BlockStateId;
use horizon_world::view_direction::view_vector;

use crate::containers::ModBlockEntity;

use super::create_machines::{axis_index, float, reading, set_float};
use super::create_visuals::{draw_rotating, wheel_angle};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const FLYWHEEL: &str = "create:flywheel";
pub(super) const ROTOR_MODEL: &str = "create:block/flywheel/block";
const SHAFT_MODEL: &str = "create:block/shaft";
const PREVIOUS_RPM: usize = 3;
const VISIBLE_RPM: usize = 4;
const ANGLE: usize = 5;
const AXES: [&str; 3] = ["x", "y", "z"];

pub(super) fn placement(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    let preferred = super::create_hand_crank::preferred_direction(level, context.pos);
    let selected = if let Some(connection) = preferred {
        let direction = if context.sneaking {
            context.face
        } else {
            connection
        };
        direction.normal().iter().position(|part| *part != 0)?
    } else {
        let view = view_vector(context.pitch, context.yaw);
        let [x, y, z] = [view.x.abs(), view.y.abs(), view.z.abs()];
        if y > x.max(z) {
            1
        } else if x > z {
            0
        } else {
            2
        }
    };
    level.native_state_with_property(state, "axis", AXES[selected])
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    wheel: &mut ModBlockEntity,
    speed_changed: bool,
) {
    let target = reading(wheel, 0);
    let previously_moving = reading(wheel, PREVIOUS_RPM) != 0.0;
    let previous = reading(wheel, VISIBLE_RPM);
    let delta = f64::from(target) - f64::from(previous);
    let speed = if delta.abs() < 1.0e-5 {
        target
    } else {
        (f64::from(previous) + delta / 64.0) as f32
    };
    let angle = (reading(wheel, ANGLE) + speed * 3.0 / 10.0) % 360.0;
    if wheel.data.len() <= ANGLE {
        wheel.data.resize(ANGLE + 1, 0);
    }
    wheel.data[PREVIOUS_RPM..=ANGLE]
        .copy_from_slice(&[previous, speed, angle].map(|value| value.to_bits() as i32));
    if speed_changed || previously_moving || previous != 0.0 || speed != 0.0 {
        game.native_block_entity_sync(pos);
    }

    static TRACE_POS: OnceLock<Option<[i32; 3]>> = OnceLock::new();
    if TRACE_POS
        .get_or_init(|| {
            let setting = std::env::var("CREATE_FLYWHEEL_TRACE_POS").ok()?;
            let coordinates: Vec<i32> = setting
                .split(',')
                .map(str::parse)
                .collect::<Result<_, _>>()
                .ok()?;
            coordinates.try_into().ok()
        })
        .as_ref()
        == Some(&pos)
    {
        eprintln!(
            "CREATE_FLYWHEEL_HORIZON {},{target:.9},{previous:.9},{speed:.9},{angle:.9}",
            game.world.game_time,
        );
    }
}

pub(super) fn update_tag(wheel: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    for (key, index) in [
        ("VisualSpeed", 0),
        ("RotorPreviousRPM", PREVIOUS_RPM),
        ("RotorRPM", VISIBLE_RPM),
        ("RotorAngle", ANGLE),
    ] {
        set_float(&mut tag, key, reading(wheel, index));
    }
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    block_state: BlockStateId,
    wheel: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(axis) = game
        .native_block_state_property(block_state, "axis")
        .and_then(axis_index)
    else {
        return;
    };
    let partial = draw.partial;
    let raw_speed = float(&wheel.nbt, "VisualSpeed").unwrap_or(0.0);
    let previous = float(&wheel.nbt, "RotorPreviousRPM").unwrap_or(0.0);
    let current = float(&wheel.nbt, "RotorRPM").unwrap_or(0.0);
    let speed = (f64::from(previous)
        + (f64::from(current) - f64::from(previous)) * f64::from(partial)) as f32;
    let angle = float(&wheel.nbt, "RotorAngle").unwrap_or(0.0) + speed * 3.0 / 10.0 * partial;
    let parity = pos[(axis + 1) % 3].wrapping_add(pos[(axis + 2) % 3]);
    let offset = if parity % 2 == 0 { 22.5 } else { 0.0 };
    let shaft_angle = wheel_angle(draw.game_time, partial, raw_speed, offset);
    draw_rotating(game, draw, axis, shaft_angle, SHAFT_MODEL);
    draw_rotating(game, draw, axis, angle, ROTOR_MODEL);
}
