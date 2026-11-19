fn level_tick_post(game: &mut crate::game::Game<'_>, dimension: &str) {
    crate::game::create_elevator::seats(game);
    crate::game::create_elevator_collision::sync(game);
    crate::game::create_machines::level_tick_post(game, dimension);
    crate::game::create_elevator_floors::publish_controls(game);
}
