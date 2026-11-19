use super::{Game, lan::LanHost, lan_pvp::Victim};
use horizon_client::health::HurtSource;
use horizon_core::geometry::Vec3;

const SWORD: &str = "create:cardboard_sword";
const BONK: &str = "create:cardboard_bonk";
const PLAYERS: usize = 7;

fn holds_sword(game: &Game<'_>) -> bool {
    game.held().is_some_and(|stack| stack.item.as_ref() == SWORD)
}

fn bonks_mob(game: &Game<'_>, index: usize) -> bool {
    let mob = &game.mobs[index];
    holds_sword(game) && mob.alive()
        && !game.res.stations().enchantments.entity_tags
            .get("minecraft:arthropod")
            .is_some_and(|tag| tag.contains(&mob.kind.id))
}

fn stop_attacker(game: &mut Game<'_>) {
    if let Some(player) = game.player.as_mut() {
        player.velocity.x *= 0.6;
        player.velocity.z *= 0.6;
        let _ = player.set_sprinting(false);
    }
}

struct Bonk {
    from: [f64; 3],
    attacker: i32,
    power: f64,
    xd: f64,
    zd: f64,
}

fn prepare_bonk(game: &mut Game<'_>, kind: &str) -> Option<Bonk> {
    let player = game.player.as_mut()?;
    let Vec3 { x, y, z } = player.position;
    let from = [x, y, z];
    let attacker = player.entity_id;
    let base = player.attribute("minecraft:attack_knockback").unwrap_or(0.0) as f32;
    game.native_play_sound_in_place(BONK, from.map(|v| v.floor() + 0.5), PLAYERS, 0.75, 1.85);
    let scale = game.attack_strength_scale();
    let (extra, _) = game.extra_knockback(kind, scale);
    // The pinned engine's helper covers enchantments and charged sprint.
    let power = f64::from((base + 2.0) * 0.5 + extra);
    let (xd, zd) = game.extra_knockback_direction();
    Some(Bonk { from, attacker, power, xd, zd })
}

pub(super) fn attack_mob(game: &mut Game<'_>, entity: i32, canceled: &mut bool) {
    if *canceled {
        return;
    }
    let Some(index) = game.mobs.iter().position(|mob| mob.id as i32 == entity && !mob.removed)
    else {
        return;
    };
    if !bonks_mob(game, index) {
        return;
    }
    let kind = game.mobs[index].kind.id.clone();
    let Some(Bonk { from, attacker, power, xd, zd }) = prepare_bonk(game, &kind) else {
        return;
    };
    *canceled = true;
    if power <= 0.0 {
        return;
    }
    let source = game.attack_source(from);
    if game.mobs[index].extra.mount.is_some() {
        game.dismount_mob(entity as u32);
    }
    let _attacker = game.knockback_scope(attacker);
    let mob = &mut game.mobs[index];
    mob.knockback(power, xd, zd, &source);
    if matches!(mob.category(), "creature" | "misc") {
        mob.add_effect_with("minecraft:slowness", 60, 9, true, false);
    }
    stop_attacker(game);
}

pub(super) fn attack_player(game: &mut Game<'_>, host: &mut LanHost, conn: u32, victim: Victim) -> bool {
    let Some(Some(bonk)) = game.as_guest(host, conn, |g| {
        if !holds_sword(g) {
            return None;
        }
        let bonk = prepare_bonk(g, "minecraft:player")?;
        if bonk.power > 0.0 {
            stop_attacker(g);
        }
        Some(bonk)
    }) else {
        return false;
    };
    if bonk.power > 0.0 {
        let Victim::Guest(receiver) = victim;
        game.guest_hit_by(host, receiver, |g| {
            g.stop_riding();
            let _attacker = g.knockback_scope(bonk.attacker);
            let source = HurtSource {
                damage_type: "minecraft:player_attack",
                causing: bonk.attacker,
                direct: bonk.attacker,
            };
            g.knock_back_player(bonk.power, bonk.xd, bonk.zd, source);
            if std::env::var_os("HORIZON_CREATE_SWORD_PVP_TRACE").is_some()
                && let Some(player) = g.player.as_ref()
            {
                let Vec3 { x, y, z } = player.velocity;
                eprintln!("CREATE_SWORD_PVP {},{},{},{x},{y},{z},{},{}", bonk.attacker,
                    player.entity_id, player.health.health(), g.riding.is_some(), player.ground.on_ground);
            }
        });
    }
    true
}

pub(super) fn client_attack(game: &mut Game<'_>, target: u32, player: bool) {
    if player {
        if holds_sword(game) {
            stop_attacker(game);
        }
        return;
    }
    let Some(index) = game.mobs.iter().position(|mob| mob.id == target && !mob.removed)
    else {
        return;
    };
    if bonks_mob(game, index) {
        stop_attacker(game);
    }
}

pub(super) fn block_attack(game: &mut Game<'_>, pos: [i32; 3], canceled: bool) {
    if !canceled && holds_sword(game) {
        let at = pos.map(|value| f64::from(value) + 0.5);
        game.native_play_sound_in_place(BONK, at, PLAYERS, 0.5, 1.85);
    }
}
