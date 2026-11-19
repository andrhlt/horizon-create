use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_burner::{self, BURNER};
use super::create_crafter::{self, CRAFTER};
use super::create_depot::{compound, encode};
use super::create_machines::{float, int, offset, set_float};

pub(super) const ARM: &str = "create:mechanical_arm";

#[derive(Clone, Copy, PartialEq, Eq)]
enum Phase {
    SearchInputs,
    MoveInput,
    SearchOutputs,
    MoveOutput,
}

impl Phase {
    fn read(nbt: &Compound) -> Self {
        match nbt.get(&"Phase".into()) {
            Some(Tag::String(name)) if name.to_string_lossy() == "MOVE_TO_INPUT" => Self::MoveInput,
            Some(Tag::String(name)) if name.to_string_lossy() == "SEARCH_OUTPUTS" => {
                Self::SearchOutputs
            }
            Some(Tag::String(name)) if name.to_string_lossy() == "MOVE_TO_OUTPUT" => {
                Self::MoveOutput
            }
            _ => Self::SearchInputs,
        }
    }

    fn saved(self) -> &'static str {
        match self {
            Self::SearchInputs => "SEARCH_INPUTS",
            Self::MoveInput => "MOVE_TO_INPUT",
            Self::SearchOutputs => "SEARCH_OUTPUTS",
            Self::MoveOutput => "MOVE_TO_OUTPUT",
        }
    }
}

fn points(game: &Game<'_>, pos: [i32; 3], nbt: &Compound, mode: &str) -> Vec<Option<[i32; 3]>> {
    let Some(Tag::List(points)) = nbt.get(&"InteractionPoints".into()) else {
        return Vec::new();
    };
    points
        .iter()
        .filter_map(|point| {
            let Tag::Compound(point) = point else {
                return None;
            };
            let (
                Some(Tag::String(kind)),
                Some(Tag::IntArray(local)),
                Some(Tag::String(point_mode)),
            ) = (
                point.get(&"Type".into()),
                point.get(&"Pos".into()),
                point.get(&"Mode".into()),
            )
            else {
                return None;
            };
            if point_mode.to_string_lossy() != mode {
                return None;
            }
            let target = offset(pos, local.as_slice().try_into().ok()?);
            let kind = kind.to_string_lossy();
            let block = if kind == "create:crafter" {
                CRAFTER
            } else {
                kind.as_str()
            };
            let exists = game.native_block(target) == block;
            Some(exists.then_some(target))
        })
        .collect()
}

fn capacity(game: &Game<'_>, at: [i32; 3], stack: &ItemStack) -> u32 {
    match game.native_block(at).as_str() {
        BURNER => return u32::from(create_burner::accepts_from_arm(game, at, stack)),
        CRAFTER => return create_crafter::room(game, at),
        _ => {}
    }
    let limit = game.native_max_stack_size(&stack.item).unwrap_or(64);
    game.native_container_slots(game.native_dimension(), at, Direction::Up)
        .into_iter()
        .flatten()
        .filter(|slot| game.block_can_place(at, slot.slot, stack))
        .map(|slot| match slot.stack {
            None => limit,
            Some(current) if current.item == stack.item && current.extra == stack.extra => {
                limit.saturating_sub(current.count)
            }
            _ => 0,
        })
        .sum()
}

fn extractable(game: &Game<'_>, from: [i32; 3], dest: &[Option<[i32; 3]>]) -> Option<(usize, u32)> {
    game.native_container_slots(game.native_dimension(), from, Direction::Up)?
        .into_iter()
        .find_map(|slot| {
            let stack = slot.stack.filter(|_| slot.can_take)?;
            let room = dest
                .iter()
                .flatten()
                .map(|at| capacity(game, *at, &stack))
                .sum::<u32>();
            let count = room.min(stack.count);
            (count > 0).then_some((slot.slot, count))
        })
}

