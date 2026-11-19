use std::cell::RefCell;
use std::collections::HashMap;

use horizon_client::block_entity_render::vertex_light;
use horizon_core::geometry::Vec3;
use horizon_core::geometry::trig::{RAD_TO_DEG, atan2};
use horizon_world::nbt::Tag;

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_chain_conveyor::loop_position;
use super::create_chain_conveyor_packages::{CARGO_SAMPLE_TIME, VisualCargo, visual_cargo};
use super::create_chain_conveyor_span::rotate_y;
use super::create_chain_conveyor_visual::directed_span;
use super::create_machines::{CONVEYOR, int, mod_entity};
use super::create_package_style::dimensions;
use super::native_block_entity_draw::BlockEntityDraw;

const Y: [f32; 3] = [0.0, 1.0, 0.0];
const X: [f32; 3] = [1.0, 0.0, 0.0];
const Z: [f32; 3] = [0.0, 0.0, 1.0];

#[derive(Clone, Copy)]
struct Point {
    target: Vec3,
    physical: Vec3,
    yaw: f32,
}

#[derive(Clone, Copy)]
struct Motion {
    tick: i64,
    source_yaw: f32,
    last_step: Option<(Point, Vec3)>,
    previous: Point,
    current: Point,
    velocity: Vec3,
}

thread_local! {
    static BOXES: RefCell<HashMap<i64, Motion>> = RefCell::new(HashMap::new());
}

fn wrap(degrees: f32) -> f32 {
    let mut degrees = degrees % 360.0;
    if degrees >= 180.0 {
        degrees -= 360.0;
    }
    if degrees < -180.0 {
        degrees += 360.0;
    }
    degrees
}

fn interpolate(from: Vec3, to: Vec3, fraction: f64) -> Vec3 {
    from.add_vector(to.subtract(from).scale(fraction))
}

fn anchor(
    game: &Game<'_>,
    at: [i32; 3],
    entity: &ModBlockEntity,
    cargo: &VisualCargo,
) -> Option<(Vec3, f32, bool)> {
    let reversed = int(&entity.nbt, "Reversed") == Some(1);
    let (position, yaw) = if let Some(edge) = cargo.edge {
        let span = directed_span(game, at, entity, edge)?;
        let x = span.end[0] - span.start[0];
        let z = span.end[2] - span.start[2];
        (
            span.position(cargo.position),
            wrap(atan2(x, z) as f32 * RAD_TO_DEG - 90.0),
        )
    } else {
        (
            loop_position(at, cargo.position),
            wrap(cargo.position) + if reversed { 180.0 } else { 0.0 },
        )
    };
    let [x, y, z] = position;
    Some((Vec3::new(x, y, z), yaw, reversed))
}

fn sample_time(game: &Game<'_>, entity: &ModBlockEntity) -> i64 {
    if game.remote.is_some()
        && let Some(Tag::Long(tick)) = entity.nbt.get(&CARGO_SAMPLE_TIME.into())
    {
        return *tick;
    }
    game.world.game_time
}

fn animate(id: i64, tick: i64, anchor: Vec3, yaw: f32) -> Motion {
    BOXES.with_borrow_mut(|boxes| {
        let target = anchor.add_vector(Vec3::new(0.0, -9.0 / 16.0, 0.0));
        let start = Point {
            target,
            physical: target,
            yaw: 0.0,
        };
        let recorded = boxes
            .get(&id)
            .copied()
            .filter(|state| (0..30).contains(&(tick - state.tick)));
        let last_step = match recorded {
            Some(state) if state.tick == tick => {
                if state.current.target == target && state.source_yaw == yaw {
                    return state;
                }
                // A later block snapshot can correct this tick's pose.
                // Reuse its original input instead of advancing twice.
                state.last_step
            }
            Some(state) => Some((state.current, state.velocity)),
            None => None,
        };
        let (previous, physical, velocity) = if let Some((prior, velocity)) = last_step {
            let delta = prior.physical.subtract(anchor);
            let physical = if delta.length_squared() > 2.25 {
                anchor.add_vector(delta.scale(1.5 / delta.length()))
            } else {
                prior.physical
            };
            let velocity = velocity
                .add_vector(Vec3::new(0.0, -0.25, 0.0))
                .scale(0.75)
                .add_vector(anchor.subtract(physical).scale(0.25));
            (prior, physical.add_vector(velocity), velocity)
        } else {
            (start, target, Vec3::new(0.0, 0.0, 0.0))
        };
        let motion = Motion {
            tick,
            source_yaw: yaw,
            last_step,
            previous,
            current: Point {
                target,
                physical,
                yaw: previous.yaw + 0.25 * wrap(yaw - previous.yaw),
            },
            velocity,
        };
        boxes.insert(id, motion);
        motion
    })
}

