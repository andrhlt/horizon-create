fn train_schedule_key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    crate::game::create_train_schedule::key(game, key, modifiers, canceled);
}
