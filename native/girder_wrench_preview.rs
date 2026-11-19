fn girder_wrench_preview(
    game: &crate::game::Game<'_>,
    primitives: &mut crate::world_primitives::WorldPrimitives,
) {
    crate::game::create_shaft::render_girder_wrench(game, primitives);
}
