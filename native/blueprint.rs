use horizon_core::geometry::{Aabb, Vec3};
use horizon_world::nbt::{Compound, Tag};

use super::{Game, Hit};
use crate::{items::ItemStack, save::item_to_nbt};

pub const ENTITY: &str = "create:blueprint";
const ITEM: &str = "create:crafting_blueprint";
const RESULT: &str = "minecraft:crafting_table";
const RECIPE_KEY: &str = "CreateBlueprintRecipe";
const PLANKS_REQUIRED: usize = 4;

fn dimensions(size: i32) -> (f64, f64) {
    let side = f64::from(size.clamp(1, 3)) / 2.0;
    (side, side)
}

fn stack_from_name(name: &str, count: u32) -> ItemStack {
    ItemStack {
        item: name.into(),
        count,
        damage: 0,
        extra: None,
    }
}

fn is_plank(item: &str) -> bool {
    item.strip_prefix("minecraft:")
        .is_some_and(|name| name.ends_with("_planks"))
}

fn recipe_is_configured(game: &mut Game<'_>, id: u32) -> bool {
    let Some(entity) = game.native_entity(id) else {
        return false;
    };
    game.native_entity_nbt(entity)
        .and_then(|data| data.get(&RECIPE_KEY.into()).cloned())
        .is_some_and(|recipe| matches!(recipe, Tag::Compound(_)))
}

fn configure_representative_recipe(game: &mut Game<'_>, id: u32) -> bool {
    let Some(entity) = game.native_entity(id) else {
        return false;
    };
    let recipe = Tag::compound([
        ("Output", Tag::String(RESULT.into())),
        ("Ingredient", Tag::String("#minecraft:planks".into())),
        ("IngredientCount", Tag::Int(PLANKS_REQUIRED as i32)),
    ]);
    game.native_entity_merge_nbt(entity, Compound::from([(RECIPE_KEY.into(), recipe)]))
        || recipe_is_configured(game, id)
}

fn entity<'a>(game: &'a Game<'_>, id: u32) -> Option<&'a crate::mobs::Mob> {
    game.mobs
        .iter()
        .find(|mob| mob.id == id && mob.kind.id == ENTITY && !mob.removed)
}

fn supported_at_center(game: &Game<'_>, pos: [i32; 3], face: [i32; 3]) -> bool {
    let block = game.native_block(pos);
    if matches!(
        block.as_str(),
        "minecraft:repeater" | "minecraft:comparator"
    ) {
        return true;
    }
    game.native_block_collision(pos).iter().any(|bounds| {
        let inside = |axis: usize| bounds[axis] <= 0.5 && bounds[axis + 3] >= 0.5;
        let touches = match face {
            [1, 0, 0] => bounds[3] >= 1.0,
            [-1, 0, 0] => bounds[0] <= 0.0,
            [0, 1, 0] => bounds[4] >= 1.0,
            [0, -1, 0] => bounds[1] <= 0.0,
            [0, 0, 1] => bounds[5] >= 1.0,
            [0, 0, -1] => bounds[2] <= 0.0,
            _ => false,
        };
        touches
            && match face {
                [1, 0, 0] | [-1, 0, 0] => inside(1) && inside(2),
                [0, 1, 0] | [0, -1, 0] => inside(0) && inside(2),
                _ => inside(0) && inside(1),
            }
    })
}

fn placement(game: &Game<'_>, hit: &Hit, size: i32) -> Option<[f64; 3]> {
    let (width, height) = dimensions(size);
    let target = std::array::from_fn::<_, 3, _>(|axis| hit.pos[axis] + hit.face[axis]);
    let center = std::array::from_fn::<_, 3, _>(|axis| {
        f64::from(target[axis]) + 0.5 - f64::from(hit.face[axis]) * 0.46875
    });

    let horizontal = if hit.face[1] == 0 {
        [-hit.face[2], 0, hit.face[0]]
    } else {
        let yaw = game.player.as_ref().map_or(0.0, |player| player.yaw);
        let facing = (yaw / 90.0).round() as i32;
        match facing.rem_euclid(4) {
            0 => [1, 0, 0],
            1 => [0, 0, -1],
            2 => [-1, 0, 0],
            _ => [0, 0, 1],
        }
    };
    let start = -(size - 1) / 2;
    for index in 0..size {
        let offset = start + index;
        let support = std::array::from_fn(|axis| hit.pos[axis] + horizontal[axis] * offset);
        if !supported_at_center(game, support, hit.face) {
            return None;
        }
    }

    let half = [width / 2.0, height / 2.0, width / 2.0];
    let half = match hit.face {
        [1, 0, 0] | [-1, 0, 0] => [0.03125, half[1], half[2]],
        [0, 1, 0] | [0, -1, 0] => [half[0], 0.03125, half[2]],
        _ => [half[0], half[1], 0.03125],
    };
    let [x, y, z] = center;
    let bounds = Aabb::new(
        Vec3::new(x - half[0], y - half[1], z - half[2]),
        Vec3::new(x + half[0], y + half[1], z + half[2]),
    );
    if game
        .mobs
        .iter()
        .any(|mob| !mob.removed && mob.kind.id == ENTITY && mob.bounds().intersects(bounds))
    {
        None
    } else {
        Some(center)
    }
}

