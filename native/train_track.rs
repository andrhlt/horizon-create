use std::collections::{HashMap, HashSet};

use horizon_core::geometry::Vec3;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_machines::offset;
use super::create_track::{TRACK, curves_at, track_axis};
use super::create_track_curve::{Curve, End};

const UP: Vec3 = Vec3::new(0.0, 1.0, 0.0);
const EPSILON: f64 = 1.0e-6;

fn vec(pos: [i32; 3]) -> Vec3 {
    let [x, y, z] = pos.map(f64::from);
    Vec3::new(x, y, z)
}

fn same(a: Vec3, b: Vec3) -> bool {
    a.distance_squared(b) < EPSILON * EPSILON
}

fn axes(shape: &str) -> Vec<Vec3> {
    let paths: &[&str] = match shape {
        "cr_o" => &["xo", "zo"],
        "cr_d" => &["pd", "nd"],
        "cr_pdx" => &["pd", "xo"],
        "cr_ndx" => &["nd", "xo"],
        "cr_pdz" => &["pd", "zo"],
        "cr_ndz" => &["nd", "zo"],
        _ => &[shape],
    };
    paths.iter().filter_map(|shape| track_axis(shape)).collect()
}

#[derive(Clone, Copy)]
enum Edge {
    Straight(End),
    Curve(Curve),
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum EdgeKey {
    Straight([i32; 3], [i32; 3]),
    Curve([i32; 3], [i32; 3]),
}

impl Edge {
    fn key(self) -> EdgeKey {
        match self {
            Self::Straight(end) => EdgeKey::Straight(
                end.pos,
                end.axis.components().map(|coordinate| coordinate as i32),
            ),
            Self::Curve(curve) => EdgeKey::Curve(curve.ends[0].pos, curve.ends[1].pos),
        }
    }

    fn length(self) -> f64 {
        match self {
            Self::Straight(end) => end.axis.length(),
            Self::Curve(curve) => curve.length,
        }
    }

    fn point(self, t: f64) -> Vec3 {
        match self {
            Self::Straight(end) => end.start().add_vector(end.axis.scale(t - 1.0)),
            Self::Curve(curve) => curve.point(f64::from(t as f32)),
        }
    }

    fn normal(self, t: f64) -> Vec3 {
        match self {
            Self::Straight(end) => end.normal,
            Self::Curve(curve) => {
                let derivative = curve.derivative(t as f32).normalize();
                let normal = curve.ends[0].normal.lerp(curve.ends[1].normal, t);
                derivative.cross(normal.cross(derivative).normalize())
            }
        }
    }

    fn endpoint(self, last: bool) -> (Vec3, Vec3, [i32; 3]) {
        match self {
            Self::Straight(end) => (
                if last {
                    end.start()
                } else {
                    end.start().subtract(end.axis)
                },
                end.axis.scale(if last { 1.0 } else { -1.0 }),
                end.pos,
            ),
            Self::Curve(curve) => {
                let i = usize::from(last);
                (
                    curve.starts[i],
                    curve.ends[i].axis.reverse(),
                    curve.ends[i].pos,
                )
            }
        }
    }

    fn reversed(self) -> Self {
        match self {
            Self::Straight(end) => Self::Straight(End {
                axis: end.axis.reverse(),
                ..end
            }),
            Self::Curve(mut curve) => {
                curve.starts.swap(0, 1);
                curve.ends.swap(0, 1);
                Self::Curve(curve)
            }
        }
    }

    fn advance(self, offset: f64, blocks: f64) -> f64 {
        match self {
            Self::Curve(curve) if blocks.abs() <= 5.0 => {
                let t = (offset / curve.length) as f32;
                offset + blocks * curve.length / curve.derivative(t).length()
            }
            _ => offset + blocks,
        }
    }

