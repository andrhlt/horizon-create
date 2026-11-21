fn blueprint_interact(
    game: &mut crate::game::Game<'_>,
    entity: i32,
    stack: Option<&crate::items::ItemStack>,
    _location: [f64; 3],
    cancel: &mut bool,
) {
    if !*cancel && crate::game::create_blueprint::interact(game, entity as u32, stack) {
        *cancel = true;
    }
}
