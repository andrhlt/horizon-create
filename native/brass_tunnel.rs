use horizon_core::geometry::Direction;
use horizon_core::random::RandomSource;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_belt::{can_feed, feed, feed_point};
use super::create_depot::{DEPOT, compound, encode, receive_stack};
use super::create_machines::{int, mod_entity, offset};
use super::create_threshold_switch::delta;

pub(super) const TUNNEL: &str = "create:brass_tunnel";

const HORIZONTAL: [Direction; 4] = [
    Direction::North,
    Direction::East,
    Direction::South,
    Direction::West,
];
const BUFFER: &str = "StackToDistribute";
const PROGRESS: &str = "DistributionProgress";
const ARRIVAL: &str = "NewItemArrived";
const ENTERED: &str = "StackEnteredFrom";
const MODE: &str = "ScrollValue";
const SYNCED: &str = "SyncedOutput";

const SPLIT: i32 = 0;
const FORCED_SPLIT: i32 = 1;
const ROUND_ROBIN: i32 = 2;
const FORCED_ROUND_ROBIN: i32 = 3;
const PREFER_NEAREST: i32 = 4;
const RANDOMIZE: i32 = 5;
const SYNCHRONIZE: i32 = 6;

fn down(pos: [i32; 3]) -> [i32; 3] {
    offset(pos, [0, -1, 0])
}

fn axis(movement: Direction) -> &'static str {
    if matches!(movement, Direction::East | Direction::West) {
        "x"
    } else {
        "z"
    }
}

fn sides(movement: Direction) -> [Direction; 2] {
    if axis(movement) == "x" {
        [Direction::North, Direction::South]
    } else {
        [Direction::East, Direction::West]
    }
}

fn face_index(face: Direction) -> i32 {
    match face {
        Direction::Down => 0,
        Direction::Up => 1,
        Direction::North => 2,
        Direction::South => 3,
        Direction::West => 4,
        Direction::East => 5,
    }
}

fn filter(
    game: &Game<'_>,
    entity: &ModBlockEntity,
    pos: [i32; 3],
    face: Direction,
    stack: &ItemStack,
) -> Option<bool> {
    if let Some(Tag::List(filters)) = entity.nbt.get(&"Filters".into()) {
        for entry in filters {
            let Tag::Compound(entry) = entry else {
                continue;
            };
            if int(entry, "Side") == Some(face_index(face)) {
                let present = compound(entry, "Filter").is_some_and(|filter| !filter.is_empty());
                return super::create_item_filters::accepts(game.items(), entry, stack).then_some(present);
            }
        }
    }
    if let Some(neighbor) = mod_entity(game, offset(pos, delta(face))) {
        let present = compound(&neighbor.nbt, "Filter").is_some_and(|filter| !filter.is_empty());
        return super::create_item_filters::accepts(game.items(), &neighbor.nbt, stack).then_some(present);
    }
    Some(false)
}

fn stack(nbt: &Compound) -> Option<ItemStack> {
    ItemStack::from_nbt(compound(nbt, BUFFER)?).filter(|stack| stack.count > 0)
}

fn set_stack(nbt: &mut Compound, stored: Option<&ItemStack>) {
    nbt.insert(
        BUFFER.into(),
        stored.map_or(Tag::Compound(Compound::new()), encode),
    );
}

fn adjacent(game: &Game<'_>, pos: [i32; 3], direction: Direction, axis: &str) -> Option<[i32; 3]> {
    let next = offset(pos, delta(direction));
    (game.native_block(next) == TUNNEL
        && game.native_block_property(next, "axis").as_deref() == Some(axis)
        && feed_point(game, down(next)).is_some())
    .then_some(next)
}

fn side_open(game: &Game<'_>, pos: [i32; 3], direction: Direction) -> bool {
    let at = offset(down(pos), delta(direction));
    game.native_block(at) == DEPOT
        || feed_point(game, at).is_some_and(|(_, _, movement, _)| movement != direction.opposite())
}

fn group(game: &Game<'_>, pos: [i32; 3], movement: Direction) -> Vec<[i32; 3]> {
    let mut tunnels = vec![pos];
    for side in sides(movement) {
        let mut next = pos;
        while let Some(near) = adjacent(game, next, side, axis(movement)) {
            tunnels.push(near);
            next = near;
        }
    }
    tunnels
}

pub(super) enum Arrival {
    Pass,
    Wait,
    Capture,
}

