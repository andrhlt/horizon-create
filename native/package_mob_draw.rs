fn package_mob_draw(
    game: &Game<'_>,
    mob: &Mob,
    partial: f32,
    camera: DVec3,
    light: u32,
    out: &mut Vec<Vertex>,
) -> std::ops::ControlFlow<bool> {
    if mob.kind.id != super::create_package_style::ENTITY {
        return std::ops::ControlFlow::Continue(());
    }
    let drawn = game.mod_entity_draw(mob, partial, camera, light, out, |_, draw| {
        if let Some(item) = mob.extra.main_hand_stack()
            && let Some(name) = item.item.strip_prefix("create:")
        {
            draw.translate([-0.5, 0.0, -0.5]);
            draw.rotate_about([0.0, 1.0, 0.0], -90.0, [0.5; 3]);
            game.native_draw_model(draw, &format!("create:item/{name}"), 0xffffff);
        }
        true
    });
    std::ops::ControlFlow::Break(drawn)
}
