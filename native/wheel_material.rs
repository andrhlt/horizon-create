use horizon_world::nbt::{Compound, JavaString, Tag};

use crate::items::ItemStack;

use super::Game;
use super::create_machines::{LARGE_WHEEL, WHEEL, mod_entity};

pub(super) const WOODS: [&str; 12] = [
    "oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "crimson", "warped", "mangrove",
    "bamboo", "cherry", "pale_oak",
];

pub(super) fn material(nbt: &Compound) -> String {
    if let Some(Tag::Compound(state)) = nbt.get(&JavaString::from("Material"))
        && let Some(Tag::String(name)) = state.get(&JavaString::from("Name"))
    {
        name.to_string_lossy()
    } else {
        "minecraft:spruce_planks".into()
    }
}

pub(super) fn use_planks(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) -> bool {
    if !game
        .native_block_name_in_tag(stack.item.as_ref(), "minecraft:planks")
        .is_ok_and(|member| member)
        || stack.count == 0
    {
        return false;
    }
    let pos = if game.native_block(at) == "create:water_wheel_structure" {
        let Some((master, _)) =
            game.with_level(|_, level, _| super::create_large_wheel::rim_master(level, at))
        else {
            return false;
        };
        master
    } else {
        at
    };
    let Some(wheel) = mod_entity(game, pos) else {
        return false;
    };
    if !matches!(wheel.id.as_str(), WHEEL | LARGE_WHEEL)
        || material(&wheel.nbt) == stack.item.as_ref()
    {
        return false;
    }
    let mut state = Compound::new();
    state.insert("Name".into(), Tag::String(stack.item.as_ref().into()));
    game.native_with_mod_block_entity(pos, |wheel| {
        wheel.nbt.insert("Material".into(), Tag::Compound(state));
    });
    game.native_block_entity_sync(pos);
    true
}
