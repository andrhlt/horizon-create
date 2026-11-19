use super::{Game, Hand};
use crate::items::ItemStack;
use horizon_client::{
    mobs::Who,
    projectiles::{Projectile, ProjectileKind, create_cannon_ammo, thrown_type},
};
use horizon_core::{geometry::{trig, Vec3}, random::RandomSource};
use horizon_world::{nbt::Tag, player_inventory::EquipmentSlot};

const CANNON: &str = "create:potato_cannon";
const PROJECTILE: &str = "create:potato_projectile";

fn supported(stack: &ItemStack) -> bool {
    if stack.item.as_ref() == "minecraft:suspicious_stew"
        && stack.extra.as_ref().is_some_and(|data| {
            data.stew_effects.iter().any(|(effect, _)| {
                !matches!(effect.as_ref(), "minecraft:night_vision" | "minecraft:weakness")
            })
        })
    {
        return false;
    }
    stack.count > 0
        && matches!(
            stack.item.as_ref(),
            "create:blaze_cake"
                | "create:chocolate_glazed_berries"
                | "create:honeyed_apple"
                | "minecraft:apple"
                | "minecraft:baked_potato"
                | "minecraft:beetroot"
                | "minecraft:cake"
                | "minecraft:carrot"
                | "minecraft:chorus_fruit"
                | "minecraft:cod"
                | "minecraft:cooked_cod"
                | "minecraft:cooked_salmon"
                | "minecraft:enchanted_golden_apple"
                | "minecraft:glistering_melon_slice"
                | "minecraft:glow_berries"
                | "minecraft:golden_apple"
                | "minecraft:golden_carrot"
                | "minecraft:melon"
                | "minecraft:melon_slice"
                | "minecraft:poisonous_potato"
                | "minecraft:potato"
                | "minecraft:pufferfish"
                | "minecraft:pumpkin"
                | "minecraft:pumpkin_pie"
                | "minecraft:salmon"
                | "minecraft:suspicious_stew"
                | "minecraft:sweet_berries"
                | "minecraft:tropical_fish"
        )
}

// BacktankUtil consumes the base 900-air capacity divided by 200 shots.
fn consume_backtank_air(game: &mut Game<'_>) -> bool {
    let Some(mut tank) = game.native_equipment(EquipmentSlot::Chest) else {
        return false;
    };
    if !matches!(
        tank.item.as_ref(),
        "create:copper_backtank" | "create:netherite_backtank"
    ) {
        return false;
    }
    let air = match game.native_component(&tank, "create:banktank_air") {
        Ok(Some(Tag::Int(air))) => *air,
        _ => 0,
    };
    if air <= 0 {
        return false;
    }
    let capacity = 900 + 300 * tank.enchantment_level("create:capacity") as i32;
    if game
        .native_set_component(
            &mut tank,
            "create:banktank_air",
            Tag::Int((air.min(capacity) - 4).max(0)),
        )
        .is_err()
    {
        return false;
    }
    game.armor[1] = Some(tank);
    true
}

