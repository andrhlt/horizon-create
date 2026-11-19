fn worldshaper_screen_use(
    game: &mut Game<'_>,
    stack: &crate::items::ItemStack,
    claimed: &mut bool,
) {
    if !*claimed
        && (crate::game::create_worldshaper_screen::open(game, stack)
            || crate::game::create_worldshaper::use_tool(game, stack, None))
    {
        *claimed = true;
    }
}
