fn toolbox_hotbar_hud(game: &crate::game::Game<'_>, batch: &mut horizon_client::hud::HudBatch) {
    crate::game::create_toolbox_radial::hud(game, batch);
}
