use horizon_client::mobs::{Damage, Mob};

/// PackageEntity.hurt ignites an unlit package for 100 ticks. While already
/// burning, each fire hit takes 0.15 health regardless of the source amount.
pub(super) fn damage(mob: &mut Mob, source: &Damage) -> bool {
    if mob.refuses_damage(source) || mob.fire_immune() {
        return false;
    }
    if mob.fire_ticks <= 0 {
        mob.fire_ticks = 100;
        return false;
    }
    let health = mob.health - 0.15;
    if health <= 0.5 {
        return true;
    }
    mob.health = health;
    false
}
