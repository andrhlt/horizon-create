fn motor_board_screen_draw(
    game: &crate::game::Game<'_>,
    block: &str,
    _data: &[i32],
    batch: &mut horizon_client::hud::HudBatch,
    origin: [f32; 2],
) {
    if block == crate::game::create_motor_board::BLOCK {
        crate::game::create_motor_board::draw_screen(game, batch, origin);
    }
}
