fn smart_observer_tick(game: &mut crate::game::Game<'_>) {
    crate::game::create_machines::update_clutches(game);
    crate::game::create_tank_reconnect::finish_moved(game);
    crate::game::create_machines::update_tanks(game);
    crate::game::create_funnel::loose_items(game);
    crate::game::create_rope::recover_detached_payloads(game);
    crate::game::create_smart_observer::tick(game);
    crate::game::create_redstone_link::tick(game);
}
