fn blueprint_attack(game: &mut crate::game::Game<'_>, entity: i32, canceled: &mut bool) {
    crate::game::create_blueprint::break_entity(game, entity as u32, canceled);
}
