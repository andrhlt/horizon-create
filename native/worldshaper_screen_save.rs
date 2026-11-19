fn worldshaper_screen_save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    crate::game::create_worldshaper_screen::save(game, player, channel, data);
}
