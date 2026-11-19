fn chain_conveyor_box_visual_tick(game: &mut Game<'_>) {
    if game.remote.is_some() {
        crate::game::create_chain_conveyor_box_visual::tick(game);
    }
}
