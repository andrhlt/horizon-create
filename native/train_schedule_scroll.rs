fn train_schedule_scroll(
    game: &mut Game<'_>,
    mouse: [f32; 2],
    scroll: [f64; 2],
    modifiers: u32,
    canceled: &mut bool,
) {
    crate::game::create_train_schedule::scroll(game, mouse, scroll[1], modifiers, canceled);
}
