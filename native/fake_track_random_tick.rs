fn fake_track_random_tick(
    level: &mut crate::game::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: horizon_core::position::BlockPos,
    state: horizon_world::registry::BlockStateId,
    handled: &mut bool,
) {
    use crate::containers::BlockEntity;
    use horizon_world::level::flags;
    if !level
        .registry
        .state(state)
        .is_some_and(|block| block.name == crate::game::create_fake_track::FAKE_TRACK)
    {
        return;
    }
    *handled = true;
    let key = (pos.x, pos.y, pos.z);
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key) else {
        return;
    };
    if entity.data.is_empty() {
        entity.data.push(3);
    }
    entity.data[0] -= 1;
    if entity.data[0] > 0 {
        return;
    }
    let wet = level
        .registry
        .state(state)
        .and_then(|s| s.properties.get("waterlogged"))
        .is_some_and(|v| v == "true");
    let name = if wet {
        "minecraft:water"
    } else {
        "minecraft:air"
    };
    if let Some(replacement) = level.registry.default_state(name) {
        let behaviours = level.behaviours;
        behaviours.set_block(level, ticks, pos, replacement, flags::UPDATE_ALL);
    }
}
