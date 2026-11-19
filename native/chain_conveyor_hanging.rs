use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::Arc;

use horizon_client::mobs::{Mob, anim::BodyPose};

use super::create_chain_conveyor_hanging_math::pose;

use super::create_chain_conveyor_ride_packets::roster;
use super::create_chain_conveyor_rider::local_grip;
use super::{Game, Hand};

pub(super) const CHANNEL: &str = "create:chain_riders";

#[derive(Default)]
struct HangingPlayers {
    roster: Vec<(u128, bool)>,
    entities: HashMap<u32, bool>,
}

thread_local! {
    static HANGING: RefCell<HangingPlayers> = RefCell::new(HangingPlayers::default());
}

pub(super) fn receive(game: &Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL || game.remote.is_none() {
        return;
    }
    if let Ok(roster) = serde_json::from_slice(data) {
        HANGING.with_borrow_mut(|state| state.roster = roster);
        if std::env::var_os("CREATE_CHAIN_RIDE_POSE").is_some() {
            let count = HANGING.with_borrow(|state| state.roster.len());
            println!("CREATE_CHAIN_SKYHOOK_ROSTER {},{count}", game.ticks);
        }
    }
}

pub(super) fn clear() {
    HANGING.with_borrow_mut(|state| *state = HangingPlayers::default());
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.pause {
        return;
    }
    HANGING.with_borrow_mut(|state| {
        state.entities.clear();
        if let Some(remote) = &game.remote {
            for &(id, offhand) in &state.roster {
                if let Some(entity) = remote.player_entity(id) {
                    state.entities.insert(entity, offhand);
                }
            }
            if let Some(model) = &game.player_model
                && let Some((_, offhand)) =
                    state.roster.iter().find(|(id, _)| *id == remote.profile())
            {
                state.entities.insert(model.id, *offhand);
            }
        } else {
            if let Some(lan) = &game.lan {
                for guest in &lan.hub.guests {
                    if let Some(offhand) = roster(guest.uuid) {
                        state.entities.insert(guest.entity_id as u32, offhand);
                    }
                }
            }
            if let Some(model) = &game.player_model
                && let Some(hand) = local_grip(game)
            {
                state.entities.insert(model.id, hand == Hand::Off);
            }
        }
        let clock = game.ticks as f32;
        for mob in game.mobs.iter_mut() {
            if mob.kind.id.as_str() == "minecraft:player" {
                apply(mob, clock, state.entities.get(&mob.id).copied());
            }
        }
        if let Some(mob) = game.player_model.as_mut() {
            apply(mob, clock, state.entities.get(&mob.id).copied());
        }
    });
}

#[derive(Debug)]
struct HangingPose {
    id: u32,
    clock: f32,
    age: f32,
    left: bool,
    slim: bool,
    previous: Option<Arc<dyn BodyPose>>,
}

impl BodyPose for HangingPose {
    fn pose(&self, age: f32, at_rest: &[[f32; 9]; 6], poses: &mut [[f32; 9]; 6]) -> bool {
        let time = self.clock + (age - self.age).clamp(0.0, 1.0);
        let mut rest = *at_rest;
        // The original Java slim player starts its arms half a texel lower.
        if self.slim {
            rest[2][1] = 2.5;
            rest[3][1] = 2.5;
        }
        *poses = pose(time, self.left, rest, poses[0]);
        // Horizon's hat inherits the pose from its parent head.
        if std::env::var_os("CREATE_CHAIN_RIDE_POSE").is_some() {
            let arm = if self.left { 3 } else { 2 };
            println!(
                "CREATE_CHAIN_SKYHOOK_POSE {},{},{time:.6},{:.9},{:.9}",
                self.id, self.left, poses[arm][3], poses[arm][5]
            );
        }
        true
    }
}

fn apply(mob: &mut Mob, clock: f32, offhand: Option<bool>) {
    let hanging = mob
        .emote
        .as_ref()
        .and_then(|current| (current.as_ref() as &dyn std::any::Any).downcast_ref::<HangingPose>());
    let Some(offhand) = offhand else {
        if let Some(hanging) = hanging {
            mob.emote = hanging.previous.clone();
        }
        return;
    };
    let previous = match hanging {
        Some(hanging) => hanging.previous.clone(),
        None => mob.emote.take(),
    };
    mob.emote = Some(Arc::new(HangingPose {
        id: mob.id,
        clock,
        age: mob.age as f32,
        left: mob.extra.left_handed ^ offhand,
        slim: mob.slim,
        previous,
    }));
}
