use std::{cell::RefCell, collections::{HashMap, HashSet}, sync::{Arc, Weak}};
use horizon_client::save::SaveDir;
use horizon_world::nbt::{Compound, Tag};
use super::Game;
use crate::items::ItemStack;

const DATA: &str = "CreateMinecartCoupling";
thread_local! {
    static SELECTED: RefCell<HashMap<Option<u128>, (Weak<SaveDir>, [i32; 4])>> = RefCell::new(HashMap::new());
}

// Java clears each player's pending selection when neither hand holds the item.
pub(super) fn tick_selection(game: &Game<'_>) {
    let is_coupling = |stack: Option<&ItemStack>| stack.is_some_and(|stack| stack.item.as_ref() == "create:minecart_coupling");
    if !is_coupling(game.stack_in(game.selected)) && !is_coupling(game.offhand.as_ref()) {
        SELECTED.with_borrow_mut(|selected| { selected.remove(&game.lan_acting_uuid); });
    }
}

fn pairs(game: &Game<'_>, uuid: [i32; 4]) -> Vec<(u32, [i32; 4])> {
    game.others.iter().filter_map(|marker| {
        if marker.kind != "minecraft:marker" { return None; }
        let Tag::Compound(raw) = game.persist.raw.get(&marker.id)? else { return None; };
        let Tag::Compound(pair) = raw.get(&DATA.into())? else { return None; };
        let (Some(Tag::IntArray(a)), Some(Tag::IntArray(b))) = (pair.get(&"A".into()), pair.get(&"B".into())) else { return None; };
        let other: [i32; 4] = if a.as_slice() == uuid { b.as_slice().try_into().ok()? } else if b.as_slice() == uuid { a.as_slice().try_into().ok()? } else { return None; };
        Some((marker.id, other))
    }).collect()
}

// A killed cart releases each loaded neighbour and drops one coupling at the midpoint.
// This is called only for terminal destruction, never for a chunk unload.
pub(super) fn cart_destroyed(game: &mut Game<'_>, id: u32) {
    let Some(cart) = game.carts.iter().find(|cart| cart.id == id) else { return; };
    cart_destroyed_at(game, id, cart.position);
}

// Exploding TNT carts have already left the cart list when the blast finishes.
pub(super) fn cart_destroyed_at(game: &mut Game<'_>, id: u32, pos: horizon_core::geometry::Vec3) {
    let Some(uuid) = game.persist.uuid_of(id) else { return; };
    let releases: Vec<_> = pairs(game, uuid).into_iter().filter_map(|(marker, other)| {
        let neighbour = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(other))?;
        Some((marker, [
            (pos.x + neighbour.position.x) * 0.5,
            (pos.y + neighbour.position.y) * 0.5,
            (pos.z + neighbour.position.z) * 0.5,
        ]))
    }).collect();
    for (marker, midpoint) in releases {
        game.native_remove_entity(game.native_dimension(), marker);
        game.spawn_item_own(ItemStack::new("create:minecart_coupling", 1), midpoint, 10);
    }
}

// Linked carts use Create's pinned Java Entity.move low-speed behavior.
pub(super) fn is_linked(game: &Game<'_>, id: u32) -> bool {
    game.persist.uuid_of(id).is_some_and(|uuid| !pairs(game, uuid).is_empty())
}

fn connected(game: &Game<'_>, start: [i32; 4], target: [i32; 4]) -> bool {
    let mut seen = HashSet::new();
    let mut pending = vec![start];
    while let Some(cart) = pending.pop() {
        if cart == target { return true; }
        if !seen.insert(cart) { continue; }
        pending.extend(pairs(game, cart).into_iter().map(|(_, other)| other));
    }
    false
}

