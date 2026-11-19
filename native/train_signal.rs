use horizon_core::position::BlockPos;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;

use super::create_machines::{int, mod_entity, offset};
use super::create_station::{assembly_axis, targeting_position, valid_track};
use super::create_train_track::{Point, SignalSection, StationRoute, signal_exits};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const SIGNAL: &str = "create:track_signal";
pub(super) const INDICATOR_ON: &str = "create:block/track_signal/indicator_on";
pub(super) const INDICATOR_OFF: &str = "create:block/track_signal/indicator_off";
const ATTACHED: &str = "LinkedAt";
const REPORTED: &str = "Power";
const POWER_CHANGE: &str = "PowerChangedAt";
const FALL: &str = "PowerReleaseAt";
const ROUTE_STATE: &str = "RouteState";
const PREVIOUS_ROUTE_STATE: &str = "PreviousRouteState";
const ROUTE_CHANGED: &str = "RouteChangedAt";

thread_local! {
    static CHANGED_OUTPUTS: std::cell::RefCell<Vec<(usize, [i32; 3])>> =
        const { std::cell::RefCell::new(Vec::new()) };
}

pub(super) fn flush_outputs(game: &mut Game<'_>) {
    let world = std::ptr::from_ref(&game.world) as usize;
    let positions = CHANGED_OUTPUTS.with_borrow_mut(|pending| {
        pending
            .extract_if(.., |(owner, _)| *owner == world)
            .map(|(_, pos)| pos)
            .collect::<Vec<_>>()
    });
    for pos in positions {
        game.native_update_output_neighbors(game.native_dimension(), pos);
    }
}

fn text(nbt: &Compound, key: &str) -> Option<String> {
    match nbt.get(&key.into()) {
        Some(Tag::String(value)) => Some(value.to_string_lossy()),
        _ => None,
    }
}

fn time(nbt: &Compound, key: &str) -> Option<i64> {
    match nbt.get(&key.into()) {
        Some(Tag::Long(value)) => Some(*value),
        _ => None,
    }
}

pub(super) fn new_tag() -> Compound {
    Compound::from([
        ("State".into(), Tag::String("INVALID".into())),
        ("Overlay".into(), Tag::String("SKIP".into())),
        ("TargetDirection".into(), Tag::Byte(1)),
        (REPORTED.into(), Tag::Byte(0)),
    ])
}

fn set_power(game: &mut Game<'_>, pos: [i32; 3], powered: bool) {
    game.native_set_block_property_with(
        pos,
        "powered",
        if powered { "true" } else { "false" },
        flags::UPDATE_CLIENTS,
    );
}

pub(super) fn neighbor_changed(game: &mut Game<'_>, pos: [i32; 3]) {
    let active = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
    let powered = game.native_block_property(pos, "powered").as_deref() == Some("true");
    let now = game.world.game_time;
    if active {
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.remove(&FALL.into());
        });
        if !powered {
            set_power(game, pos, true);
        }
    } else if powered {
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.entry(FALL.into()).or_insert(Tag::Long(now + 4));
        });
    }
}

fn power_at_boundary(nbt: &Compound, now: i64) -> bool {
    let power = int(nbt, REPORTED) == Some(1);
    if time(nbt, POWER_CHANGE) == Some(now) {
        !power
    } else {
        power
    }
}

pub(super) fn wrench(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some((track, facing)) = mod_entity(game, pos).and_then(|e| targeting_position(&e.nbt, pos))
    else {
        return;
    };
    if valid_track(game, track).is_none() {
        return;
    }
    let next = if game.native_block_property(pos, "type").as_deref() == Some("cross_signal") {
        "entry_signal"
    } else {
        "cross_signal"
    };
    let members: Vec<_> = game
        .world
        .block_entities
        .iter()
        .filter_map(|(&(x, y, z), _)| {
            let peer = [x, y, z];
            let entry = mod_entity(game, peer).filter(|e| e.id == SIGNAL)?;
            (targeting_position(&entry.nbt, peer) == Some((track, facing))).then_some(peer)
        })
        .collect();
    for peer in members {
        game.native_with_mod_block_entity(peer, |entry| {
            entry
                .nbt
                .insert("RequestedType".into(), Tag::String(next.into()));
        });
    }
}