    fn continues(self, next: Self) -> bool {
        !match (self, next) {
            (Self::Straight(a), Self::Straight(b)) => a.pos == b.pos,
            (Self::Curve(a), Self::Curve(b)) => {
                a.ends.iter().all(|p| b.ends.iter().any(|q| p.pos == q.pos))
            }
            _ => false,
        }
    }
}

fn straight(at: [i32; 3], axis: Vec3) -> Edge {
    let normal = if axis.y == 0.0 {
        UP
    } else {
        UP.subtract(axis.horizontal().scale(axis.y)).normalize()
    };
    Edge::Straight(End {
        pos: at,
        axis,
        normal,
    })
}

fn open_edges(game: &Game<'_>, pos: [i32; 3]) -> Vec<Edge> {
    if game.native_block(pos) != TRACK {
        return Vec::new();
    }
    let mut edges = Vec::new();
    if let Some(shape) = game.native_block_property(pos, "shape") {
        for axis in axes(&shape) {
            edges.push(straight(pos, axis));
            edges.push(straight(pos, axis.reverse()));
        }
    }
    edges.extend(curves_at(game, pos).into_iter().map(Edge::Curve));
    edges
}

fn connected_edges(game: &Game<'_>, previous: Edge, last: bool) -> Vec<(f64, Edge)> {
    let (point, outgoing, origin) = previous.endpoint(last);
    let direction = outgoing.normalize();
    let mut possibilities = Vec::new();
    for x in -1..=1 {
        for y in -1..=1 {
            for z in -1..=1 {
                let pos = offset(origin, [x, y, z]);
                for edge in open_edges(game, pos) {
                    let (start, opposite, _) = edge.endpoint(false);
                    let next = opposite.reverse().normalize();
                    let dot = direction.dot(next);
                    if same(start, point) && previous.continues(edge) {
                        possibilities.push((dot, edge));
                    }
                }
            }
        }
    }
    possibilities
}

fn station_graph_node(edge: Edge, connections: &[(f64, Edge)]) -> bool {
    let [(dot, next)] = connections else {
        return true;
    };
    if *dot < 1.0 - EPSILON || matches!(edge, Edge::Curve(_)) || matches!(next, Edge::Curve(_)) {
        return true;
    }
    let point = edge.endpoint(true).0;
    let centered_x = (point.x - point.x.round()).abs() > EPSILON;
    let centered_z = (point.z - point.z.round()).abs() > EPSILON;
    let coordinate = if centered_x && !centered_z {
        point.z
    } else {
        point.x
    };
    coordinate.round() as i32 % 16 == 0
}

fn following(game: &Game<'_>, previous: Edge, last: bool, steer: i32) -> Option<Edge> {
    let (point, outgoing, _) = previous.endpoint(last);
    let direction = outgoing.normalize();
    connected_edges(game, previous, last)
        .into_iter()
        .filter(|(dot, _)| *dot > 0.875)
        .map(|(dot, edge)| {
            let exit = edge.endpoint(true).0;
            let turn = direction.cross(point.vector_to(exit).normalize()).y;
            let rank = if steer == 0 {
                -turn.abs()
            } else {
                turn * f64::from(steer)
            };
            (rank, dot, edge)
        })
        .max_by(|a, b| a.0.total_cmp(&b.0).then(a.1.total_cmp(&b.1)))
        .map(|(_, _, edge)| if last { edge } else { edge.reversed() })
}

pub(super) fn signal_exits(
    game: &Game<'_>,
    track: [i32; 3],
    axis: Vec3,
    boundaries: &HashSet<[i32; 3]>,
) -> HashSet<([i32; 3], bool)> {
    let start = straight(track, axis);
    let mut visited = HashSet::from([start.key()]);
    let mut frontier = vec![start];
    let mut exits = HashSet::new();
    while let Some(edge) = frontier.pop() {
        for (dot, next) in connected_edges(game, edge, true) {
            if dot <= 0.875 || !visited.insert(next.key()) {
                continue;
            }
            if let Edge::Straight(end) = next
                && boundaries.contains(&end.pos)
            {
                if let Some(axis) = game
                    .native_block_property(end.pos, "shape")
                    .as_deref()
                    .and_then(track_axis)
                {
                    exits.insert((end.pos, end.axis.dot(axis) < 0.0));
                }
                continue;
            }
            frontier.push(next);
        }
    }
    exits
}

pub(super) struct SignalSection {
    spans: HashMap<EdgeKey, (f64, f64)>,
    pub(super) has_curve: bool,
}

impl SignalSection {
    pub(super) fn walk(
        game: &Game<'_>,
        track: [i32; 3],
        axis: Vec3,
        boundaries: &HashSet<[i32; 3]>,
    ) -> Self {
        let mut spans = HashMap::new();
        let mut has_curve = false;
        let first = straight(track, axis);
        let mut frontier = vec![(first, first.length() * 0.5)];
        while let Some((edge, from)) = frontier.pop() {
            let key = edge.key();
            if spans.contains_key(&key) {
                continue;
            }
            let stops = matches!(edge, Edge::Straight(end) if end.pos == track || boundaries.contains(&end.pos))
                && key != first.key();
            let length = edge.length();
            let to = if stops { length * 0.5 } else { length };
            spans.insert(key, (from, to));
            has_curve |= matches!(edge, Edge::Curve(_));
            if !stops {
                // A section occupies the connected rails even where a train cannot take
                // the branch without reversing.
                frontier.extend(
                    connected_edges(game, edge, true)
                        .into_iter()
                        .map(|(_, next)| (next, 0.0)),
                );
            }
        }
        Self { spans, has_curve }
    }

