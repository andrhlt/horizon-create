fn blueprint_world_goals(mob: &mut crate::mobs::Mob) {
    if mob.kind.id.as_str() == "create:blueprint" {
        mob.ai.goals.clear();
        mob.ai.targets.clear();
    }
}