fn admission(
    game: &Game<'_>,
    pos: [i32; 3],
    movement: Direction,
    face: Direction,
    incoming: &ItemStack,
) -> Arrival {
    let Some(entity) = mod_entity(game, pos).filter(|entity| entity.id == TUNNEL) else {
        return Arrival::Pass;
    };
    if filter(game, entity, pos, face.opposite(), incoming).is_none() {
        return Arrival::Wait;
    }
    if group(game, pos, movement).len() == 1
        && sides(movement)
            .into_iter()
            .all(|side| !side_open(game, pos, side))
    {
        return Arrival::Pass;
    }
    if stack(&entity.nbt).is_some() || int(&entity.nbt, SYNCED) == Some(1) {
        return Arrival::Wait;
    }
    Arrival::Capture
}

pub(super) fn arrive(
    game: &mut Game<'_>,
    belt: [i32; 3],
    direction: Direction,
    incoming: &ItemStack,
) -> Arrival {
    insert_at_belt(game, belt, direction, direction, incoming)
}

fn insert_at_belt(
    game: &mut Game<'_>,
    belt: [i32; 3],
    movement: Direction,
    face: Direction,
    incoming: &ItemStack,
) -> Arrival {
    let pos = offset(belt, [0, 1, 0]);
    let arrival = admission(game, pos, movement, face, incoming);
    if matches!(arrival, Arrival::Capture) {
        game.native_with_mod_block_entity(pos, |tunnel| {
            set_stack(&mut tunnel.nbt, Some(incoming));
            tunnel
                .nbt
                .insert(PROGRESS.into(), Tag::Float((-1.0_f32).to_bits()));
            tunnel.nbt.insert(ARRIVAL.into(), Tag::Byte(1));
            tunnel
                .nbt
                .insert(ENTERED.into(), Tag::Int(face_index(face.opposite())));
        });
        game.native_block_entity_sync(pos);
    }
    arrival
}

#[derive(Clone, Copy)]
enum Destination {
    Depot([i32; 3]),
    Belt {
        at: [i32; 3],
        start: [i32; 3],
        index: i32,
        movement: Direction,
        speed: f32,
        face: Direction,
    },
    Eject {
        at: [i32; 3],
        face: Direction,
        speed: f32,
    },
}

impl Destination {
    fn capacity(self, game: &Game<'_>, stack: &ItemStack) -> u32 {
        let open = match self {
            Self::Depot(pos) => mod_entity(game, pos).is_some_and(|entity| {
                entity.items.iter().all(Option::is_none)
                    && compound(&entity.nbt, "HeldItem").is_none_or(Compound::is_empty)
            }),
            Self::Belt {
                at,
                start,
                index,
                movement,
                speed,
                face,
            } => match admission(game, offset(at, [0, 1, 0]), movement, face, stack) {
                Arrival::Capture => true,
                Arrival::Wait => false,
                Arrival::Pass => can_feed(game, start, index, movement, face, speed),
            },
            Self::Eject { .. } => true,
        };
        if open {
            game.native_max_stack_size(&stack.item).unwrap_or(64)
        } else {
            0
        }
    }

    fn send(self, game: &mut Game<'_>, incoming: &ItemStack, count: u32) -> u32 {
        let stack = ItemStack {
            count,
            ..incoming.clone()
        };
        match self {
            Self::Depot(pos) => {
                count - receive_stack(game, pos, stack).map_or(0, |rest| rest.count)
            }
            Self::Belt {
                at,
                start,
                index,
                movement,
                speed,
                face,
            } => match insert_at_belt(game, at, movement, face, &stack) {
                Arrival::Capture => count,
                Arrival::Wait => 0,
                Arrival::Pass => {
                    feed(game, start, index, movement, face, speed, stack);
                    count
                }
            },
            Self::Eject { at, face, speed } => {
                let launch = [
                    f64::from(at[0]) + 0.5,
                    f64::from(at[1]) + 0.875,
                    f64::from(at[2]) + 0.5,
                ];
                let normal = delta(face);
                let velocity = [
                    f64::from(normal[0]) * f64::from(speed.abs().max(0.125)),
                    0.125,
                    f64::from(normal[2]) * f64::from(speed.abs().max(0.125)),
                ];
                game.add_item_entity(stack, launch, Some(velocity), 10);
                count
            }
        }
    }
}