fn select(
    nbt: &mut Compound,
    points: &[Option<[i32; 3]>],
    cursor: &str,
    available: impl Fn([i32; 3]) -> bool,
) -> Option<i32> {
    let mode = int(nbt, "ScrollValue").unwrap_or(0);
    let last = int(nbt, cursor).unwrap_or(-1);
    let first = if mode == 2 {
        0
    } else {
        (last + 1).max(0) as usize
    };
    let range = if mode == 1 { 1 } else { points.len() };
    let found = points
        .iter()
        .enumerate()
        .skip(first)
        .take(range)
        .find(|(_, pos)| pos.is_some_and(&available))
        .map(|(index, _)| index as i32);
    if let Some(index) = found {
        nbt.insert(
            cursor.into(),
            Tag::Int(if index as usize + 1 == points.len() {
                -1
            } else {
                index
            }),
        );
    } else if mode != 1 {
        nbt.insert(cursor.into(), Tag::Int(-1));
    }
    found
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    let mut phase = Phase::read(&entity.nbt);
    let start_phase = phase;
    let mut progress = float(&entity.nbt, "MovementProgress").unwrap_or(0.0);
    let mut index = int(&entity.nbt, "TargetPointIndex").unwrap_or(0);
    let initial_index = index;
    let mut held = compound(&entity.nbt, "HeldItem").and_then(ItemStack::from_nbt);
    let powered = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
    let previous_clock = int(&entity.nbt, "LazyTicks");
    let clock = previous_clock.unwrap_or(0) + 1;
    let lazy = clock == 11;
    entity
        .nbt
        .insert("LazyTicks".into(), Tag::Int(if lazy { 0 } else { clock }));

    if lazy
        && progress >= 0.5
        && phase == Phase::SearchOutputs
        && let Some(stack) = held.as_ref()
    {
        let outputs = points(game, pos, &entity.nbt, "DEPOSIT");
        if let Some(target) = select(&mut entity.nbt, &outputs, "LastOutput", |at| {
            capacity(game, at, stack) > 0
        }) {
            index = target;
            phase = Phase::MoveOutput;
            progress = 0.0;
        }
    }

    let was_reached = progress >= 1.0;
    if previous_clock.is_some() || !matches!(phase, Phase::MoveInput | Phase::MoveOutput) {
        progress = (progress + rpm.abs().min(256.0) / 1024.0).min(1.0);
    }
    if progress >= 1.0 {
        match phase {
            Phase::SearchInputs if !powered => {
                let inputs = points(game, pos, &entity.nbt, "TAKE");
                let outputs = points(game, pos, &entity.nbt, "DEPOSIT");
                if let Some(target) = select(&mut entity.nbt, &inputs, "LastInput", |at| {
                    extractable(game, at, &outputs).is_some()
                }) {
                    index = target;
                    phase = Phase::MoveInput;
                    progress = 0.0;
                }
            }
            Phase::MoveInput => {
                let inputs = points(game, pos, &entity.nbt, "TAKE");
                let outputs = points(game, pos, &entity.nbt, "DEPOSIT");
                held = inputs
                    .get(index as usize)
                    .copied()
                    .flatten()
                    .and_then(|at| {
                        let (slot, count) = extractable(game, at, &outputs)?;
                        game.native_extract_item(
                            game.native_dimension(),
                            at,
                            Direction::Up,
                            slot,
                            count,
                        )
                    });
                phase = if held.is_some() {
                    Phase::SearchOutputs
                } else {
                    Phase::SearchInputs
                };
                index = -1;
                progress = 0.0;
            }
            Phase::SearchOutputs if !was_reached => {
                let outputs = points(game, pos, &entity.nbt, "DEPOSIT");
                if let Some(stack) = held.as_ref()
                    && let Some(target) = select(&mut entity.nbt, &outputs, "LastOutput", |at| {
                        capacity(game, at, stack) > 0
                    })
                {
                    index = target;
                    phase = Phase::MoveOutput;
                    progress = 0.0;
                }
            }
            Phase::MoveOutput => {
                let outputs = points(game, pos, &entity.nbt, "DEPOSIT");
                if let Some(at) = outputs.get(index as usize).copied().flatten()
                    && let Some(stack) = held.take()
                {
                    held = match game.native_block(at).as_str() {
                        BURNER => create_burner::feed_from_arm(game, at, stack),
                        CRAFTER => create_crafter::insert(game, at, stack),
                        _ => game.native_insert_item(at, Direction::Up, stack),
                    };
                }
                phase = if held.is_some() {
                    Phase::SearchOutputs
                } else {
                    Phase::SearchInputs
                };
                index = -1;
                progress = 0.0;
            }
            _ => {}
        }
    }

    entity
        .nbt
        .insert("Powered".into(), Tag::Byte(i8::from(powered)));
    entity
        .nbt
        .insert("Phase".into(), Tag::String(phase.saved().into()));
    entity
        .nbt
        .insert("TargetPointIndex".into(), Tag::Int(index));
    entity.nbt.insert(
        "HeldItem".into(),
        held.as_ref()
            .map_or_else(|| Tag::Compound(Compound::new()), encode),
    );
    set_float(&mut entity.nbt, "MovementProgress", progress);
    let changed_pose = pose(
        game,
        pos,
        &mut entity.nbt,
        (start_phase, initial_index),
        (phase, index),
        progress,
    );
    if changed_pose || phase != start_phase {
        game.native_block_entity_sync(pos);
    }
}

