fn blueprint_world_goals(mob: &mut crate::mobs::Mob) {
    if mob.kind.id == crate::game::create_blueprint::ENTITY {
        mob.ai.goals.clear();
        mob.ai.targets.clear();
    }
}
