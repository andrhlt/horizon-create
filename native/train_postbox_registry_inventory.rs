fn train_postbox_registry_inventory(game: &mut crate::game::Game<'_>, pos: (i32, i32, i32)) {
    crate::game::create_train_postbox_registry::inventory_changed(game, [pos.0, pos.1, pos.2]);
}