pub(super) fn interact(game: &mut Game<'_>, id: u32, stack: Option<&ItemStack>) -> bool {
    let Some(held) = stack else { return false; };
    let Some(cart) = game.carts.iter().find(|cart| cart.id == id) else { return false; };
    let pos = cart.position;
    let uuid = game.uuid_for(id);
    if held.item.as_ref() == "create:wrench" {
        let links = pairs(game, uuid);
        if links.is_empty() { return false; }
        for (marker, _) in &links { game.native_remove_entity(game.native_dimension(), *marker); }
        if !game.creative { game.give_or_drop(ItemStack::new("create:minecart_coupling", links.len() as u32)); }
        return true;
    }
    if held.item.as_ref() != "create:minecart_coupling" { return false; }
    if pairs(game, uuid).len() >= 2 { return true; }
    let player = game.lan_acting_uuid;
    let previous = SELECTED.with_borrow_mut(|selected| {
        let previous = selected.get(&player).and_then(|(save, cart)| save.upgrade().filter(|saved| Arc::ptr_eq(saved, &game.save)).map(|_| *cart));
        if previous.is_none() || previous == Some(uuid) { selected.insert(player, (Arc::downgrade(&game.save), uuid)); } else { selected.remove(&player); }
        previous
    });
    let Some(first) = previous.filter(|first| *first != uuid) else { return true; };
    let Some(other) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(first)) else { return true; };
    let dx = other.position.x - pos.x;
    let dy = other.position.y - pos.y;
    let dz = other.position.z - pos.z;
    let length = (dx * dx + dy * dy + dz * dz).sqrt() as i32;
    if length > 32 || pairs(game, first).len() >= 2 || connected(game, first, uuid) { return true; }
    let data = Compound::from([
        ("A".into(), Tag::IntArray(first.to_vec())),
        ("B".into(), Tag::IntArray(uuid.to_vec())),
        ("Length".into(), Tag::Float((length.max(2) as f32).to_bits())),
    ]);
    let marker = Compound::from([
        ("Tags".into(), Tag::List(vec![Tag::String("create_minecart_coupling".into())])),
        (DATA.into(), Tag::Compound(data)),
    ]);
    if game.native_summon(game.native_dimension(), "minecraft:marker", [pos.x, pos.y, pos.z], marker).is_some() {
        game.consume_held();
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    true
}

