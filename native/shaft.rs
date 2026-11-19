use horizon_core::geometry::{Direction, Vec3};
use horizon_core::position::BlockPos;
use horizon_world::chunk::BlockState;
use horizon_world::fluid::{FluidKind, FluidState};
use horizon_world::level::{PlaceContext, PlacementContext};
use horizon_world::registry::BlockStateId;

use super::create_cogwheel::direction_axis;
use super::create_cogwheel::{
    CASED_ANDESITE_COG, CASED_ANDESITE_LARGE_COG, CASED_COG, CASED_LARGE_COG, encased_size,
};
use super::create_machines::{COG, LARGE_COG, SHAFT};
use super::{Game, GameLevel};

const POWERED_SHAFT: &str = "create:powered_shaft";
pub(super) const VERTICAL_GEARBOX: &str = "create:vertical_gearbox";
const PLACEMENT_ASSIST_RANGE: i32 = 12;

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    let block = level.native_state_block(state)?;
    match block {
        "create:gearbox" if context.item == VERTICAL_GEARBOX => {
            return Some(place_vertical_gearbox(level, state, context));
        }
        GIRDER => return Some(place_girder(level, state, context.face, fluid)),
        SHAFT | "create:clutch" | "create:gearshift" => {}
        _ => return None,
    }
    let preferred = super::create_hand_crank::preferred_direction(level, context.pos);
    let direction = match preferred {
        Some(_) if context.sneaking => context.face,
        Some(direction) => direction,
        None => context.nearest_looking_direction(),
    };
    let placed = level.native_state_with_property(state, "axis", direction_axis(direction));
    if block != SHAFT {
        return Some(placed);
    }
    let wet = if fluid.kind() == FluidKind::Water {
        "true"
    } else {
        "false"
    };
    Some(placed.and_then(|state| level.native_state_with_property(state, "waterlogged", wet)))
}

fn place_vertical_gearbox(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    let horizontal = [Direction::North, Direction::South, Direction::West, Direction::East];
    let preferred = super::create_hand_crank::preferred_in_directions(level, context.pos, horizontal);
    let axis = match preferred {
        Some(Direction::East | Direction::West) => "z",
        Some(_) => "x",
        None if ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32) & 1 != 0 => "z",
        None => "x",
    };
    level.native_state_with_property(state, "axis", axis)
}

