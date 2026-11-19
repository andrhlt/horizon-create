fn speed_controller_input_tick(game: &mut crate::game::Game<'_>) {
    crate::game::create_speed_controller_controls::tick(game);
}