// This initial physics slice covers two ordinary carts on the same flat straight
// track. Create's soft collision projects the predicted separation onto the
// rail and shares the resulting stress between the carts.
pub(super) fn tick_straight_pairs(game: &mut Game<'_>, move_cart: &mut impl FnMut(&mut Game<'_>, u32, [f64; 3])) {
    use super::minecarts::{CartKind, Shape};
    let mut links: Vec<([i32; 4], [i32; 4], f64)> = game.others.iter().filter_map(|marker| {
        let Tag::Compound(raw) = game.persist.raw.get(&marker.id)? else { return None; };
        let Tag::Compound(pair) = raw.get(&DATA.into())? else { return None; };
        let (Some(Tag::IntArray(a)), Some(Tag::IntArray(b)), Some(Tag::Float(length))) =
            (pair.get(&"A".into()), pair.get(&"B".into()), pair.get(&"Length".into())) else { return None; };
        Some((a.as_slice().try_into().ok()?, b.as_slice().try_into().ok()?, f32::from_bits(*length) as f64))
    }).collect();
    // Create iterates leading carts in a Java HashSet. Recognize isolated
    // directed two- and three-link paths and apply their edges in bucket order.
    // Colliding buckets need insertion history we do not have.
    let mut mask = 15_usize;
    while links.len() > (mask + 1) * 3 / 4 { mask = mask * 2 + 1; }
    let bucket = |id: [i32; 4]| {
        let hash = id.into_iter().fold(0_u32, |hash, word| hash ^ word as u32);
        ((hash ^ (hash >> 16)) as usize) & mask
    };
    let mut chain_edges = HashSet::new();
    for &(a, b, _) in &links {
        if pairs(game, a).len() != 1 || pairs(game, b).len() != 2 { continue; }
        let Some(&(middle, c, _)) = links.iter().find(|&&(start, end, _)| start == b && end != a) else { continue; };
        if bucket(a) == bucket(middle) { continue; }
        if pairs(game, c).len() == 1 {
            chain_edges.insert((a, b));
            chain_edges.insert((middle, c));
            continue;
        }
        if pairs(game, c).len() != 2 { continue; }
        let Some(&(third, d, _)) = links.iter().find(|&&(start, end, _)| start == c && end != middle) else { continue; };
        if d == a || d == b || pairs(game, d).len() != 1
            || bucket(third) == bucket(a) || bucket(third) == bucket(middle) { continue; }
        chain_edges.insert((a, b));
        chain_edges.insert((middle, c));
        chain_edges.insert((third, d));
    }
    links.sort_by_key(|link| bucket(link.0));
    for (a, b, length) in links {
        // Do not apply the pair solver independently to unsupported chain shapes.
        if !chain_edges.contains(&(a, b)) && (pairs(game, a).len() != 1 || pairs(game, b).len() != 1) { continue; }
        let Some(ai) = game.carts.iter().position(|cart| game.persist.uuid_of(cart.id) == Some(a)) else { continue; };
        let Some(bi) = game.carts.iter().position(|cart| game.persist.uuid_of(cart.id) == Some(b)) else { continue; };
        if ai == bi { continue; }
        let ca = &game.carts[ai];
        let cb = &game.carts[bi];
        if ca.kind != CartKind::Rideable || cb.kind != CartKind::Rideable { continue; }
        let isolated_pair = pairs(game, a).len() == 1 && pairs(game, b).len() == 1;
        if (isolated_pair || chain_edges.contains(&(a, b)))
            && tick_flat_curve_or_slope(game, ai, bi, length, !isolated_pair) {
            if !isolated_pair { tick_hard_chain_on_off_link(game, a, b, length, move_cart); }
            continue;
        }
        let ca = &game.carts[ai];
        let cb = &game.carts[bi];
        let rail_at = |p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32).map(|rail| rail.shape);
        let (Some(shape_a), Some(shape_b)) = (rail_at(ca.position), rail_at(cb.position)) else { continue; };
        if shape_a != shape_b || !matches!(shape_a, Shape::EastWest | Shape::NorthSouth) { continue; }
        let x_axis = shape_a == Shape::EastWest;
        let (pa, pb, va, vb, cross_a, cross_b) = if x_axis {
            (ca.position.x, cb.position.x, ca.velocity.x, cb.velocity.x, ca.position.z, cb.position.z)
        } else {
            (ca.position.z, cb.position.z, ca.velocity.z, cb.velocity.z, ca.position.x, cb.position.x)
        };
        if (cross_a - cross_b).abs() > 1e-6 || (ca.position.y - cb.position.y).abs() > 1e-6 { continue; }
        let predicted_a = pa + va.clamp(-1.0, 1.0);
        let predicted_b = pb + vb.clamp(-1.0, 1.0);
        let separation = predicted_b - predicted_a;
        if separation == 0.0 { continue; }
        let stress = (length - separation.abs()) as f32;
        if stress.abs() < 1.0e-5_f32 {
            if chain_edges.contains(&(a, b)) { tick_hard_straight_link(game, a, b, length, move_cart); }
            continue;
        }
        let correction = -(stress / 2.0) as f64 * separation.signum();
        let speed = 0.4_f32 as f64;
        let new_a = (va + correction.clamp(-speed, speed)).clamp(-speed, speed);
        let new_b = (vb - correction.clamp(-speed, speed)).clamp(-speed, speed);
        if x_axis { game.carts[ai].velocity.x = new_a; game.carts[bi].velocity.x = new_b; }
        else { game.carts[ai].velocity.z = new_a; game.carts[bi].velocity.z = new_b; }
        if chain_edges.contains(&(a, b)) { tick_hard_straight_link(game, a, b, length, move_cart); }
    }
}

