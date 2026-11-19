use std::{
    cell::RefCell,
    collections::{HashMap, HashSet, VecDeque},
};

use horizon_core::{
    geometry::Direction,
    position::BlockPos,
    random::{LegacyRandom, RandomSource},
};
use horizon_world::level::LevelAccess;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use super::{Game, GameLevel, Ticks};

const ITEM: &str = "create:handheld_worldshaper";
const SELECTED: &str = "create:shaper_block_used";
const BLOCK_DATA: &str = "create:shaper_block_data";

pub(super) fn register(types: &mut Vec<String>) {
    types.extend([
        SELECTED.into(),
        BLOCK_DATA.into(),
        "create:shaper_brush_params".into(),
        "create:shaper_brush".into(),
        "create:shaper_tool".into(),
        "create:shaper_placement_options".into(),
        "create:placement_pattern".into(),
    ]);
}

pub(super) fn claim_selection(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    let Some(stack) = game
        .stack_in(game.selected)
        .filter(|s| s.item.as_ref() == ITEM)
        .cloned()
    else {
        return false;
    };
    if !game.native_sneaking() {
        select(game, stack, pos);
    }
    // ZapperItem.canAttackBlock also suppresses breaking when the block is unchanged or rejected.
    true
}

fn select(game: &mut Game<'_>, mut stack: crate::items::ItemStack, pos: [i32; 3]) {
    let [x, y, z] = pos;
    let raw = game.world.block(x, y, z);
    let Some(state) = game.pack.assets.registry.state(raw) else {
        return;
    };
    let name = state.name.as_str();
    if name == "minecraft:air"
        || game.world.block_entities.get(&(x, y, z)).is_some()
        || (!matches!(name, "minecraft:farmland" | "minecraft:dirt_path")
            && game.native_max_stack_size(name).is_none())
    {
        return;
    }
    let properties = &state.properties;
    if properties.contains_key("attached")
        || properties.contains_key("hanging")
        || matches!(
            properties.get("half").map(String::as_str),
            Some("lower" | "upper")
        )
        || matches!(
            properties.get("part").map(String::as_str),
            Some("head" | "foot")
        )
    {
        return;
    }
    let mut saved = Compound::from([("Name".into(), Tag::String(name.into()))]);
    if !properties.is_empty() {
        let stairs = name.ends_with("_stairs");
        let encoded = properties
            .iter()
            .map(|(key, value)| {
                let value = match key.as_str() {
                    "persistent" => "true",
                    "waterlogged" => "false",
                    "shape" if stairs => "straight",
                    _ => value.as_str(),
                };
                (key.as_str().into(), Tag::String(value.into()))
            })
            .collect();
        saved.insert("Properties".into(), Tag::Compound(encoded));
    }
    let selection = Tag::Compound(saved);
    if game
        .native_component(&stack, SELECTED)
        .is_ok_and(|prior| prior == Some(&selection))
        && game
            .native_component(&stack, BLOCK_DATA)
            .is_ok_and(|prior| prior.is_none())
    {
        return;
    }
    if game
        .native_set_component(&mut stack, SELECTED, selection)
        .is_err()
    {
        return;
    }
    stack.data_mut().set_other(BLOCK_DATA, None);
    *game.stack_in_mut(game.selected) = Some(stack);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    if let Some(player) = &game.player {
        let feet = player.position.components().map(|p| p.floor() + 0.5);
        game.native_play_sound_in_place("create:confirm", feet, 4, 1.0, 1.0);
    }
}

fn setting(game: &Game<'_>, stack: &crate::items::ItemStack, key: &str, fallback: &str) -> String {
    match game.native_component(stack, key) {
        Ok(Some(Tag::String(value))) => value.to_string_lossy().to_string(),
        _ => fallback.to_owned(),
    }
}

#[derive(Clone, Copy, Default)]
pub(super) enum Brush {
    #[default]
    Cuboid,
    Sphere,
    Cylinder,
    Surface,
    Cluster,
}

