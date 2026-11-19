fn train_postbox_registry_tick(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut crate::containers::ModBlockEntity,
) {
    crate::game::create_train_postbox_registry::tick(game, pos, entity);
}
