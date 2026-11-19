fn toolbox_radial_receive(game: &mut crate::game::Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_toolbox_radial::receive(game, channel, data);
}