impl Brush {
    pub(super) const ALL: [Self; 5] = [
        Self::Cuboid,
        Self::Sphere,
        Self::Cylinder,
        Self::Surface,
        Self::Cluster,
    ];

    pub(super) fn name(self) -> &'static str {
        match self {
            Self::Cuboid => "cuboid",
            Self::Sphere => "sphere",
            Self::Cylinder => "cylinder",
            Self::Surface => "surface",
            Self::Cluster => "cluster",
        }
    }

    pub(super) fn index(self) -> u8 {
        self as u8
    }

    pub(super) fn count(self) -> usize {
        match self {
            Self::Cuboid => 3,
            Self::Sphere | Self::Surface | Self::Cluster => 1,
            Self::Cylinder => 2,
        }
    }

    pub(super) fn bounds(self, parameter: usize) -> (i32, i32) {
        match self {
            Self::Cuboid => (1, 32),
            Self::Sphere => (0, 10),
            Self::Cylinder => (i32::from(parameter != 0), 8),
            Self::Surface | Self::Cluster if parameter == 0 => (1, 10),
            Self::Surface | Self::Cluster => (0, 1),
        }
    }

    pub(super) fn clamp(self, parameters: [i32; 3]) -> [i32; 3] {
        std::array::from_fn(|index| {
            let (min, max) = self.bounds(index);
            parameters[index].clamp(min, max)
        })
    }

    pub(super) fn connected(self) -> bool {
        matches!(self, Self::Surface | Self::Cluster)
    }

    pub(super) fn tools(self) -> &'static [usize] {
        match self {
            Self::Surface => &[4, 2, 3],
            Self::Cluster => &[2, 3],
            _ => &[0, 1, 2, 3, 4, 5],
        }
    }

    fn offset(self, size: [i32; 3], axis: usize, sign: i32, attached: bool) -> i32 {
        let negative = sign < 0;
        match self {
            Self::Cuboid => {
                let extra = if attached {
                    if negative { 2 } else { 1 }
                } else {
                    0
                };
                (size[axis] + extra) / 2
            }
            Self::Cylinder if axis == 1 => {
                let extra = match (attached, negative) {
                    (true, true) => 1,
                    (true, false) => 2,
                    (false, true) => 0,
                    (false, false) => -1,
                };
                (size[1] + extra) / 2
            }
            Self::Sphere | Self::Cylinder => size[0] + i32::from(attached),
            Self::Surface | Self::Cluster => 0,
        }
    }

    fn cells(self, size: [i32; 3]) -> Vec<[i32; 3]> {
        let mut cells = Vec::new();
        match self {
            Self::Cuboid => {
                let low = size.map(|n| (n - 1) / -2);
                let high = size.map(|n| n / 2);
                for z in low[2]..=high[2] {
                    for y in low[1]..=high[1] {
                        for x in low[0]..=high[0] {
                            cells.push([x, y, z]);
                        }
                    }
                }
            }
            Self::Sphere => {
                let radius = size[0];
                let limit = f64::from(radius as f32 + 0.5).powi(2);
                for z in -radius..=radius {
                    for y in -radius..=radius {
                        for x in -radius..=radius {
                            if f64::from(x * x + y * y + z * z) < limit {
                                cells.push([x, y, z]);
                            }
                        }
                    }
                }
            }
            Self::Cylinder => {
                let [radius, height, _] = size;
                let limit = f64::from(radius as f32 + 0.42).powi(2);
                for layer in 0..height {
                    for z in -radius..=radius {
                        for x in -radius..=radius {
                            if f64::from(x * x + z * z) < limit {
                                cells.push([x, layer - height / 2, z]);
                            }
                        }
                    }
                }
            }
            Self::Surface | Self::Cluster => {}
        }
        cells
    }

    fn connected_cells(
        self,
        level: &GameLevel<'_>,
        target: BlockPos,
        face: Direction,
        size: [i32; 3],
        overlay: bool,
    ) -> Vec<BlockPos> {
        let [range, diagonals, fuzzy] = size;
        let surface = matches!(self, Self::Surface);
        let [fx, fy, fz] = face.normal();
        let start = if overlay {
            target.offset(fx, fy, fz)
        } else {
            target
        };
        let behaviours = level.behaviours;
        let original = &level.facts.get(level.block_state(target)).name;
        let leaves = level.items.block_tags.get("minecraft:leaves");
        let mut steps = Vec::new();
        for x in -1_i32..=1 {
            for y in -1_i32..=1 {
                for z in -1_i32..=1 {
                    if (diagonals == 0 || x.abs() + y.abs() + z.abs() < 2)
                        && (!surface || x * fx + y * fy + z * fz == 0)
                    {
                        steps.push([x, y, z]);
                    }
                }
            }
        }
        let mut frontier = VecDeque::from([start]);
        let mut visited = HashSet::new();
        let mut affected = Vec::new();
        while let Some(at) = frontier.pop_front() {
            let distance =
                (at.x - start.x).pow(2) + (at.y - start.y).pow(2) + (at.z - start.z).pow(2);
            if distance >= range * range || !visited.insert(at) {
                continue;
            }
            let state = level.block_state(at);
            if overlay {
                let backing = level.block_state(at.offset(-fx, -fy, -fz));
                if !behaviours.is_replaceable(state)
                    || behaviours.is_replaceable(backing)
                    || (fuzzy != 0 && level.facts.get(backing).name != *original)
                {
                    continue;
                }
            } else {
                let facts = behaviours.facts(state);
                if facts.hardness == -1.0
                    || behaviours.is_replaceable(state)
                    || (fuzzy != 0 && level.facts.get(state).name != *original)
                {
                    continue;
                }
                if surface {
                    let cover = level.block_state(at.offset(fx, fy, fz));
                    let name = &level.facts.get(cover).name;
                    let full =
                        behaviours.shape_info(cover).full_faces & (1 << face.opposite() as u8) != 0;
                    if full && !leaves.is_some_and(|tag| tag.contains(name.as_ref())) {
                        continue;
                    }
                }
            }
            affected.push(at);
            for &[x, y, z] in &steps {
                frontier.push_back(at.offset(x, y, z));
            }
        }
        affected
    }
}