fn output(
    game: &Game<'_>,
    pos: [i32; 3],
    movement: Direction,
    face: Direction,
    speed: f32,
) -> Option<Destination> {
    if face == movement.opposite() || (face == movement && speed == 0.0) {
        return None;
    }
    let at = offset(down(pos), delta(face));
    let potential_funnel = offset(at, [0, 1, 0]);
    if matches!(
        game.native_block(potential_funnel).as_str(),
        super::create_belt_funnel::ANDESITE | super::create_belt_funnel::BRASS
    ) && game
        .native_block_property(potential_funnel, "shape")
        .as_deref()
        == Some("pulling")
        && super::create_fan::facing(
            game,
            game.world.block(
                potential_funnel[0],
                potential_funnel[1],
                potential_funnel[2],
            ),
        ) == Some(face)
    {
        return None;
    }
    if game.native_block(at) == DEPOT {
        return Some(Destination::Depot(at));
    }
    if let Some((start, index, next, speed)) = feed_point(game, at) {
        return (face != next.opposite()).then_some(Destination::Belt {
            at,
            start,
            index,
            movement: next,
            speed,
            face,
        });
    }
    let state = game.world.block(at[0], at[1], at[2]);
    (face == movement && game.res.behaviours().is_replaceable(state))
        .then_some(Destination::Eject { at, face, speed })
}

fn targets(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    tunnels: &[[i32; 3]],
    stack: &ItemStack,
) -> [Vec<Destination>; 2] {
    let mut outputs = [Vec::new(), Vec::new()];
    for &tunnel in tunnels {
        let Some((_, _, movement, speed)) = feed_point(game, down(tunnel)) else {
            continue;
        };
        let neighbor;
        let data = if tunnel == pos {
            entity
        } else {
            neighbor = mod_entity(game, tunnel);
            let Some(neighbor) = neighbor else { continue };
            neighbor
        };
        let faces: Vec<_> = if tunnel == pos {
            HORIZONTAL
                .into_iter()
                .filter(|face| axis(*face) != axis(movement))
                .chain([movement])
                .collect()
        } else {
            HORIZONTAL.to_vec()
        };
        for face in faces {
            if axis(face) != axis(movement)
                && adjacent(game, tunnel, face, axis(movement)).is_some()
            {
                continue;
            }
            if tunnel == pos && int(&entity.nbt, ENTERED) == Some(face_index(face)) {
                continue;
            }
            if let Some(filtered) = filter(game, data, tunnel, face, stack)
                && let Some(destination) = output(game, tunnel, movement, face, speed)
            {
                outputs[usize::from(!filtered)].push(destination);
            }
        }
    }
    outputs
}

