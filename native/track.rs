use horizon_core::geometry::{Direction, Vec3, trig};
use horizon_core::position::BlockPos;
use horizon_core::random::RandomSource;
use horizon_world::attachments::AttachmentType;
use horizon_world::level::{PlacementContext, Ticks, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;
use horizon_client::actions::Action;

use super::create_machines::{int, mod_entity, offset};
use super::create_track_curve::{self, Curve, End};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel, Hand};

pub(super) const TRACK: &str = "create:track";

fn selected(yaw: f32) -> &'static str {
    let radians = -yaw * (std::f32::consts::PI / 180.0);
    let x = f64::from(trig::sin(f64::from(radians)));
    let z = f64::from(trig::cos(f64::from(radians)));
    let magnitude = (x * x + z * z).sqrt();
    let (x, z) = (x / magnitude, z / magnitude);
    let mut best = ("zo", f64::INFINITY);
    for (shape, ax, ay, az) in [
        ("none", 0.0_f64, 0.0_f64, 0.0_f64),
        ("zo", 0.0, 0.0, 1.0),
        ("xo", 1.0, 0.0, 0.0),
        ("pd", 1.0, 0.0, 1.0),
        ("nd", -1.0, 0.0, 1.0),
        ("an", 0.0, 1.0, -1.0),
        ("as", 0.0, 1.0, 1.0),
        ("ae", 1.0, 1.0, 0.0),
        ("aw", -1.0, 1.0, 0.0),
    ] {
        let length = (ax * ax + ay * ay + az * az).sqrt();
        let forward = (ax - x).powi(2) + ay * ay + (az - z).powi(2);
        let distance = if length == 0.0 {
            forward
        } else {
            forward
                .min((ax / length + x).powi(2) + (ay / length).powi(2) + (az / length + z).powi(2))
        };
        if distance <= best.1 {
            best = (shape, distance);
        }
    }
    best.0
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
) -> Option<Option<BlockStateId>> {
    let mut placed = level.registry.state(state)?.clone();
    if placed.name != TRACK {
        return None;
    }
    let p = ctx.pos;
    let at = |x, y, z| level.world.block(p.x + x, p.y + y, p.z + z);
    if level
        .registry
        .state(at(0, -1, 0))
        .is_some_and(|below| below.name == TRACK)
    {
        return Some(None);
    }
    let original = selected(ctx.yaw);
    let uphill = match original {
        "xo" => [(Direction::West, "aw"), (Direction::East, "ae")].as_slice(),
        "zo" => [(Direction::North, "an"), (Direction::South, "as")].as_slice(),
        _ => &[],
    };
    let slope = uphill.iter().find_map(|&(direction, shape)| {
        let [x, _, z] = direction.normal();
        (level.behaviours.is_face_sturdy(at(x, 0, z), Direction::Up)
            && !level
                .behaviours
                .is_face_sturdy(at(x, 1, z), Direction::Down))
        .then_some(shape)
    });
    placed
        .properties
        .insert("shape".into(), slope.unwrap_or(original).into());
    let water = level
        .registry
        .state(at(0, 0, 0))
        .is_some_and(|block| block.name == "minecraft:water");
    placed
        .properties
        .insert("waterlogged".into(), water.to_string());
    Some(level.registry.id(&placed))
}

const CONNECTING: &str = "create:track_connecting_from";

const CONNECTIONS: &str = "Connections";
const CANCEL_DROPS: &str = "CancelCurveDrops";
const EXTENDED: &str = "create:track_extend_curve";
const SPRINT_INPUT: AttachmentType<bool> = AttachmentType {
    namespace: "create",
    name: "sprint_input",
    default: || false,
    codec: None,
    copy_on_death: false,
    sync: false,
};

pub(super) fn guest_input(game: &mut Game<'_>, player: u128, flags: u8) {
    if flags & (1 << 6) != 0 {
        let _ = game
            .guest_attachments
            .entry(player)
            .or_default()
            .set(&SPRINT_INPUT, true);
    } else if let Some(data) = game.guest_attachments.get_mut(&player) {
        let _ = data.remove(&SPRINT_INPUT);
    }
}

