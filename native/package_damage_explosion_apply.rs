fn package_damage_explosion_apply(
    game: &mut Game<'_>,
    victim: u32,
    hurtable: bool,
    destroyed_contents: &mut Vec<(ItemStack, Vec3)>,
) {
    if hurtable && crate::game::create_package_damage::can_hurt(game, victim) {
        crate::game::create_package_damage::spill(game, victim, destroyed_contents);
    }
}