const SELECTION: &str = "create:mechanical_arm_points";
const RANGE: i64 = 5;

fn selection(stack: &ItemStack) -> Vec<Tag> {
    match stack
        .custom_data()
        .and_then(|data| data.get(&SELECTION.into()))
    {
        Some(Tag::List(points)) => points.clone(),
        _ => Vec::new(),
    }
}

fn save_selection(stack: &mut ItemStack, points: Vec<Tag>) {
    let mut data = stack.custom_data().cloned().unwrap_or_default();
    if points.is_empty() {
        data.remove(&SELECTION.into());
    } else {
        data.insert(SELECTION.into(), Tag::List(points));
    }
    stack.data_mut().set_other(
        "minecraft:custom_data",
        (!data.is_empty()).then_some(Tag::Compound(data)),
    );
    stack.tidy();
}

fn saved_pos(point: &Compound) -> Option<[i32; 3]> {
    match point.get(&"Pos".into()) {
        Some(Tag::IntArray(pos)) => pos.as_slice().try_into().ok(),
        _ => None,
    }
}

fn point_in_level(point: &Compound, dimension: &str, pos: [i32; 3]) -> bool {
    matches!(point.get(&"Dimension".into()), Some(Tag::String(level)) if level.to_string_lossy() == dimension)
        && saved_pos(point) == Some(pos)
}

pub(super) fn choose_point(game: &mut Game<'_>, pos: [i32; 3], remove: bool) -> bool {
    if game.held().is_none_or(|stack| stack.item.as_ref() != ARM) {
        return false;
    }
    let dimension = game.native_dimension();
    let block = game.native_block(pos);
    let can_insert = game
        .native_container_slots(dimension, pos, Direction::Up)
        .is_some();
    let Some(held) = game
        .held_mut()
        .as_mut()
        .filter(|stack| stack.item.as_ref() == ARM)
    else {
        return false;
    };
    let mut points = selection(held);
    let index = points.iter().position(
        |value| matches!(value, Tag::Compound(point) if point_in_level(point, dimension, pos)),
    );
    if remove {
        let Some(index) = index else { return false };
        points.remove(index);
    } else {
        if !can_insert && block != BURNER {
            return false;
        }
        let mode = if matches!(block.as_str(), "create:basin" | BURNER | CRAFTER) {
            "DEPOSIT"
        } else if index.is_some_and(|index| {
            matches!(&points[index], Tag::Compound(point)
                if matches!(point.get(&"Mode".into()), Some(Tag::String(mode)) if mode.to_string_lossy() == "TAKE"))
        }) {
            "DEPOSIT"
        } else {
            "TAKE"
        };
        let point = Tag::Compound(Compound::from([
            ("Pos".into(), Tag::IntArray(pos.to_vec())),
            ("Dimension".into(), Tag::String(dimension.into())),
            ("Mode".into(), Tag::String(mode.into())),
            (
                "Type".into(),
                Tag::String(
                    if block == CRAFTER {
                        "create:crafter"
                    } else {
                        block.as_str()
                    }
                    .into(),
                ),
            ),
        ]));
        if let Some(index) = index {
            points[index] = point;
        } else {
            points.push(point);
        }
    }
    save_selection(held, points);
    true
}

pub(super) fn setup(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) {
    if stack.item.as_ref() != ARM || game.native_block(pos) != ARM {
        return;
    }
    let dimension = game.native_dimension();
    let points = selection(stack)
        .into_iter()
        .filter_map(|point| {
            let Tag::Compound(mut point) = point else {
                return None;
            };
            let world = saved_pos(&point)?;
            if !point_in_level(&point, dimension, world) {
                return None;
            }
            let relative =
                std::array::from_fn::<_, 3, _>(|i| i64::from(world[i]) - i64::from(pos[i]));
            if relative.iter().any(|n| n.abs() >= RANGE)
                || relative.iter().map(|n| n * n).sum::<i64>() >= RANGE * RANGE
            {
                return None;
            }
            point.remove(&"Dimension".into());
            point.insert(
                "Pos".into(),
                Tag::IntArray(relative.map(|n| n as i32).to_vec()),
            );
            Some(Tag::Compound(point))
        })
        .collect();
    game.native_with_mod_block_entity(pos, |entity| {
        entity
            .nbt
            .insert("InteractionPoints".into(), Tag::List(points));
    });
    game.native_block_entity_sync(pos);
    if let Some(held) = game.held_mut().as_mut() {
        save_selection(held, Vec::new());
    }
}

