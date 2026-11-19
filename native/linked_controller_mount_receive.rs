fn linked_controller_mount_receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_linked_controller::receive_mount(game, channel, data);
}