    pub(super) fn contains(&self, point: Point) -> bool {
        let contains = |edge: Edge, offset: f64| {
            self.spans
                .get(&edge.key())
                .is_some_and(|&(from, to)| offset >= from && offset <= to)
        };
        contains(point.edge, point.offset)
            || contains(point.edge.reversed(), point.edge.length() - point.offset)
    }
}

fn routed_next(game: &Game<'_>, current: Edge, route: &StationRoute) -> Option<Edge> {
    let key = route.next.get(&current.key())?;
    connected_edges(game, current, true)
        .into_iter()
        .find_map(|(_, edge)| (edge.key() == *key).then_some(edge))
}

pub(super) struct StationRoute {
    pub(super) distance: f64,
    pub(super) curve_ahead: Option<f64>,
    station_order: (u8, f64),
    next: HashMap<EdgeKey, EdgeKey>,
}

impl StationRoute {
    pub(super) fn station_order(&self, other: &Self) -> std::cmp::Ordering {
        self.station_order
            .0
            .cmp(&other.station_order.0)
            .then_with(|| self.station_order.1.total_cmp(&other.station_order.1))
            .then_with(|| self.distance.total_cmp(&other.distance))
    }
}

#[derive(Clone, Copy)]
pub(super) struct Point {
    edge: Edge,
    offset: f64,
}

impl Point {
    pub(super) fn start(at: [i32; 3], assembly: [i32; 3], coordinate: f64) -> Self {
        let at_block = coordinate.floor();
        let tile = offset(at, assembly.map(|n| n * at_block as i32));
        let edge = straight(tile, vec(assembly).reverse());
        Self {
            edge,
            offset: 1.0 - (coordinate - at_block),
        }
    }

    pub(super) fn location(self) -> Vec3 {
        let t = (self.offset / self.edge.length()).clamp(0.0, 1.0);
        self.edge.point(t).add_vector(self.edge.normal(t))
    }

    pub(super) fn in_curve(self) -> bool {
        matches!(self.edge, Edge::Curve(_))
    }

    pub(super) fn reversed(self) -> Self {
        Self {
            edge: self.edge.reversed(),
            offset: self.edge.length() - self.offset,
        }
    }

