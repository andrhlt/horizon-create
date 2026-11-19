fn train_target(
    game: &crate::game::Game<'_>,
    id: i32,
) -> std::ops::ControlFlow<Option<([f64; 3], [f64; 3], [f64; 3])>> {
    crate::game::create_train::hitbox(game, id as u32)
        .map_or(std::ops::ControlFlow::Continue(()), |target| {
            std::ops::ControlFlow::Break(Some(target))
        })
}