pub(super) fn track_axis(shape: &str) -> Option<Vec3> {
    Some(match shape {
        "xo" => Vec3::new(1.0, 0.0, 0.0),
        "zo" => Vec3::new(0.0, 0.0, 1.0),
        "pd" => Vec3::new(1.0, 0.0, 1.0),
        "nd" => Vec3::new(-1.0, 0.0, 1.0),
        "an" => Vec3::new(0.0, 1.0, -1.0),
        "as" => Vec3::new(0.0, 1.0, 1.0),
        "ae" => Vec3::new(1.0, 1.0, 0.0),
        "aw" => Vec3::new(-1.0, 1.0, 0.0),
        _ => return None,
    })
}

pub(super) fn face_vector(yaw: f32) -> Vec3 {
    let angle = f64::from(yaw).to_radians();
    Vec3::new(-angle.sin(), 0.0, angle.cos())
}

fn new_end(pos: [i32; 3], shape: &str, yaw: f32) -> Option<End> {
    let choices: &[&str] = match shape {
        "cr_o" => &["zo", "xo"],
        "cr_d" => &["pd", "nd"],
        "cr_pdx" => &["xo", "pd"],
        "cr_pdz" => &["zo", "pd"],
        "cr_ndx" => &["xo", "nd"],
        "cr_ndz" => &["zo", "nd"],
        _ => &[shape],
    };
    let look = face_vector(yaw);
    let axis = choices
        .iter()
        .filter_map(|shape| track_axis(shape))
        .max_by(|a, b| {
            a.normalize()
                .dot(look)
                .abs()
                .total_cmp(&b.normalize().dot(look).abs())
        })?;
    let normal = if axis.y == 0.0 {
        Vec3::new(0.0, 1.0, 0.0)
    } else {
        Vec3::new(-axis.x, 1.0, -axis.z).normalize()
    };
    let axis = if axis.dot(look) < 0.0 {
        axis.reverse()
    } else {
        axis
    };
    Some(End { pos, axis, normal })
}

fn position(tag: &Tag) -> Option<[i32; 3]> {
    match tag {
        Tag::IntArray(values) => values.as_slice().try_into().ok(),
        Tag::List(values) => match values.as_slice() {
            [Tag::Int(x), Tag::Int(y), Tag::Int(z)] => Some([*x, *y, *z]),
            _ => None,
        },
        _ => None,
    }
}

fn vector(value: Vec3) -> Tag {
    Tag::List(
        value
            .components()
            .map(|part| Tag::Double(part.to_bits()))
            .to_vec(),
    )
}

fn read_vector(tag: &Tag) -> Option<Vec3> {
    let Tag::List(values) = tag else { return None };
    let [Tag::Double(x), Tag::Double(y), Tag::Double(z)] = values.as_slice() else {
        return None;
    };
    Some(Vec3::new(
        f64::from_bits(*x),
        f64::from_bits(*y),
        f64::from_bits(*z),
    ))
}

fn selection(stack: &ItemStack) -> Option<End> {
    let Tag::Compound(data) = stack.data()?.other(CONNECTING)? else {
        return None;
    };
    Some(End {
        pos: position(data.get(&"pos".into())?)?,
        axis: read_vector(data.get(&"axis".into())?)?,
        normal: read_vector(data.get(&"normal".into())?)?,
    })
}

fn remember(game: &mut Game<'_>, end: End) {
    let saved = Tag::Compound(Compound::from([
        ("pos".into(), Tag::IntArray(end.pos.to_vec())),
        ("axis".into(), vector(end.axis)),
        ("normal".into(), vector(end.normal)),
        ("end".into(), vector(end.start())),
    ]));
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(CONNECTING, Some(saved));
    }
}

fn overlay(current: &str, placed: &str) -> Option<&'static str> {
    match (current, placed) {
        ("xo", "zo") | ("zo", "xo") => Some("cr_o"),
        ("pd", "nd") | ("nd", "pd") => Some("cr_d"),
        ("xo", "pd") | ("pd", "xo") => Some("cr_pdx"),
        ("zo", "pd") | ("pd", "zo") => Some("cr_pdz"),
        ("xo", "nd") | ("nd", "xo") => Some("cr_ndx"),
        ("zo", "nd") | ("nd", "zo") => Some("cr_ndz"),
        _ => None,
    }
}

