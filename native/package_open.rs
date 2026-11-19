use horizon_world::nbt::Tag;

use crate::items::ItemStack;

use super::{Game, create_depot::compound, create_machines::int, creatures::SpawnYaw};

const CONTENTS: &str = "create:package_contents";
pub(super) const ORDER: &str = "create:package_order_data";
const PACKAGE_SLOTS: usize = 9;

pub(super) fn register(types: &mut Vec<String>) {
    types.extend([CONTENTS, ORDER].map(String::from));
}

pub(super) fn contents(game: &Game<'_>, package: &ItemStack) -> [Option<ItemStack>; PACKAGE_SLOTS] {
    let mut contents = std::array::from_fn(|_| None);
    if let Ok(Some(Tag::List(entries))) = game.native_component(package, CONTENTS) {
        for entry in entries {
            let Tag::Compound(entry) = entry else {
                continue;
            };
            let Some(slot) = int(entry, "slot")
                .and_then(|slot| usize::try_from(slot).ok())
                .filter(|&slot| slot < PACKAGE_SLOTS)
            else {
                continue;
            };
            contents[slot] = compound(entry, "item").and_then(ItemStack::from_nbt);
        }
    }
    contents
}

pub(super) fn spawn_egg(game: &mut Game<'_>, stack: &ItemStack, at: [f64; 3]) -> bool {
    let Some(kind) = stack.item.strip_suffix("_spawn_egg") else {
        return false;
    };
    if game.res.mob_types().get(kind).is_none() {
        return false;
    }
    let Some(id) = game.spawn_mob_spawned(kind, at, SpawnYaw::Created) else {
        return false;
    };
    if let Some(mob) = game.mobs.iter_mut().find(|mob| mob.id == id) {
        horizon_client::entity_nbt::apply_item_components(mob, stack);
    }
    game.apply_spawn_egg_entity_data(id, stack);
    true
}

pub(super) fn open(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed
        || !game.native_sneaking()
        || !game
            .items()
            .item_tags
            .get("create:packages")
            .is_some_and(|items| items.contains(stack.item.as_ref()))
    {
        return;
    }
    let Some(player) = game.native_acting_player() else {
        return;
    };
    let contents = contents(game, stack);
    let held = game.held_mut();
    let Some(package) = held.as_mut().filter(|item| item.item == stack.item) else {
        return;
    };
    package.count = package.count.saturating_sub(1);
    if package.count == 0 {
        *held = None;
    }
    *claimed = true;

    let radians = f64::from(player.yaw).to_radians();
    let [x, y, z] = player.position;
    let egg_position = [
        (x - radians.sin()).floor() + 0.5,
        y.floor(),
        (z + radians.cos()).floor() + 0.5,
    ];
    for mut item in contents.into_iter().flatten() {
        if spawn_egg(game, &item, egg_position) {
            item.count -= 1;
        }
        if let Some(overflow) = game.native_give_stack(player.uuid, item)
            && let Some(eye) = game.eye_position()
        {
            game.throw_from_eyes(overflow, eye, false);
        }
    }

    play_pop(game, player.position);
}

pub(super) fn play_pop(game: &mut Game<'_>, position: [f64; 3]) {
    let center = position.map(|position| position.floor() + 0.5);
    game.native_play_sound_in_place("create:package_pop", center, 4, 0.75, 1.0);
    game.native_play_sound_in_place("create:package_pop_compounded_1", center, 4, 0.25, 1.15);
}
