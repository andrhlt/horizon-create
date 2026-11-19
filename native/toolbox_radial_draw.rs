fn toolbox_radial_draw(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    batch: &mut horizon_client::hud::HudBatch,
) {
    crate::game::create_toolbox_radial::draw(game, screen, batch);
}
