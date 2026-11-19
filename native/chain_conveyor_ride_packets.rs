use std::cell::RefCell;
use std::collections::HashMap;

use horizon_core::geometry::Vec3;
use serde::{Deserialize, Serialize};

use super::create_chain_conveyor::Span;
use super::create_chain_conveyor_connect::MAX_DISTANCE;
use super::create_chain_conveyor_ride_motion::{Rider, target_at};
use super::create_chain_conveyor_rider::{rideable_hand, wheel};
use super::{Game, Hand};

const CHANNEL: &str = "create:chain_ride";
const TTL: u64 = 20;

thread_local! {
    static RIDERS: RefCell<HashMap<u128, (u64, bool)>> = RefCell::new(HashMap::new());
}

#[derive(Deserialize, Serialize)]
enum Update {
    Keepalive {
        at: [i32; 3],
        edge: Option<[i32; 3]>,
        progress: f32,
    },
    Stop,
}

fn send(game: &mut Game<'_>, update: Update) {
    if game.remote.is_some()
        && let Ok(data) = serde_json::to_vec(&update)
    {
        let _ = game.native_net_send_to_server(CHANNEL, &data);
    }
}

pub(super) fn keepalive(game: &mut Game<'_>, rider: &Rider) {
    if let Some(at) = rider.wheel {
        send(
            game,
            Update::Keepalive {
                at,
                edge: rider.connection,
                progress: rider.position,
            },
        );
    }
}

pub(super) fn stop(game: &mut Game<'_>) {
    send(game, Update::Stop);
}

fn validate(
    game: &mut Game<'_>,
    at: [i32; 3],
    edge: Option<[i32; 3]>,
    progress: f32,
) -> Option<Hand> {
    if !game.may_build() {
        return None;
    }
    let grip = rideable_hand(game)?;
    let Some(wheel) = wheel(game, at) else {
        return None;
    };
    let limit = if let Some(edge) = edge {
        if !wheel.links.contains(&edge) {
            return None;
        }
        Span::new(at, edge, wheel.reversed).length
    } else {
        360.0
    };
    if !(0.0..=limit).contains(&progress) {
        return None;
    }

    let Some(player) = &mut game.player else {
        return None;
    };
    if player.flying || player.is_passenger || player.health.dead_or_dying() {
        return None;
    }
    let [x, y, z] = at.map(f64::from);
    let center = Vec3::new(x + 0.5, y + 0.5, z + 0.5);
    if player.position.distance_squared(center) > (MAX_DISTANCE * 2.0).powi(2) {
        return None;
    }
    let [x, y, z] = target_at(at, edge, progress, wheel.reversed);
    let scale = player.attribute("minecraft:scale").unwrap_or(1.0);
    let hand_height = f64::from(player.dimensions.height) + 0.5 * scale;
    let head = player.position.add_vector(Vec3::new(0.0, hand_height, 0.0));
    let delta = Vec3::new(x, y, z).subtract(head);
    if delta.y < -1.0 || delta.length_squared() > 9.0 {
        return None;
    }
    player.fall_distance = 0.0;
    Some(grip)
}

fn reset_guest_counters(game: &mut Game<'_>, player: u128) {
    if let Some(host) = &mut game.lan
        && let Some(guest) = host
            .hub
            .guests
            .iter_mut()
            .find(|g| g.placed && g.uuid == player)
    {
        guest.above_ground_ticks = 0;
        guest.above_ground_vehicle_ticks = 0;
        if let Some(body) = guest.motion.as_deref_mut() {
            body.fall_distance = 0.0;
        }
    }
}

pub(super) fn receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 128 {
        return;
    }
    let Ok(update) = serde_json::from_slice(data) else {
        return;
    };
    let (event, changed) = match update {
        Update::Keepalive { at, edge, progress } => {
            let mut accepted = None;
            game.native_as_player(player, |game| accepted = validate(game, at, edge, progress));
            let Some(grip) = accepted else { return };
            let offhand = grip == Hand::Off;
            let prior = RIDERS.with_borrow_mut(|riders| {
                riders.insert(player, (game.ticks.saturating_add(TTL), offhand))
            });
            (
                "KEEPALIVE",
                prior.is_none_or(|(_, was_offhand)| was_offhand != offhand),
            )
        }
        Update::Stop => {
            if RIDERS
                .with_borrow_mut(|riders| riders.remove(&player))
                .is_none()
            {
                return;
            }
            ("STOP", true)
        }
    };
    reset_guest_counters(game, player);
    if changed {
        broadcast(game);
    }
    if std::env::var_os("CREATE_CHAIN_RIDE_PACKETS").is_some() {
        println!("CREATE_CHAIN_RIDE_{event} {},{player:032x}", game.ticks);
    }
}

pub(super) fn roster(uuid: u128) -> Option<bool> {
    RIDERS.with_borrow(|riders| riders.get(&uuid).map(|(_, offhand)| *offhand))
}

fn broadcast(game: &mut Game<'_>) {
    let mut roster: Vec<_> = RIDERS.with_borrow(|riders| {
        riders
            .iter()
            .map(|(&uuid, &(_, offhand))| (uuid, offhand))
            .collect()
    });
    roster.sort_unstable();
    let Ok(data) = serde_json::to_vec(&roster) else {
        return;
    };
    for player in game.native_server_players() {
        let _ = game.native_net_send_to_player(
            player.uuid,
            super::create_chain_conveyor_hanging::CHANNEL,
            &data,
        );
    }
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.remote.is_some() || game.lan.is_none() {
        return;
    }
    let removed = RIDERS.with_borrow_mut(|riders| {
        let before = riders.len();
        riders.retain(|player, (expires, _)| {
            let active = game.ticks < *expires;
            if !active && std::env::var_os("CREATE_CHAIN_RIDE_PACKETS").is_some() {
                println!("CREATE_CHAIN_RIDE_EXPIRED {},{player:032x}", game.ticks);
            }
            active
        });
        before != riders.len()
    });
    if removed || game.ticks % 10 == 0 {
        broadcast(game);
    }
}
