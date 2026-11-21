fn train_schedule_receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_train_feedback::receive(channel, data);
    crate::game::create_train_schedule::receive(game, channel, data);
}