// Java projects the three-dimensional predicted link onto each horizontal
// rail axis. This covers the measured flat curves and cardinal slopes.
fn tick_flat_curve_or_slope(game: &mut Game<'_>, ai: usize, bi: usize, length: f64, flat_only: bool) -> bool {
    use horizon_core::geometry::Vec3;
    use super::minecarts::Shape;
    let a = &game.carts[ai];
    let b = &game.carts[bi];
    let clamp = |v: Vec3, max: f64| {
        let size = v.length();
        if size > max { v.scale(max / size) } else { v }
    };
    let va = clamp(a.velocity, 1.0);
    let vb = clamp(b.velocity, 1.0);
    let pa = a.position.add_vector(va);
    let pb = b.position.add_vector(vb);
    let rail_at = |p: Vec3| {
        let x = p.x.floor() as i32;
        let y = p.y.floor() as i32;
        let z = p.z.floor() as i32;
        game.rail(x, y - 1, z).or_else(|| game.rail(x, y, z)).map(|rail| rail.shape)
    };
    let (sa, sb) = (rail_at(pa), rail_at(pb));
    if let (Some(sa), Some(sb)) = (sa, sb) {
        // The measured chain slope cases stay on an aligned cardinal axis.
        let east_slope = matches!(sa, Shape::EastWest | Shape::AscendingEast)
            && matches!(sb, Shape::EastWest | Shape::AscendingEast);
        let west_slope = matches!(sa, Shape::EastWest | Shape::AscendingWest)
            && matches!(sb, Shape::EastWest | Shape::AscendingWest);
        let south_slope = matches!(sa, Shape::NorthSouth | Shape::AscendingSouth)
            && matches!(sb, Shape::NorthSouth | Shape::AscendingSouth);
        let north_slope = matches!(sa, Shape::NorthSouth | Shape::AscendingNorth)
            && matches!(sb, Shape::NorthSouth | Shape::AscendingNorth);
        if flat_only && (sa.is_slope() || sb.is_slope())
            && !(((east_slope || west_slope) && (a.position.z - b.position.z).abs() < 1e-6)
                || ((south_slope || north_slope) && (a.position.x - b.position.x).abs() < 1e-6)) { return false; }
        // Keep the existing one-dimensional path for aligned straight rails.
        if sa == sb && matches!(sa, Shape::EastWest | Shape::NorthSouth)
            && (a.position.y - b.position.y).abs() < 1e-6
            && (pa.y - pb.y).abs() < 1e-6
            && (if sa == Shape::EastWest { pa.z - pb.z } else { pa.x - pb.x }).abs() < 1e-6
            && rail_at(a.position) == Some(sa) && rail_at(b.position) == Some(sb)
        { return false; }
    }
    let diagonal = 1.0 / 2.0_f64.sqrt();
    let axis = |shape| match shape {
        Shape::EastWest | Shape::AscendingEast | Shape::AscendingWest => Some(Vec3::new(1.0, 0.0, 0.0)),
        Shape::NorthSouth | Shape::AscendingNorth | Shape::AscendingSouth => Some(Vec3::new(0.0, 0.0, 1.0)),
        Shape::NorthEast | Shape::SouthWest => Some(Vec3::new(diagonal, 0.0, diagonal)),
        Shape::NorthWest | Shape::SouthEast => Some(Vec3::new(diagonal, 0.0, -diagonal)),
        _ => None,
    };
    let (ra, rb) = (sa.and_then(axis), sb.and_then(axis));
    if (sa.is_some() && ra.is_none()) || (sb.is_some() && rb.is_none()) { return false; }
    let link = pa.vector_to(pb);
    let distance = link.length();
    let stress = (length - distance) as f32;
    if stress.abs() < 1e-5 { return true; }
    let magnitude = (-stress / 2.0) as f64;
    let speed = 0.4_f32 as f64;
    let correction = |link: Vec3, rail: Option<Vec3>| {
        let Some(rail) = rail else {
            return if distance == 0.0 { Vec3::ZERO } else { clamp(link.scale(magnitude / distance), speed) };
        };
        let dot = rail.dot(link);
        if dot == 0.0 { return Vec3::ZERO; }
        let direction = rail.scale(-dot.signum());
        let projection = -direction.dot(link);
        let radius = distance - magnitude;
        let discriminant = projection * projection - (distance * distance - radius * radius);
        let scale = if discriminant >= 0.0 { -projection + discriminant.sqrt() } else { -projection };
        clamp(direction.scale(scale), speed)
    };
    let new_a = clamp(va.add_vector(correction(link, ra)), speed);
    let new_b = clamp(vb.add_vector(correction(link.reverse(), rb)), speed);
    game.carts[ai].velocity = new_a;
    game.carts[bi].velocity = new_b;
    true
}

