use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    fluid::FluidKind,
    level::{PlaceContext, flags},
    registry::BlockStateId,
};

use super::{Game, GameLevel};

pub(super) fn metal_ladder(name: &str) -> bool {
    matches!(
        name,
        "create:andesite_ladder" | "create:brass_ladder" | "create:copper_ladder"
    )
}

fn support(level: &GameLevel<'_>, state: BlockStateId, at: BlockPos) -> Option<bool> {
    let state = level.registry.state(state)?;
    if !metal_ladder(&state.name) {
        return None;
    }
    let facing = state.properties.get("facing")?;
    let facing = Direction::ALL
        .into_iter()
        .find(|&side| super::create_fluids::name(side) == facing.as_str())?;
    let [dx, _, dz] = facing.opposite().normal();
    let backing = level.world.block(at.x + dx, at.y, at.z + dz);
    if level.behaviours.is_face_sturdy(backing, facing) {
        return Some(true);
    }
    let above = level.world.block(at.x, at.y + 1, at.z);
    Some(level.registry.state(above).is_some_and(|upper| {
        upper.name == state.name && upper.properties.get("facing") == state.properties.get("facing")
    }))
}

pub(super) fn wrench(game: &mut Game<'_>, pos: [i32; 3], face: Direction) -> Option<bool> {
    let at = BlockPos::new(pos[0], pos[1], pos[2]);
    let current = game.world.block(at.x, at.y, at.z);
    let next = game.with_level(|_, level, _| {
        let mut next = current;
        if matches!(face, Direction::Up | Direction::Down) {
            let state = level.registry.state(current)?;
            let facing = state.properties.get("facing")?;
            let direction = Direction::ALL
                .into_iter()
                .find(|&side| super::create_fluids::name(side) == facing.as_str())?;
            let rotated = super::create_wrench::rotate(direction, face);
            next = level.native_state_with_property(
                current,
                "facing",
                super::create_fluids::name(rotated),
            )?;
        }
        (support(level, next, at) == Some(true)).then_some(next)
    })?;
    Some(
        next != current
            && game.native_set_block(game.native_dimension(), pos, next, flags::UPDATE_ALL),
    )
}

pub(super) fn survive(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    survives: &mut Option<bool>,
) {
    if let Some(supported) = support(level, state, pos) {
        *survives = Some(supported);
    }
}

pub(super) fn shape(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    result: &mut Option<BlockStateId>,
) {
    if support(level, state, pos) == Some(false) {
        let replacement = if level.behaviours.fluid(state).kind() == FluidKind::Water {
            "minecraft:water"
        } else {
            "minecraft:air"
        };
        *result = level.registry.default_state(replacement);
    }
}

pub(super) fn redirect_placement(game: &mut Game<'_>, context: &mut PlaceContext) {
    if context.sneaking || !game.may_build() || !metal_ladder(&context.item) {
        return;
    }
    let origin = context.clicked_pos;
    let source = game.world.block(origin.x, origin.y, origin.z);
    let registry = &game.pack.assets.registry;
    let Some(source_state) = registry
        .state(source)
        .filter(|state| metal_ladder(&state.name))
    else {
        return;
    };
    let Some(facing) = source_state.properties.get("facing").cloned() else {
        return;
    };
    let step = if context.pitch < 0.0 { 1 } else { -1 };
    // Java's default placement assist finds the first non-ladder among 12 cells.
    let target = (1..=12)
        .map(|distance| origin.offset(0, step * distance, 0))
        .find(|at| {
            !game
                .res
                .facts()
                .get(game.world.block(at.x, at.y, at.z))
                .has_class("LadderBlock")
        });
    let Some(target) = target else {
        return;
    };
    let wet = game.with_level(|behaviour, level, _| {
        let previous = level.world.block(target.x, target.y, target.z);
        if !behaviour.is_replaceable(previous) || support(level, source, target) != Some(true) {
            return None;
        }
        let fluid = behaviour.fluid(previous);
        Some(fluid.kind() == FluidKind::Water && fluid.is_source())
    });
    let Some(wet) = wet else {
        return;
    };
    let registry = &game.pack.assets.registry;
    let Some(mut state) = registry
        .default_state(&context.item)
        .and_then(|id| registry.state(id))
        .cloned()
    else {
        return;
    };
    state.properties.insert("facing".into(), facing);
    state
        .properties
        .insert("waterlogged".into(), wet.to_string());
    if let Some(id) = registry.id(&state) {
        context.clicked_pos = target;
        context.state_override = Some(id);
    }
}
