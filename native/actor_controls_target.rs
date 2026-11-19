fn actor_controls_target(
    game: &Game<'_>,
    id: i32,
) -> std::ops::ControlFlow<Option<([f64; 3], [f64; 3], [f64; 3])>> {
    let entity_id = id as u32;
    if game
        .persist
        .raw
        .get(&entity_id)
        .and_then(|raw| raw.get("CreateControlPos"))
        .is_none()
    {
        return std::ops::ControlFlow::Continue(());
    }
    let Some(entity) = game.others.iter().find(|entity| entity.id == entity_id) else {
        return std::ops::ControlFlow::Continue(());
    };
    let Some(hitbox) = entity.interaction.as_ref() else {
        return std::ops::ControlFlow::Continue(());
    };
    let [x, y, z] = entity.position.components();
    let half = f64::from(hitbox.width) / 2.0;
    let min = [x - half, y, z - half];
    let max = [x + half, y + f64::from(hitbox.height), z + half];
    std::ops::ControlFlow::Break(Some((min, max, [x, y, z])))
}