fn can_replace(game: &Game<'_>, state: BlockStateId) -> bool {
    game.res.behaviours().is_replaceable(state)
        || game.native_state_block(state).is_some_and(|block| {
            game.res
                .items()
                .block_tags
                .get("minecraft:flowers")
                .is_some_and(|tag| tag.contains(&*block))
        })
}

fn pay(game: &mut Game<'_>, mut charge: u32) {
    let (before, rest) = game.inventory.split_at_mut(game.selected);
    let (selected, after) = rest.split_first_mut().expect("selected hotbar slot");
    for cell in before
        .iter_mut()
        .chain(after)
        .chain([selected, &mut game.offhand])
    {
        if let Some(stack) = cell.as_mut().filter(|stack| stack.item.as_ref() == TRACK) {
            let used = stack.count.min(charge);
            stack.count -= used;
            charge -= used;
            if stack.count == 0 {
                *cell = None;
            }
        }
        if charge == 0 {
            break;
        }
    }
}

struct TrackPlacement {
    pos: [i32; 3],
    state: BlockStateId,
    cost: u32,
}

fn track_at(game: &Game<'_>, pos: [i32; 3], shape: &str, turn: bool) -> Option<TrackPlacement> {
    let old_id = game.world.block(pos[0], pos[1], pos[2]);
    let registry = game.pack.assets.registry;
    let old = registry.state(old_id)?;
    let can_place = can_replace(game, old_id);
    let regular = registry.state(registry.default_state(TRACK)?)?;
    let mut next = if old.name == TRACK {
        let mut next = old.clone();
        if let Some(combined) = old
            .properties
            .get("shape")
            .and_then(|current| overlay(current, shape))
        {
            next.properties.insert("shape".into(), combined.into());
        }
        next
    } else if can_place || turn {
        let mut next = regular.clone();
        next.properties.insert("shape".into(), shape.into());
        next
    } else {
        return None;
    };
    if turn {
        next.properties.insert("turn".into(), "true".into());
    }
    let wet = old.name == "minecraft:water"
        || old
            .properties
            .get("waterlogged")
            .is_some_and(|v| v == "true");
    next.properties
        .insert("waterlogged".into(), wet.to_string());
    Some(TrackPlacement {
        pos,
        state: registry.id(&next)?,
        cost: u32::from(can_place),
    })
}

fn connections(entity: &ModBlockEntity) -> impl Iterator<Item = &Compound> {
    match entity.nbt.get(&CONNECTIONS.into()) {
        Some(Tag::List(saved)) => saved.as_slice(),
        _ => &[],
    }
    .iter()
    .filter_map(|tag| match tag {
        Tag::Compound(data) => Some(data),
        _ => None,
    })
}

fn pair<T>(
    connection: &Compound,
    key: &str,
    mut read: impl FnMut(&Compound) -> Option<T>,
) -> Option<[T; 2]> {
    let Tag::List(items) = connection.get(&key.into())? else {
        return None;
    };
    let [Tag::Compound(a), Tag::Compound(b)] = items.as_slice() else {
        return None;
    };
    Some([read(a)?, read(b)?])
}

fn connection_target(connection: &Compound, origin: [i32; 3]) -> Option<[i32; 3]> {
    let [_, to] = pair(connection, "Positions", |end| {
        position(end.get(&"Pos".into())?)
    })?;
    Some(offset(origin, to))
}

fn connected(game: &Game<'_>, from: [i32; 3], to: [i32; 3]) -> bool {
    mod_entity(game, from).is_some_and(|entity| {
        connections(entity).any(|connection| connection_target(connection, from) == Some(to))
    })
}

fn local_vec(pos: [i32; 3]) -> Vec3 {
    let [x, y, z] = pos.map(f64::from);
    Vec3::new(x, y, z)
}

