fn train_schedule_save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_train_schedule::save(game, player, channel, data);
}