// The captured Java flat-rail case resolves hard stress through Entity.move
// after its soft velocity update. Keep this to standalone, dry, flat pairs;
// the caller supplies the cart actuator so collisions are not bypassed.
pub(super) fn tick_hard_straight_pairs(
    game: &mut Game<'_>,
    mut move_cart: impl FnMut(&mut Game<'_>, u32, [f64; 3]),
) {
    let links: Vec<([i32; 4], [i32; 4], f64)> = game.others.iter().filter_map(|marker| {
        let Tag::Compound(raw) = game.persist.raw.get(&marker.id)? else { return None; };
        let Tag::Compound(pair) = raw.get(&DATA.into())? else { return None; };
        let (Some(Tag::IntArray(a)), Some(Tag::IntArray(b)), Some(Tag::Float(length))) =
            (pair.get(&"A".into()), pair.get(&"B".into()), pair.get(&"Length".into())) else { return None; };
        Some((a.as_slice().try_into().ok()?, b.as_slice().try_into().ok()?, f32::from_bits(*length) as f64))
    }).collect();
    for (a, b, length) in links {
        if pairs(game, a).len() != 1 || pairs(game, b).len() != 1 { continue; }
        tick_hard_straight_link(game, a, b, length, &mut move_cart);
    }
}


// One Java hard pass is performed immediately after its chain edge's soft pass.
fn tick_hard_straight_link(
    game: &mut Game<'_>, a: [i32; 4], b: [i32; 4], length: f64,
    move_cart: &mut impl FnMut(&mut Game<'_>, u32, [f64; 3]),
) {
    use super::minecarts::{CartKind, Shape};
    let Some(ai) = game.carts.iter().position(|cart| game.persist.uuid_of(cart.id) == Some(a)) else { return; };
    let Some(bi) = game.carts.iter().position(|cart| game.persist.uuid_of(cart.id) == Some(b)) else { return; };
    if ai == bi { return; }
    let ca = &game.carts[ai];
    let cb = &game.carts[bi];
    if ca.kind != CartKind::Rideable || cb.kind != CartKind::Rideable || ca.in_water || cb.in_water { return; }
    let rail = |p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32).map(|rail| rail.shape);
    let (Some(sa), Some(sb)) = (rail(ca.position), rail(cb.position)) else { return; };
    if sa != sb || !matches!(sa, Shape::EastWest | Shape::NorthSouth) { return; }
    let x_axis = sa == Shape::EastWest;
    let cross = if x_axis { ca.position.z - cb.position.z } else { ca.position.x - cb.position.x };
    if cross.abs() > 1e-6 || (ca.position.y - cb.position.y).abs() > 1e-6 { return; }
    // Java asks the block above getCurrentRailPosition; only its observed
    // non-rail Entity.move branch is represented here.
    let above_rail = |p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32 + 1, p.z.floor() as i32).is_some();
    if above_rail(ca.position) || above_rail(cb.position) { return; }
    let mut first = true;
    for (current, other) in [(a, b), (b, a), (a, b)] {
        let Some(cart) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(current)) else { break; };
        let Some(peer) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(other)) else { break; };
        let separation = if x_axis { peer.position.x - cart.position.x } else { peer.position.z - cart.position.z };
        let stress = (length - separation.abs()) as f32;
        if stress.abs() < 0.125 { continue; }
        if separation == 0.0 { continue; }
        let magnitude = if first { -stress / 2.0 } else { -stress };
        let correction = ((magnitude as f64) * separation.signum()).clamp(-(0.4_f32 as f64), 0.4_f32 as f64);
        let id = cart.id;
        move_cart(game, id, if x_axis { [correction, 0.0, 0.0] } else { [0.0, 0.0, correction] });
        first = false;
    }
}

fn slope_hard_rail_above(game: &Game<'_>, p: horizon_core::geometry::Vec3) -> bool {
    game.rail(p.x.floor() as i32, p.y.floor() as i32 + 1, p.z.floor() as i32).is_some()
}

