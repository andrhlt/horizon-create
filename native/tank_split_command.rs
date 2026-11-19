fn tank_split_command(game: &mut crate::game::Game<'_>, pos: [i32; 3], state: horizon_world::registry::BlockStateId) {
    let block = game.native_block(pos);
    if !matches!(block.as_str(), crate::game::create_fluid_tank::TANK | crate::game::create_fluid_tank::CREATIVE)
        || game.pack.assets.registry.state(state).is_some_and(|next| next.name == block) {
        return;
    }
    game.with_level(|_, level, ticks| crate::game::create_fluid_tank::split_pair(level, ticks, pos));
}