fn occupied_section(
    game: &Game<'_>,
    track: [i32; 3],
    front: bool,
    exclude: Option<u32>,
) -> (bool, bool) {
    let mut trains = super::create_train::wheel_positions(game, exclude).peekable();
    if trains.peek().is_none() {
        return (false, false);
    }
    let shape = game.native_block_property(track, "shape");
    let rail_axis = match shape.as_deref() {
        Some("xo") => 0,
        Some("zo") => 2,
        _ => return (false, false),
    };
    let side_axis = 2 - rail_axis;
    let sign = if front { -1 } else { 1 };
    let step = std::array::from_fn(|axis| if axis == rail_axis { sign } else { 0 });
    let boundaries: std::collections::HashSet<_> = game
        .world
        .block_entities
        .iter()
        .filter_map(|(&(x, y, z), _)| {
            let pos = [x, y, z];
            let entity = mod_entity(game, pos)
                .filter(|e| e.id == SIGNAL && time(&e.nbt, ATTACHED).is_some())?;
            targeting_position(&entity.nbt, pos).map(|(rail, _)| rail)
        })
        .collect();
    let mut has_curve = !super::create_track::curves_at(game, track).is_empty();
    let mut distance = 0.0;
    let mut cursor = track;
    let limit = loop {
        cursor = offset(cursor, step);
        if game.native_block(cursor) != super::create_track::TRACK
            || game.native_block_property(cursor, "shape") != shape
        {
            break distance + 0.5;
        }
        distance += 1.0;
        if boundaries.contains(&cursor) {
            break distance;
        }
        has_curve |= !super::create_track::curves_at(game, cursor).is_empty();
    };
    if has_curve && let Some(axis) = shape.as_deref().and_then(super::create_track::track_axis) {
        let axis = axis.scale(f64::from(sign));
        let section = SignalSection::walk(game, track, axis, &boundaries);
        if section.has_curve {
            let mut opposite = None;
            let mut occupied = false;
            let mut entering = false;
            for wheels in trains {
                if wheels.iter().any(|wheel| section.contains(*wheel)) {
                    occupied = true;
                    if wheels.iter().any(|wheel| !section.contains(*wheel)) {
                        let reverse = opposite.get_or_insert_with(|| {
                            SignalSection::walk(game, track, axis.reverse(), &boundaries)
                        });
                        entering |= wheels.iter().any(|wheel| reverse.contains(*wheel));
                    }
                }
            }
            return (occupied, entering);
        }
    }
    let middle = f64::from(track[rail_axis]) + 0.5;
    let side = f64::from(track[side_axis]) + 0.5;
    let height = f64::from(track[1]) + 1.0;
    let direction = f64::from(sign);
    let mut occupied = false;
    let mut entering_here = false;
    for wheels in trains {
        let mut start = f64::INFINITY;
        let mut end = f64::NEG_INFINITY;
        for wheel in wheels {
            let wheel = wheel.location().components();
            if (wheel[side_axis] - side).abs() <= 1.0e-6 && (wheel[1] - height).abs() <= 1.0e-6 {
                let here = (wheel[rail_axis] - middle) * direction;
                start = start.min(here);
                end = end.max(here);
            }
        }
        if end > 0.0 && start < limit {
            occupied = true;
            entering_here |= start <= 0.0 && end < limit;
        }
    }
    (occupied, entering_here)
}

#[derive(Clone, Copy)]
pub(super) struct SignalStop {
    pub(super) pos: [i32; 3],
    pub(super) distance: f64,
    pub(super) cross: bool,
}

fn forced_power(game: &Game<'_>, pos: [i32; 3], nbt: &Compound) -> bool {
    game.native_block_property(pos, "powered").as_deref() == Some("true")
        && time(nbt, FALL).is_none_or(|due| due > game.world.game_time)
}

