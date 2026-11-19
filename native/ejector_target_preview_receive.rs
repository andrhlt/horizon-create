fn ejector_target_preview_receive(game: &mut crate::game::Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_ejector_target::receive_preview(game, channel, data);
}
