use horizon_client::particles::ParticleOptions;
use horizon_core::geometry::Direction;

use crate::world_primitives::WorldPrimitives;

use super::Game;
use super::create_ejector::{EJECTOR, Trajectory, distances, target};
use super::create_fan::facing;
use super::create_machines::mod_entity;

const AMBER: u32 = 0xffffcb74;
const GREEN: u32 = 0xff9ede73;
const RED: u32 = 0xffff7171;
const WIDTH: f64 = 1.0 / 16.0;

struct Aim {
    at: [i32; 3],
    target: [i32; 3],
    direction: Direction,
    distance: i32,
    elevation: i32,
    color: u32,
}

fn wrench_aim(game: &Game<'_>) -> Option<Aim> {
    if !game.stack_in(game.selected).is_some_and(|stack| stack.item.as_ref() == "create:wrench") {
        return None;
    }
    let at = game.pick()?.pos;
    let entity = mod_entity(game, at).filter(|entity| entity.id == EJECTOR)?;
    let direction = facing(game, game.world.block(at[0], at[1], at[2]))?;
    let (distance, elevation) = distances(&entity.nbt);
    let distance = distance.max(1);
    Some(Aim {
        at,
        target: target(at, direction, distance, elevation),
        direction,
        distance,
        elevation,
        color: GREEN,
    })
}

fn held_aim(game: &Game<'_>, target: [i32; 3]) -> Option<Aim> {
    let hit = game.pick()?;
    let at: [i32; 3] = std::array::from_fn(|axis| hit.pos[axis] + hit.face[axis]);
    let [dx, dy, dz] = std::array::from_fn(|axis| target[axis] - at[axis]);
    let x_distance = if dz.abs() > dx.abs() { 0 } else { dx };
    let z_distance = if dz.abs() < dx.abs() { 0 } else { dz };
    let direction = match (x_distance, z_distance) {
        (1..=32, 0) => Direction::East,
        (-32..=-1, 0) => Direction::West,
        (0, 1..=32) => Direction::South,
        (0, -32..=-1) => Direction::North,
        _ => return None,
    };
    Some(Aim {
        at: [target[0] - x_distance, at[1], target[2] - z_distance],
        target,
        direction,
        distance: (x_distance + z_distance).abs(),
        elevation: dy,
        color: if x_distance == dx && z_distance == dz { GREEN } else { RED },
    })
}

fn preview(game: &Game<'_>) -> Option<([i32; 3], Option<Aim>, &'static str)> {
    if let Some(aim) = wrench_aim(game) {
        Some((aim.target, Some(aim), "WRENCH"))
    } else {
        let selection = super::create_ejector_target::preview_target(game)?;
        Some((selection, held_aim(game, selection), "HELD"))
    }
}

fn tracing(mode: &str) -> bool {
    static WRENCH: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    static HELD: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    if mode == "WRENCH" {
        *WRENCH.get_or_init(|| std::env::var_os("CREATE_EJECTOR_WRENCH_PREVIEW").is_some())
    } else {
        *HELD.get_or_init(|| std::env::var_os("CREATE_EJECTOR_HELD_PREVIEW").is_some())
    }
}

pub(super) fn tick(game: &mut Game<'_>) {
    super::create_ejector_target::client_tick(game);
    let Some((_, Some(aim), mode)) = preview(game) else {
        return;
    };
    let trajectory = Trajectory::new(aim.distance, aim.elevation);
    let duration = trajectory.time + 3.0;
    let count = duration as i32 / 3 + 1;
    let spacing = duration / f64::from(count);
    let render_time = (game.ticks % 1_728_000) as f32 + game.clock.fraction() as f32;
    let phase = f64::from(render_time / 3.0) % spacing;
    let rgb = [16, 8, 0].map(|shift| ((aim.color >> shift) & 0xff) as f32 / 255.0);
    let options = ParticleOptions::dust(rgb, 1.0);
    let (at, facing) = (aim.at, aim.direction.normal());
    if tracing(mode) {
        let [x, y, z] = at;
        let [dx, _, dz] = facing;
        eprintln!(
            "CREATE_EJECTOR_{mode}_ARC {x},{y},{z},{dx},{dz},{},{},{count},{render_time:.9},{spacing:.9},{:06x}",
            aim.distance, aim.elevation, aim.color & 0xffffff
        );
    }
    for index in 0..count {
        let time = phase + f64::from(index) * spacing;
        let point = trajectory.world_point(at, aim.direction, time).components();
        game.particles.add(&options, point, [0.0; 3]);
        if tracing(mode) {
            let [x, y, z] = point;
            eprintln!("CREATE_EJECTOR_{mode}_DUST {index},{time:.9},{x:.9},{y:.9},{z:.9}");
        }
    }
}

fn outline(primitives: &mut WorldPrimitives, low: [f64; 3], high: [f64; 3], color: u32) {
    for axis in (0..3).filter(|&axis| low[axis] != high[axis]) {
        let a = (axis + 1) % 3;
        let b = (axis + 2) % 3;
        let choices_a = if low[a] == high[a] { 1 } else { 2 };
        let choices_b = if low[b] == high[b] { 1 } else { 2 };
        for first in [low[a], high[a]].into_iter().take(choices_a) {
            for second in [low[b], high[b]].into_iter().take(choices_b) {
                let mut start = low;
                let mut end = high;
                start[a] = first - WIDTH / 2.0;
                end[a] = first + WIDTH / 2.0;
                start[b] = second - WIDTH / 2.0;
                end[b] = second + WIDTH / 2.0;
                primitives.filled_box(start, end, color);
            }
        }
    }
}

pub(super) fn draw(game: &Game<'_>, primitives: &mut WorldPrimitives) {
    let Some((target, aim, mode)) = preview(game) else {
        return;
    };
    let [tx, ty, tz] = target;
    let state = game.world.block(tx, ty, tz);
    let facts = game.res.facts();
    let shape = &facts.get(state).outline;
    let (mut low, mut high) = ([0.0; 3], [1.0; 3]);
    if let Some(first) = shape.first() {
        low = [first[0], first[1], first[2]].map(f64::from);
        high = [first[3], first[4], first[5]].map(f64::from);
        for part in shape.iter().skip(1) {
            for axis in 0..3 {
                low[axis] = low[axis].min(f64::from(part[axis]));
                high[axis] = high[axis].max(f64::from(part[axis + 3]));
            }
        }
    }
    if let Some(aim) = aim {
        let at = aim.at.map(f64::from);
        outline(primitives, at, [at[0] + 1.0, at[1], at[2] + 1.0], aim.color);
    }
    outline(primitives,
        std::array::from_fn(|axis| low[axis] + f64::from(target[axis])),
        std::array::from_fn(|axis| high[axis] + f64::from(target[axis])),
        AMBER);
    if tracing(mode) {
        let [x0, y0, z0] = low;
        let [x1, y1, z1] = high;
        eprintln!("CREATE_EJECTOR_{mode}_OUTLINE {tx},{ty},{tz},{x0:.5},{y0:.5},{z0:.5},{x1:.5},{y1:.5},{z1:.5},ffcb74,{WIDTH:.5}");
    }
}
