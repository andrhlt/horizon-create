fn elevator_seat_block(
    game: &mut Game<'_>,
    hit: Option<&Hit>,
) -> std::ops::ControlFlow<Result<bool>> {
    if hit.is_some_and(|hit| {
        crate::game::create_elevator_seats::dye_static(game, hit.pos)
            || crate::game::create_elevator_seats::board_static(game, hit.pos)
    }) {
        game.swing_arm();
        std::ops::ControlFlow::Break(Ok(true))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
