fn toolbox_link_packet(game: &mut crate::game::Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_toolbox_links::receive(game, player, channel, data);
}
