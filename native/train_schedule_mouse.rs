fn train_schedule_mouse(game: &Game<'_>, screen: &NativeScreenView<'_>, button: i32, modifiers: u32, canceled: &mut bool) {
    crate::game::create_train_schedule::mouse(game, screen, button, modifiers, canceled);
}
