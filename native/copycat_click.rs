fn copycat_click(game: &mut Game<'_>, hit: Option<&Hit>) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| crate::game::create_copycat::use_material(game, hit)) {
        game.swing_arm();
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
