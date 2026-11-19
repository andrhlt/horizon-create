fn tank_command_changed(game: &mut crate::game::Game<'_>, pos: [i32; 3]) {
    crate::game::create_fluid_tank::placed(game, pos);
    crate::game::create_fluid_tank::trace_storage(game, "command");
}