pub fn place(game: &mut Game<'_>, stack: &ItemStack, pos: [i32; 3], face: [i32; 3]) -> bool {
    if stack.item.as_ref() != ITEM || !game.native_authoritative() || game.native_sneaking() {
        return false;
    }
    let Some(hit) = game.pick().filter(|hit| hit.pos == pos && hit.face == face) else {
        return false;
    };
    let size = [3, 2, 1]
        .into_iter()
        .find(|&size| placement(game, &hit, size).is_some());
    let Some(size) = size else {
        return false;
    };
    let Some(position) = placement(game, &hit, size) else {
        return false;
    };
    let mut nbt = Compound::new();
    nbt.insert("Silent".into(), Tag::Byte(1));
    nbt.insert("NoAI".into(), Tag::Byte(1));
    nbt.insert("PersistenceRequired".into(), Tag::Byte(1));
    nbt.insert("Invulnerable".into(), Tag::Byte(1));
    nbt.insert("Health".into(), Tag::Float((size as f32).to_bits()));
    nbt.insert("BlueprintSize".into(), Tag::Int(size));
    nbt.insert(
        "equipment".into(),
        Tag::compound([("mainhand", item_to_nbt(stack))]),
    );
    let Some(id) = game.native_summon(game.native_dimension(), ENTITY, position, nbt) else {
        return false;
    };
    if let Some(mob) = game.mobs.iter_mut().find(|mob| mob.id == id) {
        let yaw = match face {
            [0, 0, 1] => 0.0,
            [-1, 0, 0] => 90.0,
            [0, 0, -1] => 180.0,
            [1, 0, 0] => 270.0,
            _ => mob.yaw,
        };
        mob.yaw = yaw;
        mob.previous_yaw = yaw;
        mob.body_yaw = yaw;
        mob.previous_body_yaw = yaw;
        mob.head_yaw = yaw;
        mob.previous_head_yaw = yaw;
    }
    game.consume_held();
    true
}

pub fn interact(game: &mut Game<'_>, id: u32, stack: Option<&ItemStack>) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    if entity(game, id).is_none() {
        return false;
    }
    if stack.is_some_and(|stack| stack.item.as_ref() == "create:wrench") {
        configure_representative_recipe(game, id);
        return true;
    }
    if !recipe_is_configured(game, id) {
        return true;
    }

    let mut crafted = 0;
    loop {
        let available: u32 = game
            .inventory
            .iter()
            .flatten()
            .filter(|item| is_plank(&item.item))
            .map(|item| item.count)
            .sum();
        if available < PLANKS_REQUIRED as u32 || crafted == 64 {
            break;
        }
        if !game.creative {
            let mut remaining = PLANKS_REQUIRED as u32;
            for slot in &mut game.inventory {
                let Some(item) = slot.as_mut().filter(|item| is_plank(&item.item)) else {
                    continue;
                };
                let taken = remaining.min(item.count);
                item.count -= taken;
                remaining -= taken;
                if item.count == 0 {
                    *slot = None;
                }
                if remaining == 0 {
                    break;
                }
            }
        }
        crafted += 1;
        if !game.native_sneaking() {
            break;
        }
    }
    if crafted > 0 {
        game.give_or_drop(stack_from_name(RESULT, crafted));
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    true
}

pub fn break_entity(game: &mut Game<'_>, id: u32, canceled: &mut bool) {
    let Some(mob) = entity(game, id) else {
        return;
    };
    let pos = mob.position;
    if game.native_remove_mob(game.native_dimension(), id) {
        let count = if game.creative { 0 } else { 1 };
        if count > 0 {
            game.add_item_entity(
                stack_from_name(ITEM, count),
                [pos.x, pos.y, pos.z],
                None,
                10,
            );
        }
        *canceled = true;
    }
}
