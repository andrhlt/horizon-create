use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, PlacementContext, Ticks, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use super::create_bearing::relative;
use super::create_fan::facing;
use super::{Game, GameLevel};

pub(super) const CONTACT: &str = "create:redstone_contact";
const ELEVATOR_CONTACT: &str = "create:elevator_contact";

fn direction(name: &str) -> Direction {
    match name {
        "down" => Direction::Down,
        "east" => Direction::East,
        "north" => Direction::North,
        "south" => Direction::South,
        "west" => Direction::West,
        _ => Direction::Up,
    }
}

fn face(level: &GameLevel<'_>, state: BlockStateId) -> Option<Direction> {
    let info = level.registry.state(state)?;
    (info.name == CONTACT || info.name == ELEVATOR_CONTACT)
        .then(|| direction(info.properties.get("facing").map_or("up", String::as_str)))
}

pub(super) fn face_name(side: Direction) -> &'static str {
    match side {
        Direction::Down => "down",
        Direction::East => "east",
        Direction::North => "north",
        Direction::South => "south",
        Direction::West => "west",
        Direction::Up => "up",
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
) -> Option<BlockStateId> {
    face(level, state)?;
    let to_support = ctx.face.opposite();
    let connects = |side: Direction| {
        let [x, y, z] = side.normal();
        let pos = BlockPos::new(ctx.pos.x + x, ctx.pos.y + y, ctx.pos.z + z);
        face(level, level.block_state(pos)) == Some(side.opposite())
    };
    let side = if ctx.sneaking || connects(to_support) {
        to_support
    } else {
        let look = super::view_vector(ctx.yaw, ctx.pitch);
        Direction::ALL
            .into_iter()
            .max_by(|a, b| {
                let dot = |direction: Direction| {
                    direction
                        .normal()
                        .into_iter()
                        .zip(look)
                        .map(|(delta, value)| f64::from(delta) * value)
                        .sum::<f64>()
                };
                dot(*a).total_cmp(&dot(*b))
            })?
            .opposite()
    };
    let state = level.native_state_with_property(state, "facing", face_name(side))?;
    level.native_state_with_property(
        state,
        "powered",
        if connects(side) { "true" } else { "false" },
    )
}

pub(super) fn shape(
    level: &GameLevel<'_>,
    state: BlockStateId,
    side: Direction,
    neighbor: BlockStateId,
    result: &mut Option<BlockStateId>,
) {
    if face(level, state) == Some(side) {
        let connected = face(level, neighbor) == Some(side.opposite());
        *result = level.native_state_with_property(
            state,
            "powered",
            if connected { "true" } else { "false" },
        );
    }
}

pub(super) fn tick(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: BlockPos,
    state: BlockStateId,
) {
    let Some(side) = face(level, state) else {
        return;
    };
    let [dx, dy, dz] = side.normal();
    let neighbor = level.block_state(BlockPos::new(pos.x + dx, pos.y + dy, pos.z + dz));
    let powered = face(level, neighbor) == Some(side.opposite());
    level.native_set_block_property(
        ticks,
        [pos.x, pos.y, pos.z],
        "powered",
        if powered { "true" } else { "false" },
        flags::UPDATE_ALL,
    );
}

pub(super) fn source(level: &GameLevel<'_>, state: BlockStateId, out: &mut bool) {
    *out |= level.registry.state(state).is_some_and(|info| {
        info.name == CONTACT && info.properties.get("powered").is_some_and(|v| v == "true")
    });
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    state: BlockStateId,
    side: Direction,
    direct: bool,
    out: &mut i32,
) {
    if direct {
        return;
    }
    let mut powered = false;
    source(level, state, &mut powered);
    if powered && face(level, state).is_some_and(|face| face != side) {
        *out = 15;
    }
}

fn schedule_reset(game: &mut Game<'_>, at: [i32; 3]) {
    game.with_level(|_, level, ticks| level.native_schedule_block_tick(ticks, at, CONTACT, 1));
}

pub(super) fn moving(
    game: &mut Game<'_>,
    blocks: &[Compound],
    origin: [f64; 3],
    data: &mut Compound,
    enabled: bool,
) {
    let key = "Contacts".into();
    let old = match data.remove(&key) {
        Some(Tag::List(contacts)) => contacts,
        _ => Vec::new(),
    };
    let mut next = Vec::new();
    if enabled {
        for block in blocks {
            let Some(state) = block
                .get(&"BlockState".into())
                .and_then(|tag| game.state_from_nbt(tag))
            else {
                continue;
            };
            if game.native_state_block(state) != Some(CONTACT) {
                continue;
            }
            let Some(side) = facing(game, state) else {
                continue;
            };
            let pos = relative(block);
            let ray = side.normal();
            let at = std::array::from_fn(|i| {
                (origin[i] + f64::from(pos[i]) + 0.5 + f64::from(ray[i]) * 0.65).floor() as i32
            });
            let target = game.world.block(at[0], at[1], at[2]);
            if game.native_state_block(target) != Some(CONTACT)
                || facing(game, target) != Some(side.opposite())
            {
                continue;
            }
            let entry = Tag::IntArray(at.to_vec());
            if !old.contains(&entry) && !next.contains(&entry) {
                game.native_set_block_property(at, "powered", "true");
            }
            next.push(entry);
        }
    }
    for area in old {
        if !next.contains(&area)
            && let Tag::IntArray(coords) = area
            && let Ok(at) = coords.as_slice().try_into()
        {
            schedule_reset(game, at);
        }
    }
    if !next.is_empty() {
        data.insert(key, Tag::List(next));
    }
}
