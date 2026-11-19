fn container_accepts(
    game: &crate::game::Game<'_>,
    entity: &crate::containers::ModBlockEntity,
    slot: usize,
    stack: &crate::items::ItemStack,
    cancel: &mut bool,
) {
    crate::game::create_machines::container_accepts(game, entity, slot, stack, cancel);
}
