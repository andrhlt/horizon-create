fn repackager_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use crate::containers::BlockEntity;
    use horizon_world::level::{LevelAccess, ordered_by_nearest};

    if answer.is_some() || level.native_state_block(state) != Some("create:repackager") {
        return;
    }
    let directions = ordered_by_nearest(context.yaw, context.pitch);
    let facing = directions
        .into_iter()
        .find(|direction| {
            let [x, y, z] = direction.normal();
            let target = context.pos.offset(x, y, z);
            level.native_state_block(level.block_state(target)) == Some("minecraft:barrel")
                && matches!(
                    level
                        .world
                        .block_entities
                        .get(&(target.x, target.y, target.z)),
                    Some(BlockEntity::Chest(_))
                )
        })
        .map(|direction| direction.opposite())
        .unwrap_or_else(|| {
            if context.sneaking {
                directions[0]
            } else {
                directions[0].opposite()
            }
        });
    *answer = Some(level.native_state_with_property(
        state,
        "facing",
        crate::game::create_fluids::name(facing),
    ));
}
