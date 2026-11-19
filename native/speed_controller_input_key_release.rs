fn speed_controller_input_key_release(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    key: &str,
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_speed_controller_controls::key_released(
        game, screen, key, modifiers, canceled,
    );
}
