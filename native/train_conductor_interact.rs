fn train_conductor_interact(
    game: &mut Game<'_>,
    entity: i32,
    stack: Option<&ItemStack>,
    location: [f64; 3],
    cancel: &mut bool,
) {
    if !*cancel && crate::game::create_train::interact_trapdoor(game, entity as u32, location) {
        *cancel = true;
    }
    if !*cancel
        && crate::game::create_train_conductor::interact(game, entity as u32, game.hand, stack)
    {
        *cancel = true;
    }
}