// Ordinary hand-held shots for the supported ammunition types.
pub(super) fn fire(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed || stack.item.as_ref() != CANNON || !game.native_authoritative() {
        return;
    }
    let Some(player) = game.native_acting_player() else {
        return;
    };
    let other_hand_ammo = if game.hand == Hand::Main {
        game.offhand.as_ref().filter(|s| supported(s))
    } else {
        None
    };
    let main_hand_ammo = game.hand == Hand::Off
        && game
            .inventory
            .get(game.selected)
            .and_then(Option::as_ref)
            .is_some_and(supported);
    let index = if other_hand_ammo.is_some() {
        None
    } else if main_hand_ammo {
        Some(game.selected)
    } else {
        game.inventory
            .iter()
            .position(|s| s.as_ref().is_some_and(supported))
    };
    let selected = other_hand_ammo.or_else(|| index.and_then(|i| game.inventory[i].as_ref()));
    let Some(ammo) = selected.cloned() else {
        return;
    };
    let Some(properties) = create_cannon_ammo(&ammo.item) else {
        return;
    };
    let Some(kind) = thrown_type(PROJECTILE) else {
        return;
    };
    let yaw = (player.yaw / -180.0 * std::f32::consts::PI) as f64;
    let pitch = (player.pitch / -180.0 * std::f32::consts::PI) as f64;
    let (sy, cy) = yaw.sin_cos();
    let (sp, cp) = pitch.sin_cos();
    let rotate = |x: f64, y: f64, z: f64| {
        let py = y * cp + z * sp;
        let pz = z * cp - y * sp;
        Vec3::new(x * cy + pz * sy, py, pz * cy - x * sy)
    };
    let dominant_left = game
        .lan_acting_main_hand_left
        .unwrap_or(game.settings.main_hand_left);
    let firing_left = dominant_left != (game.hand == Hand::Off);
    let side = if firing_left { 1.0 } else { -1.0 };
    let barrel = rotate(side * 0.75, -0.15_f32 as f64, 1.5);
    let correction = rotate(-side * f64::from(0.05_f32), 0.0, 0.0);
    let look = rotate(0.0, 0.0, 1.0);
    let velocity = look
        .add_vector(correction)
        .normalize()
        .scale(2.0 * f64::from(properties.velocity));
    let [x, y, z] = player.position;
    let position = Vec3::new(x, y + f64::from(player.eye_height), z).add_vector(barrel);
    let trace_ammo = std::env::var_os("HORIZON_CREATE_CANNON_TRACE")
        .map(|_| ammo.item.clone());
    let split = match ammo.item.as_ref() {
        "minecraft:sweet_berries" | "create:chocolate_glazed_berries" => 3,
        "minecraft:glow_berries" => 2,
        _ => 1,
    };
    if split == 1 {
        let mut shot = Projectile::new(ProjectileKind::Thrown(kind), position, Some(Who::Player));
        shot.velocity = velocity;
        shot.item = Some(ammo);
        shot.guest = game.lan_acting;
        game.add_projectile(shot);
    } else {
        // Create draws pitch before the initial cone rotation, even if sound is muted.
        let _sound_pitch = game.world.random.next_float();
        let base_angle = 360.0_f32 * game.world.random.next_float();
        let rotate_z = |v: Vec3, degrees: f64| {
            let radians = (degrees / 180.0 * std::f64::consts::PI) as f32;
            let index = (radians * 10430.378_f32) as i32;
            let cosine_index = (radians * 10430.378_f32 + 16384.0) as i32;
            let sin = f64::from(trig::sine_table()[(index & 65535) as usize]);
            let cos = f64::from(trig::sine_table()[(cosine_index & 65535) as usize]);
            Vec3::new(v.x * cos - v.y * sin, v.x * sin + v.y * cos, v.z)
        };
        let base = rotate_z(Vec3::new(0.0, 0.1, 0.0), f64::from(base_angle));
        let forward = velocity.normalize();
        let dot = forward.y;
        let up = if dot.abs() > 0.999 {
            Vec3::new(0.0, 0.0, if dot > 0.0 { 1.0 } else { -1.0 })
        } else {
            Vec3::new(0.0, 1.0, 0.0)
        };
        let right = forward.cross(up).normalize();
        let up = right.cross(forward).normalize();
        let change = 360.0_f32 / split as f32;
        for i in 0..split {
            let imperfection = 40.0_f32 * (game.world.random.next_float() - 0.5);
            let angle = i as f32 * change + imperfection;
            let offset = rotate_z(base, f64::from(angle));
            let spread = right.scale(offset.x).add_vector(up.scale(offset.y)).add_vector(forward.scale(offset.z));
            let mut shot = Projectile::new(ProjectileKind::Thrown(kind), position, Some(Who::Player));
            shot.velocity = velocity.add_vector(spread);
            shot.item = Some(ammo.clone());
            shot.guest = game.lan_acting;
            game.add_projectile(shot);
        }
    }
    if let Some(ammo) = trace_ammo {
        let play_time = game.stats.values.get("minecraft:custom")
            .and_then(|stats| stats.get("minecraft:play_time"))
            .copied().unwrap_or(0);
        let role = if game.lan_acting.is_some() { "lan_actor" } else { "local" };
        eprintln!("CREATE_CANNON_SHOT role={role} conn={:?} ammo={ammo} play_time={play_time}", game.lan_acting);
    }
    if !game.creative {
        let slot = if let Some(index) = index {
            &mut game.inventory[index]
        } else {
            &mut game.offhand
        };
        let ammo = slot.as_mut().unwrap();
        ammo.count -= 1;
        if ammo.count == 0 {
            *slot = None;
        }
        if !consume_backtank_air(game) {
            let slot = if game.hand == Hand::Main {
                EquipmentSlot::MainHand
            } else {
                EquipmentSlot::OffHand
            };
            game.damage_held_in_slot(1, slot);
        }
    }
    game.add_cooldown(stack.item.clone(), properties.reload);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    *claimed = true;
}
