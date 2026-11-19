use super::Game;
use crate::containers::ModBlockEntity;
use horizon_world::nbt::Tag;

pub(super) fn window_enabled(entity: &ModBlockEntity) -> bool {
    match entity.nbt.get(&"Window".into()) {
        Some(Tag::Byte(value)) => *value != 0,
        _ => true,
    }
}

pub(super) fn sync(
    game: &mut Game<'_>,
    root: [i32; 3],
    width: usize,
    parts: &[[i32; 3]],
    enabled: bool,
) {
    for &pos in parts {
        let x = pos[0] - root[0];
        let z = pos[2] - root[2];
        let shape = if !enabled {
            "plain"
        } else {
            match width {
                1 => "window",
                2 => match (x, z) {
                    (0, 0) => "window_nw",
                    (0, 1) => "window_sw",
                    (1, 0) => "window_ne",
                    (1, 1) => "window_se",
                    _ => "plain",
                },
                3 if (x - z).abs() == 1 => "window",
                _ => "plain",
            }
        };
        if game.native_block_property(pos, "shape").as_deref() != Some(shape) {
            game.native_set_block_property_with(pos, "shape", shape, 2);
        }
    }
}

pub(super) fn tick(
    game: &mut Game<'_>,
    root: [i32; 3],
    entity: &ModBlockEntity,
    width: usize,
    parts: &[[i32; 3]],
) {
    sync(game, root, width, parts, window_enabled(entity));
}

pub(super) fn wrench(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some((width, parts)) = super::create_fluid_tank::parts(game, pos) else {
        return false;
    };
    let Some(&root) = parts.first() else {
        return false;
    };
    if super::create_steam::accepts_water(game, root) {
        return true;
    }
    let Some(entity) = super::create_machines::mod_entity(game, root) else {
        return false;
    };
    let enabled = !window_enabled(entity);
    game.native_with_mod_block_entity(root, |entity| {
        entity
            .nbt
            .insert("Window".into(), Tag::Byte(i8::from(enabled)));
    });
    sync(game, root, width, &parts, enabled);
    if let Some(entity) = super::create_machines::mod_entity(game, root).cloned() {
        super::create_tank_lighting::sync(game, root, width, &parts, &entity);
    }
    true
}

// ConnectivityHandler.removeController resets each surviving part's own
// block state before the removed part disappears.
pub(super) fn split_singleton(level: &mut super::GameLevel<'_>, ticks: &mut horizon_world::level::Ticks, pos: [i32; 3]) {
    let Some(crate::containers::BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos[0], pos[1], pos[2])) else { return };
    let shape = if window_enabled(entity) { "window" } else { "plain" };
    level.native_set_block_property(ticks, pos, "shape", shape, 2);
    level.native_set_block_property(ticks, pos, "top", "true", 2);
    level.native_set_block_property(ticks, pos, "bottom", "true", 2);
}
