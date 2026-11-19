fn valve_support_shape(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    direction: horizon_core::geometry::Direction,
    neighbour_pos: horizon_core::position::BlockPos,
    neighbour: horizon_world::registry::BlockStateId,
    new: &mut Option<horizon_world::registry::BlockStateId>,
) {
    if new.is_some() || !level.native_authoritative {
        return;
    }
    if let Some(replacement) = crate::game::create_factory_gauge::update_support(level, state, direction, neighbour_pos, neighbour) {
        *new = Some(replacement);
        return;
    }
    let Some(state) = level.registry.state(state) else {
        return;
    };
    if !crate::game::create_valve::is_handle(&state.name) {
        return;
    }
    let face = state
        .properties
        .get("facing")
        .and_then(|facing| crate::game::machines::dir_from_name(facing));
    if face != Some(direction.opposite()) {
        return;
    }

    let mut scene = horizon_client::collisions::SceneCollisions {
        world: &*level.world,
        binding: level.collision,
        subject: None,
    };
    if level
        .collision
        .collision_shape(
            &mut scene,
            neighbour,
            [neighbour_pos.x, neighbour_pos.y, neighbour_pos.z],
        )
        .is_ok_and(|shape| shape.is_empty())
    {
        // The shape updater destroys an air result, including restoring the
        // old block's fluid and emitting its normal drops.
        *new = level.registry.default_state("minecraft:air");
    }
}
