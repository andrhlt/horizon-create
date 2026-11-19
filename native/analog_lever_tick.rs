fn analog_lever_tick(game: &mut crate::game::Game<'_>, pos: (i32, i32, i32)) {
    crate::game::create_analog_lever::tick(game, pos);
}