pub(super) fn gearbox_item(game: &Game<'_>, state: BlockStateId) -> &'static str {
    match game.native_block_state_property(state, "axis") {
        Some("x" | "z") => VERTICAL_GEARBOX,
        _ => "create:gearbox",
    }
}

pub(super) fn redirect_placement(game: &mut Game<'_>, context: &mut PlaceContext) {
    if context.sneaking || !game.may_build() {
        return;
    }
    if context.item == GIRDER {
        redirect_girder(game, context);
        return;
    }
    if !matches!(context.item.as_str(), SHAFT | COG | LARGE_COG) {
        return;
    }
    let origin = context.clicked_pos;
    let pos = [origin.x, origin.y, origin.z];
    if !matches!(game.native_block(pos).as_str(), SHAFT | POWERED_SHAFT) {
        return;
    }
    let Some(axis) = game.native_block_property(pos, "axis") else {
        return;
    };
    let (axis_index, negative, positive) = match axis.as_str() {
        "x" => (0, Direction::West, Direction::East),
        "y" => (1, Direction::Down, Direction::Up),
        "z" => (2, Direction::North, Direction::South),
        _ => return,
    };
    let center = f64::from(pos[axis_index]) + 0.5;
    let directions = if context.hit.components()[axis_index] > center {
        [positive, negative]
    } else {
        [negative, positive]
    };
    let placement = extension_target(game, context, directions, |state, _| {
        matches!(state.name.as_str(), SHAFT | POWERED_SHAFT | COG | LARGE_COG)
            && state.properties.get("axis") == Some(&axis)
    });
    let Some((last, direction)) = placement else {
        return;
    };
    use_extension(context, last, direction);
    match axis.as_str() {
        "x" => {
            context.yaw = 90.0;
            context.pitch = 0.0;
        }
        "y" => {
            context.pitch = 90.0;
        }
        _ => {
            context.yaw = 0.0;
            context.pitch = 0.0;
        }
    }
}

fn extension_target(
    game: &mut Game<'_>,
    context: &PlaceContext,
    directions: impl IntoIterator<Item = Direction>,
    continues: impl Fn(&BlockState, Direction) -> bool,
) -> Option<(BlockPos, Direction)> {
    let origin = context.clicked_pos;
    game.with_level(|b, level, ticks| {
        for direction in directions {
            let [dx, dy, dz] = direction.normal();
            for distance in 1..=PLACEMENT_ASSIST_RANGE {
                let next = origin.offset(dx * distance, dy * distance, dz * distance);
                let block = level.world.block(next.x, next.y, next.z);
                if level
                    .registry
                    .state(block)
                    .is_some_and(|state| continues(state, direction))
                {
                    continue;
                }
                let checked = PlaceContext {
                    clicked_pos: next,
                    face: direction,
                    ..context.clone()
                };
                if b.directional_can_place(level, ticks, &checked) {
                    return Some((next.offset(-dx, -dy, -dz), direction));
                }
                break;
            }
        }
        None
    })
}

fn use_extension(context: &mut PlaceContext, last: BlockPos, direction: Direction) {
    context.clicked_pos = last;
    context.face = direction;
    context.hit = Vec3::new(
        f64::from(last.x) + 0.5,
        f64::from(last.y) + 0.5,
        f64::from(last.z) + 0.5,
    );
}

fn continues_girder(state: &BlockState, direction: Direction) -> bool {
    let axis = direction_axis(direction);
    let property = |key| state.properties.get(key).map(String::as_str);
    match state.name.as_str() {
        GIRDER => {
            let x = property("x") == Some("true");
            let z = property("z") == Some("true");
            match (x, z) {
                (true, true) => true,
                (true, false) => axis == "x",
                (false, true) => axis == "z",
                (false, false) => axis == "y",
            }
        }
        GIRDER_SHAFT => axis != "y" && property("axis") != Some(axis),
        _ => false,
    }
}

fn redirect_girder(game: &mut Game<'_>, context: &mut PlaceContext) {
    let origin = context.clicked_pos;
    let [x, y, z] = [origin.x, origin.y, origin.z];
    if game.native_block([x, y, z]) != GIRDER {
        return;
    }
    let mut directions = game.with_level(|_, level, _| {
        let state = level.world.block(x, y, z);
        level.registry.state(state).map_or_else(Vec::new, |state| {
            Direction::ALL
                .into_iter()
                .filter(|&direction| continues_girder(state, direction))
                .collect()
        })
    });
    let center = [x, y, z].map(|v| f64::from(v) + 0.5);
    let hit = context.hit.components();
    let score = |direction: Direction| {
        direction
            .normal()
            .into_iter()
            .enumerate()
            .map(|(axis, component)| (hit[axis] - center[axis]) * f64::from(component))
            .sum::<f64>()
    };
    directions.sort_by(|a, b| score(*b).total_cmp(&score(*a)));
    if let Some((last, direction)) = extension_target(game, context, directions, continues_girder) {
        use_extension(context, last, direction);
    }
}

pub(super) const GIRDER: &str = "create:metal_girder";
pub(super) const GIRDER_SHAFT: &str = "create:metal_girder_encased_shaft";

pub(super) fn update_girder_shape(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    direction: Direction,
    neighbor: BlockStateId,
) -> Option<BlockStateId> {
    let center = level.registry.state(state)?;
    let plain = center.name == GIRDER;
    if !plain && center.name != GIRDER_SHAFT {
        return None;
    }
    let axis = center.properties.get("axis")?.as_str();
    let changed_axis = direction_axis(direction);
    let property = match direction {
        Direction::Up => "top",
        Direction::Down => "bottom",
        _ if plain => changed_axis,
        _ => return None,
    };
    let was_connected = center
        .properties
        .get(property)
        .is_some_and(|value| value == "true");
    let adjacent = level.registry.state(neighbor)?;
    let connected = if changed_axis == "y" {
        if plain && axis == "y" || matches!(adjacent.name.as_str(), GIRDER | GIRDER_SHAFT) {
            true
        } else {
            was_connected && !level.facts.get(neighbor).outline.is_empty()
        }
    } else if changed_axis == axis {
        true
    } else {
        let [dx, dy, dz] = direction.opposite().normal();
        let other = level.world.block(pos.x + dx, pos.y + dy, pos.z + dz);
        [neighbor, other].into_iter().any(|side| {
            let facts = level.facts.get(side);
            level
                .registry
                .state(side)
                .is_some_and(|block| continues_girder(block, direction))
                || was_connected && facts.legacy_solid && facts.full_collision
        })
    };
    if connected == was_connected {
        return None;
    }
    level.native_state_with_property(state, property, if connected { "true" } else { "false" })
}

fn single_girder_beam(state: &BlockState) -> bool {
    let shape = |name| {
        state
            .properties
            .get(name)
            .is_some_and(|value| value == "true")
    };
    shape("x") != shape("z")
}

fn toggle_girder_cap(
    level: &GameLevel<'_>,
    state: BlockStateId,
    cap: &str,
) -> Option<BlockStateId> {
    let prior = level.registry.state(state)?;
    let property = |name| prior.properties.get(name).map(String::as_str);
    let closing = property(cap)? == "true";
    let other = if cap == "top" { "bottom" } else { "top" };
    let changed =
        level.native_state_with_property(state, cap, if closing { "false" } else { "true" })?;
    if property("axis") == Some("y") && (closing || property(other) != Some("true")) {
        let axis = if property("x") == Some("true") {
            "x"
        } else {
            "z"
        };
        return level.native_state_with_property(changed, "axis", axis);
    }
    Some(changed)
}

fn girder_wrench_direction(game: &Game<'_>, pos: [i32; 3], hit_y: f64) -> Option<(i32, bool)> {
    let [x, y, z] = pos;
    let registry = game.pack.assets.registry;
    let center = registry.state(game.world.block(x, y, z))?;
    if center.name != GIRDER || !single_girder_beam(center) {
        return None;
    }
    let directions = if hit_y > f64::from(y) + 0.5 {
        [1, -1]
    } else {
        [-1, 1]
    };
    for dy in directions {
        let neighbor = registry.state(game.world.block(x, y + dy, z))?;
        if neighbor.name != GIRDER {
            return Some((dy, false));
        }
        if single_girder_beam(neighbor) {
            return Some((dy, true));
        }
    }
    None
}

pub(super) fn wrench_girder(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some((_, hit)) = game.native_view_hit() else {
        return false;
    };
    if [hit.block_x, hit.block_y, hit.block_z] != pos {
        return false;
    }
    let Some((dy, paired)) = girder_wrench_direction(game, pos, hit.y) else {
        return false;
    };
    let [x, y, z] = pos;
    let (own_cap, other_cap) = if dy > 0 {
        ("top", "bottom")
    } else {
        ("bottom", "top")
    };
    let at = [x, y + dy, z];
    let updates = game.with_level(|_, level, _| {
        let center = toggle_girder_cap(level, level.world.block(x, y, z), own_cap)?;
        let neighbor = if paired {
            Some((
                at,
                toggle_girder_cap(level, level.world.block(x, y + dy, z), other_cap)?,
            ))
        } else {
            None
        };
        Some((center, neighbor))
    });
    let Some((center, paired)) = updates else {
        return false;
    };
    use horizon_world::level::flags::{UPDATE_CLIENTS, UPDATE_KNOWN_SHAPE};
    let flags = UPDATE_CLIENTS | UPDATE_KNOWN_SHAPE;
    if !game.native_set_block(game.native_dimension(), pos, center, flags) {
        return false;
    }
    if let Some((at, state)) = paired {
        game.native_set_block(game.native_dimension(), at, state, flags);
    }
    true
}

pub(super) fn render_girder_wrench(
    game: &Game<'_>,
    primitives: &mut crate::world_primitives::WorldPrimitives,
) {
    if game.native_sneaking()
        || !game
            .stack_in(game.selected)
            .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
    {
        return;
    }
    let Some(hit) = game.pick() else {
        return;
    };
    let Some((dy, paired)) = girder_wrench_direction(game, hit.pos, hit.point[1]) else {
        return;
    };
    let [x, y, z] = hit.pos.map(f64::from);
    let sign = f64::from(dy);
    let inner_y = 0.5 + 0.2 * sign;
    let outer_y = 0.5 + (0.4 + if paired { 0.4 } else { 0.1 }) * sign;
    let low_y = inner_y.min(outer_y);
    let high_y = inner_y.max(outer_y);
    let low = [x + 0.2, y + low_y, z + 0.2];
    let high = [x + 0.8, y + high_y, z + 0.8];
    const WIDTH: f64 = 1.0 / 32.0;
    const COLOR: u32 = 0xff7f7f7f;
    for axis in 0..3 {
        let a = (axis + 1) % 3;
        let b = (axis + 2) % 3;
        for first in [low[a], high[a]] {
            for second in [low[b], high[b]] {
                let mut start = low;
                let mut finish = high;
                start[a] = first - WIDTH / 2.0;
                finish[a] = first + WIDTH / 2.0;
                start[b] = second - WIDTH / 2.0;
                finish[b] = second + WIDTH / 2.0;
                primitives.filled_box(start, finish, COLOR);
            }
        }
    }
    static TRACE: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    if *TRACE.get_or_init(|| std::env::var_os("CREATE_GIRDER_WRENCH_OUTLINE").is_some()) {
        let side = if dy > 0 { "up" } else { "down" };
        println!(
            "CREATE_GIRDER_WRENCH_OUTLINE {side},{paired},0.20000,{low_y:.5},0.20000,0.80000,{high_y:.5},0.80000,{WIDTH:.5},127"
        );
    }
}

fn place_girder(
    level: &GameLevel<'_>,
    state: BlockStateId,
    face: Direction,
    fluid: FluidState,
) -> Option<BlockStateId> {
    let axis = direction_axis(face);
    let flag = |enabled: bool| if enabled { "true" } else { "false" };
    [
        ("axis", axis),
        ("x", flag(axis == "x")),
        ("z", flag(axis == "z")),
        ("top", flag(axis == "y")),
        ("bottom", flag(axis == "y")),
        ("waterlogged", flag(fluid.kind() == FluidKind::Water)),
    ]
    .into_iter()
    .try_fold(state, |state, (key, value)| {
        level.native_state_with_property(state, key, value)
    })
}

fn change_girder(game: &mut Game<'_>, pos: [i32; 3], shaft_axis: &str, inserting: bool) -> bool {
    let block = if inserting { GIRDER_SHAFT } else { GIRDER };
    let Some(default) = game.native_default_state(block) else {
        return false;
    };
    let values =
        ["top", "bottom", "waterlogged"].map(|key| (key, game.native_block_property(pos, key)));
    let state = game.with_level(|_, level, _| {
        let state = values
            .into_iter()
            .try_fold(default, |state, (key, value)| {
                level.native_state_with_property(state, key, value.as_deref()?)
            })?;
        if inserting {
            return level.native_state_with_property(state, "axis", shaft_axis);
        }
        let beam = if shaft_axis == "z" { "x" } else { "z" };
        let state = level.native_state_with_property(state, "axis", beam)?;
        level.native_state_with_property(state, beam, "true")
    });
    state.is_some_and(|state| {
        game.native_set_block(
            game.native_dimension(),
            pos,
            state,
            horizon_world::level::flags::UPDATE_ALL,
        )
    })
}

pub(super) fn insert_into_girder(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    held: &crate::items::ItemStack,
) -> bool {
    if !game.native_authoritative()
        || !game.may_build()
        || game.native_sneaking()
        || held.item.as_ref() != SHAFT
        || game.native_block(pos) != GIRDER
    {
        return false;
    }
    let shaft_axis =
        if face[2] != 0 || game.native_block_property(pos, "x").as_deref() == Some("true") {
            "z"
        } else {
            "x"
        };
    if !change_girder(game, pos, shaft_axis, true) {
        return false;
    }
    game.consume_held();
    game.guest_inventory_resend |= game.lan_acting.is_some();
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    game.native_play_sound_in_place("minecraft:block.netherite_block.hit", at, 4, 0.5, 1.25);
    true
}

pub(super) fn remove_from_girder(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some(axis) = game.native_block_property(pos, "axis") else {
        return false;
    };
    if !game.native_authoritative() || !change_girder(game, pos, &axis, false) {
        return false;
    }
    if !game.creative {
        if let Some(uncollected) = game.give(crate::items::ItemStack::new(SHAFT, 1)) {
            game.pop_resource(pos, uncollected);
        }
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    true
}

const ANDESITE_ENCASED_SHAFT: &str = "create:andesite_encased_shaft";
const BRASS_ENCASED_SHAFT: &str = "create:brass_encased_shaft";

fn change_casing(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> bool {
    let Some(axis) = game.native_block_property(pos, "axis") else {
        return false;
    };
    let Some(default) = game.native_default_state(block) else {
        return false;
    };
    let replacement = game.with_level(|_, level, _| {
        let state = level.native_state_with_property(default, "axis", &axis)?;
        if encased_size(block).is_none() {
            return Some(state);
        }
        let ends = match axis.as_str() {
            "x" => [Direction::West, Direction::East],
            "y" => [Direction::Down, Direction::Up],
            "z" => [Direction::North, Direction::South],
            _ => return None,
        };
        let at = BlockPos::new(pos[0], pos[1], pos[2]);
        ends.into_iter()
            .zip(["bottom_shaft", "top_shaft"])
            .try_fold(state, |state, (direction, key)| {
                let attached =
                    super::create_hand_crank::preferred_in_directions(level, at, [direction])
                        .is_some();
                level.native_state_with_property(
                    state,
                    key,
                    if attached { "true" } else { "false" },
                )
            })
    });
    let Some(replacement) = replacement else {
        return false;
    };
    game.native_set_block(
        game.native_dimension(),
        pos,
        replacement,
        horizon_world::level::flags::UPDATE_ALL,
    )
}

pub(super) fn encase(game: &mut Game<'_>, pos: [i32; 3], held: &crate::items::ItemStack) -> bool {
    if !game.native_authoritative() || !game.may_build() || game.native_sneaking() {
        return false;
    }
    let block = game.native_block(pos);
    let variant = match (block.as_str(), held.item.as_ref()) {
        (SHAFT, "create:andesite_casing") => ANDESITE_ENCASED_SHAFT,
        (SHAFT, "create:brass_casing") => BRASS_ENCASED_SHAFT,
        (COG, "create:andesite_casing") => CASED_ANDESITE_COG,
        (COG, "create:brass_casing") => CASED_COG,
        (LARGE_COG, "create:andesite_casing") => CASED_ANDESITE_LARGE_COG,
        (LARGE_COG, "create:brass_casing") => CASED_LARGE_COG,
        _ => return false,
    };
    if !change_casing(game, pos, variant) {
        return false;
    }
    // Encasing preserves the casing stack. The client may have predicted
    // placing an ordinary casing against the shaft, which consumes one.
    game.guest_inventory_resend |= game.lan_acting.is_some();
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    game.native_play_sound_in_place("minecraft:block.stone.place", at, 4, 1.0, 0.8);
    true
}

pub(super) fn uncase(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> bool {
    let bare = match block {
        ANDESITE_ENCASED_SHAFT | BRASS_ENCASED_SHAFT => SHAFT,
        _ if encased_size(block) == Some(false) => COG,
        _ if encased_size(block) == Some(true) => LARGE_COG,
        _ => return false,
    };
    if game.native_authoritative() {
        let state = game.world.block(pos[0], pos[1], pos[2]);
        game.level_events
            .push(horizon_world::level::LevelEvent::LevelEvent {
                id: 2001,
                pos: BlockPos::new(pos[0], pos[1], pos[2]),
                data: state.0 as i32,
            });
        change_casing(game, pos, bare);
    }
    true
}
