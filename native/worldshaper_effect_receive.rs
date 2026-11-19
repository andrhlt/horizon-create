fn worldshaper_effect_receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    crate::game::create_worldshaper_effect::receive(game, channel, data);
}
