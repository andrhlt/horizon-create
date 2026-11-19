use std::cell::RefCell;

use horizon_client::mod_api::ServerTickPhase;
use horizon_client::first_person::Hand as RenderHand;
use horizon_client::particles::{ParticleOptions, ParticleType};
use horizon_core::random::RandomSource;
use serde::{Deserialize, Serialize};

use super::{Game, Hand};
use crate::world_primitives::WorldPrimitives;

const CHANNEL: &str = "create:worldshaper_shot";
const SOUND: &str = "minecraft:block.note_block.basedrum";

#[derive(Clone, Serialize, Deserialize)]
struct Shot {
    start: [f64; 3],
    end: [f64; 3],
    dimension: String,
    main_hand: bool,
    self_shot: bool,
}

struct Pending {
    eye: [f64; 3], yaw: f32, pitch: f32, end: [f64; 3], dimension: String,
    main_hand: bool, shooter: Option<u128>, fallback_left: bool,
}

struct Beam { shot: Shot, intensity: f32 }

thread_local! {
    static PENDING: RefCell<Vec<Pending>> = const { RefCell::new(Vec::new()) };
    static RECOIL: RefCell<[(f32, f32); 2]> = const { RefCell::new([(0.0, 0.0); 2]) };
    static BEAMS: RefCell<Vec<Beam>> = const { RefCell::new(Vec::new()) };
}

/// Called only after a successful authoritative target hit, before the target changes.
pub(super) fn shot(game: &mut Game<'_>, end: [f64; 3]) {
    let Some(eye) = game.eye_position() else { return };
    let pending = Pending {
        eye, yaw: game.yaw, pitch: game.pitch, end, dimension: game.native_dimension().to_owned(),
        main_hand: game.hand == Hand::Main, shooter: game.native_acting_player().map(|p| p.uuid),
        fallback_left: game.settings.main_hand_left,
    };
    if std::env::var_os("CREATE_WORLDSHAPER_EFFECT_TRACE").is_some() {
        eprintln!("CREATE_WORLDSHAPER_EFFECT enqueue window={} shooter={:?} end={:?}", game.native_window(), pending.shooter, end);
    }
    PENDING.with_borrow_mut(|queue| queue.push(pending));
}

pub(super) fn server_tick(game: &mut Game<'_>, phase: ServerTickPhase) {
    if !matches!(phase, ServerTickPhase::ServerTickEnd { .. }) { return; }
    let shots = PENDING.with_borrow_mut(std::mem::take);
    if shots.is_empty() { return; }
    if std::env::var_os("CREATE_WORLDSHAPER_EFFECT_TRACE").is_some() {
        eprintln!("CREATE_WORLDSHAPER_EFFECT dispatch count={}", shots.len());
    }
    let players = game.native_server_players();
    for pending in shots {
        // During a guest interaction the hub is borrowed out; it is restored here.
        let left = pending.shooter.and_then(|id| game.native_player_client(id))
            .map_or(pending.fallback_left, |info| info.main_hand == 0);
        let right = pending.main_hand != left;
        let [x, y, z] = [if right { -0.35 } else { 0.35 }, -0.1, 1.0];
        // The accepted hit is on the shooter's actual view ray. The server's
        // last look packet can lag the interaction, so use that ray for the
        // barrel orientation rather than a stale server yaw/pitch.
        let delta: [f64; 3] = std::array::from_fn(|i| pending.end[i] - pending.eye[i]);
        let horizontal = delta[0].hypot(delta[2]);
        let pitch = if horizontal > 1e-9 { delta[1].atan2(horizontal) }
            else { f64::from(-pending.pitch).to_radians() };
        let yaw = if horizontal > 1e-9 { delta[0].atan2(delta[2]) }
            else { f64::from(-pending.yaw).to_radians() };
        let (sp, cp) = pitch.sin_cos();
        let (sy, cy) = yaw.sin_cos();
        let rotated_y = y * cp + z * sp;
        let rotated_z = z * cp - y * sp;
        let start = [pending.eye[0] + x * cy + rotated_z * sy, pending.eye[1] + rotated_y,
                     pending.eye[2] + rotated_z * cy - x * sy];
        for player in &players {
            if player.dimension != pending.dimension || distance_squared(player.position, start) > 10000.0 { continue; }
            let shot = Shot { start, end: pending.end, dimension: pending.dimension.clone(),
                              main_hand: pending.main_hand, self_shot: pending.shooter == Some(player.uuid) };
            if let Ok(data) = serde_json::to_vec(&shot) {
                let _ = game.native_net_send_to_player(player.uuid, CHANNEL, &data);
            }
        }
        if std::env::var_os("CREATE_WORLDSHAPER_EFFECT_TRACE").is_some() {
            eprintln!("CREATE_WORLDSHAPER_EFFECT barrel left={} start={:?}", left, start);
        }
    }
}

