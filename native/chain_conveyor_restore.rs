fn chain_conveyor_restore(game: &mut crate::game::Game<'_>, chunk: [i32; 2], new: bool) {
    if !new {
        crate::game::create_chain_conveyor_packages::restore_chunk(game, chunk);
    }
}
