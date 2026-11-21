fn postbox_break_contents_capture(game: &crate::game::Game<'_>, pos: [i32; 3]) {
    crate::game::create_postbox::before_player_break(game, pos);
}
