fn worldshaper_effect_server(game: &mut Game<'_>, phase: horizon_client::mod_api::ServerTickPhase) {
    crate::game::create_worldshaper_effect::server_tick(game, phase);
}
