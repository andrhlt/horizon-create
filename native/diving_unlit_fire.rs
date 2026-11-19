fn diving_unlit_fire(mob: &crate::mobs::Mob, reset: &mut bool) {
    // Create's reference runs the idle-fire reset when the protected mob first moves.
    if mob.fire_ticks < 0
        && mob.position == mob.previous
        && crate::mobs::create_diving::fire_immune(mob)
    {
        *reset = false;
    }
}
