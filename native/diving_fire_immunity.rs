fn diving_fire_immunity(mob: &crate::mobs::Mob, immune: &mut bool) {
    *immune |= crate::mobs::create_diving::fire_immune(mob);
}
