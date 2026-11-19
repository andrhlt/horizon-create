fn toolbox_link_tick(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut crate::containers::ModBlockEntity,
) {
    if entity.id == crate::game::create_toolbox::ENTITY {
        crate::game::create_toolbox_links::tick(game, pos, entity);
    }
}
