use std::cell::RefCell;
use std::collections::HashMap;

use horizon_core::geometry::trig::{RAD_TO_DEG, atan2};
use horizon_core::geometry::{Aabb, Vec3};
use horizon_world::nbt::{Compound, Tag};

use super::create_chain_conveyor::loop_position;
use super::create_chain_conveyor_packages::{attach_port, insert_player_package, package};
use super::create_machines::{CONVEYOR, FROGPORT, mod_entity, set_float};
use super::{Game, Hand};
use crate::items::ItemStack;

const PACKAGE_PORT_RANGE: f64 = 5.0;
type SelectionKey = ([i32; 4], String, String);
pub(super) struct Target {
    pub(super) conveyor: [i32; 3],
    pub(super) edge: Option<[i32; 3]>,
    pub(super) position: f32,
    pub(super) anchor: [f64; 3],
}

thread_local! {
    static TARGETS: RefCell<HashMap<SelectionKey, Target>> = RefCell::new(HashMap::new());
}

fn player_key(game: &mut Game<'_>) -> SelectionKey {
    (
        game.acting_player_uuid(),
        game.level.name.clone(),
        game.native_dimension().into(),
    )
}

fn angle(game: &Game<'_>, at: [i32; 3]) -> Option<f32> {
    let hit = game.pick().filter(|hit| hit.pos == at)?;
    let [ex, ey, ez] = game.aim()?.0;
    let eye = Vec3::new(ex, ey, ez);
    let [x, y, z] = at.map(f64::from);
    let bounds = Aabb::new(
        Vec3::new(x - 0.5, y, z - 0.5),
        Vec3::new(x + 1.5, y + 0.5, z + 1.5),
    );
    let [hx, hy, hz] = hit.point;
    // Include a hit where the loop and the ordinary outline share a surface.
    let endpoint = eye.add_vector(Vec3::new(hx - ex, hy - ey, hz - ez).scale(1.0000001));
    let intersection = bounds.clip(eye, endpoint)?;
    let angle = (f64::from(RAD_TO_DEG) * atan2(x + 0.5 - intersection.x, z + 0.5 - intersection.z)
        + 540.0) as f32
        % 360.0;
    Some((angle / 45.0).round() * 45.0)
}

pub(super) fn loop_target(game: &Game<'_>) -> Option<Target> {
    let at = game.pick()?.pos;
    if game.native_block(at) != CONVEYOR {
        return None;
    }
    let position = angle(game, at)?;
    Some(Target {
        conveyor: at,
        edge: None,
        position,
        anchor: loop_position(at, position),
    })
}

pub(super) fn selects_loop(game: &Game<'_>, at: [i32; 3], held: &ItemStack) -> bool {
    (held.item.as_ref() == FROGPORT || package(game, held))
        && game.native_block(at) == CONVEYOR
        && angle(game, at).is_some()
}

pub(super) fn click(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if !game.may_build() || game.hand != Hand::Main || game.native_block(at) != CONVEYOR {
        return false;
    }
    let Some(held) = game.held().cloned() else {
        return false;
    };
    let is_port = held.item.as_ref() == FROGPORT;
    if !is_port && !package(game, &held) {
        return false;
    }
    let Some(target) = loop_target(game) else {
        // A Frogport click on the conveyor is consumed even when the crosshair
        // misses the chain loop. Other blocks still use ordinary placement.
        return is_port;
    };
    apply(game, target, held);
    true
}

pub(super) fn apply(game: &mut Game<'_>, target: Target, held: ItemStack) {
    if held.item.as_ref() == FROGPORT {
        let key = player_key(game);
        TARGETS.with_borrow_mut(|targets| targets.insert(key, target));
    } else if insert_player_package(game, target.conveyor, target.position, target.edge, held) {
        game.with_hand(Hand::Main, |game| game.consume_held());
    }
}

pub(super) fn placed(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) {
    if stack.item.as_ref() != FROGPORT || game.native_block(pos) != FROGPORT {
        return;
    }
    if let Some(player) = game.native_acting_player() {
        let x = f64::from(pos[0]) + 0.5 - player.position[0];
        let z = f64::from(pos[2]) + 0.5 - player.position[2];
        let yaw = (atan2(x, z) * f64::from(RAD_TO_DEG)) as f32;
        let passive = (yaw / 11.25 + 0.5).floor() * 11.25;
        game.native_with_mod_block_entity(pos, |entity| {
            set_float(&mut entity.nbt, "PassiveYaw", passive)
        });
        game.native_block_entity_sync(pos);
    }
    let key = player_key(game);
    let Some(Target {
        conveyor,
        edge,
        position,
        anchor,
    }) = TARGETS.with_borrow_mut(|targets| targets.remove(&key))
    else {
        return;
    };
    if !mod_entity(game, conveyor).is_some_and(|entity| {
        entity.id == CONVEYOR
            && edge.is_none_or(|edge| {
                super::create_chain_conveyor_connect::links(&entity.nbt).any(|link| link == edge)
            })
    }) {
        return;
    }

    let [x, y, z] = pos.map(f64::from);
    let [dx, dy, dz] = [anchor[0] - x - 0.5, anchor[1] - y, anchor[2] - z - 0.5];
    if dy < 0.0 || dx * dx + dy * dy + dz * dz > PACKAGE_PORT_RANGE * PACKAGE_PORT_RANGE {
        return;
    }

    let port = std::array::from_fn(|axis| pos[axis] - conveyor[axis]);
    attach_port(game, conveyor, port, position, edge);
    let target = port.map(|axis| -axis);
    game.native_with_mod_block_entity(pos, |entity| {
        let mut binding = Compound::from([
            ("RelativePos".into(), Tag::IntArray(target.to_vec())),
            ("ChainPosition".into(), Tag::Float(position.to_bits())),
        ]);
        if let Some(edge) = edge {
            binding.insert("Connection".into(), Tag::IntArray(edge.to_vec()));
        }
        entity.nbt.insert("Target".into(), Tag::Compound(binding));
    });
    game.native_block_entity_sync(pos);
}
