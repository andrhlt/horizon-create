fn use_elevator(game: &mut Game<'_>, hit: Option<&Hit>) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| crate::game::create_elevator::click(game, hit.pos)) {
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
