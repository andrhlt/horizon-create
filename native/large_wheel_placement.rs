fn large_wheel_placement(
    level: &crate::game::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
    fluid: horizon_world::fluid::FluidState,
    answer: &mut Option<Option<horizon_world::registry::BlockStateId>>,
) {
    use crate::game::{create_fluids, create_hand_crank, create_machines};
    use horizon_core::geometry::Direction;
    use horizon_world::fluid::FluidKind;

    if answer.is_none() && level.native_state_block(state) == Some(create_machines::WHEEL) {
        // DirectionalKineticBlock prefers a neighboring shaft unless sneaking.
        // WaterWheelBlock's unused immutable setValue does not change its sign.
        let looking = context.nearest_looking_direction();
        // DirectionalKineticBlock faces opposite the nearest look direction
        // unless a preferred neighboring shaft overrides it.
        let placement_direction = if context.sneaking {
            looking
        } else {
            looking.opposite()
        };
        let facing = if context.sneaking {
            placement_direction
        } else {
            create_hand_crank::preferred_direction(level, context.pos)
                .unwrap_or(placement_direction)
        };
        let normal = facing.normal();
        let axis = normal.iter().position(|&component| component != 0).unwrap();
        // WaterWheelBlock.canSurvive permits neighboring wheels only along
        // their common axle. Reject before placement consumes the held item.
        for direction in Direction::ALL {
            let step = direction.normal();
            let pos = context.pos.offset(step[0], step[1], step[2]);
            let neighbor = level.world.block(pos.x, pos.y, pos.z);
            if level.native_state_block(neighbor) == Some(create_machines::WHEEL)
                && (step[axis] == 0
                    || !level
                        .registry
                        .state(neighbor)
                        .and_then(|state| state.properties.get("facing"))
                        .is_some_and(|facing| match axis {
                            0 => matches!(facing.as_str(), "east" | "west"),
                            1 => matches!(facing.as_str(), "up" | "down"),
                            _ => matches!(facing.as_str(), "north" | "south"),
                        }))
            {
                *answer = Some(None);
                return;
            }
        }
        *answer = Some(
            level
                .native_state_with_property(state, "facing", create_fluids::name(facing))
                .and_then(|state| {
                    level.native_state_with_property(
                        state,
                        "waterlogged",
                        if fluid.kind() == FluidKind::Water {
                            "true"
                        } else {
                            "false"
                        },
                    )
                }),
        );
        return;
    }
    if answer.is_none()
        && let Some(placement) = crate::game::create_track::place(level, state, context)
    {
        *answer = Some(placement);
        return;
    }
    if answer.is_none()
        && let Some(placement) = crate::game::create_latches::placement(level, state, context)
    {
        *answer = Some(placement);
        return;
    }
    crate::game::create_large_wheel::placement(level, state, context, answer);
    if answer.is_none()
        && let Some(placement) = crate::game::create_funnel::place(level, state, context)
            .or_else(|| crate::game::create_arm::place(level, state, context))
            .or_else(|| crate::game::create_contact::place(level, state, context))
            .or_else(|| crate::game::create_redstone_link::place(level, state, context))
            .or_else(|| crate::game::create_hose::place(level, state, context))
            .or_else(|| crate::game::create_portable_interface::place(level, state, context))
            .or_else(|| crate::game::create_mechanical_piston::place(level, state, context))
            .or_else(|| crate::game::create_saw::place(level, state, context))
            .or_else(|| crate::game::create_drill::placement(level, state, context))
    {
        *answer = Some(Some(placement));
    }
}
