use super::Game;
use super::remote_vehicles::ObjectHit;
use glam::{Quat, Vec3};
use horizon_core::geometry::{Aabb, Vec3 as GeometryVec3};

pub(super) fn bounds(open: bool, top: bool, facing: &str) -> Option<([f64; 3], [f64; 3])> {
    if !open {
        return Some((
            [0.0, if top { 0.8125 } else { 0.0 }, 0.0],
            [1.0, if top { 1.0 } else { 0.1875 }, 1.0],
        ));
    }
    match facing {
        "north" => Some(([0.0, 0.0, 0.8125], [1.0, 1.0, 1.0])),
        "south" => Some(([0.0, 0.0, 0.0], [1.0, 1.0, 0.1875])),
        "west" => Some(([0.8125, 0.0, 0.0], [1.0, 1.0, 1.0])),
        "east" => Some(([0.0, 0.0, 0.0], [0.1875, 1.0, 1.0])),
        _ => None,
    }
}

pub(super) fn client_pick(
    game: &Game<'_>,
    attacking: bool,
    original: Option<ObjectHit>,
) -> Option<ObjectHit> {
    if attacking {
        return original;
    }
    let Some((eye, direction)) = game.aim() else {
        return original;
    };
    let mut best = original;
    for display in game.text_displays.values() {
        let Some(state) = display.block_state() else {
            continue;
        };
        let Some(name) = game.native_state_block(state) else {
            continue;
        };
        let is_door = super::create_elevator_doors::sliding(name);
        if !is_door && !matches!(name, "create:train_trapdoor" | "create:framed_glass_trapdoor") {
            continue;
        }
        let top = game.native_block_state_property(state, "half") == Some("top");
        let Some(facing) = game.native_block_state_property(state, "facing") else {
            continue;
        };
        let rotation = Quat::from_array(display.data.left_rotation);
        if !rotation.is_finite() {
            continue;
        }
        let inv = rotation.conjugate();
        let origin = display.position();
        let relative = Vec3::new(
            (eye[0] - origin.x) as f32,
            (eye[1] - origin.y) as f32,
            (eye[2] - origin.z) as f32,
        );
        let local_eye = (inv * relative).to_array().map(f64::from);
        let local_dir = (inv * Vec3::from_array(direction.map(|v| v as f32)))
            .to_array()
            .map(f64::from);
        for (&id, proxy) in &game.interactions {
            if !proxy.response
                || proxy.width != 0.0
                || !(proxy.height == 0.0 || proxy.height == 0.0001)
            {
                continue;
            }
            let shape = if is_door {
                super::create_elevator_doors::train_door_pick_shape(
                    name,
                    proxy.height > 0.0,
                    game.native_block_state_property(state, "hinge") == Some("right"),
                    facing,
                )
            } else {
                bounds(proxy.height > 0.0, top, facing)
            };
            let Some((lo, hi)) = shape else { continue };
            let center = Vec3::new(
                ((lo[0] + hi[0]) * 0.5) as f32,
                lo[1] as f32,
                ((lo[2] + hi[2]) * 0.5) as f32,
            );
            let center = origin + (rotation * center).as_dvec3();
            let at = proxy.position.components();
            let d = (at[0] - center.x).powi(2)
                + (at[1] - center.y).powi(2)
                + (at[2] - center.z).powi(2);
            if d >= 0.04 {
                continue;
            }
            let box_at = Aabb::new(
                GeometryVec3::new(lo[0], lo[1], lo[2]),
                GeometryVec3::new(hi[0], hi[1], hi[2]),
            );
            let Some(distance) = super::ray_box(local_eye, local_dir, game.entity_reach, box_at)
            else {
                continue;
            };
            if best.as_ref().is_some_and(|hit| hit.distance <= distance) {
                continue;
            }
            best = Some(ObjectHit {
                id,
                distance,
                location: std::array::from_fn(|i| eye[i] + direction[i] * distance - at[i]),
            });
        }
    }
    best
}