fn save_connection(game: &mut Game<'_>, curve: Curve, index: usize) {
    let ends = [curve.ends[index], curve.ends[1 - index]];
    let from = ends[0].pos;
    let to = ends[1].pos;
    let origin = local_vec(from);
    let wrap = |key: &str, values: [Tag; 2]| {
        Tag::List(
            values
                .into_iter()
                .map(|value| Tag::Compound(Compound::from([(key.into(), value)])))
                .collect(),
        )
    };
    let connection = Compound::from([
        (
            "Positions".into(),
            wrap(
                "Pos",
                ends.map(|end| {
                    Tag::IntArray((0..3).map(|axis| end.pos[axis] - from[axis]).collect())
                }),
            ),
        ),
        (
            "Starts".into(),
            wrap(
                "V",
                [index, 1 - index].map(|index| vector(origin.vector_to(curve.starts[index]))),
            ),
        ),
        (
            "Axes".into(),
            wrap("V", ends.map(|end| vector(end.axis.normalize()))),
        ),
        (
            "Normals".into(),
            wrap("V", ends.map(|end| vector(end.normal))),
        ),
        ("Primary".into(), Tag::Byte(i8::from(index == 0))),
        ("Girder".into(), Tag::Byte(0)),
        ("Material".into(), Tag::String("create:andesite".into())),
    ]);
    game.native_with_mod_block_entity(from, |entity| {
        let mut saved: Vec<_> = connections(entity)
            .filter(|previous| connection_target(previous, from) != Some(to))
            .map(|previous| Tag::Compound(previous.clone()))
            .collect();
        saved.push(Tag::Compound(connection));
        entity.nbt.insert(CONNECTIONS.into(), Tag::List(saved));
    });
    game.native_block_entity_sync(from);
}

fn curve(connection: &Compound) -> Option<Curve> {
    let positions = pair(connection, "Positions", |end| {
        position(end.get(&"Pos".into())?)
    })?;
    let vectors = |key| pair(connection, key, |end| read_vector(end.get(&"V".into())?));
    let axes = vectors("Axes")?;
    let normals = vectors("Normals")?;
    Some(Curve::with_starts(
        std::array::from_fn(|index| End {
            pos: positions[index],
            axis: axes[index],
            normal: normals[index],
        }),
        vectors("Starts")?,
    ))
}

fn absolute_curve(mut curve: Curve, pos: [i32; 3]) -> Curve {
    for end in &mut curve.ends {
        end.pos = offset(pos, end.pos);
    }
    curve.starts = curve.starts.map(|start| start.add_vector(local_vec(pos)));
    curve
}

pub(super) fn prepare_break(game: &mut Game<'_>, pos: [i32; 3]) {
    let creative = game.creative;
    game.native_with_mod_block_entity(pos, |entity| {
        if entity.id != TRACK {
            return;
        }
        if creative {
            entity.runtime.insert(CANCEL_DROPS.into(), Tag::Byte(1));
        } else {
            entity.runtime.remove(&CANCEL_DROPS.into());
        }
    });
}

pub(super) fn remove_endpoint(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos) {
    if !level.native_authoritative {
        return;
    }
    let owner = [pos.x, pos.y, pos.z];
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    else {
        return;
    };
    if entity.id != TRACK {
        return;
    }
    let drop = level.rules.block_drops && entity.runtime.get(&CANCEL_DROPS.into()).is_none();
    let removed: Vec<_> = connections(entity)
        .filter_map(|data| {
            Some((
                absolute_curve(curve(data)?, owner),
                int(data, "Girder") == Some(1),
            ))
        })
        .collect();
    for (curve, girder) in removed {
        let unlinked = remove_inbound(level, ticks, curve.ends[1].pos, owner);
        super::create_fake_track::remove_markers(level, ticks, curve);
        if drop && unlinked {
            drop_curve_items(level, curve, girder);
        }
    }
}

fn remove_inbound(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    pos: [i32; 3],
    owner: [i32; 3],
) -> bool {
    let [x, y, z] = pos;
    let key = (x, y, z);
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get_mut(&key) else {
        return false;
    };
    if entity.id != TRACK {
        return false;
    }
    let Some(Tag::List(saved)) = entity.nbt.get_mut(&CONNECTIONS.into()) else {
        return false;
    };
    let count = saved.len();
    saved.retain(
        |tag| !matches!(tag, Tag::Compound(data) if connection_target(data, pos) == Some(owner)),
    );
    if count == saved.len() {
        return false;
    }
    if saved.is_empty() {
        level.native_set_block_property(ticks, pos, "turn", "false", flags::UPDATE_ALL);
    }
    // Send the empty Connections tag too so clients discard their cached curve.
    level.world.modified.insert((x >> 4, z >> 4));
    if let Some(log) = level.world.block_log.as_mut() {
        log.push(key);
    }
    true
}