pub(super) fn tick(game: &Game<'_>) {
    let Some([x, _, z]) = game.eye_position() else {
        return;
    };
    let day = game.world.game_time;
    BOXES.with_borrow_mut(|boxes| boxes.retain(|_, motion| day.saturating_sub(motion.tick) < 30));
    for &(x, y, z) in game.world.block_entities.mods_near(x, z, 64.0) {
        let at = [x, y, z];
        if let Some(entity) = mod_entity(game, at).filter(|entity| entity.id == CONVEYOR) {
            for cargo in visual_cargo(&entity.nbt) {
                if let Some((anchor, yaw, _)) = anchor(game, at, entity, &cargo) {
                    animate(cargo.id, sample_time(game, entity), anchor, yaw);
                }
            }
        }
    }
}

pub(super) fn draw(
    game: &Game<'_>,
    at: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
    trace: bool,
) {
    for cargo in visual_cargo(&entity.nbt) {
        let Some((anchor, facing, reversed)) = anchor(game, at, entity, &cargo) else {
            continue;
        };
        let Some((width, height)) = dimensions(&cargo.item) else {
            continue;
        };
        let width = (width * 16.0).round() as i32;
        let height = (height * 16.0).round() as i32;
        let hook = match (width, height) {
            (12, 12) => 23.0,
            (10, 12) => 22.0,
            (10, 8) => 18.0,
            _ => 21.0,
        };
        let pose = animate(cargo.id, sample_time(game, entity), anchor, facing);
        let fraction = f64::from(draw.partial);
        let target = interpolate(pose.previous.target, pose.current.target, fraction);
        let physical = interpolate(pose.previous.physical, pose.current.physical, fraction);
        let yaw = pose.previous.yaw + draw.partial * wrap(pose.current.yaw - pose.previous.yaw);
        let delta = rotate_y(
            target
                .add_vector(Vec3::new(0.0, 0.5, 0.0))
                .subtract(physical),
            -f64::from(yaw),
        );
        let roll = (wrap(atan2(-delta.x, delta.y) as f32 * RAD_TO_DEG) * 0.5).clamp(-25.0, 25.0);
        let pitch = (wrap(atan2(delta.z, delta.y) as f32 * RAD_TO_DEG) * 0.5).clamp(-25.0, 25.0);
        let model = format!("create:item/{}", cargo.item.trim_start_matches("create:"));
        let rig = format!("create:item/package/rigging_{width}x{height}");
        let translated = [
            target.x - f64::from(at[0]),
            target.y - f64::from(at[1]) + 10.0 / 16.0,
            target.z - f64::from(at[2]),
        ];
        let [lx, ly, lz] = [physical.x, physical.y, physical.z].map(|axis| axis.floor() as i32);
        let wheel_light = draw.light;
        draw.light = vertex_light(game.world.light(lx, ly, lz));
        let mut vertices = [0; 2];
        let mut vertex_lights = [u32::MAX; 2];
        draw.push();
        draw.translate(translated.map(|value| value as f32));
        draw.rotate_about(Y, yaw, [0.0; 3]);
        draw.rotate_about(Z, roll, [0.0; 3]);
        draw.rotate_about(X, pitch, [0.0; 3]);
        for (i, model) in [model, rig].into_iter().enumerate() {
            draw.push();
            if i == 1 && reversed {
                draw.rotate_about(Y, 180.0, [0.0; 3]);
            }
            draw.translate([-0.5, -0.5 + (7.0 - hook) / 16.0, -0.5]);
            let before = draw.vertices_mut().len();
            game.native_draw_model(draw, &model, 0xFFFFFF);
            let drawn = &draw.vertices_mut()[before..];
            vertices[i] = drawn.len();
            if trace
                && let Some(first) = drawn.first()
                && drawn.iter().all(|vertex| vertex.light == first.light)
            {
                vertex_lights[i] = first.light;
            }
            draw.pop();
        }
        draw.pop();
        draw.light = wheel_light;
        if trace {
            println!(
                "CREATE_CHAIN_BOX_LIGHT {},{},{:.9},{lx},{ly},{lz},{wheel_light},{},{}",
                cargo.id, pose.tick, draw.partial, vertex_lights[0], vertex_lights[1]
            );
            let point = pose.current;
            println!(
                "CREATE_CHAIN_BOX {at:?},{},{},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9},{},{}",
                cargo.id,
                pose.tick,
                draw.partial,
                point.target.x,
                point.target.y,
                point.target.z,
                point.physical.x,
                point.physical.y,
                point.physical.z,
                point.yaw,
                roll,
                pitch,
                vertices[0],
                vertices[1]
            );
        }
    }
}
