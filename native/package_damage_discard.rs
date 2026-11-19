fn package_damage_discard(mob: &mut Mob, damage: Damage) -> std::ops::ControlFlow<bool> {
    use std::ops::ControlFlow::{Break, Continue};

    if mob.kind.id != crate::mobs::create_package_style::ENTITY {
        return Continue(());
    }
    if damage.is_fire() {
        // Carry lethal contact from the mob-only damage hook to the level's
        // post-tick spill before it publishes the entity state.
        if !mob.extra.flag && crate::mobs::create_package_fire::damage(mob, &damage) {
            mob.extra.flag = true;
        }
        return Break(false);
    }
    if damage.kind.bypasses_invulnerability() {
        if !mob.extra.client_side && mob.alive() {
            mob.removed = true;
        }
        return Break(false);
    }
    if matches!(
        damage.kind,
        DamageKind::Fall | DamageKind::Stalagmite | DamageKind::Explosion
    ) {
        return Break(false);
    }
    Continue(())
}
