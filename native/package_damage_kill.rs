fn package_damage_kill(game: &mut Game<'_>, target: Target) -> std::ops::ControlFlow<()> {
    if let Target::Mob(entity) = target
        && crate::game::create_package_damage::discard(game, entity)
    {
        std::ops::ControlFlow::Break(())
    } else {
        std::ops::ControlFlow::Continue(())
    }
}
