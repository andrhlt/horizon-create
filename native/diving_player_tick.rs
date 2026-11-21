fn diving_player_tick(game: &mut crate::game::Game<'_>) {
    crate::game::create_backtank::diving_movement_tick(game);
}
