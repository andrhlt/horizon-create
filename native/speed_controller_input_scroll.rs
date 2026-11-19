fn speed_controller_input_scroll(
    game: &mut crate::game::Game<'_>,
    mouse: [f32; 2],
    scroll: [f64; 2],
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_speed_controller_controls::scroll(
        game, mouse, scroll[1], modifiers, canceled,
    );
}