fn same_curve(a: Curve, b: Curve) -> bool {
    let matches = |left: Curve, right: Curve| {
        left.ends
            .iter()
            .zip(right.ends.iter())
            .all(|(left, right)| {
                left.pos == right.pos
                    && left.axis.distance(right.axis) < 1.0e-6
                    && left.normal.distance(right.normal) < 1.0e-6
            })
            && left
                .starts
                .iter()
                .zip(right.starts.iter())
                .all(|(left, right)| left.distance(*right) < 1.0e-6)
            && left.segments == right.segments
    };
    matches(a, b)
        || matches(
            a,
            Curve {
                ends: [b.ends[1], b.ends[0]],
                starts: [b.starts[1], b.starts[0]],
                ..b
            },
        )
}

pub(super) fn marker_owned_by_other(level: &GameLevel<'_>, at: [i32; 3], removed: Curve) -> bool {
    let mut skipped_removed = false;
    for (&(x, y, z), block_entity) in level.world.block_entities.iter() {
        let BlockEntity::Mod(entity) = block_entity else {
            continue;
        };
        if entity.id != TRACK {
            continue;
        }
        for data in connections(entity) {
            let Some(candidate) = curve(data).map(|curve| absolute_curve(curve, [x, y, z])) else {
                continue;
            };
            if !skipped_removed && same_curve(candidate, removed) {
                skipped_removed = true;
                continue;
            }
            if super::create_fake_track::rasterise(candidate).contains(&at) {
                return true;
            }
        }
    }
    false
}

fn drop_curve_items(level: &mut GameLevel<'_>, curve: Curve, girder: bool) {
    use super::spill::Spawn;
    let segments = curve.segments as f32;
    for (index, factor) in curve
        .step_lut()
        .into_iter()
        .take(curve.segments as usize)
        .enumerate()
        .step_by(2)
    {
        let t = f64::from(index as f32 * factor / segments);
        let mut pos = curve.point(t).components();
        pos[1] += 3.0 / 16.0;
        for axis in &mut pos {
            *axis += f64::from((level.world.random.next_float() - 0.5) * 0.25);
        }
        level.spill.spawns.push(Spawn {
            stack: ItemStack::new(TRACK, 1),
            pos,
            motion: None,
            delay: 10,
        });
        if girder {
            for _ in 0..2 {
                level.spill.spawns.push(Spawn {
                    stack: ItemStack::new("create:metal_girder", 1),
                    pos,
                    motion: None,
                    delay: 10,
                });
            }
        }
    }
}

pub(super) fn curves_at(game: &Game<'_>, pos: [i32; 3]) -> Vec<Curve> {
    let Some(entity) = mod_entity(game, pos) else {
        return Vec::new();
    };
    connections(entity)
        .filter_map(curve)
        .map(|mut curve| {
            for end in &mut curve.ends {
                end.pos = offset(pos, end.pos);
            }
            curve.starts = curve.starts.map(|start| start.add_vector(local_vec(pos)));
            curve
        })
        .collect()
}

