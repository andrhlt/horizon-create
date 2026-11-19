use horizon_core::geometry::trig::{RAD_TO_DEG, atan2, sine_table};
use horizon_core::geometry::{Aabb, Vec3};

use super::create_chain_conveyor::Span;
use super::create_chain_conveyor_connect::{CHAIN, disconnect, links};
use super::create_chain_conveyor_packages::{package, retrieve};
use super::create_chain_conveyor_target::{Target, apply};
use super::create_machines::{CONVEYOR, FROGPORT, int, mod_entity, offset};
use super::{Game, GuestUse, Hand};
use crate::items::ItemStack;

const WRENCH: &str = "create:wrench";
const RADIUS: f64 = 0.175;

fn rotation(angle: f64) -> (f64, f64) {
    let phase = (angle / 180.0 * std::f64::consts::PI) as f32 * 10430.378_f32;
    let table = sine_table();
    (
        f64::from(table[(phase as i32 & 65535) as usize]),
        f64::from(table[((phase + 16384.0) as i32 & 65535) as usize]),
    )
}

pub(super) fn rotate_y(v: Vec3, angle: f64) -> Vec3 {
    let (sin, cos) = rotation(angle);
    Vec3::new(v.x * cos + v.z * sin, v.y, v.z * cos - v.x * sin)
}

fn rotate_x(v: Vec3, angle: f64) -> Vec3 {
    let (sin, cos) = rotation(angle);
    Vec3::new(v.x, v.y * cos - v.z * sin, v.z * cos + v.y * sin)
}

fn clipped_span(
    span: &Span,
    edge: [i32; 3],
    from: Vec3,
    to: Vec3,
) -> Option<(Vec3, f32, [f64; 3])> {
    let start = Vec3::new(span.start[0], span.start[1], span.start[2]);
    let end = Vec3::new(span.end[0], span.end[1], span.end[2]);
    let diff = end.subtract(start);
    let xz = (diff.x * diff.x + diff.z * diff.z).sqrt();
    let yaw = f64::from(RAD_TO_DEG) * atan2(diff.x, diff.z);
    let pitch = f64::from(RAD_TO_DEG) * atan2(-diff.y, xz);
    let inverse = |v: Vec3| rotate_x(rotate_y(v.subtract(start), -yaw), -pitch);
    let bounds = Aabb::new(
        Vec3::new(-RADIUS, -RADIUS, 0.0),
        Vec3::new(RADIUS, RADIUS, diff.length()),
    );
    let local_hit = bounds.clip(inverse(from), inverse(to))?;
    let transform = |v: Vec3| start.add_vector(rotate_y(rotate_x(v, pitch), yaw));
    let hit = transform(local_hit);
    let length = diff.length();
    let [dx, dy, dz] = edge.map(f64::from);
    let dots = ((dx * dx + dy * dy + dz * dz).sqrt() - 3.0).round();
    let margin = length - dots;
    let selection = hit.subtract(start).length().min(length);
    let position = ((selection - margin)
        .max(0.0)
        .min(length - margin * 2.0)
        .round()
        + margin
        + 0.025) as f32;
    let anchor = transform(Vec3::new(0.0, 0.0, f64::from(position).clamp(0.0, length)));
    Some((hit, position, [anchor.x, anchor.y, anchor.z]))
}

pub(super) fn nearest_span(game: &Game<'_>) -> Option<Target> {
    let (eye, direction) = game.aim()?;
    let eye = Vec3::new(eye[0], eye[1], eye[2]);
    let max = game.reach() + 1.0;
    let direction = Vec3::new(direction[0], direction[1], direction[2]);
    let end = eye.add_vector(direction.scale(max));
    let limit = game.pick().map_or(max * max, |hit| {
        Vec3::new(hit.point[0], hit.point[1], hit.point[2])
            .subtract(eye)
            .length_squared()
    });
    let mut closest = None;
    let mut distance = limit;
    for (&(x, y, z), _) in game.world.block_entities.iter() {
        let at = [x, y, z];
        let Some(entity) = mod_entity(game, at).filter(|entity| entity.id == CONVEYOR) else {
            continue;
        };
        let reversed = int(&entity.nbt, "Reversed") == Some(1);
        for edge in links(&entity.nbt) {
            let other = offset(at, edge);
            if !mod_entity(game, other).is_some_and(|other| {
                other.id == CONVEYOR && links(&other.nbt).any(|back| back == edge.map(|axis| -axis))
            }) {
                continue;
            }
            let span = Span::new(at, edge, reversed);
            if let Some((hit, position, anchor)) = clipped_span(&span, edge, eye, end) {
                let hit_distance = hit.subtract(eye).length_squared();
                if hit_distance <= distance {
                    distance = hit_distance;
                    closest = Some(Target {
                        conveyor: at,
                        edge: Some(edge),
                        position,
                        anchor,
                    });
                }
            }
        }
    }
    closest
}

fn wrench(game: &mut Game<'_>) -> Option<Hand> {
    if !game.may_build()
        || !game.native_sneaking()
        || matches!(game.guest_use, Some(GuestUse::Entity(..)))
    {
        return None;
    }
    let hand = Hand::BOTH.into_iter().find(|hand| {
        let stack = match hand {
            Hand::Main => game.stack_in(game.selected),
            Hand::Off => game.offhand.as_ref(),
        };
        stack.is_some_and(|stack| stack.item.as_ref() == WRENCH)
    })?;
    let target = nearest_span(game)?;
    disconnect(game, target.conveyor, target.edge?);
    Some(hand)
}

pub(super) fn selects_span(game: &Game<'_>, stack: &ItemStack) -> bool {
    (stack.item.as_ref() == FROGPORT || package(game, stack)) && nearest_span(game).is_some()
}

pub(super) fn use_target(game: &mut Game<'_>) -> Option<Hand> {
    if let Some(hand) = wrench(game) {
        return Some(hand);
    }
    if !game.may_build()
        || matches!(
            game.guest_use,
            Some(GuestUse::Entity(..) | GuestUse::Item(Hand::Off) | GuestUse::OnBlock(Hand::Off))
        )
    {
        return None;
    }
    if game.guest_use.is_none()
        && let Some(hand) = super::create_chain_conveyor_rider::board(game)
    {
        return Some(hand);
    }
    let held = game.stack_in(game.selected).cloned();
    if let Some(held) = &held {
        let item = held.item.as_ref();
        if item == FROGPORT || package(game, held) {
            if let Some(target) = nearest_span(game) {
                apply(game, target, held.clone());
                return Some(Hand::Main);
            }
            if item == FROGPORT
                || game.pick().is_some_and(|hit| {
                    super::create_chain_conveyor_target::selects_loop(game, hit.pos, held)
                })
            {
                return None;
            }
        }
        if matches!(item, CHAIN | WRENCH) {
            return None;
        }
    }
    // The guest sends Item.use only with a held stack. An empty hand
    // here means the preceding block use in this click spent that stack.
    if held.is_none() && matches!(game.guest_use, Some(GuestUse::Item(Hand::Main))) {
        return None;
    }
    retrieve(game).then_some(Hand::Main)
}