// Captured cardinal-slope, opposing south-curve, and off-rail hard resolution uses
// Entity.move, not the rail-following branch. Apply it only to standalone
// dry pairs with no rail directly above; use the collision-aware actuator.
pub(super) fn tick_hard_cardinal_slope_pairs(
    game: &mut Game<'_>,
    mut move_cart: impl FnMut(&mut Game<'_>, u32, [f64; 3]),
) {
    use super::minecarts::{CartKind, Shape};
    let links: Vec<([i32; 4], [i32; 4], f64)> = game.others.iter().filter_map(|marker| {
        let Tag::Compound(raw) = game.persist.raw.get(&marker.id)? else { return None; };
        let Tag::Compound(pair) = raw.get(&DATA.into())? else { return None; };
        let (Some(Tag::IntArray(a)), Some(Tag::IntArray(b)), Some(Tag::Float(length))) =
            (pair.get(&"A".into()), pair.get(&"B".into()), pair.get(&"Length".into())) else { return None; };
        Some((a.as_slice().try_into().ok()?, b.as_slice().try_into().ok()?, f32::from_bits(*length) as f64))
    }).collect();
    for (a, b, length) in links {
        if pairs(game, a).len() != 1 || pairs(game, b).len() != 1 { continue; }
        let Some(ca) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(a)) else { continue; };
        let Some(cb) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(b)) else { continue; };
        if ca.id == cb.id || ca.kind != CartKind::Rideable || cb.kind != CartKind::Rideable || ca.in_water || cb.in_water { continue; }
        let rail_at = |game: &Game<'_>, p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32).map(|rail| rail.shape);
        let (sa, sb) = (rail_at(game, ca.position), rail_at(game, cb.position));
        let rail_below = |game: &Game<'_>, p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32 - 1, p.z.floor() as i32).is_some();
        let both_off = sa.is_none() && sb.is_none() && !rail_below(game, ca.position) && !rail_below(game, cb.position);
        if let (Some(sa), Some(sb)) = (sa, sb) {
            let x_axis = matches!(sa, Shape::EastWest | Shape::AscendingEast | Shape::AscendingWest);
            let same_axis = if x_axis {
                matches!(sb, Shape::EastWest | Shape::AscendingEast | Shape::AscendingWest)
            } else {
                matches!(sa, Shape::NorthSouth | Shape::AscendingNorth | Shape::AscendingSouth)
                    && matches!(sb, Shape::NorthSouth | Shape::AscendingNorth | Shape::AscendingSouth)
            };
            let cross = if x_axis { ca.position.z - cb.position.z } else { ca.position.x - cb.position.x };
            let slope_pair = same_axis && (sa.is_slope() || sb.is_slope()) && cross.abs() <= 1e-6;
            let opposing_south_curves = matches!((sa, sb),
                (Shape::SouthEast, Shape::SouthWest) | (Shape::SouthWest, Shape::SouthEast))
                && (ca.position.z - cb.position.z).abs() <= 1e-6
                && (ca.position.y - cb.position.y).abs() <= 1e-6;
            if !slope_pair && !opposing_south_curves { continue; }
        } else if !both_off { continue; }
        if slope_hard_rail_above(game, ca.position) || slope_hard_rail_above(game, cb.position) { continue; }
        tick_hard_3d_link(game, a, b, length, &mut move_cart, both_off);
    }
}


// Apply the same collision-aware 3D hard iterations used for isolated pairs.
fn tick_hard_3d_link(
    game: &mut Game<'_>, a: [i32; 4], b: [i32; 4], length: f64,
    move_cart: &mut impl FnMut(&mut Game<'_>, u32, [f64; 3]), both_off: bool,
) {
    let rail_at = |game: &Game<'_>, p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32).is_some();
    let rail_below = |game: &Game<'_>, p: horizon_core::geometry::Vec3| game.rail(p.x.floor() as i32, p.y.floor() as i32 - 1, p.z.floor() as i32).is_some();
    let mut first = true;
    for (current, other) in [(a, b), (b, a), (a, b)] {
        let Some(cart) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(current)) else { break; };
        let Some(peer) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(other)) else { break; };
        if slope_hard_rail_above(game, cart.position) { break; }
        if both_off && (rail_at(game, cart.position) || rail_below(game, cart.position)) { break; }
        let link = cart.position.vector_to(peer.position);
        let distance = link.length();
        let stress = (length - distance) as f32;
        if stress.abs() < 0.125 { continue; }
        if distance == 0.0 { continue; }
        let magnitude = if first { -stress / 2.0 } else { -stress };
        let correction = link.scale((magnitude as f64) / distance);
        let size = correction.length();
        let speed = 0.4_f32 as f64;
        let correction = if size > speed { correction.scale(speed / size) } else { correction };
        let id = cart.id;
        move_cart(game, id, correction.components());
        first = false;
    }
}

// The measured chain hard cases have at least one current off-rail endpoint.
fn tick_hard_chain_on_off_link(
    game: &mut Game<'_>, a: [i32; 4], b: [i32; 4], length: f64,
    move_cart: &mut impl FnMut(&mut Game<'_>, u32, [f64; 3]),
) {
    use super::minecarts::CartKind;
    let Some(ca) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(a)) else { return; };
    let Some(cb) = game.carts.iter().find(|cart| game.persist.uuid_of(cart.id) == Some(b)) else { return; };
    if ca.kind != CartKind::Rideable || cb.kind != CartKind::Rideable || ca.in_water || cb.in_water { return; }
    let on_rail = |p: horizon_core::geometry::Vec3| {
        let (x, y, z) = (p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32);
        game.rail(x, y, z).is_some() || game.rail(x, y - 1, z).is_some()
    };
    let (a_on_rail, b_on_rail) = (on_rail(ca.position), on_rail(cb.position));
    if a_on_rail && b_on_rail { return; }
    if slope_hard_rail_above(game, ca.position) || slope_hard_rail_above(game, cb.position) { return; }
    tick_hard_3d_link(game, a, b, length, move_cart, !a_on_rail && !b_on_rail);
}
