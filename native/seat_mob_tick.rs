fn seat_mob_tick(game: &mut crate::game::Game<'_>) {
    crate::game::create_elevator_seats::tick_static_mob_riders(game);
}
