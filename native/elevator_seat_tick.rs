fn elevator_seat_tick(game: &mut Game<'_>) {
    crate::game::create_elevator_seats::advance_riders(game);
}
