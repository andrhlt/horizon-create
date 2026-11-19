use super::{Game, GameLevel};
use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    level::{Ticks, flags},
    registry::BlockStateId,
};

pub(super) const WHISTLE: &str = "create:steam_whistle";
const EXTENSION: &str = "create:steam_whistle_extension";

pub(super) fn neighbor(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    let blocks = level.behaviours;
    let powered = blocks.has_neighbor_signal(level, ticks, pos);
    if let Some(next) =
        level.native_state_with_property(state, "powered", if powered { "true" } else { "false" })
    {
        if next != state {
            blocks.set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
        }
    }
}

fn root(game: &Game<'_>, mut pos: [i32; 3]) -> Option<[i32; 3]> {
    while game.native_block(pos) == EXTENSION {
        pos[1] -= 1;
    }
    (game.native_block(pos) == WHISTLE).then_some(pos)
}

pub(super) fn grow(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game
        .held()
        .is_some_and(|stack| stack.item.as_ref() == WHISTLE)
    {
        return false;
    }
    let Some(root) = root(game, pos) else {
        return false;
    };
    if !game.native_authoritative() {
        return true;
    }
    let size = game
        .native_block_property(root, "size")
        .unwrap_or_else(|| "medium".into());
    for i in 1..=6 {
        let at = [root[0], root[1] + i, root[2]];
        let block = game.native_block(at);
        if block == EXTENSION {
            if game.native_block_property(at, "shape").as_deref() == Some("single") {
                game.native_set_block_property_with(at, "shape", "double", flags::UPDATE_ALL);
                break;
            }
            continue;
        }
        if block != "minecraft:air" {
            break;
        }
        let state = game.with_level(|_, level, _| {
            let state = level.registry.default_state(EXTENSION)?;
            level.native_state_with_property(state, "size", &size)
        });
        if let Some(state) = state {
            game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL);
            if i > 1 {
                game.native_set_block_property_with(
                    [at[0], at[1] - 1, at[2]],
                    "shape",
                    "double_connected",
                    flags::UPDATE_ALL,
                );
            }
        }
        break;
    }
    game.swing_arm();
    true
}

pub(super) fn wrench(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some(root) = root(game, pos) else {
        return false;
    };
    if game.native_authoritative() {
        let next = match game.native_block_property(root, "size").as_deref() {
            Some("small") => "medium",
            Some("medium") => "large",
            _ => "small",
        };
        game.native_set_block_property_with(root, "size", next, flags::UPDATE_ALL);
        for i in 1..=6 {
            let at = [root[0], root[1] + i, root[2]];
            if game.native_block(at) != EXTENSION {
                break;
            }
            game.native_set_block_property_with(at, "size", next, flags::UPDATE_ALL);
        }
        game.swing_arm();
    }
    true
}

fn support(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId) -> Option<bool> {
    let data = level.registry.state(state)?;
    let side = if data.name == WHISTLE {
        if data
            .properties
            .get("wall")
            .is_some_and(|value| value == "true")
        {
            let facing = data.properties.get("facing")?;
            Direction::ALL
                .into_iter()
                .find(|&side| super::create_fluids::name(side) == facing.as_str())?
        } else {
            Direction::Down
        }
    } else if data.name == EXTENSION {
        Direction::Down
    } else {
        return None;
    };
    let [x, y, z] = side.normal();
    let at = pos.offset(x, y, z);
    let below = level.world.block(at.x, at.y, at.z);
    let Some(backing) = level.registry.state(below) else {
        return Some(false);
    };
    if data.name == WHISTLE {
        return Some(matches!(
            backing.name.as_str(),
            "create:fluid_tank" | "create:creative_fluid_tank"
        ));
    }
    Some(
        backing.name == WHISTLE
            || (backing.name == EXTENSION
                && backing
                    .properties
                    .get("shape")
                    .is_some_and(|shape| shape != "single")),
    )
}

pub(super) fn survive(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    answer: &mut Option<bool>,
) {
    if answer.is_none() {
        *answer = support(level, pos, state);
    }
}

pub(super) fn shape(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    result: &mut Option<BlockStateId>,
) {
    if result.is_some() {
        return;
    }
    let Some(supported) = support(level, pos, state) else {
        return;
    };
    if !supported {
        *result = level.registry.default_state("minecraft:air");
        return;
    }
    let Some(data) = level
        .registry
        .state(state)
        .filter(|data| data.name == EXTENSION)
    else {
        return;
    };
    let below = level.world.block(pos.x, pos.y - 1, pos.z);
    let Some(lower) = level.registry.state(below) else {
        return;
    };
    let Some(size) = lower.properties.get("size") else {
        return;
    };
    let Some(shape) = data.properties.get("shape") else {
        return;
    };
    let above = level.world.block(pos.x, pos.y + 1, pos.z);
    let connected = level.native_state_block(above) == Some(EXTENSION);
    let desired = if connected {
        "double_connected"
    } else if shape == "double_connected" {
        "double"
    } else {
        shape.as_str()
    };
    *result = level
        .native_state_with_property(state, "size", size)
        .and_then(|next| level.native_state_with_property(next, "shape", desired))
        .filter(|&next| next != state);
}
