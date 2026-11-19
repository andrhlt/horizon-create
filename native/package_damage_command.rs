fn package_damage_command(
    game: &mut Game<'_>,
    entity: u32,
    damage: Damage,
) -> std::ops::ControlFlow<bool> {
    use horizon_client::mobs::DamageKind;
    use std::ops::ControlFlow::{Break, Continue};

    use crate::game::{create_package_damage, create_package_fire, create_package_style};

    if damage.is_fire()
        && let Some(package) = game.mobs.iter_mut().find(|mob| {
            mob.id == entity && mob.kind.id == create_package_style::ENTITY && !mob.removed
        })
    {
        if create_package_fire::damage(package, &damage) {
            create_package_damage::spill_now(game, entity);
        }
        return Break(false);
    }
    if matches!(damage.kind, DamageKind::Generic | DamageKind::Explosion)
        && create_package_damage::can_hurt(game, entity)
        && create_package_damage::spill_now(game, entity)
    {
        Break(false)
    } else {
        Continue(())
    }
}
