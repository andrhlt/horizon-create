fn hand_crank_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    fluid: horizon_world::fluid::FluidState,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use horizon_core::geometry::Direction;
    use horizon_world::fluid::FluidKind;

    if answer.is_some()
        || !level.native_state_block(state).is_some_and(|name| {
            name == crate::game::create_hand_crank::CRANK
                || crate::game::create_valve::is_handle(name)
        })
    {
        return;
    }
    let direction = if context.sneaking {
        context.face
    } else {
        crate::game::create_hand_crank::preferred_direction(level, context.pos)
            .unwrap_or(context.face)
    };
    let [x, y, z] = direction.opposite().normal();
    let rear = context.pos.offset(x, y, z);
    let support = level.world.block(rear.x, rear.y, rear.z);
    let mut scene = horizon_client::collisions::SceneCollisions {
        world: &*level.world,
        binding: level.collision,
        subject: None,
    };
    if !level
        .collision
        .collision_shape(&mut scene, support, [rear.x, rear.y, rear.z])
        .is_ok_and(|shape| !shape.is_empty())
    {
        *answer = Some(None);
        return;
    }
    let face = match direction {
        Direction::Down => "down",
        Direction::Up => "up",
        Direction::North => "north",
        Direction::South => "south",
        Direction::West => "west",
        Direction::East => "east",
    };
    let waterlogged = if fluid.kind() == FluidKind::Water {
        "true"
    } else {
        "false"
    };
    *answer = Some(
        level
            .native_state_with_property(state, "facing", face)
            .and_then(|state| level.native_state_with_property(state, "waterlogged", waterlogged)),
    );
}
