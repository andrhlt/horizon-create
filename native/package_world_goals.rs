fn package_world_goals(mob: &mut crate::mobs::Mob) {
    if mob.kind.id.as_str() == "create:package" {
        mob.ai.goals.clear();
        mob.ai.targets.clear();
    }
}