fn distribute(
    game: &mut Game<'_>,
    incoming: &mut ItemStack,
    outputs: &[Destination],
    index: u32,
    mode: i32,
) -> Option<u32> {
    if outputs.is_empty() {
        return None;
    }
    let first = match mode {
        PREFER_NEAREST | SYNCHRONIZE => 0,
        RANDOMIZE => game
            .native_level_random(game.native_dimension())
            .map_or(0, |random| {
                random
                    .next_int_bound(outputs.len() as i32)
                    .unwrap_or_default() as usize
            }),
        _ => (index as usize) % outputs.len(),
    };
    let cycle: Vec<_> = outputs
        .iter()
        .cycle()
        .skip(first)
        .take(outputs.len())
        .copied()
        .collect();
    let mut capacities: Vec<_> = cycle
        .iter()
        .map(|out| out.capacity(game, incoming))
        .collect();
    let mut planned = vec![0; cycle.len()];
    let split = matches!(mode, SPLIT | FORCED_SPLIT);
    if split {
        let mut remaining = incoming.count;
        while remaining > 0 {
            let available = capacities.iter().filter(|&&count| count > 0).count() as u32;
            if available == 0 {
                break;
            }
            let share = remaining / available;
            let mut remainder = remaining % available;
            for (cap, plan) in capacities.iter_mut().zip(&mut planned) {
                if *cap == 0 {
                    continue;
                }
                let wanted = share + u32::from(remainder > 0);
                remainder = remainder.saturating_sub(1);
                let amount = wanted.min(*cap);
                if mode == FORCED_SPLIT && wanted > *cap {
                    return None;
                }
                *plan += amount;
                *cap -= amount;
                remaining -= amount;
            }
        }
        if mode == FORCED_SPLIT
            && (remaining > 0
                || capacities
                    .iter()
                    .zip(&planned)
                    .any(|(capacity, plan)| capacity + plan == 0))
        {
            return None;
        }
    } else if matches!(mode, ROUND_ROBIN | FORCED_ROUND_ROBIN) {
        if mode == FORCED_ROUND_ROBIN && capacities[0] < incoming.count {
            return None;
        }
        planned[0] = capacities[0].min(incoming.count);
    } else if let Some(open) = capacities.iter().position(|&available| available > 0) {
        planned[open] = capacities[open].min(incoming.count);
    }
    for (target, count) in cycle
        .into_iter()
        .zip(planned)
        .filter(|(_, count)| *count > 0)
    {
        incoming.count -= target.send(game, incoming, count);
    }
    Some((index + 1) % outputs.len() as u32)
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    super::create_andesite_tunnel::tick(game, pos);
    let Some((_, _, movement, speed)) = feed_point(game, down(pos)) else {
        return;
    };
    let mode = int(&entity.nbt, MODE).unwrap_or(0);
    if entity.data.first() != Some(&mode) {
        entity.data = vec![mode];
    }
    let mut progress = super::create_machines::float(&entity.nbt, PROGRESS).unwrap_or(-1.0);
    if progress > 0.0 {
        progress -= 1.0;
        entity
            .nbt
            .insert(PROGRESS.into(), Tag::Float(progress.to_bits()));
    }
    if speed == 0.0 {
        return;
    }
    let incoming = stack(&entity.nbt);
    let active = int(&entity.nbt, SYNCED) == Some(1);
    if incoming.is_none() && !active {
        return;
    }
    let tunnels = group(game, pos, movement);
    if mode == SYNCHRONIZE && progress == -1.0 {
        let full = tunnels
            .iter()
            .filter(|&&other| {
                if other == pos {
                    incoming.is_some()
                } else {
                    mod_entity(game, other)
                        .and_then(|tunnel| stack(&tunnel.nbt))
                        .is_some()
                }
            })
            .count();
        if full == 0 || full == tunnels.len() {
            let on = Tag::Byte(i8::from(full != 0));
            entity.nbt.insert(SYNCED.into(), on.clone());
            for &other in tunnels.iter().filter(|&&other| other != pos) {
                game.native_with_mod_block_entity(other, |tunnel| {
                    tunnel.nbt.insert(SYNCED.into(), on.clone());
                });
            }
        }
        if !active {
            return;
        }
    }
    let Some(mut incoming) = incoming else { return };
    if progress == -1.0 {
        if targets(game, pos, entity, &tunnels, &incoming)
            .iter()
            .all(Vec::is_empty)
        {
            return;
        }
        let fresh = int(&entity.nbt, ARRIVAL) == Some(1);
        entity.nbt.remove(&ARRIVAL.into());
        let delay: f32 = if fresh { 2.0 } else { 10.0 };
        entity
            .nbt
            .insert(PROGRESS.into(), Tag::Float(delay.to_bits()));
        return;
    }
    if progress != 0.0 {
        return;
    }
    let mut previous = int(&entity.nbt, "PreviousIndex").unwrap_or(0).max(0) as u32;
    for dest in targets(game, pos, entity, &tunnels, &incoming) {
        if incoming.count > 0
            && let Some(index) = distribute(game, &mut incoming, &dest, previous, mode)
        {
            previous = index;
        }
    }
    set_stack(&mut entity.nbt, (incoming.count > 0).then_some(&incoming));
    entity
        .nbt
        .insert("PreviousIndex".into(), Tag::Int(previous as i32));
    entity
        .nbt
        .insert(PROGRESS.into(), Tag::Float((-1.0_f32).to_bits()));
    if incoming.count == 0 {
        entity.nbt.remove(&ENTERED.into());
    }
}

