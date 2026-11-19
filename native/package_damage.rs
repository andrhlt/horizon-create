use horizon_core::geometry::Vec3;

use crate::items::ItemStack;

use super::{
    Game,
    create_package_open::{contents, play_pop, spawn_egg},
    create_package_style::ENTITY,
};

fn package<'a>(game: &'a Game<'_>, entity: u32) -> Option<&'a horizon_client::mobs::Mob> {
    game.mobs
        .iter()
        .find(|mob| mob.id == entity && mob.kind.id == ENTITY && !mob.removed)
}

pub(super) fn can_hurt(game: &Game<'_>, entity: u32) -> bool {
    package(game, entity).is_some_and(|mob| mob.alive() && !mob.is_invulnerable())
}

pub(super) fn discard(game: &mut Game<'_>, entity: u32) -> bool {
    package(game, entity).is_some() && game.native_remove_mob(game.native_dimension(), entity)
}

pub(super) fn spill(game: &mut Game<'_>, entity: u32, drops: &mut Vec<(ItemStack, Vec3)>) -> bool {
    let Some(package) = package(game, entity).filter(|mob| mob.alive()) else {
        return false;
    };
    let Some(stack) = package.extra.main_hand_stack() else {
        return false;
    };
    let position = package.position;
    let contents = contents(game, stack);
    if !game.native_remove_mob(game.native_dimension(), entity) {
        return false;
    }

    play_pop(game, [position.x, position.y, position.z]);
    let egg_at = [
        position.x.floor() + 0.5,
        position.y.floor(),
        position.z.floor() + 0.5,
    ];
    for mut item in contents.into_iter().flatten() {
        if spawn_egg(game, &item, egg_at) {
            item.count -= 1;
        }
        if item.count > 0 {
            drops.push((item, position));
        }
    }
    true
}

pub(super) fn spill_now(game: &mut Game<'_>, entity: u32) -> bool {
    let mut drops = Vec::new();
    if !spill(game, entity, &mut drops) {
        return false;
    }
    game.spawn_destroyed_contents(drops);
    true
}

pub(super) fn tick(game: &mut Game<'_>, entity: u32) {
    let Some(package) = game
        .mobs
        .iter_mut()
        .find(|mob| mob.id == entity && mob.kind.id == ENTITY && !mob.removed && mob.alive())
    else {
        return;
    };
    if std::mem::take(&mut package.extra.flag) {
        spill_now(game, entity);
        return;
    }
    if package.fire_immune() {
        package.fire_ticks = 0;
    } else if package.fire_ticks == 0 {
        package.fire_ticks = -1;
    }
    let bounds = package.bounds();
    let min = bounds.min_position();
    let max = bounds.max_position();
    let [x, y, z] = [min.x, min.y, min.z].map(|n| (n + 1e-7).floor() as i32);
    let [ex, ey, ez] = [max.x, max.y, max.z].map(|n| (n - 1e-7).floor() as i32);
    if (x..=ex).any(|x| {
        (y..=ey).any(|y| {
            (z..=ez).any(|z| {
                let at = [x, y, z];
                game.native_block(at) == "minecraft:water"
                    || game.native_block_property(at, "waterlogged").as_deref() == Some("true")
            })
        })
    }) {
        spill_now(game, entity);
    }
}
