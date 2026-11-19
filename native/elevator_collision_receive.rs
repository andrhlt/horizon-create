fn elevator_collision_receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_elevator_collision::receive(game, channel, data);
}