pub(super) fn place(
    level: &super::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<horizon_world::registry::BlockStateId> {
    let mut state = level.registry.state(state)?.clone();
    if state.name != ARM {
        return None;
    }
    state.properties.insert(
        "ceiling".into(),
        (context.face == Direction::Down).to_string(),
    );
    level.registry.id(&state)
}

const PARTS: [&str; 7] = [
    "create:block/mechanical_arm/cog",
    "create:block/mechanical_arm/base",
    "create:block/mechanical_arm/lower_body",
    "create:block/mechanical_arm/upper_body",
    "create:block/mechanical_arm/claw_base",
    "create:block/mechanical_arm/upper_claw_grip",
    "create:block/mechanical_arm/lower_claw_grip",
];
const REST: [f32; 4] = [0.0, 135.0, 45.0, 0.0];

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(PARTS.map(String::from));
}

fn angles(nbt: &Compound, key: &str) -> Option<[f32; 4]> {
    let Tag::List(values) = nbt.get(&key.into())? else {
        return None;
    };
    let [
        Tag::Float(base),
        Tag::Float(lower),
        Tag::Float(upper),
        Tag::Float(head),
    ] = values.as_slice()
    else {
        return None;
    };
    Some([*base, *lower, *upper, *head].map(f32::from_bits))
}

fn save_angles(nbt: &mut Compound, key: &str, value: [f32; 4]) {
    nbt.insert(
        key.into(),
        Tag::List(value.map(|v| Tag::Float(v.to_bits())).to_vec()),
    );
}

fn rotate_x(v: [f64; 3], degrees: f32) -> [f64; 3] {
    let (sin, cos) = f64::from(degrees).to_radians().sin_cos();
    [v[0], v[1] * cos - v[2] * sin, v[1] * sin + v[2] * cos]
}

fn arm_angles(game: &Game<'_>, pos: [i32; 3], target: [i32; 3], ceiling: bool) -> [f32; 4] {
    use horizon_core::geometry::trig::atan2_degrees;
    let origin_y = if ceiling { 0.125 } else { 0.875 };
    let grab_y = if game.native_block(target) == super::create_depot::DEPOT {
        0.875
    } else {
        0.5
    };
    let [x, y, z] = std::array::from_fn(|i| f64::from(target[i] - pos[i]));
    let y = y + grab_y - origin_y + 0.5;
    let base = atan2_degrees(x, z) + 180.0;
    let base = if ceiling { 180.0 - base } else { base };
    let sign = if ceiling { -1.0 } else { 1.0 };
    let distance = x.hypot(z) as f32;
    let first = 14_f32 / 16.0;
    let second = 15_f32 / 16.0;
    let length = ((y * y + f64::from(distance * distance)) as f32)
        .sqrt()
        .clamp(0.125, first + second);
    let angle = |ratio: f32| ratio.clamp(-1.0, 1.0).acos().to_degrees();
    let lower = angle((first * first - second * second + length * length) / (2.0 * first * length))
        + atan2_degrees(y * sign, f64::from(distance));
    let upper = angle((first * first + second * second - length * length) / (2.0 * first * second));
    let mut head = rotate_x([0.0, f64::from(second), 0.0], upper + 180.0);
    head[1] += f64::from(first);
    head = rotate_x(head, lower - 90.0);
    let (sin, cos) = f64::from(base).to_radians().sin_cos();
    head = [
        head[0] * cos + head[2] * sin,
        head[1],
        head[2] * cos - head[0] * sin,
    ];
    if ceiling {
        head = rotate_x(head, 180.0);
    }
    let wrist = -lower - upper - 135.0
        + atan2_degrees((y - 0.5 - head[1]) * sign, (x - head[0]).hypot(z - head[2]));
    [base, lower, upper, wrist]
}

fn lerp_angle(from: f32, to: f32, progress: f32) -> f32 {
    from + ((to - from + 180.0).rem_euclid(360.0) - 180.0) * progress
}

