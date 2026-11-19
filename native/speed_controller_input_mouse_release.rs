fn speed_controller_input_mouse_release(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_speed_controller_controls::mouse_released(
        game, screen, button, modifiers, canceled,
    );
}
