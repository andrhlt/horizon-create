fn steam_whistle_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use horizon_core::geometry::Direction;
    if answer.is_some() || level.native_state_block(state) != Some("create:steam_whistle") {
        return;
    }
    let side = context.face;
    let wall = !matches!(side, Direction::Up | Direction::Down);
    let support_side = if wall {
        side.opposite()
    } else {
        Direction::Down
    };
    let [dx, dy, dz] = support_side.normal();
    let at = context.pos.offset(dx, dy, dz);
    let support = level.world.block(at.x, at.y, at.z);
    if !matches!(
        level.native_state_block(support),
        Some("create:fluid_tank" | "create:creative_fluid_tank")
    ) {
        *answer = Some(None);
        return;
    }
    let facing = if wall {
        crate::game::create_fluids::name(side.opposite())
    } else {
        let rotation = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4);
        ["south", "west", "north", "east"][rotation as usize]
    };
    *answer = Some(
        level
            .native_state_with_property(state, "facing", facing)
            .and_then(|s| {
                level.native_state_with_property(s, "wall", if wall { "true" } else { "false" })
            }),
    );
}