pub(super) fn use_track(
    game: &mut Game<'_>,
    clicked: [i32; 3],
    face: [i32; 3],
    stack: &ItemStack,
) -> bool {
    if stack.item.as_ref() != TRACK || game.hand != Hand::Main {
        return false;
    }
    let state = game.world.block(clicked[0], clicked[1], clicked[2]);
    let clicked_track = game.native_state_block(state) == Some(TRACK);
    let Some(start) = selection(stack) else {
        if !clicked_track {
            return false;
        }
        if let Some(shape) = game.native_block_property(clicked, "shape")
            && track_axis(&shape).is_some()
            && let Some(end) = new_end(clicked, &shape, game.yaw)
        {
            remember(game, end);
        }
        return true;
    };
    if game.native_sneaking() {
        return clear_selection(game, stack);
    }
    let target = if clicked_track || game.res.behaviours().is_replaceable(state) {
        clicked
    } else {
        offset(clicked, face)
    };
    if game.native_block(start.pos) != TRACK {
        return true;
    }
    let Some(shape) = game.native_block_property(start.pos, "shape") else {
        return true;
    };
    let end_shape = if clicked_track {
        game.native_block_property(clicked, "shape")
    } else {
        Some(selected(game.yaw).into())
    };
    let Some(end_shape) = end_shape else {
        return true;
    };
    let Some(end) = new_end(target, &end_shape, game.yaw) else {
        return true;
    };
    let extended = game.keys.held(Action::Sprint)
        || game
            .player_attachments
            .get_existing(&SPRINT_INPUT)
            .ok()
            .flatten()
            == Some(true)
        || matches!(
            stack.data().and_then(|data| data.other(EXTENDED)),
            Some(Tag::Byte(1))
        );
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(EXTENDED, None);
    }
    let Some(plan) = create_track_curve::connect(start, end, extended) else {
        return true;
    };
    let mut blocks = Vec::new();
    let mut by_block = 0;
    let shapes = [&shape, &end_shape];
    for (index, &length) in plan.extent.iter().enumerate() {
        let endpoint = plan.ends[index];
        let extra = i32::from(plan.curve.is_some());
        for step in 0..length + extra {
            let pos = endpoint.across(step).pos;
            if let Some(block) = track_at(game, pos, shapes[index], extra != 0 && step == length) {
                if !blocks
                    .iter()
                    .any(|placed: &TrackPlacement| placed.pos == pos)
                {
                    by_block += block.cost;
                    blocks.push(block);
                }
            }
        }
    }

    let curve_cost = plan
        .curve
        .filter(|curve| !connected(game, curve.ends[0].pos, curve.ends[1].pos))
        .map_or(0, |curve| curve.segments.div_ceil(2));
    let supply = game
        .inventory
        .iter()
        .chain(std::iter::once(&game.offhand))
        .flatten()
        .filter(|stack| stack.item.as_ref() == TRACK)
        .map(|stack| stack.count)
        .sum::<u32>();
    if !game.creative && by_block + curve_cost > supply {
        return true;
    }
    let mut charge = curve_cost;
    for block in blocks {
        if game.native_set_block(
            game.native_dimension(),
            block.pos,
            block.state,
            flags::UPDATE_ALL,
        ) {
            charge += block.cost;
        }
    }
    if let Some(curve) = plan.curve {
        save_connection(game, curve, 0);
        save_connection(game, curve, 1);
        super::create_fake_track::manage(game, curve, false);
    }
    if !game.creative {
        pay(game, charge);
    }
    clear_selection(game, stack);
    true
}

pub(super) fn clear_selection(game: &mut Game<'_>, stack: &ItemStack) -> bool {
    if let Some(held) = game.held_mut()
        && stack.item.as_ref() == TRACK
        && held
            .data()
            .is_some_and(|data| data.other(CONNECTING).is_some())
    {
        held.data_mut().set_other(CONNECTING, None);
        true
    } else {
        false
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if game.world.game_time % 20 != 0 {
        return;
    }
    let is_valid = |data: &Compound| {
        connection_target(data, pos).is_some_and(|pos| {
            !game.world.loaded(pos[0], pos[2])
                || game.native_block_property(pos, "turn").as_deref() == Some("true")
        })
    };
    let removed: Vec<_> = connections(entity)
        .filter(|data| !is_valid(data))
        .filter_map(curve)
        .map(|curve| absolute_curve(curve, pos))
        .collect();
    let refreshed: Vec<_> = if game.world.game_time % 100 == 0 {
        connections(entity)
            .filter(|data| is_valid(data) && int(data, "Primary") == Some(1))
            .filter_map(curve)
            .map(|curve| absolute_curve(curve, pos))
            .collect()
    } else {
        Vec::new()
    };
    for curve in removed {
        super::create_fake_track::manage(game, curve, true);
    }
    for curve in refreshed {
        super::create_fake_track::manage(game, curve, false);
    }
    let valid: Vec<_> = connections(entity)
        .filter(|data| {
            connection_target(data, pos).is_some_and(|pos| {
                !game.world.loaded(pos[0], pos[2])
                    || game.native_block_property(pos, "turn").as_deref() == Some("true")
            })
        })
        .map(|data| Tag::Compound(data.clone()))
        .collect();
    if valid.len() != connections(entity).count() {
        if valid.is_empty() {
            game.native_set_block_property(pos, "turn", "false");
        }
        entity.nbt.insert(CONNECTIONS.into(), Tag::List(valid));
        game.native_block_entity_sync(pos);
    }
}

const TIE: &str = "create:block/track/tie";
const LEFT_RAIL: &str = "create:block/track/segment_left";
const RIGHT_RAIL: &str = "create:block/track/segment_right";

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([TIE, LEFT_RAIL, RIGHT_RAIL].map(String::from));
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    entity
        .nbt
        .get(&CONNECTIONS.into())
        .map_or_else(Compound::new, |data| {
            Compound::from([(CONNECTIONS.into(), data.clone())])
        })
}

