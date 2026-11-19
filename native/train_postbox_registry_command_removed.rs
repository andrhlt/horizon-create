fn train_postbox_registry_command_removed(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
) {
    if !game.native_authoritative() {
        return;
    }
    let previous = game.world.block(pos[0], pos[1], pos[2]);
    let old_name = game.native_block(pos);
    let next_name = game.pack.assets.registry.state(state).map(|block| block.name.as_str());
    if next_name == Some(old_name.as_str()) {
        return;
    }
    if crate::game::create_postbox::block(&old_name) || old_name == crate::game::create_station::STATION {
        game.with_level(|_, level, _| {
            crate::game::create_train_postbox_registry::removed(level, pos, previous);
        });
    }
}
