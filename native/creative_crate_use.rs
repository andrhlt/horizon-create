fn creative_crate_use(
    game: &mut Game<'_>,
    hit: Option<&Hit>,
) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| crate::game::create_creative_crate::interact(game, hit)) {
        game.swing_arm();
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