pub(super) fn bounds(entity: &ModBlockEntity, bounds: &mut [f32; 6]) {
    for shape in connections(entity)
        .filter(|data| int(data, "Primary") == Some(1))
        .filter_map(curve)
    {
        for sample in 0..=8 {
            for (axis, coordinate) in shape
                .point(sample as f64 / 8.0)
                .components()
                .into_iter()
                .enumerate()
            {
                bounds[axis] = bounds[axis].min(coordinate as f32 - 1.375);
                bounds[axis + 3] = bounds[axis + 3].max(coordinate as f32 + 1.375);
            }
        }
    }
}

fn segment_pose(draw: &mut BlockEntityDraw, origin: Vec3, diff: Vec3, normal: Vec3) {
    let yaw = diff.x.atan2(diff.z);
    let pitch = diff.horizontal_distance().atan2(diff.y) - std::f64::consts::FRAC_PI_2;
    let up = Vec3::new(
        yaw.sin() * pitch.sin(),
        pitch.cos(),
        yaw.cos() * pitch.sin(),
    );
    let roll = diff
        .cross(normal)
        .normalize()
        .dot(up)
        .clamp(-1.0, 1.0)
        .acos()
        * if up.dot(normal) < 0.0 { -1.0 } else { 1.0 };
    draw.translate(origin.components().map(|part| part as f32));
    draw.rotate_about([0.0, 1.0, 0.0], yaw.to_degrees() as f32, [0.0; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], pitch.to_degrees() as f32, [0.0; 3]);
    draw.rotate_about([0.0, 0.0, 1.0], roll.to_degrees() as f32, [0.0; 3]);
}

pub(super) fn render(game: &Game<'_>, entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    for shape in connections(entity)
        .filter(|data| int(data, "Primary") == Some(1))
        .filter_map(curve)
    {
        let mut distance = 0.0_f32;
        if shape.segments == 0 {
            continue;
        }
        let mut previous = shape.point(0.0);
        let mut rails: Option<[Vec3; 2]> = None;
        let segments = shape.segments;
        for i in 0..=segments {
            let raw_t = i as f32 / segments as f32;
            let raw = shape.point(f64::from(raw_t));
            distance += (raw.distance(previous) / shape.length) as f32;
            previous = raw;
            let t = if i == 0 || i == segments {
                raw_t
            } else {
                i as f32 * (raw_t / distance) / segments as f32
            };
            let t = f64::from(t);
            let middle = shape.point(t).add_vector(Vec3::new(0.0, 3.0 / 16.0, 0.0));
            let before = shape.point((t - 0.0001).max(0.0));
            let after = shape.point((t + 0.0001).min(1.0));
            let normal = shape.ends[0]
                .normal
                .lerp(shape.ends[1].normal, t)
                .cross(before.vector_to(after))
                .normalize();
            let next = [
                middle.add_vector(normal.scale(0.965)),
                middle.subtract(normal.scale(0.965)),
            ];
            if let Some([left, right]) = rails {
                let trail: [Vec3; 2] = [left, right];
                let prior = left.lerp(right, 0.5);
                draw.push();
                segment_pose(draw, prior, prior.vector_to(middle), normal);
                draw.translate([-0.5, -2.0 / 16.0 - 1.0 / 256.0, 0.0]);
                game.native_draw_model(draw, TIE, 0xFFFFFF);
                draw.pop();
                for ((previous, current), model) in
                    trail.into_iter().zip(next).zip([LEFT_RAIL, RIGHT_RAIL])
                {
                    let diff = previous.vector_to(current);
                    draw.push();
                    segment_pose(draw, previous, diff, normal);
                    draw.translate([0.0, -2.0 / 16.0 - 1.0 / 256.0, -1.0 / 32.0]);
                    draw.scale([
                        1.0,
                        1.0,
                        diff.length() as f32 * if i == segments { 2.2 } else { 2.1 },
                    ]);
                    game.native_draw_model(draw, model, 0xFFFFFF);
                    draw.pop();
                }
            }
            rails = Some(next);
        }
    }
    draw.keep();
}
