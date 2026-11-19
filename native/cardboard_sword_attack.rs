fn cardboard_sword_attack(game: &mut crate::game::Game<'_>, entity: i32, canceled: &mut bool) {
    crate::game::create_cardboard_sword::attack_mob(game, entity, canceled);
}