pub(super) const PATTERNS: [&str; 6] = [
    "solid",
    "checkered",
    "inversecheckered",
    "chance25",
    "chance50",
    "chance75",
];

thread_local! {
    // Replay the Java oracle's pattern draws independently of unrelated world ticks.
    static PATTERN_TEST_RANDOM: RefCell<Option<LegacyRandom>> = RefCell::new(
        std::env::var("CREATE_WORLDSHAPER_PATTERN_TRACE_SEED").ok()
            .and_then(|seed| seed.parse().ok())
            .map(LegacyRandom::new),
    );
}

pub(super) const TOOLS: [&str; 6] = ["fill", "place", "replace", "clear", "overlay", "flatten"];

fn selected_state(game: &Game<'_>, stack: &crate::items::ItemStack) -> Option<BlockStateId> {
    let saved = game.native_component(stack, SELECTED).ok()??;
    let name @ Tag::String(_) = saved.get("Name")? else {
        return None;
    };
    let mut state = Compound::from([("id".into(), name.clone())]);
    if let Some(properties @ Tag::Compound(_)) = saved.get("Properties") {
        state.insert("properties".into(), properties.clone());
    }
    game.pack
        .assets
        .registry
        .saved_state_id(&Tag::Compound(state))
}

pub(super) fn use_tool(
    game: &mut Game<'_>,
    stack: &crate::items::ItemStack,
    target: Option<([i32; 3], [i32; 3])>,
) -> bool {
    use horizon_world::level::flags;

    if stack.item.as_ref() != ITEM || !game.native_authoritative() || game.native_sneaking() {
        return false;
    }
    let Ok(Some(Tag::IntArray(params))) =
        game.native_component(stack, "create:shaper_brush_params")
    else {
        return false;
    };
    let Ok(size) = <[i32; 3]>::try_from(params.as_slice()) else {
        return false;
    };
    let tool = setting(game, stack, "create:shaper_tool", "fill");
    let brush_name = setting(game, stack, "create:shaper_brush", "cuboid");
    let Some(brush) = Brush::ALL
        .into_iter()
        .find(|brush| brush.name() == brush_name)
    else {
        return false;
    };
    let pattern = setting(game, stack, "create:placement_pattern", "solid");
    if size[..brush.count()] != brush.clamp(size)[..brush.count()]
        || !PATTERNS.contains(&pattern.as_str())
        || !TOOLS.contains(&tool.as_str())
    {
        return false;
    }
    let painted = if matches!(tool.as_str(), "clear" | "flatten") {
        game.pack.assets.registry.default_state("minecraft:air")
    } else {
        if game
            .native_component(stack, BLOCK_DATA)
            .is_ok_and(|data| data.is_some())
        {
            return false;
        }
        selected_state(game, stack)
    };
    let Some(painted) = painted else {
        return false;
    };
    let ray_hit = game.eye_position().and_then(|eye| {
        let direction = super::view_vector(game.yaw, game.pitch);
        game.clip_ray(eye, direction, 128.0)
    });
    let target = target.or_else(|| ray_hit.as_ref().map(|hit| (hit.pos, hit.face)));
    let Some((mut center, face)) = target else {
        game.add_cooldown(stack.item.clone(), 2);
        return true;
    };
    let matches_target = |hit: &super::Hit| hit.pos == center && hit.face == face;
    let impact = ray_hit
        .filter(matches_target)
        .or_else(|| game.forced_hit.filter(matches_target))
        .map(|hit| hit.point);
    let Some(axis) = face.iter().position(|value| *value != 0) else {
        return false;
    };
    match setting(game, stack, "create:shaper_placement_options", "merged").as_str() {
        "merged" => {}
        "attached" => center[axis] += face[axis] * brush.offset(size, axis, face[axis], true),
        "inserted" => center[axis] -= face[axis] * brush.offset(size, axis, face[axis], false),
        _ => return false,
    }
    game.with_level(|behaviour, level, ticks| {
        let center = BlockPos::new(center[0], center[1], center[2]);
        let mut affected: Vec<_> = if brush.connected() {
            let direction = Direction::ALL
                .into_iter()
                .find(|direction| direction.normal() == face);
            let Some(direction) = direction else { return };
            brush.connected_cells(level, center, direction, size, tool == "overlay")
        } else {
            brush
                .cells(size)
                .into_iter()
                .map(|[x, y, z]| center.offset(x, y, z))
                .collect()
        };
        match pattern.as_str() {
            "checkered" | "inversecheckered" => {
                affected.retain(|at| {
                    let even = (at.x ^ at.y ^ at.z) & 1 == 0;
                    even == (pattern == "inversecheckered")
                });
            }
            "chance25" | "chance50" | "chance75" => {
                PATTERN_TEST_RANDOM.with_borrow_mut(|seed| {
                    let random = seed.as_mut().unwrap_or_else(|| level.random());
                    affected.retain(|_| match pattern.as_str() {
                        "chance25" => !(random.next_boolean() || random.next_boolean()),
                        "chance50" => !random.next_boolean(),
                        _ => !(random.next_boolean() && random.next_boolean()),
                    });
                    if let Some(seed) = seed.as_ref() {
                        eprintln!(
                            "Worldshaper pattern RNG fingerprint: {}",
                            seed.clone().next_long()
                        );
                    }
                });
            }
            _ => {}
        }
        if tool == "flatten" {
            flatten(level, ticks, &affected, axis, face[axis]);
            return;
        }
        for mut at in affected {
            let prior = level.block_state(at);
            let replaceable = behaviour.is_replaceable(prior);
            let apply = match tool.as_str() {
                "fill" => replaceable,
                "replace" => !replaceable,
                "overlay" if !brush.connected() => {
                    at.y += 1;
                    !replaceable
                        && prior != painted
                        && behaviour.is_replaceable(level.block_state(at))
                }
                _ => true,
            };
            if apply {
                behaviour.set_block(level, ticks, at, painted, flags::UPDATE_ALL);
            }
        }
    });
    let _ = game.process_level_events();
    game.add_cooldown(stack.item.clone(), 2);
    if let Some(point) = impact {
        super::create_worldshaper_effect::shot(game, point);
    }
    true
}