fn pose(
    game: &Game<'_>,
    pos: [i32; 3],
    nbt: &mut Compound,
    previous: (Phase, i32),
    current: (Phase, i32),
    progress: f32,
) -> bool {
    let ceiling = game.native_block_property(pos, "ceiling").as_deref() == Some("true");
    let target_angles = |nbt: &Compound, (phase, index)| {
        let mode = match phase {
            Phase::MoveInput => "TAKE",
            Phase::MoveOutput => "DEPOSIT",
            _ => return None,
        };
        let target = points(game, pos, nbt, mode)
            .get(index as usize)
            .copied()
            .flatten()?;
        Some(arm_angles(game, pos, target, ceiling))
    };
    let mut start = angles(nbt, "ArmStartingPose").unwrap_or(REST);
    if previous != current {
        start = target_angles(nbt, previous).unwrap_or([start[0], REST[1], REST[2], REST[3]]);
        save_angles(nbt, "ArmStartingPose", start);
    }
    let target = target_angles(nbt, current);
    let base = target.map_or(start[0], |end| lerp_angle(start[0], end[0], progress));
    let fraction = if progress >= 1.0 {
        1.0
    } else {
        (progress % 0.5) * 2.0
    };
    let (from, to) = if progress < 0.5 {
        (start, REST)
    } else {
        (REST, target.unwrap_or(REST))
    };
    let value = [
        base,
        from[1] + (to[1] - from[1]) * fraction,
        from[2] + (to[2] - from[2]) * fraction,
        lerp_angle(from[3], to[3], fraction),
    ];
    let last = angles(nbt, "ArmPose").unwrap_or(REST);
    save_angles(nbt, "ArmPreviousPose", last);
    save_angles(nbt, "ArmPose", value);
    last != value
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(
        &mut tag,
        "VisualSpeed",
        super::create_machines::reading(entity, 0),
    );
    for key in ["ArmPose", "ArmPreviousPose", "HeldItem"] {
        if let Some(value) = entity.nbt.get(&key.into()) {
            tag.insert(key.into(), value.clone());
        }
    }
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    use super::create_visuals::{draw_rotating, wheel_angle};
    use horizon_assets::item_model::DisplayContext;
    const X: [f32; 3] = [1.0, 0.0, 0.0];
    const Y: [f32; 3] = [0.0, 1.0, 0.0];
    const Z: [f32; 3] = [0.0, 0.0, 1.0];
    const ORIGIN: [f32; 3] = [0.0; 3];

    let now = angles(&entity.nbt, "ArmPose").unwrap_or(REST);
    let last = angles(&entity.nbt, "ArmPreviousPose").unwrap_or(now);
    let [base, lower, upper, wrist] =
        std::array::from_fn(|i| lerp_angle(last[i], now[i], draw.partial));
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let phase = if (pos[0] + pos[2]) % 2 == 0 {
        22.5
    } else {
        0.0
    };
    let ceiling = game.native_block_state_property(state, "ceiling") == Some("true");

    draw.push();
    if ceiling {
        draw.rotate_about(X, 180.0, [0.5; 3]);
    }
    draw_rotating(
        game,
        draw,
        1,
        wheel_angle(draw.game_time, draw.partial, rpm, phase),
        PARTS[0],
    );
    draw.translate([0.5, 0.75, 0.5]);
    draw.rotate_about(Y, base, ORIGIN);
    game.native_draw_model(draw, PARTS[1], 0xffffff);
    draw.translate([0.0, 0.125, 0.0]);
    draw.rotate_about(X, lower, ORIGIN);
    game.native_draw_model(draw, PARTS[2], 0xffffff);
    draw.translate([0.0, 0.0, -14.0 / 16.0]);
    draw.rotate_about(X, upper - 180.0, ORIGIN);
    game.native_draw_model(draw, PARTS[3], 0xffffff);
    draw.translate([0.0, 0.0, -15.0 / 16.0]);
    draw.rotate_about(X, wrist - 45.0, ORIGIN);
    draw.push();
    if ceiling {
        draw.rotate_about(Z, 180.0, ORIGIN);
    }
    game.native_draw_model(draw, PARTS[4], 0xffffff);
    draw.pop();

    let held = compound(&entity.nbt, "HeldItem").and_then(ItemStack::from_nbt);
    let is_block = held
        .as_ref()
        .is_some_and(|stack| game.native_default_state(&stack.item).is_some());
    let opening = match (held.is_some(), is_block) {
        (true, true) => 3.0 / 16.0,
        (true, false) => 5.0 / 64.0,
        _ => 1.0 / 16.0,
    };
    for (index, direction) in [(5, -1.0), (6, 1.0)] {
        draw.push();
        draw.translate([0.0, -direction * opening, -6.0 / 16.0]);
        game.native_draw_model(draw, PARTS[index], 0xffffff);
        draw.pop();
    }
    if let Some(stack) = held {
        draw.rotate_about(X, 90.0, ORIGIN);
        draw.translate([0.0, (if is_block { -9.0 } else { -10.0 }) / 16.0, 0.0]);
        draw.scale([if is_block { 0.5 } else { 0.625 }; 3]);
        game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0);
    }
    draw.pop();
}