fn distance_squared(a: [f64; 3], b: [f64; 3]) -> f64 {
    (0..3).map(|i| (a[i] - b[i]).powi(2)).sum()
}

fn accept(game: &mut Game<'_>, shot: Shot) {
    if !game.native_window() || game.player.is_none() || game.native_dimension() != shot.dimension
        || !shot.start.into_iter().chain(shot.end).all(f64::is_finite)
        || game.eye_position().is_none_or(|at| distance_squared(at, shot.start) > 10000.0)
    { return; }
    let rod = ParticleOptions::simple(ParticleType::EndRod);
    let firework = ParticleOptions::simple(ParticleType::Firework);
    let mut rods = 0;
    let mut fireworks = 0;
    for _ in 0..10 {
        let velocity = std::array::from_fn(|_| (game.world.random.next_double() - 0.5) * f64::from(0.2_f32));
        let offset: [f64; 3] = std::array::from_fn(|_| (game.world.random.next_double() - 0.5) * f64::from(0.2_f32));
        rods += usize::from(game.native_add_particle(&rod, shot.end, velocity));
        fireworks += usize::from(game.native_add_particle(&firework, std::array::from_fn(|i| shot.end[i] + offset[i]), [0.0; 3]));
    }
    if shot.self_shot {
        RECOIL.with_borrow_mut(|recoil| recoil[usize::from(!shot.main_hand)] = (0.0, 0.2));
    }
    let pitch = if shot.main_hand { 0.1 } else { 0.9 };
    game.audio.play_on(7, SOUND, Some(shot.start), 0.1, pitch);
    if std::env::var_os("CREATE_WORLDSHAPER_EFFECT_TRACE").is_some() {
        eprintln!("CREATE_WORLDSHAPER_EFFECT shot {:?} {:?} main={} rods={} fireworks={} sound={} pitch={}",
            shot.start, shot.end, shot.main_hand, rods, fireworks, SOUND, pitch);
        eprintln!("CREATE_WORLDSHAPER_EFFECT recoil self={} main={}", shot.self_shot, shot.main_hand);
    }
    BEAMS.with_borrow_mut(|beams| beams.push(Beam { shot, intensity: 1.0 }));
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel == CHANNEL && data.len() <= 512 && let Ok(shot) = serde_json::from_slice::<Shot>(data) {
        if std::env::var_os("CREATE_WORLDSHAPER_EFFECT_TRACE").is_some() { eprintln!("CREATE_WORLDSHAPER_EFFECT receive"); }
        accept(game, shot);
    }
}

pub(super) fn tick(game: &mut Game<'_>) {
    RECOIL.with_borrow_mut(|recoil| for (previous, current) in recoil { *previous = *current; *current *= 0.8; });
    BEAMS.with_borrow_mut(|beams| {
        beams.retain(|beam| beam.intensity >= 0.1 && beam.shot.dimension == game.native_dimension());
        for beam in beams { beam.intensity *= 0.6; }
    });
}

pub(super) fn draw(primitives: &mut WorldPrimitives) {
    BEAMS.with_borrow(|beams| for beam in beams {
        let progress = f64::from(1.0 - beam.intensity);
        let end = std::array::from_fn(|i| beam.shot.start[i] + (beam.shot.end[i] - beam.shot.start[i]) * progress);
        primitives.line(beam.shot.start, end, 0xffffffff, (3.0 * beam.intensity).max(0.5));
    });
}

pub(super) fn hand_pose(hand: RenderHand, stack: Option<&crate::items::ItemStack>, partial: f32, z: &mut f32) {
    if stack.is_none_or(|stack| stack.item.as_ref() != "create:handheld_worldshaper") { return; }
    let index = usize::from(hand == RenderHand::Off);
    RECOIL.with_borrow(|recoil| {
        let (previous, current) = recoil[index];
        *z += previous + (current - previous) * partial;
    });
}

pub(super) fn clear() {
    BEAMS.with_borrow_mut(Vec::clear);
    RECOIL.with_borrow_mut(|recoil| *recoil = [(0.0, 0.0); 2]);
}
