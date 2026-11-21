//! Survival-facing Crafting Blueprint display.
//!
//! The Java implementation stores the display as an entity rather than a block.
//! Horizon's persisted mob NBT gives us the same useful lifecycle: placement,
//! recipe state, guest interaction, drops and save/reopen all use one identity.

use horizon_core::geometry::{Aabb, Vec3};
use horizon_world::nbt::{Compound, Tag};

use super::{Game, Hit};
use crate::{items::ItemStack, save::item_to_nbt};

pub const ENTITY: &str = "create:blueprint";
const ITEM: &str = "create:crafting_blueprint";
const INGREDIENT: &str = "minecraft:paper";
const RESULT: &str = "minecraft:crafting_table";

fn dimensions(size: i32) -> (f64, f64) {
    match size {
        3 => (3.0, 2.0),
        2 => (2.0, 2.0),
        _ => (1.0, 1.0),
    }
}

fn stack_from_name(name: &str) -> ItemStack {
    ItemStack {
        item: name.into(),
        count: 1,
        data: None,
    }
}

fn entity<'a>(game: &'a Game<'_>, id: u32) -> Option<&'a crate::mobs::Mob> {
    game.mobs
        .iter()
        .find(|mob| mob.id == id && mob.kind.id == ENTITY && !mob.removed)
}

fn placement(game: &Game<'_>, hit: &Hit, size: i32) -> Option<[f64; 3]> {
    let (width, height) = dimensions(size);
    let [mut x, mut y, mut z] = hit.point;
    if hit.face[1] < 0 {
        y -= height + 0.25;
    } else if hit.face[1] == 0 {
        x += f64::from(hit.face[0]) * width / 2.0;
        z += f64::from(hit.face[2]) * width / 2.0;
    }
    let bounds = Aabb::new(
        Vec3::new(x - width / 2.0, y, z - width / 2.0),
        Vec3::new(x + width / 2.0, y + height, z + width / 2.0),
    );
    if game
        .mobs
        .iter()
        .any(|mob| !mob.removed && mob.kind.id == ENTITY && mob.bounds().intersects(bounds))
    {
        None
    } else {
        Some([x, y, z])
    }
}

pub fn place(game: &mut Game<'_>, stack: &ItemStack, pos: [i32; 3], face: [i32; 3]) -> bool {
    if stack.item != ITEM || !game.native_authoritative() || game.native_sneaking() {
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
    nbt.insert("PersistenceRequired".into(), Tag::Byte(1));
    nbt.insert("Health".into(), Tag::Float(5.0f32.to_bits()));
    nbt.insert("BlueprintSize".into(), Tag::Int(size));
    nbt.insert(
        "equipment".into(),
        Tag::compound([("mainhand", item_to_nbt(stack))]),
    );
    let Some(id) = game.native_summon(game.native_dimension(), ENTITY, position, nbt) else {
        return false;
    };
    if let Some(mob) = game.mobs.iter_mut().find(|mob| mob.id == id) {
        mob.extra.ints[0] = size;
    }
    game.consume_held();
    true
}

pub fn size(mob: &crate::mobs::Mob) -> std::ops::ControlFlow<(f64, f64, f64)> {
    if mob.kind.id != ENTITY {
        return std::ops::ControlFlow::Continue(());
    }
    let size = mob
        .extra
        .ints
        .first()
        .copied()
        .filter(|value| (1..=3).contains(value))
        .unwrap_or(1);
    let (w, h) = dimensions(size);
    std::ops::ControlFlow::Break((w, h, h * 0.85))
}

pub fn draw(
    game: &Game<'_>,
    mob: &crate::mobs::Mob,
    partial: f32,
    camera: horizon_core::geometry::DVec3,
    light: u32,
    out: &mut Vec<horizon_client::render::Vertex>,
) -> std::ops::ControlFlow<bool> {
    if mob.kind.id != ENTITY {
        return std::ops::ControlFlow::Continue(());
    }
    let drawn = game.mod_entity_draw(mob, partial, camera, light, out, |_, draw| {
        draw.translate([-0.5, 0.0, -0.5]);
        game.native_draw_model(draw, "create:item/crafting_blueprint", 0xffffff);
        true
    });
    std::ops::ControlFlow::Break(drawn)
}

pub fn interact(game: &mut Game<'_>, id: u32, stack: Option<&ItemStack>) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    let Some(mob) = entity(game, id) else {
        return false;
    };
    let ingredient = Some(INGREDIENT.to_string());
    let result = Some(RESULT.to_string());
    if stack.is_some_and(|stack| stack.item == "create:wrench") {
        if let Some(mob) = game
            .mobs
            .iter_mut()
            .find(|mob| mob.id == id && mob.kind.id == ENTITY)
        {
            mob.extra.ints[0] = 3;
        }
        return true;
    }
    let (Some(ingredient), Some(result)) = (ingredient, result) else {
        return false;
    };
    let Some(index) = game.inventory.iter().position(|slot| {
        slot.as_ref()
            .is_some_and(|item| item.item == ingredient && item.count > 0)
    }) else {
        return false;
    };
    if !game.creative {
        if let Some(item) = game.inventory[index].as_mut() {
            item.count -= 1;
            if item.count == 0 {
                game.inventory[index] = None;
            }
        }
    }
    game.give_or_drop(stack_from_name(&result));
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub fn break_entity(game: &mut Game<'_>, id: u32, canceled: &mut bool) {
    let Some(mob) = entity(game, id) else {
        return;
    };
    let pos = mob.position;
    if game.native_remove_mob(game.native_dimension(), id) {
        game.add_item_entity(stack_from_name(ITEM), [pos.x, pos.y, pos.z], None, 10);
        *canceled = true;
    }
}