fn route_signals<'a>(
    game: &'a Game<'_>,
    lead: Point,
    route: &'a StationRoute,
) -> impl Iterator<Item = (SignalStop, [i32; 3], bool, &'a Compound)> + 'a {
    game.world
        .block_entities
        .keys()
        .filter_map(move |&(x, y, z)| {
            let pos = [x, y, z];
            let signal = mod_entity(game, pos)
                .filter(|entry| entry.id == SIGNAL && time(&entry.nbt, ATTACHED).is_some())?;
            let (track, front) = targeting_position(&signal.nbt, pos)?;
            let direction = assembly_axis(game, track, front)?.map(|value| -value);
            let distance = lead.boundary_distance(game, route, track, direction, route.distance)?;
            let cross = game.native_block_property(pos, "type").as_deref() == Some("cross_signal");
            Some((
                SignalStop {
                    pos,
                    distance,
                    cross,
                },
                track,
                front,
                &signal.nbt,
            ))
        })
}

pub(super) fn forced_red_cost(game: &Game<'_>, lead: Point, route: &StationRoute) -> f64 {
    let signals: std::collections::HashSet<_> = route_signals(game, lead, route)
        .filter(|(stop, _, _, nbt)| forced_power(game, stop.pos, nbt))
        .map(|(_, track, front, _)| (track, front))
        .collect();
    400.0 * signals.len() as f64
}

pub(super) fn scan_route(
    game: &Game<'_>,
    train: u32,
    lead: Point,
    route: &StationRoute,
    limit: f64,
    prior: &[[i32; 3]],
) -> (Option<SignalStop>, Vec<SignalStop>) {
    let mut signals: Vec<_> = route_signals(game, lead, route).collect();
    signals.sort_by(|a, b| {
        a.0.distance
            .total_cmp(&b.0.distance)
            .then_with(|| a.0.pos.cmp(&b.0.pos))
    });

    let mut reserved: Vec<_> = signals
        .iter()
        .map(|(stop, _, _, _)| *stop)
        .filter(|stop| prior.contains(&stop.pos))
        .collect();
    let mut chain: Vec<SignalStop> = Vec::new();
    for (signal, track, front, nbt) in signals {
        if chain.is_empty() && signal.distance > limit {
            break;
        }
        // Navigation observes the due release before the lamp publishes it.
        let powered = forced_power(game, signal.pos, nbt);
        if powered
            || occupied_section(game, track, front, Some(train)).0
            || super::create_train::reservation_age(game, signal.pos, Some(train)).is_some()
        {
            reserved
                .retain(|stop| stop.pos != signal.pos && !chain.iter().any(|s| s.pos == stop.pos));
            return (Some(chain.first().copied().unwrap_or(signal)), reserved);
        }
        if signal.cross || !chain.is_empty() {
            chain.push(signal);
        }
        if !signal.cross {
            for stop in chain.drain(..) {
                if !reserved.iter().any(|s| s.pos == stop.pos) {
                    reserved.push(stop);
                }
            }
        }
    }
    for stop in chain {
        if !reserved.iter().any(|s| s.pos == stop.pos) {
            reserved.push(stop);
        }
    }
    (None, reserved)
}

fn reported_occupancy(
    game: &Game<'_>,
    entity: &mut ModBlockEntity,
    track: [i32; 3],
    front: bool,
) -> bool {
    let (occupied, entering_here) = occupied_section(game, track, front, None);
    let old = int(&entity.nbt, "SectionOccupied") == Some(1);
    let now = game.world.game_time;
    if occupied != old {
        let delay = if occupied && !entering_here { 1 } else { 2 };
        entity
            .nbt
            .insert("SectionOccupied".into(), Tag::Byte(i8::from(occupied)));
        entity
            .nbt
            .insert("SectionUpdateAt".into(), Tag::Long(now + delay));
    }
    if time(&entity.nbt, "SectionUpdateAt").is_some_and(|due| now < due) {
        !occupied
    } else {
        occupied
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
#[repr(i8)]
enum RouteState {
    Green,
    Yellow,
    Red,
}

impl RouteState {
    fn from_nbt(value: Option<i32>) -> Self {
        match value {
            Some(1) => Self::Yellow,
            Some(2) => Self::Red,
            _ => Self::Green,
        }
    }

    fn text(self) -> &'static str {
        match self {
            Self::Green => "GREEN",
            Self::Yellow => "YELLOW",
            Self::Red => "RED",
        }
    }
}

fn downstream_state(game: &Game<'_>, track: [i32; 3], front: bool) -> RouteState {
    let Some(axis) = valid_track(game, track) else {
        return RouteState::Green;
    };
    let peers = game
        .world
        .block_entities
        .iter()
        .filter_map(|(&(x, y, z), _)| {
            let pos = [x, y, z];
            let peer = mod_entity(game, pos)
                .filter(|entry| entry.id == SIGNAL && time(&entry.nbt, ATTACHED).is_some())?;
            let (rail, direction) = targeting_position(&peer.nbt, pos)?;
            Some(((rail, direction), pos, peer))
        })
        .collect::<Vec<_>>();
    let boundaries = peers.iter().map(|((rail, _), _, _)| *rail).collect();
    let axis = if front { axis.reverse() } else { axis };
    let exits = signal_exits(game, track, axis, &boundaries);
    let now = game.world.game_time;
    let mut states = peers.into_iter().filter_map(|(key, pos, peer)| {
        if !exits.contains(&key) {
            return None;
        }
        if super::create_train::reservation_age(game, pos, None) == Some(1)
            && time(&peer.nbt, POWER_CHANGE) == Some(now - 1)
            && int(&peer.nbt, REPORTED) == Some(0)
        {
            return Some(RouteState::Green);
        }
        // The graph compares the raw boundary state, before the lamp's grace period.
        let field = if time(&peer.nbt, ROUTE_CHANGED) == Some(now) {
            PREVIOUS_ROUTE_STATE
        } else {
            ROUTE_STATE
        };
        Some(RouteState::from_nbt(int(&peer.nbt, field)))
    });
    let state = states.next().unwrap_or(RouteState::Green);
    if states.any(|other| other != state) {
        RouteState::Yellow
    } else {
        state
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let now = game.world.game_time;
    if time(&entity.nbt, FALL).is_some_and(|due| now >= due) {
        entity.nbt.remove(&FALL.into());
        if game.native_neighbor_signal(game.native_dimension(), pos) == 0 {
            set_power(game, pos, false);
        }
    }
    let cross = game.native_block_property(pos, "type").as_deref() == Some("cross_signal");
    if let Some(Tag::String(next)) = entity.nbt.remove(&"RequestedType".into()) {
        game.native_set_block_property_with(
            pos,
            "type",
            &next.to_string_lossy(),
            flags::UPDATE_ALL,
        );
    }
    let before = text(&entity.nbt, "State").unwrap_or_else(|| "INVALID".to_owned());
    let Some((track, front)) =
        targeting_position(&entity.nbt, pos).filter(|(at, _)| valid_track(game, *at).is_some())
    else {
        entity.nbt.remove(&ATTACHED.into());
        entity.nbt.remove(&ROUTE_STATE.into());
        entity.nbt.remove(&PREVIOUS_ROUTE_STATE.into());
        entity.nbt.remove(&ROUTE_CHANGED.into());
        publish(game, pos, entity, "INVALID", "RENDER", before != "INVALID");
        return;
    };
    let attached = time(&entity.nbt, ATTACHED).unwrap_or(now);
    entity.nbt.entry(ATTACHED.into()).or_insert(Tag::Long(now));

    let mut first = None;
    let mut sides = [false; 2];
    let occupied = reported_occupancy(game, entity, track, front);
    let mut wants_red = power_at_boundary(&entity.nbt, now)
        || occupied
        || super::create_train::reservation_age(game, pos, None).is_some_and(|age| age >= 2);
    for (peer, peer_front) in
        std::iter::once((pos, front)).chain(game.world.block_entities.iter().filter_map(
            |(&(x, y, z), _)| {
                let peer = [x, y, z];
                let entry = mod_entity(game, peer)
                    .filter(|e| e.id == SIGNAL && time(&e.nbt, ATTACHED).is_some())?;
                let (peer_track, peer_front) = targeting_position(&entry.nbt, peer)?;
                if peer_track != track {
                    return None;
                }
                if peer_front == front {
                    wants_red |= power_at_boundary(&entry.nbt, now);
                }
                Some((peer, peer_front))
            },
        ))
    {
        let key = (!peer_front, peer);
        first = Some(first.map_or(key, |prior| key.min(prior)));
        sides[usize::from(peer_front)] = true;
    }
    let route = if wants_red {
        RouteState::Red
    } else if cross {
        downstream_state(game, track, front)
    } else {
        RouteState::Green
    };
    let previous = RouteState::from_nbt(int(&entity.nbt, ROUTE_STATE));
    if route != previous {
        entity
            .nbt
            .insert(ROUTE_STATE.into(), Tag::Byte(route as i8));
        entity
            .nbt
            .insert(PREVIOUS_ROUTE_STATE.into(), Tag::Byte(previous as i8));
        entity.nbt.insert(ROUTE_CHANGED.into(), Tag::Long(now));
    }
    let overlay = match first {
        Some((_, first_pos)) if first_pos == pos => {
            if sides == [true, true] {
                "DUAL"
            } else {
                "RENDER"
            }
        }
        _ => "SKIP",
    };

    let power = game.native_block_property(pos, "powered").as_deref() == Some("true");
    let power_changed = (int(&entity.nbt, REPORTED) == Some(1)) != power;
    if power_changed {
        entity
            .nbt
            .insert(REPORTED.into(), Tag::Byte(i8::from(power)));
        entity.nbt.insert(POWER_CHANGE.into(), Tag::Long(now));
    }
    let state = if now == attached {
        "INVALID"
    } else if route == RouteState::Red && now < time(&entity.nbt, "GreenUntil").unwrap_or(now) {
        &before
    } else {
        route.text()
    };
    if state != before && (state == "GREEN" || state == "YELLOW") {
        entity.nbt.insert("GreenUntil".into(), Tag::Long(now + 15));
    }
    publish(
        game,
        pos,
        entity,
        state,
        overlay,
        power_changed || state != before,
    );
}

fn publish(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    state: &str,
    overlay: &str,
    changed: bool,
) {
    let overlay_changed = text(&entity.nbt, "Overlay").as_deref() != Some(overlay);
    let previously_red = text(&entity.nbt, "State").as_deref() == Some("RED");
    if previously_red != (state == "RED") {
        let world = std::ptr::from_ref(&game.world) as usize;
        // A neighboring comparator must read this entity after its ticker puts it back.
        CHANGED_OUTPUTS.with_borrow_mut(|pending| pending.push((world, pos)));
    }
    if changed || overlay_changed {
        entity.nbt.insert("State".into(), Tag::String(state.into()));
        entity
            .nbt
            .insert("Overlay".into(), Tag::String(overlay.into()));
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn has_output(level: &GameLevel<'_>, state: BlockStateId, output: &mut bool) {
    *output |= level.native_state_block(state) == Some(SIGNAL);
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, output: &mut i32) {
    if level.native_state_block(state) == Some(SIGNAL)
        && let Some(crate::containers::BlockEntity::Mod(entity)) =
            level.world.block_entities.get(&(pos.x, pos.y, pos.z))
        && text(&entity.nbt, "State").as_deref() == Some("RED")
    {
        *output = 15;
    }
}

pub(super) fn render(game: &Game<'_>, entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    let red = match text(&entity.nbt, "State").as_deref() {
        Some("RED") => true,
        Some("INVALID") | None => game.ticks % 40 < 3,
        _ => false,
    };
    let ambient = draw.light;
    if red {
        // Java LightTexture.FULL_BLOCK sets block light to 15 and sky light to zero.
        draw.light = 240 << 8;
    }
    game.native_draw_model(
        draw,
        if red { INDICATOR_ON } else { INDICATOR_OFF },
        0xFFFFFF,
    );
    draw.light = ambient;
}
