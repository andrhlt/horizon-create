fn blueprint_mob_size(mob: &crate::mobs::Mob) -> std::ops::ControlFlow<(f64, f64, f64)> {
    crate::mobs::create_blueprint_mob::size(mob)
}
