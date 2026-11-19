fn elevator_seat_target(
    game: &Game<'_>,
    id: i32,
) -> std::ops::ControlFlow<Option<([f64; 3], [f64; 3], [f64; 3])>> {
    if let Some(bounds) = crate::game::create_elevator_seats::interaction_bounds(game, id as u32) {
        std::ops::ControlFlow::Break(Some(bounds))
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
