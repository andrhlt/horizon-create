fn blueprint_mob_draw(
    game: &Game<'_>,
    mob: &Mob,
    partial: f32,
    camera: DVec3,
    light: u32,
    out: &mut Vec<Vertex>,
) -> std::ops::ControlFlow<bool> {
    if mob.kind.id.as_str() != "create:blueprint" {
        return std::ops::ControlFlow::Continue(());
    }
    let drawn = game.mod_entity_draw(mob, partial, camera, light, out, |_, draw| {
        draw.translate([-0.5, 0.0, -0.5]);
        game.native_draw_model(draw, "create:item/crafting_blueprint", 0xffffff);
        true
    });
    std::ops::ControlFlow::Break(drawn)
}
