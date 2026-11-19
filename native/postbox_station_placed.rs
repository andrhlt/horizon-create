fn postbox_station_placed(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    stack: &crate::items::ItemStack,
) {
    crate::game::create_postbox::placed(game, pos, stack);
}
