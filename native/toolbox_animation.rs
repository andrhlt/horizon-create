use std::{cell::RefCell, collections::HashMap};

use horizon_client::sound_engine::SoundInstance;
use horizon_core::random::{LegacyRandom, RandomSource};
use horizon_world::{
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use super::{
    Game,
    create_machines::mod_entity,
    create_toolbox::{self, COLORS, ENTITY},
    create_toolbox_animation_math::{Cue, Motion},
    native_block_entity_draw::BlockEntityDraw,
};
use crate::containers::{BlockEntity, ModBlockEntity};

const OPEN_COUNT: &str = "OpenCount";
const VIEWERS: usize = 1;
const DRAWER: &str = "create:block/toolbox/drawer";
const LID: &str = "create:block/toolbox/lid/";

thread_local! {
    static MOTION: RefCell<HashMap<[i32; 3], Motion>> = RefCell::new(HashMap::new());
    static AUDIO_RANDOM: RefCell<LegacyRandom> = RefCell::new(LegacyRandom::new(
        std::time::SystemTime::UNIX_EPOCH.elapsed().unwrap_or_default().as_nanos() as i64,
    ));
}

pub(super) fn viewers(game: &mut Game<'_>, pos: [i32; 3], viewers: u32) {
    if !create_toolbox::block(&game.native_block(pos)) {
        return;
    }
    if game
        .native_with_mod_block_entity(pos, |entity| {
            if entity.data.len() <= VIEWERS {
                entity.data.resize(VIEWERS + 1, 0);
            }
            entity.data[VIEWERS] = viewers as i32;
        })
        .is_some()
    {
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity, update: &mut Compound) {
    update.insert(OPEN_COUNT.into(), Tag::Int(count(entity, false)));
}

fn count(entity: &ModBlockEntity, remote: bool) -> i32 {
    if remote {
        match entity.nbt.get(&OPEN_COUNT.into()) {
            Some(Tag::Int(count)) => *count,
            _ => 0,
        }
    } else {
        entity.data.get(VIEWERS).copied().unwrap_or(0)
    }
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.pause {
        return;
    }
    let tracing = std::env::var_os("CREATE_TOOLBOX_ANIMATION").is_some();
    let remote = game.remote.is_some();
    let cues = MOTION.with_borrow_mut(|motions| {
        let mut cues = Vec::new();
        for (&(x, y, z), entity) in game.world.block_entities.iter() {
            let BlockEntity::Mod(entity) = entity else {
                continue;
            };
            if entity.id != ENTITY {
                continue;
            }
            let pos = [x, y, z];
            let viewers = count(entity, remote);
            let motion = if viewers > 0 {
                motions.entry(pos).or_default()
            } else if let Some(motion) = motions.get_mut(&pos) {
                motion
            } else {
                continue;
            };
            if let Some(cue) = motion.tick(viewers > 0) {
                cues.push((pos, cue));
            }
            if tracing {
                let [lid, drawers] = motion.at(1.0);
                println!(
                    "CREATE_TOOLBOX_MOTION {pos:?},{},{viewers},{lid:.9},{drawers:.9}",
                    game.ticks
                );
            }
        }
        motions.retain(|&pos, motion| {
            !motion.closed() && mod_entity(game, pos).is_some_and(|entity| entity.id == ENTITY)
        });
        cues
    });
    for (pos, cue) in cues {
        match cue {
            Cue::Open => {
                sound(game, pos, "minecraft:block.iron_door.open", 0.25, 1.2);
                sound(game, pos, "minecraft:block.chest.open", 0.1, 1.1);
            }
            Cue::ChestClose => sound(game, pos, "minecraft:block.chest.close", 0.1, 1.1),
            Cue::IronClose => sound(game, pos, "minecraft:block.iron_door.close", 0.25, 1.2),
        }
    }
}

fn sound(game: &mut Game<'_>, pos: [i32; 3], id: &str, volume: f32, base_pitch: f32) {
    if !game.native_window() {
        return;
    }
    let center = pos.map(|axis| f64::from(axis) + 0.5);
    let distance: f64 = center
        .into_iter()
        .zip(game.audio.listener)
        .map(|(axis, listener)| (axis - listener).powi(2))
        .sum();
    let delay = if distance > 100.0 {
        (distance.sqrt() / 2.0) as i32
    } else {
        0
    };
    let pitch = AUDIO_RANDOM.with_borrow_mut(|random| base_pitch + random.next_float() * 0.1);
    if delay == 0 {
        game.audio.play_on(4, id, Some(center), volume, pitch);
    } else {
        let random = AUDIO_RANDOM.with_borrow_mut(|random| LegacyRandom::new(random.next_long()));
        game.audio.play_instance_after(
            SoundInstance::at(id, 4, volume, pitch, random, center),
            delay,
        );
    }
    if std::env::var_os("CREATE_TOOLBOX_ANIMATION").is_some() {
        println!(
            "CREATE_TOOLBOX_CUE {pos:?},{},{id},{volume},{pitch},{delay}",
            game.ticks
        );
    }
}

pub(super) fn models(models: &mut Vec<String>) {
    models.push(DRAWER.into());
    models.extend(COLORS.map(|color| format!("{LID}{color}")));
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    block: &str,
    state: BlockStateId,
    draw: &mut BlockEntityDraw,
) {
    let Some(state) = game.pack.assets.registry.state(state) else {
        return;
    };
    let yaw = match state.properties.get("facing").map(String::as_str) {
        Some("east") => -90.0,
        Some("south") => 180.0,
        Some("west") => 90.0,
        _ => 0.0,
    };
    let [lid, drawers] = MOTION.with_borrow(|motions| {
        motions
            .get(&pos)
            .map_or([0.0; 2], |motion| motion.at(draw.partial))
    });
    let lid = lid * 135.0;
    let model = &block["create:".len()..block.len() - "_toolbox".len()];
    let before = draw.vertices_mut().len();
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.push();
    draw.rotate_about([1.0, 0.0, 0.0], lid, [0.0, 6.0 / 16.0, 12.0 / 16.0]);
    game.native_draw_model(draw, &format!("{LID}{model}"), 0xffffff);
    draw.pop();
    for drawer in [0.0, 1.0] {
        draw.push();
        draw.translate([0.0, drawer / 8.0, -drawers * 0.175 * (2.0 - drawer)]);
        game.native_draw_model(draw, DRAWER, 0xffffff);
        draw.pop();
    }
    draw.pop();
    if std::env::var_os("CREATE_TOOLBOX_ANIMATION").is_some() {
        let vertices = draw.vertices_mut().len() - before;
        println!(
            "CREATE_TOOLBOX_PARTS {pos:?},{},{:.9},{yaw},{lid:.9},{drawers:.9},{vertices}",
            draw.game_time, draw.partial
        );
    }
}

pub(super) fn clear() {
    MOTION.with_borrow_mut(HashMap::clear);
}
