use std::cell::RefCell;
use std::collections::HashMap;

use horizon_client::particles::{ParticleOptions, ParticleType};
use horizon_client::sound_engine::SoundInstance;
use horizon_core::random::{LegacyRandom, RandomSource};
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_chain_conveyor_packages::ANTICIPATE;
use super::create_chain_conveyor_visual::frog_anchor;
use super::create_frogport_anticipation::Anticipation;
use super::create_frogport_effects_math::rope_particles;
use super::create_frogport_open_math::Motion;
use super::create_machines::{FROGPORT, int, mod_entity};
use crate::containers::BlockEntity;

const VIEWERS: &str = "FrogportViewers";
const DATA_VIEWERS: usize = 1;

#[derive(Default)]
struct OpenFrogports {
    motion: HashMap<[i32; 3], Motion>,
    menu: Option<[i32; 3]>,
    packages: HashMap<[i32; 3], i64>,
    anticipation: HashMap<[i32; 3], Anticipation>,
}

thread_local! {
    static OPEN: RefCell<OpenFrogports> = RefCell::new(OpenFrogports::default());
}

pub(super) fn viewers(game: &mut Game<'_>, at: [i32; 3], viewers: u32) {
    if game.native_block(at) != FROGPORT {
        return;
    }
    let count = viewers as i32;
    if game
        .native_with_mod_block_entity(at, |entity| {
            if entity.data.len() <= DATA_VIEWERS {
                entity.data.resize(DATA_VIEWERS + 1, 0);
            }
            entity.data[DATA_VIEWERS] = count;
        })
        .is_some()
    {
        game.native_block_entity_sync(at);
        if std::env::var_os("CREATE_FROGPORT_OPEN").is_some() {
            println!(
                "CREATE_FROGPORT_VIEWERS {at:?},{},{count}",
                game.world.game_time
            );
        }
    }
}

pub(super) fn data_tag(entity: &crate::containers::ModBlockEntity, update: &mut Compound) {
    let count = entity.data.get(DATA_VIEWERS).copied().unwrap_or(0);
    update.insert(VIEWERS.into(), Tag::Int(count));
}

fn sound(game: &mut Game<'_>, at: [i32; 3], id: &str, volume: f32, pitch: f32, distant: bool) {
    if !game.native_window() {
        return;
    }
    let center = at.map(|axis| f64::from(axis) + 0.5);
    let distance_sq: f64 = center
        .into_iter()
        .zip(game.audio.listener)
        .map(|(sound, camera)| (sound - camera).powi(2))
        .sum();
    let delay = if distant && distance_sq > 100.0 {
        (distance_sq.sqrt() / 2.0) as i32
    } else {
        0
    };
    if delay == 0 {
        game.audio.play_on(4, id, Some(center), volume, pitch);
    } else {
        let random = LegacyRandom::new(game.world.random.next_long());
        game.audio.play_instance_after(
            SoundInstance::at(id, 4, volume, pitch, random, center),
            delay,
        );
    }
    if std::env::var_os("CREATE_FROGPORT_OPEN").is_some()
        || std::env::var_os("CREATE_FROGPORT_PACKAGE_EFFECTS").is_some()
    {
        println!(
            "CREATE_FROGPORT_SOUND {at:?},{},{id},{volume},{pitch},{delay}",
            game.ticks
        );
    }
}

fn package_effects(
    game: &mut Game<'_>,
    at: [i32; 3],
    deposit: bool,
    anchor: Option<[f64; 3]>,
    near: bool,
) {
    sound(game, at, "create:frogport_open", 0.5, 2.0, false);
    if near {
        let cue = if deposit {
            "create:frogport_deposit"
        } else {
            "create:frogport_catch"
        };
        sound(game, at, cue, 1.0, 1.0, false);
    }
    if deposit {
        return;
    }
    let Some(anchor) = anchor else { return };
    let Some(state) = game.native_default_state("create:rope") else {
        return;
    };
    let block = anchor.map(|coordinate| coordinate.floor() as i32);
    let Some((sprite, tint)) = game.particle_sprite(state, block) else {
        return;
    };
    let particle = ParticleOptions::block(ParticleType::Block, sprite, tint);
    for point in rope_particles(anchor, &mut game.world.random) {
        if game.native_add_particle(&particle, point, [0.0; 3])
            && std::env::var_os("CREATE_FROGPORT_PACKAGE_EFFECTS").is_some()
        {
            println!(
                "CREATE_FROGPORT_ROPE {at:?},{},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9}",
                game.ticks, point[0], point[1], point[2], anchor[0], anchor[1], anchor[2]
            );
        }
    }
}

