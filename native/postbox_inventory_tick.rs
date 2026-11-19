fn postbox_inventory_tick(game: &mut crate::game::Game<'_>, pos: (i32, i32, i32)) {
    let pos = [pos.0, pos.1, pos.2];
    crate::game::create_postbox::inventory_tick(game, pos);
    crate::game::create_toolbox::inventory_tick(game, pos);
}