    pub(super) fn forward_station(
        self,
        game: &Game<'_>,
        track: [i32; 3],
        assembly: [i32; 3],
        limit: f64,
    ) -> Option<StationRoute> {
        let mut frontier = vec![(self.edge, -self.offset, None, None, None::<f64>)];
        let mut previous = HashMap::<EdgeKey, Option<EdgeKey>>::new();
        while let Some(index) = frontier
            .iter()
            .enumerate()
            .min_by(|(_, a), (_, b)| a.1.total_cmp(&b.1))
            .map(|(index, _)| index)
        {
            let (edge, prefix, parent, mut curve_ahead, graph_entry) = frontier.swap_remove(index);
            let key = edge.key();
            if previous.contains_key(&key) {
                continue;
            }
            previous.insert(key, parent);
            if matches!(edge, Edge::Curve(_)) && curve_ahead.is_none() {
                curve_ahead = Some(prefix.max(0.0));
            }
            if let Edge::Straight(end) = edge
                && end.pos == track
                && end.axis.components().map(|coordinate| coordinate as i32)
                    == assembly.map(|coordinate| -coordinate)
            {
                let distance = prefix + edge.length() * 0.5;
                if distance > 0.0 {
                    let station_order = if let Some(entry) = graph_entry {
                        let mut exit_edge = edge;
                        let mut exit_distance = prefix + edge.length();
                        loop {
                            let connections = connected_edges(game, exit_edge, true);
                            if station_graph_node(exit_edge, &connections) || exit_distance > limit
                            {
                                break;
                            }
                            exit_edge = connections[0].1;
                            exit_distance += exit_edge.length();
                        }
                        // Java evaluates stations when discovering an edge and again when visiting
                        // its endpoint. Beyond the search limit only the last discovery survives.
                        if exit_distance <= limit {
                            (1, exit_distance)
                        } else {
                            (2, -entry)
                        }
                    } else {
                        (0, distance)
                    };
                    let mut current = key;
                    let mut next = HashMap::new();
                    while let Some(parent) = previous[&current] {
                        next.insert(parent, current);
                        current = parent;
                    }
                    return Some(StationRoute {
                        distance,
                        curve_ahead,
                        station_order,
                        next,
                    });
                }
            }
            let prefix = prefix + edge.length();
            let connections = connected_edges(game, edge, true);
            let mut graph_entry = graph_entry;
            if limit.is_finite() && station_graph_node(edge, &connections) {
                if prefix > limit {
                    continue;
                }
                graph_entry = Some(prefix);
            }
            frontier.extend(
                connections
                    .into_iter()
                    .filter(|(dot, next)| *dot > 0.875 && !previous.contains_key(&next.key()))
                    .map(|(_, next)| (next, prefix, Some(key), curve_ahead, graph_entry)),
            );
        }
        None
    }

    pub(super) fn boundary_distance(
        self,
        game: &Game<'_>,
        route: &StationRoute,
        track: [i32; 3],
        direction: [i32; 3],
        limit: f64,
    ) -> Option<f64> {
        let mut current = self.edge;
        let mut prefix = -self.offset;
        while prefix <= limit {
            let length = current.length();
            let distance = prefix + length * 0.5;
            if distance >= -EPSILON
                && distance <= limit
                && current.key() == EdgeKey::Straight(track, direction)
            {
                return Some(distance.max(0.0));
            }
            current = routed_next(game, current, route)?;
            prefix += length;
        }
        None
    }

    pub(super) fn travel(
        &mut self,
        game: &Game<'_>,
        distance: f64,
        steer: i32,
        route: Option<&StationRoute>,
    ) -> (f64, bool) {
        if distance.abs() < 1.0e-5 {
            return (0.0, false);
        }
        let forward = distance > 0.0;
        self.offset = self.edge.advance(self.offset, distance);
        loop {
            let length = self.edge.length();
            let excess = if forward {
                self.offset - length
            } else {
                -self.offset
            };
            if excess <= 0.0 {
                return (distance, false);
            }
            let traversed = if forward {
                self.edge
            } else {
                self.edge.reversed()
            };
            let next = route
                .and_then(|route| routed_next(game, traversed, route))
                .map(|edge| if forward { edge } else { edge.reversed() })
                .or_else(|| following(game, self.edge, forward, steer));
            let Some(edge) = next else {
                self.offset = if forward { length } else { 0.0 };
                return (distance - excess.copysign(distance), true);
            };
            self.edge = edge;
            self.offset = if forward {
                excess
            } else {
                edge.length() - excess
            };
        }
    }