fn nearby(at: [i32; 3], player: [f64; 3]) -> bool {
    at.into_iter()
        .zip(player)
        .map(|(block, player)| (f64::from(block) - player).powi(2))
        .sum::<f64>()
        < 400.0
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.pause {
        return;
    }
    let menu = game
        .native_screen_pos()
        .filter(|&at| game.native_block(at) == FROGPORT);
    let trace = std::env::var_os("CREATE_FROGPORT_OPEN").is_some();
    let (opened, closing, packages) = OPEN.with_borrow_mut(|state| {
        let opened = menu.filter(|_| state.menu != menu);
        state.menu = menu;
        let mut closing = Vec::new();
        let mut packages = Vec::new();
        for (&(x, y, z), entity) in game.world.block_entities.iter() {
            let BlockEntity::Mod(entity) = entity else {
                continue;
            };
            if entity.id != FROGPORT {
                continue;
            }
            let pos = [x, y, z];
            if let Some(Tag::Long(start)) = entity.nbt.get(&"AnimationStartedAt".into())
                && *start >= 0
            {
                if state.packages.insert(pos, *start) != Some(*start) {
                    let deposit = int(&entity.nbt, "CurrentlyDepositing") == Some(1);
                    let anchor = (!deposit).then(|| frog_anchor(game, pos, entity)).flatten();
                    packages.push((pos, deposit, anchor));
                    if std::env::var_os("CREATE_FROGPORT_PACKAGE_EFFECTS").is_some() {
                        println!(
                            "CREATE_FROGPORT_PACKAGE_START {pos:?},{},{start},{deposit}",
                            game.ticks
                        );
                    }
                }
            } else if state.packages.remove(&pos).is_some()
                && let Some(motion) = state.anticipation.get_mut(&pos)
            {
                motion.reset();
            }
            if let Some(Tag::Long(request)) = entity.nbt.get(&ANTICIPATE.into()) {
                let motion = state.anticipation.entry(pos).or_default();
                motion.tick(Some(*request));
                if std::env::var_os("CREATE_FROGPORT_ANTICIPATION").is_some() {
                    println!(
                        "CREATE_FROGPORT_ANTICIPATE_TICK {pos:?},{},{},{:.9}",
                        game.ticks,
                        request,
                        motion.value(1.0)
                    );
                }
            }
            let viewers = if game.remote.is_some() {
                int(&entity.nbt, VIEWERS).unwrap_or(0)
            } else {
                entity.data.get(DATA_VIEWERS).copied().unwrap_or(0)
            };
            let motion = if viewers > 0 {
                state.motion.entry(pos).or_default()
            } else if let Some(motion) = state.motion.get_mut(&pos) {
                motion
            } else {
                continue;
            };
            let closed = motion.tick(viewers);
            if trace {
                println!(
                    "CREATE_FROGPORT_OPEN_TICK {pos:?},{},{viewers},{:.9},{closed}",
                    game.ticks,
                    motion.value(1.0)
                );
            }
            if closed {
                closing.push(pos);
            }
        }
        state.motion.retain(|&pos, motion| {
            !motion.closed() && mod_entity(game, pos).is_some_and(|entity| entity.id == FROGPORT)
        });
        state
            .packages
            .retain(|&pos, _| mod_entity(game, pos).is_some_and(|entity| entity.id == FROGPORT));
        state
            .anticipation
            .retain(|&pos, _| mod_entity(game, pos).is_some_and(|entity| entity.id == FROGPORT));
        (opened, closing, packages)
    });
    if let Some(at) = opened {
        sound(game, at, "create:frogport_open", 0.5, 2.0, false);
    }
    if let Some(player) = game.player.as_ref().map(|player| player.position) {
        let player = [player.x.floor(), player.y.floor(), player.z.floor()];
        for (at, deposit, anchor) in packages {
            package_effects(game, at, deposit, anchor, nearby(at, player));
        }
        for at in closing.into_iter().filter(|&at| nearby(at, player)) {
            let pitch = 1.25 + game.world.random.next_float() * 0.25;
            sound(game, at, "create:frogport_close", 1.0, pitch, true);
        }
    }
}

pub(super) fn progress(at: [i32; 3], partial: f32) -> f32 {
    OPEN.with_borrow(|state| {
        state
            .motion
            .get(&at)
            .map_or(0.0, |motion| motion.value(partial))
    })
}

pub(super) fn anticipates(at: [i32; 3], partial: f32) -> f32 {
    OPEN.with_borrow(|state| {
        state
            .anticipation
            .get(&at)
            .map_or(0.0, |motion| motion.value(partial))
    })
}

pub(super) fn clear() {
    OPEN.with_borrow_mut(|state| *state = OpenFrogports::default());
}
