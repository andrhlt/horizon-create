fn speed_controller_input_draw(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    batch: &mut horizon_client::hud::HudBatch,
) {
    crate::game::create_speed_controller_controls::render(game, screen, batch);
}
