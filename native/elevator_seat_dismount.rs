fn elevator_seat_dismount(game: &mut Game<'_>) -> std::ops::ControlFlow<()> {
    if crate::game::create_elevator_seats::dismount(game) {
        std::ops::ControlFlow::Break(())
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
