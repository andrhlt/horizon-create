fn clipboard_attack(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
) -> std::ops::ControlFlow<Result<()>> {
    if crate::game::create_worldshaper::claim_selection(game, pos)
        || crate::game::create_placard::attack(game, pos)
        || crate::game::create_clipboard_block::pickup(game, pos)
        || crate::game::create_toolbox::pickup(game, pos)
    {
        std::ops::ControlFlow::Break(game.process_level_events())
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
