use std::collections::{BTreeSet, VecDeque};

use horizon_core::geometry::Direction;
use horizon_world::level::flags;
use horizon_world::nbt::{JavaString, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_fluids::{GLASS_PIPE, PIPE, PUMP, RANGE, name, open_to};
use super::create_machines::{mod_entity, offset};

pub(super) const BLOCK: &str = "create:encased_fluid_pipe";
const CASING: &str = "create:copper_casing";
const TRANSFER_RESTART: &str = "EncasingTransferRestart";

fn has_face(game: &Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    game.native_block_property(pos, name(face)).as_deref() == Some("true")
}

fn faces(game: &Game<'_>, pos: [i32; 3]) -> [bool; 6] {
    Direction::ALL.map(|face| has_face(game, pos, face))
}

fn neighbor_connects(game: &Game<'_>, next: [i32; 3], towards: Direction) -> bool {
    match game.native_block(next).as_str() {
        PIPE => {
            !mod_entity(game, next).is_some_and(|pipe| pipe.nbt.contains_key(&"Bracket".into()))
                || (has_face(game, next, towards)
                    && has_face(game, next, towards.opposite())
                    && faces(game, next).into_iter().filter(|&open| open).count() == 2)
        }
        "create:basin"
        | "create:fluid_tank"
        | "create:creative_fluid_tank"
        | "create:portable_fluid_interface"
        | "minecraft:beehive"
        | "minecraft:bee_nest"
        | "minecraft:cauldron"
        | "minecraft:water_cauldron"
        | "minecraft:lava_cauldron" => true,
        "create:item_drain" => towards != Direction::Up,
        "create:spout" => towards != Direction::Down,
        "create:hose_pulley" => super::create_hose::pipe_face(game, next) == Some(towards),
        _ => open_to(game, next, towards),
    }
}

fn reconnected_faces(game: &Game<'_>, pos: [i32; 3], prior: [bool; 6]) -> [bool; 6] {
    let mut connected = Direction::ALL
        .map(|face| neighbor_connects(game, offset(pos, face.normal()), face.opposite()));
    match connected.into_iter().filter(|&face| face).count() {
        0 if prior.into_iter().filter(|&face| face).count() == 2 => prior,
        0 => {
            let preferred = Direction::ALL
                .into_iter()
                .zip(prior)
                .find_map(|(face, open)| open.then_some(face))
                .unwrap_or(Direction::Up);
            connected[preferred as usize] = true;
            connected[preferred.opposite() as usize] = true;
            connected
        }
        1 => {
            let face = Direction::ALL
                .into_iter()
                .zip(connected)
                .find_map(|(face, open)| open.then_some(face))
                .expect("one face connects");
            connected[face.opposite() as usize] = true;
            connected
        }
        _ => connected,
    }
}

fn wipe_pressure(entity: &mut ModBlockEntity) {
    for direction in Direction::ALL {
        if let Some(Tag::Compound(port)) = entity.nbt.get_mut(&name(direction).into()) {
            port.remove(&"Pressure".into());
        }
    }
}

fn has_pressure(entity: &ModBlockEntity) -> bool {
    Direction::ALL.iter().any(|direction| {
        matches!(entity.nbt.get(&name(*direction).into()), Some(Tag::Compound(port))
            if port.contains_key(&"Pressure".into()))
    })
}

pub(super) fn transfer_restarting(entity: &ModBlockEntity, now: i64) -> bool {
    matches!(entity.nbt.get(&TRANSFER_RESTART.into()), Some(Tag::Long(restart)) if now < *restart)
}

fn reset_network(game: &mut Game<'_>, origin: [i32; 3], first: [bool; 6]) {
    // Preserve loaded fluid, but restart pressure propagation on the next tick.
    // Port readiness and FluidNetwork's two pre-propagation ticks delay transfer.
    let restart = game.world.game_time + 5;
    let mut visited = BTreeSet::from([origin]);
    let mut frontier = VecDeque::from([(origin, first, 0)]);
    let mut pumps = BTreeSet::new();
    while let Some((pos, open, distance)) = frontier.pop_front() {
        game.native_with_mod_block_entity(pos, |entity| {
            wipe_pressure(entity);
            entity
                .nbt
                .insert(TRANSFER_RESTART.into(), Tag::Long(restart));
        });
        for (face, connected) in Direction::ALL.into_iter().zip(open) {
            if !connected {
                continue;
            }
            let next = offset(pos, face.normal());
            if !open_to(game, next, face.opposite()) {
                continue;
            }
            if game.native_block(next) == PUMP {
                pumps.insert(next);
                continue;
            }
            let Some(pipe) = mod_entity(game, next) else {
                continue;
            };
            if (distance >= RANGE && !has_pressure(pipe)) || !visited.insert(next) {
                continue;
            }
            frontier.push_back((
                next,
                Direction::ALL.map(|side| open_to(game, next, side)),
                distance + 1,
            ));
        }
    }
    for pump in pumps {
        game.native_with_mod_block_entity(pump, |entity| {
            wipe_pressure(entity);
            entity.nbt.remove(&"PressureSpeed".into());
            entity
                .nbt
                .insert(TRANSFER_RESTART.into(), Tag::Long(restart));
        });
    }
}

fn replace(
    game: &mut Game<'_>,
    pos: [i32; 3],
    block: &str,
    prior: [bool; 6],
    open: [bool; 6],
) -> bool {
    let Some(default) = game.native_default_state(block) else {
        return false;
    };
    let Some(state) = game.with_level(|_, level, _| {
        Direction::ALL
            .into_iter()
            .zip(open)
            .try_fold(default, |state, (face, connected)| {
                level.native_state_with_property(
                    state,
                    name(face),
                    if connected { "true" } else { "false" },
                )
            })
    }) else {
        return false;
    };
    let ports: Vec<_> = Direction::ALL
        .into_iter()
        .filter_map(|face| {
            let key = JavaString::from(name(face));
            Some((key.clone(), mod_entity(game, pos)?.nbt.get(&key)?.clone()))
        })
        .collect();
    if !game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL) {
        return false;
    }
    game.native_with_mod_block_entity(pos, |entity| {
        entity.nbt.extend(ports);
    });
    reset_network(
        game,
        pos,
        std::array::from_fn(|index| prior[index] || open[index]),
    );
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn encase(game: &mut Game<'_>, pos: [i32; 3], held: &ItemStack) -> bool {
    if held.item.as_ref() != CASING
        || !game.native_authoritative()
        || !game.may_build()
        || game.native_sneaking()
    {
        return false;
    }
    let prior = match game.native_block(pos).as_str() {
        PIPE => faces(game, pos),
        GLASS_PIPE => Direction::ALL.map(|face| open_to(game, pos, face)),
        _ => return false,
    };
    let plain = game.native_block(pos) == PIPE;
    if !replace(game, pos, BLOCK, prior, prior) {
        return false;
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    if plain {
        game.native_play_sound_in_place(
            "minecraft:block.copper.place",
            pos.map(|v| f64::from(v) + 0.5),
            4,
            1.0,
            0.8,
        );
    }
    true
}

pub(super) fn uncase(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let prior = faces(game, pos);
    let open = reconnected_faces(game, pos, prior);
    replace(game, pos, PIPE, prior, open)
}
