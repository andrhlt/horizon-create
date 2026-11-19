fn use_elevator_contact(
    game: &mut Game<'_>,
    hit: Option<&Hit>,
) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| crate::game::create_elevator_floors::open_contact(game, hit.pos)) {
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