fn flatten(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    cells: &[BlockPos],
    axis: usize,
    sign: i32,
) {
    use horizon_world::{fluid::FluidKind, level::flags};

    const KERNEL: [[f32; 5]; 5] = [
        [0.003765, 0.015019, 0.023792, 0.015019, 0.003765],
        [0.015019, 0.059912, 0.094907, 0.059912, 0.015019],
        [0.023792, 0.094907, 0.150342, 0.094907, 0.023792],
        [0.015019, 0.059912, 0.094907, 0.059912, 0.015019],
        [0.003765, 0.015019, 0.023792, 0.015019, 0.003765],
    ];
    let plane = |at: BlockPos| match axis {
        0 => [at.z, at.y],
        1 => [at.x, at.z],
        _ => [at.x, at.y],
    };
    let shift = |at: BlockPos, distance: i32| {
        let mut step = [0; 3];
        step[axis] = distance * sign;
        at.offset(step[0], step[1], step[2])
    };
    let height = |at: BlockPos| [at.x, at.y, at.z][axis];
    let behaviours = level.behaviours;
    let mut heights = HashMap::new();
    let mut surfaces = Vec::new();
    let mut low = i32::MAX;
    let mut high = i32::MIN;
    for &at in cells {
        let key = plane(at);
        let above = shift(at, 1);
        if behaviours.is_replaceable(level.block_state(at)) {
            heights.entry(key).or_insert(i32::MIN);
        } else if !behaviours.is_replaceable(level.block_state(above)) {
            let stored = heights.entry(key).or_insert(i32::MIN);
            if *stored == i32::MIN {
                *stored = i32::MAX;
            }
        } else {
            surfaces.push(above);
            let value = height(above);
            let stored = heights.entry(key).or_insert(i32::MIN);
            if matches!(*stored, i32::MIN | i32::MAX) || *stored * sign < value * sign {
                *stored = value;
                low = low.min(value);
                high = high.max(value);
            }
        }
    }
    for value in heights.values_mut() {
        *value = match (*value, sign > 0) {
            (i32::MIN, true) => low - 2,
            (i32::MIN, false) => high + 2,
            (i32::MAX, true) => high + 2,
            (i32::MAX, false) => low - 2,
            (height, _) => height,
        };
    }
    for mut at in surfaces {
        let [a, b] = plane(at);
        let pivot = heights[&[a, b]];
        let mut sum = 0.0;
        for (i, row) in KERNEL.into_iter().enumerate() {
            for (j, weight) in row.into_iter().enumerate() {
                let key = [a + i as i32 - 2, b + j as i32 - 2];
                sum += weight * *heights.get(&key).unwrap_or(&pivot) as f32;
            }
        }
        let difference = ((sum + 0.5).floor() as i32 - height(at)) * sign;
        let state = level.block_state(at);
        if difference < 0 {
            let remaining = behaviours.legacy_block(behaviours.fluid(state));
            for _ in 0..(-difference).min(1001) {
                let below = shift(at, -1);
                behaviours.set_block(level, ticks, below, state, flags::UPDATE_ALL);
                behaviours.set_block(level, ticks, at, remaining, flags::UPDATE_ALL);
                at = below;
            }
        } else if difference > 0 {
            let liquid = FluidKind::of_liquid_block(&level.facts.get(state).name).is_some();
            for _ in 0..difference.min(1001) {
                let above = shift(at, 1);
                if !liquid {
                    behaviours.set_block(level, ticks, above, state, flags::UPDATE_ALL);
                }
                let below = level.block_state(shift(at, -1));
                behaviours.set_block(level, ticks, at, below, flags::UPDATE_ALL);
                at = above;
            }
        }
    }
}
