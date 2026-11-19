fn worldshaper_screen_receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_worldshaper_screen::receive(game, channel, data);
}
