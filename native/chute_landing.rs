fn chute_landing(
    game: &mut crate::game::Game<'_>,
    client: bool,
    state: horizon_world::registry::BlockStateId,
    block_pos: [i32; 3],
    item_pos: [f64; 3],
    stack: &mut crate::items::ItemStack,
) {
    if !client {
        crate::game::create_machines::chute_landing(game, state, item_pos, stack);
        crate::game::create_crushing::landing(game, state, block_pos, stack);
        crate::game::create_saw::landing(game, state, block_pos, stack);
    }
}
