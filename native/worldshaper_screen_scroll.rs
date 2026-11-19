fn worldshaper_screen_scroll(
    game: &Game<'_>,
    mouse: [f32; 2],
    scroll: [f64; 2],
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_worldshaper_screen::scroll(game, mouse, scroll, modifiers, canceled);
}
