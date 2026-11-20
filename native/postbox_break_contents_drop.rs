fn postbox_break_contents_drop(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    result: Result<bool>,
) -> Result<bool> {
    crate::game::create_postbox::after_player_break(game, pos, result)
}
