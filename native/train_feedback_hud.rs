fn train_feedback_hud(game: &crate::game::Game<'_>, batch: &mut horizon_client::hud::HudBatch) {
    crate::game::create_train_feedback::draw(game, batch);
}