const LABELS: [&str; 7] = [
    "Split",
    "Forced Split",
    "Round Robin",
    "Forced Round Robin",
    "Prefer Nearest",
    "Randomize",
    "Synchronize Inputs",
];
const ROW_LEFT: f32 = 17.0;
const ROW_TOP: f32 = 26.0;
const BUTTON_SPACING: f32 = 25.0;
const BUTTON_SIZE: f32 = 20.0;

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], clicked: [i32; 3]) -> bool {
    if game.hand != super::Hand::Main || game.native_sneaking() || game.native_block(pos) != TUNNEL
    {
        return false;
    }
    let Some((_, _, movement, _)) = feed_point(game, down(pos)) else {
        return false;
    };
    if clicked == [0, 1, 0] {
        let active = group(game, pos, movement).len() > 1
            || sides(movement)
                .into_iter()
                .any(|face| side_open(game, pos, face));
        if active {
            game.open_menu(pos);
        }
        return active;
    }

    let Some(face) = HORIZONTAL.into_iter().find(|face| face.normal() == clicked) else {
        return false;
    };
    if axis(face) != axis(movement)
        && (adjacent(game, pos, face, axis(movement)).is_some() || !side_open(game, pos, face))
    {
        return false;
    }
    let Some(hit) = game.pick().filter(|hit| hit.pos == pos) else {
        return false;
    };
    let along = if clicked[0] != 0 { 2 } else { 0 };
    if ((hit.point[along] - f64::from(pos[along])) - 0.5).abs() > 0.23
        || ((hit.point[1] - f64::from(pos[1])) - 0.8125).abs() > 0.2
    {
        return false;
    }
    let selected = game
        .held()
        .map(encode)
        .unwrap_or(Tag::Compound(Compound::new()));
    game.native_with_mod_block_entity(pos, |tunnel| {
        let key = "Filters".into();
        let stored = tunnel
            .nbt
            .entry(key)
            .or_insert_with(|| Tag::List(Vec::new()));
        if let Tag::List(filters) = stored {
            filters.retain(|tag| {
                !matches!(tag, Tag::Compound(entry) if
                int(entry, "Side") == Some(face_index(face)))
            });
            filters.push(Tag::Compound(Compound::from([
                ("Side".into(), Tag::Int(face_index(face))),
                ("Filter".into(), selected),
                ("FilterAmount".into(), Tag::Int(0)),
            ])));
        }
    });
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 204.0,
        height: 58.0,
        slots: vec![None],
        inventory_x: 12.0,
        inventory_y: 800.0,
        own_labels: true,
        own_background: true,
    }
}

fn option_at([x, y]: [f32; 2]) -> Option<usize> {
    if !(ROW_TOP..ROW_TOP + BUTTON_SIZE).contains(&y) || x < ROW_LEFT {
        return None;
    }
    let within = x - ROW_LEFT;
    let id = (within / BUTTON_SPACING).floor() as usize;
    (id < LABELS.len() && within % BUTTON_SPACING < BUTTON_SIZE).then_some(id)
}

pub(super) fn draw_screen(
    game: &Game<'_>,
    data: &[i32],
    draw: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    let mode = data
        .first()
        .copied()
        .unwrap_or_default()
        .clamp(SPLIT, SYNCHRONIZE);
    let center = |draw: &mut horizon_client::hud::HudBatch, label: &str, height, color| {
        let left = x + (204.0 - game.native_text_width(label)) / 2.0;
        game.native_text(draw, label, [left, y + height], color, false);
    };
    let background = "create:gui/value_settings";
    game.native_fill(draw, [x, y, 204.0, 58.0], 0xD02B2020);
    game.native_sprite(
        draw,
        background,
        [0.0, 31.0, 161.0, 11.0],
        [x + 16.0, y + 5.0, 172.0, 15.0],
    );
    center(draw, "Distribution Method", 9.0, 0xF2E8DD);
    for (index, label) in LABELS.into_iter().enumerate() {
        let left = x + ROW_LEFT + index as f32 * BUTTON_SPACING;
        let top = y + ROW_TOP;
        horizon_client::widgets::record(label, [left, top, BUTTON_SIZE, BUTTON_SIZE], true);
        if mode as usize == index {
            game.native_sprite(
                draw,
                background,
                [0.0, 44.0, 22.0, 20.0],
                [left - 1.0, top, 22.0, 20.0],
            );
        }
        game.native_sprite(
            draw,
            "create:gui/icons",
            [64.0 + index as f32 * 16.0, 64.0, 16.0, 16.0],
            [left + 2.0, top + 2.0, 16.0, 16.0],
        );
    }
    center(draw, LABELS[mode as usize], 49.0, 0xF2E8DD);
}

pub(super) fn screen_click(at: [f32; 2]) -> Option<i32> {
    option_at(at).map(|id| id as i32)
}

pub(super) fn tooltip(at: [f32; 2], lines: &mut Vec<String>) {
    if let Some(id) = option_at(at) {
        lines.push(LABELS[id].into());
    }
}

pub(super) fn menu_button(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    mode: i32,
) {
    if !(SPLIT..=SYNCHRONIZE).contains(&mode) {
        return;
    }
    let Some((_, _, movement, _)) = feed_point(game, down(pos)) else {
        return;
    };
    entity.nbt.insert(MODE.into(), Tag::Int(mode));
    entity.data = vec![mode];
    for linked in group(game, pos, movement)
        .into_iter()
        .filter(|&linked| linked != pos)
    {
        game.native_with_mod_block_entity(linked, |tunnel| {
            tunnel.nbt.insert(MODE.into(), Tag::Int(mode));
            tunnel.data = vec![mode];
        });
        game.native_block_entity_sync(linked);
    }
    game.native_block_entity_sync(pos);
}
