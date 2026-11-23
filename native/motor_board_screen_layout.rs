fn motor_board_screen_layout(block: &str, screen: &mut Option<crate::mod_api::NativeScreen>) {
    if block == crate::game::create_motor_board::BLOCK {
        *screen = Some(crate::game::create_motor_board::layout());
    }
}
