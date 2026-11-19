fn goggles_hud(game: &crate::game::Game<'_>, batch: &mut horizon_client::hud::HudBatch) {
    crate::game::create_goggles::draw(game, batch);
}
