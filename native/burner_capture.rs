fn burner_capture(
    game: &mut crate::game::Game<'_>,
    entity: i32,
    kind: &str,
    stack: Option<&crate::items::ItemStack>,
    claimed: &mut bool,
) {
    if !*claimed
        && kind == "minecraft:interaction"
        && crate::game::create_train::click(game, entity as u32)
    {
        *claimed = true;
        return;
    }
    if !*claimed && crate::game::create_burner::capture(game, entity, kind, stack) {
        *claimed = true;
    }
}
