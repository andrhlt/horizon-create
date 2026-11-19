fn linked_controller_receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_linked_controller::receive(game, player, channel, data);
}
