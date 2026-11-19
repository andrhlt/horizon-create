fn cardboard_sword_block(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    crate::game::create_cardboard_sword::block_attack(game, pos, *canceled);
}
