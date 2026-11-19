fn prepare_sequencers(game: &mut crate::game::Game<'_>) {
    crate::game::create_fluid_tank::finish_splits(game);
    crate::game::create_machines::resolve_motor_changes(game);
    crate::game::create_gantry::power_shafts(game);
    crate::game::create_gantry::move_existing(game);
    crate::game::create_chain_gearshift::prepare(game);
    crate::game::create_sequencer::prepare(game);
    crate::game::create_gantry::assemble_ready(game);
}
