fn worldshaper_creative_selection(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
) -> std::ops::ControlFlow<Result<()>> {
    if game.creative && crate::game::create_worldshaper::claim_selection(game, pos) {
        std::ops::ControlFlow::Break(game.process_level_events())
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
