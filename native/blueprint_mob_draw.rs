fn blueprint_mob_draw(
    game: &crate::game::Game<'_>,
    mob: &crate::mobs::Mob,
    partial: f32,
    camera: horizon_core::geometry::DVec3,
    light: u32,
    out: &mut Vec<horizon_client::render::Vertex>,
) -> std::ops::ControlFlow<bool> {
    crate::game::create_blueprint::draw(game, mob, partial, camera, light, out)
}
