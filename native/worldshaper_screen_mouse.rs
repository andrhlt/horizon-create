fn worldshaper_screen_mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    crate::game::create_worldshaper_screen::mouse(game, screen, button, canceled);
}
