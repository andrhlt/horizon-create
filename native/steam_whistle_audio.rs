use super::create_steam_whistle::WHISTLE;
use super::{
    Game,
    create_depot::compound,
    create_machines::{int, mod_entity, offset},
};
use crate::containers::{BlockEntity, ModBlockEntity};
use horizon_client::sound_engine::{InstanceId, RECORDS, SoundInstance, Sounds, Ticking};
use horizon_core::{
    geometry::Direction,
    random::{LegacyRandom, RandomSource},
};
use horizon_world::nbt::Tag;
use std::{cell::RefCell, collections::HashMap};

pub(super) fn attached(game: &Game<'_>, pos: [i32; 3]) -> Option<Direction> {
    if game.native_block_property(pos, "wall").as_deref() != Some("true") {
        return Some(Direction::Down);
    }
    let name = game.native_block_property(pos, "facing")?;
    Direction::ALL
        .into_iter()
        .find(|&side| super::create_fluids::name(side) == name)
}

pub(super) fn server_tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let Some(side) = attached(game, pos) else {
        return;
    };
    let tank = offset(pos, side.normal());
    let steam = super::create_fluid_tank::parts(game, tank)
        .and_then(|(_, parts)| parts.first().copied())
        .and_then(|root| mod_entity(game, root))
        .and_then(|tank| compound(&tank.nbt, "Boiler"))
        .is_some_and(|boiler| {
            int(boiler, "Engines").unwrap_or(0) + int(boiler, "Whistles").unwrap_or(0) > 0
                && (int(boiler, "ActiveHeat").unwrap_or(0) > 0
                    || int(boiler, "PassiveHeat").unwrap_or(0) > 0)
        });
    let mut pitch = 0;
    for y in 1..=13 {
        let at = [pos[0], pos[1] + y, pos[2]];
        if game.native_block(at) != "create:steam_whistle_extension" {
            break;
        }
        if game.native_block_property(at, "shape").as_deref() == Some("single") {
            pitch += 1;
            break;
        }
        pitch += 2;
    }
    if int(&entity.nbt, "Pitch") != Some(pitch)
        || int(&entity.nbt, "Steam") != Some(i32::from(steam))
    {
        entity.nbt.insert("Pitch".into(), Tag::Int(pitch));
        entity
            .nbt
            .insert("Steam".into(), Tag::Int(i32::from(steam)));
        game.native_block_entity_sync(pos);
    }
}

fn trace(pos: [i32; 3], event: &str, volume: f32, pitch: f32, starting: bool) {
    if std::env::var_os("HORIZON_CREATE_WHISTLE_TRACE").is_some() {
        let [x, y, z] = pos.map(|value| f64::from(value) + 0.5);
        eprintln!(
            "CREATE_WHISTLE_REQUEST {event},{RECORDS},{x},{y},{z},{volume},{pitch},{starting}"
        );
    }
}

fn event(size: &str) -> &'static str {
    match size {
        "small" => "create:whistle_high",
        "large" => "create:whistle_low",
        _ => "create:whistle",
    }
}

struct Voice {
    id: InstanceId,
    size: String,
    volume: f32,
    fading: bool,
}
thread_local! { static VOICES: RefCell<HashMap<[i32; 3], Vec<Voice>>> = RefCell::new(HashMap::new()); }

pub(super) fn client_tick(game: &mut Game<'_>) {
    if !game.native_window() {
        return;
    }
    let desired: HashMap<[i32; 3], (String, f32)> = game
        .world
        .block_entities
        .iter()
        .filter_map(|(&(x, y, z), entry)| {
            let BlockEntity::Mod(entity) = entry else {
                return None;
            };
            let pos = [x, y, z];
            if entity.id != WHISTLE
                || int(&entity.nbt, "Steam") != Some(1)
                || game.native_block_property(pos, "powered").as_deref() != Some("true")
            {
                return None;
            }
            let size = game.native_block_property(pos, "size")?;
            let pitch = 2.0_f32.powf(-(int(&entity.nbt, "Pitch").unwrap_or(0) as f32) / 12.0);
            Some((pos, (size, pitch)))
        })
        .collect();
    VOICES.with_borrow_mut(|voices| {
        for (&pos, (size, pitch)) in &desired {
            let list = voices.entry(pos).or_default();
            if !list
                .iter()
                .any(|voice| !voice.fading && &voice.size == size)
            {
                let event = event(size);
                let center = pos.map(|value| f64::from(value) + 0.5);
                let random = LegacyRandom::new(game.world.random.next_long());
                let mut instance = SoundInstance::at(event, RECORDS, 0.05, *pitch, random, center);
                instance.looping = true;
                instance.ticking = Ticking::Native;
                trace(pos, event, 0.05, *pitch, true);
                let (id, _) = game.audio.play_instance(instance, true);
                let distance = center
                    .into_iter()
                    .zip(game.audio.listener)
                    .map(|(a, b)| (a - b).powi(2))
                    .sum::<f64>()
                    .sqrt();
                let volume = ((64.0 - distance) / 64.0).clamp(0.0, 1.0) as f32 * 0.175;
                let chiff_pitch = if size == "small" {
                    *pitch + 0.75
                } else {
                    *pitch
                };
                game.audio
                    .play_on(RECORDS, "create:chiff", Some(center), volume, chiff_pitch);
                list.push(Voice {
                    id,
                    size: size.clone(),
                    volume: 0.05,
                    fading: false,
                });
            }
        }
        voices.retain(|pos, list| {
            let wanted = desired.get(pos);
            list.retain_mut(|voice| {
                if !wanted.is_some_and(|(size, _)| size == &voice.size) {
                    voice.fading = true;
                }
                let active = !voice.fading;
                voice.volume = if active {
                    (voice.volume + 0.25).min(1.0)
                } else {
                    (voice.volume - 0.25).max(0.0)
                };
                if active {
                    trace(
                        *pos,
                        event(&voice.size),
                        voice.volume,
                        wanted.unwrap().1,
                        false,
                    );
                } else {
                    trace(
                        *pos,
                        event(&voice.size),
                        voice.volume,
                        game.audio
                            .engine
                            .instance(voice.id)
                            .map_or(1.0, |instance| instance.pitch),
                        false,
                    );
                }
                if voice.volume == 0.0 {
                    game.audio.stop_instance(voice.id);
                    game.audio.release(voice.id);
                    return false;
                }
                if let Some(instance) = game.audio.engine.instance_mut(voice.id) {
                    instance.volume = voice.volume;
                    if active {
                        instance.pitch = wanted.unwrap().1;
                    }
                }
                true
            });
            !list.is_empty()
        });
    });
}

pub(super) fn clear(game: &mut Game<'_>) {
    VOICES.with_borrow_mut(|voices| {
        for voice in voices.drain().flat_map(|(_, list)| list) {
            game.audio.stop_instance(voice.id);
            game.audio.release(voice.id);
        }
    });
}
