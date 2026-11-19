use horizon_core::geometry::Vec3;

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_machines::{float, mod_entity, saved_speed};
use super::create_turntable_player_math::{camera_turn, edge_velocity};
use super::create_visuals::{draw_rotating, wheel_angle};
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const BLOCK: &str = "create:turntable";
pub(super) const MODEL: &str = "create:block/turntable";
pub(super) const STRESS_IMPACT: f32 = 4.0;

pub(super) fn connects(face: [i32; 3]) -> bool {
    face == [0, -1, 0]
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let phase = if pos[0].wrapping_add(pos[2]) % 2 == 0 {
        22.5
    } else {
        0.0
    };
    let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
    draw_rotating(game, draw, 1, angle, MODEL);
}

pub(super) fn tick_mob(game: &mut Game<'_>, id: u32) {
    let Some(index) = game
        .mobs
        .iter()
        .position(|mob| mob.id == id && mob.alive() && !mob.removed)
    else {
        return;
    };
    let mob = &game.mobs[index];
    let feet = mob.position.components()[1];
    if !mob.on_ground || mob.velocity.components()[1] > 0.0 || feet - feet.floor() < 0.5 {
        return;
    }

    // The original checks every block cell inside the mob's bounds, even when
    // another block provided the collision under its feet.
    let bounds = mob.bounds().deflate(Vec3::new(1e-7, 1e-7, 1e-7));
    let min = bounds.min_position().components().map(|n| n.floor() as i32);
    let max = bounds.max_position().components().map(|n| n.floor() as i32);
    let y = feet.floor() as i32;
    for z in min[2]..=max[2] {
        for x in min[0]..=max[0] {
            let pos = [x, y, z];
            if game.native_block(pos) != BLOCK {
                continue;
            }
            let speed = mod_entity(game, pos).map_or(0.0, |be| saved_speed(&be.nbt) * 3.0 / 10.0);
            if speed == 0.0 {
                continue;
            }
            let mob = &mut game.mobs[index];
            let head = mob.head_yaw - speed;
            mob.yaw -= speed;
            mob.body_yaw = head;
            mob.head_yaw = head;
            mob.ai.no_action_time = 20;
            mob.on_ground = false;
            mob.needs_sync = true;
            return;
        }
    }
}

fn center(pos: [i32; 3]) -> Vec3 {
    Vec3::new(
        f64::from(pos[0]) + 0.5,
        f64::from(pos[1]) + 0.5,
        f64::from(pos[2]) + 0.5,
    )
}

fn client_rpm(game: &Game<'_>, pos: [i32; 3]) -> f32 {
    mod_entity(game, pos)
        .and_then(|be| float(&be.nbt, "VisualSpeed"))
        .unwrap_or(0.0)
}

fn at_turntable(game: &Game<'_>, pos: [i32; 3]) -> bool {
    game.native_state_block(game.world.block(pos[0], pos[1], pos[2])) == Some(BLOCK)
}

fn tracing() -> bool {
    static ENABLED: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ENABLED.get_or_init(|| std::env::var("CREATE_TURNTABLE_PLAYER_TRACE").is_ok_and(|v| v == "1"))
}

fn trace_line(line: String) {
    use std::io::Write;
    let _ = std::io::stderr().lock().write_all(line.as_bytes());
}

pub(super) fn player_frame(game: &mut Game<'_>, elapsed: std::time::Duration) {
    // The original DeltaTracker advances on integer milliseconds. Keep sub-millisecond
    // time until the cumulative clock crosses a millisecond boundary.
    thread_local! {
        static FRAME_TIME: std::cell::Cell<std::time::Duration> = const {
            std::cell::Cell::new(std::time::Duration::ZERO)
        };
    }
    let delta = FRAME_TIME.with(|clock| {
        let previous = clock.get();
        let now = previous + elapsed;
        clock.set(now);
        (now.as_millis() - previous.as_millis()) as f32 / 50.0
    });
    let realtime = if delta > 7.0 { 0.5 } else { delta };
    let Some(player) = game.player.as_ref() else {
        return;
    };
    if game.pause || game.title.is_some() || !player.ground.on_ground {
        return;
    }
    let pos = player.ground.supporting_block.map_or_else(
        || {
            let [x, y, z] = player.position.components();
            [
                x.floor() as i32,
                (y - f64::from(1.0e-5_f32)).floor() as i32,
                z.floor() as i32,
            ]
        },
        |pos| [pos.x, pos.y, pos.z],
    );
    if !at_turntable(game, pos) {
        return;
    }

    let rpm = client_rpm(game, pos);
    let tick_rate = game.clock.rate();
    let partial = game.clock.fraction() as f32;
    let offset = center(pos).vector_to(player.position);
    let turn = camera_turn(rpm, tick_rate, realtime, partial, offset);
    let before = game.yaw;
    game.yaw -= turn;
    if let Some(model) = game.player_model.as_mut() {
        model.body_yaw -= turn;
    }
    if tracing() {
        let [x, y, z] = offset.components();
        trace_line(format!(
            "CREATE_TURNTABLE_FRAME {},{rpm},{tick_rate},{realtime},{partial},{x},{y},{z},{before},{}\n",
            game.ticks, game.yaw
        ));
    }
}

pub(super) fn player_contact(game: &mut Game<'_>) {
    let Some(player) = game.player.as_ref() else {
        return;
    };
    let [x, y, z] = player.position.components();
    let cell = [x.floor() as i32, y.floor() as i32, z.floor() as i32];
    if !player.ground.on_ground
        || player.velocity.y > 0.0
        || y - y.floor() < 0.5
        || at_turntable(game, cell)
    {
        return;
    }

    let bounds = player.bounds().deflate(Vec3::new(1e-7, 1e-7, 1e-7));
    let min = bounds.min_position().components().map(|n| n.floor() as i32);
    let max = bounds.max_position().components().map(|n| n.floor() as i32);
    let start_velocity = player.velocity;
    let position = player.position;
    let mut velocity = start_velocity;
    for bz in min[2]..=max[2] {
        for bx in min[0]..=max[0] {
            let origin = [bx, cell[1], bz];
            if !at_turntable(game, origin) {
                continue;
            }
            let rpm = client_rpm(game, origin);
            if rpm == 0.0 {
                continue;
            }
            velocity = velocity.add_vector(edge_velocity(rpm, center(origin), position));
            if tracing() {
                let [ox, oy, oz] = center(origin).vector_to(position).components();
                trace_line(format!(
                    "CREATE_TURNTABLE_EDGE {},{rpm},{ox},{oy},{oz},{},{},{},{},{},{}\n",
                    game.ticks,
                    start_velocity.x,
                    start_velocity.y,
                    start_velocity.z,
                    velocity.x,
                    velocity.y,
                    velocity.z
                ));
            }
        }
    }
    if let Some(player) = game.player.as_mut() {
        player.velocity = velocity;
    }
}
