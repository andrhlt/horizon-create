fn motor_board_screen_click(
    block: &str,
    _data: &[i32],
    at: [f32; 2],
    right: bool,
    button: &mut Option<i32>,
) {
    if block == crate::game::create_motor_board_screen::BLOCK {
        crate::game::create_motor_board_screen::screen_click(at, right, button);
    }
}
