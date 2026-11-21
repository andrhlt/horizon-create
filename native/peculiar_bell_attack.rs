fn peculiar_bell_attack(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    crate::game::create_peculiar_bell::attack(game, pos, canceled);
}
