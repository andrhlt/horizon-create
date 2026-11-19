fn chain_conveyor_rider_remote(game: &mut Game<'_>) -> std::ops::ControlFlow<()> {
    if game
        .remote
        .as_ref()
        .is_some_and(|remote| remote.is_destroying)
        || game.hands_busy()
    {
        return std::ops::ControlFlow::Continue(());
    }
    if crate::game::create_chain_conveyor_rider::board(game).is_none() {
        return std::ops::ControlFlow::Continue(());
    }
    game.use_delay = 4;
    std::ops::ControlFlow::Break(())
}
