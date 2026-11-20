fn glue_remove(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    crate::game::create_glue::attack_block(game, pos, canceled);
}