    pub(super) fn tag(self) -> Tag {
        let mut data = Compound::from([("Offset".into(), Tag::Double(self.offset.to_bits()))]);
        match self.edge {
            Edge::Straight(end) => {
                data.insert("Track".into(), Tag::IntArray(end.pos.to_vec()));
                data.insert(
                    "Axis".into(),
                    Tag::IntArray(end.axis.components().map(|x| x as i32).to_vec()),
                );
            }
            Edge::Curve(curve) => {
                data.insert("Track".into(), Tag::IntArray(curve.ends[0].pos.to_vec()));
                data.insert(
                    "ConnectsTo".into(),
                    Tag::IntArray(curve.ends[1].pos.to_vec()),
                );
            }
        }
        Tag::Compound(data)
    }

    pub(super) fn read(game: &Game<'_>, data: &Tag) -> Option<Self> {
        let read = |key| match data.get(key)? {
            Tag::IntArray(list) => <[i32; 3]>::try_from(list.as_slice()).ok(),
            _ => None,
        };
        let track = read("Track")?;
        let Tag::Double(offset) = data.get("Offset")? else {
            return None;
        };
        let edge = if let Some(to) = read("ConnectsTo") {
            Edge::Curve(
                curves_at(game, track)
                    .into_iter()
                    .find(|curve| curve.ends[1].pos == to)?,
            )
        } else {
            straight(track, vec(read("Axis")?))
        };
        Some(Self {
            edge,
            offset: f64::from_bits(*offset),
        })
    }
}

pub(super) fn center(points: &[Point]) -> Vec3 {
    points[0].location().lerp(points[1].location(), 0.5)
}

pub(super) fn drive(
    game: &Game<'_>,
    points: &mut [Point],
    speed: f64,
    spacing: i32,
    steer: i32,
    stop: Option<f64>,
    route: Option<&StationRoute>,
) -> (f64, bool) {
    let two = points.len() == 4;
    let stress = if two {
        f64::from(spacing) - center(&points[..2]).distance(center(&points[2..]))
    } else {
        0.0
    };
    let reversed = speed < 0.0;
    let count = points.len();
    let mut blocked = false;
    let mut distance = speed;
    for bogey in 0..count / 2 {
        let index = if reversed {
            count - 2 - bogey * 2
        } else {
            bogey * 2
        };
        let stretch = 2.0
            - points[index]
                .location()
                .distance(points[index + 1].location());
        let bogey_correction = stress * if index == 0 { 0.5 } else { -0.5 };
        for wheel in 0..2 {
            let i = if reversed { 1 - wheel } else { wheel };
            let correction = stretch * if i == 0 { 0.5 } else { -0.5 };
            let requested = distance + correction + bogey_correction;
            let requested = if bogey == 0 && wheel == 0 {
                stop.map_or(requested, |limit| {
                    if reversed {
                        requested.max(-limit)
                    } else {
                        requested.min(limit)
                    }
                })
            } else {
                requested
            };
            let (moved, stopped) = points[index + i].travel(game, requested, steer, route);
            blocked |= stopped;
            distance = moved;
        }
    }
    (distance, blocked)
}

/// Connected components of the currently loaded rails under the given stations.
pub(super) fn station_networks(game: &Game<'_>, tracks: &[([i32; 3], Vec3)]) -> Vec<i32> {
    let mut networks = HashMap::<EdgeKey, i32>::new();
    tracks
        .iter()
        .enumerate()
        .map(|(index, &(track, axis))| {
            let first = straight(track, axis);
            if let Some(&network) = networks.get(&first.key()) {
                return network;
            }
            let network = index as i32;
            let mut frontier = vec![first];
            while let Some(edge) = frontier.pop() {
                if networks.contains_key(&edge.key()) {
                    continue;
                }
                networks.insert(edge.key(), network);
                networks.insert(edge.reversed().key(), network);
                for side in [false, true] {
                    frontier.extend(
                        connected_edges(game, edge, side)
                            .into_iter()
                            .map(|(_, edge)| edge)
                            .filter(|edge| !networks.contains_key(&edge.key())),
                    );
                }
            }
            network
        })
        .collect()
}
