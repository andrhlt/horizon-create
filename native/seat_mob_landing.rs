fn seat_mob_landing(
    game: &mut crate::game::Game<'_>,
    mob: u32,
    at: [i32; 3],
    continuing_y: f64,
) {
    crate::game::create_elevator_seats::board_landing_mob(game, mob, at, continuing_y);
}
