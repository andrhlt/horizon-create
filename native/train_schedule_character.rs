fn train_schedule_character(game: &Game<'_>, c: char, canceled: &mut bool) {
    crate::game::create_train_schedule::character(game, c, canceled);
}
