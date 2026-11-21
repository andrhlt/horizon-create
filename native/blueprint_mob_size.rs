fn blueprint_mob_size(mob: &crate::mobs::Mob) -> std::ops::ControlFlow<(f64, f64, f64)> {
    crate::game::create_blueprint::size(mob)
}
