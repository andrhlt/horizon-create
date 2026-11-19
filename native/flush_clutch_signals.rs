fn flush_clutch_signals(game: &mut crate::game::Game<'_>) {
    crate::game::create_machines::flush_clutch_signals(game);
    crate::game::create_machines::flush_disconnected_motors(game);
    crate::game::create_controller_rail::flush(game);
    crate::game::create_clockwork::restore_removed(game);
}
