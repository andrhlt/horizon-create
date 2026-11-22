fn blueprint_interact(
    game: &mut Game<'_>,
    entity: i32,
    kind: &str,
    stack: Option<&ItemStack>,
    cancel: &mut bool,
) {
    if !*cancel
        && kind == "create:blueprint"
        && crate::game::create_blueprint::interact(game, entity as u32, stack)
    {
        *cancel = true;
    }
}
