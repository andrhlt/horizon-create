// Curve map-marker rasterization from Create's BezierConnection.
use super::create_track_curve::Curve;
use horizon_core::geometry::Vec3;
use std::collections::HashMap;

pub(super) const FAKE_TRACK: &str = "create:fake_track";

fn slerp(t: f32, a: Vec3, b: Vec3) -> Vec3 {
    if a == b {
        return a;
    }
    // Catnip VecHelper.slerp uses Minecraft's float sine lookup.
    let angle = a.dot(b).acos();
    let sin = |v: f32| horizon_core::geometry::trig::sin(f64::from(v)) as f32;
    a.scale(f64::from(sin(1.0 - t)) * angle)
        .add_vector(b.scale(f64::from(sin((angle * f64::from(t)) as f32))))
        .scale(f64::from(1.0_f32 / sin(angle as f32)))
}

fn doubled(a: (i32, i32), b: (i32, i32), c: (i32, i32)) -> bool {
    let (x, z) = (b.0 - a.0, b.1 - a.1);
    let (xx, zz) = (c.0 - b.0, c.1 - b.1);
    x.abs() + z.abs() == 1 && xx.abs() + zz.abs() == 1 && x != xx && z != zz
}

pub(super) fn rasterise(curve: Curve) -> Vec<[i32; 3]> {
    let count = curve.segments as usize;
    if count == 0 {
        return Vec::new();
    }
    let origin = curve.ends[0].pos;
    let base = Vec3::new(
        f64::from(origin[0]),
        f64::from(origin[1]),
        f64::from(origin[2]),
    );
    let lut = curve.step_lut();
    let center = curve.starts[0]
        .add_vector(curve.starts[1])
        .scale(0.5)
        .subtract(base);
    let mut levels = HashMap::<(i32, i32), f64>::new();
    let (mut prev, mut prev2, mut prev3) = (None, None, None);
    for (i, factor) in lut.iter().enumerate().take(count) {
        let t = (((i as f32 + 0.5) * factor / count as f32).clamp(0.0, 1.0)) as f64;
        let normal = slerp(t as f32, curve.ends[0].normal, curve.ends[1].normal);
        let point = curve
            .point(t)
            .subtract(base)
            .add_vector(Vec3::new(0.0, 3.0 / 16.0, 0.0))
            .add_vector(normal.scale(-0.25));
        let key = (point.x.floor() as i32, point.z.floor() as i32);
        let existed = levels.contains_key(&key);
        if levels.get(&key).is_some_and(|y| *y <= point.y) {
            continue;
        }
        levels.insert(key, point.y);
        if existed {
            continue;
        }
        if let (Some(a), Some(b), Some(c)) = (prev3, prev2, prev) {
            let via_prev = doubled(b, c, key);
            let via_prev2 = doubled(a, b, c);
            let dist = |p: (i32, i32)| {
                (f64::from(p.0) + 0.5 - center.x).powi(2)
                    + (f64::from(p.1) + 0.5 - center.z).powi(2)
            };
            let prev_closer = dist(c) > dist(b);
            if via_prev2 && (!via_prev || !prev_closer) {
                levels.remove(&b);
                prev2 = prev;
                prev = Some(key);
                continue;
            } else if via_prev && via_prev2 && prev_closer {
                levels.remove(&c);
                prev = Some(key);
                continue;
            }
        }
        prev3 = prev2;
        prev2 = prev;
        prev = Some(key);
    }
    levels
        .into_iter()
        .map(|((x, z), y)| {
            [
                origin[0] + x,
                origin[1] + y.floor() as i32 + 1,
                origin[2] + z,
            ]
        })
        .collect()
}

pub(super) fn manage(game: &mut super::Game<'_>, curve: Curve, remove: bool) {
    use horizon_world::{fluid::FluidKind, level::flags};
    for pos in rasterise(curve) {
        let state = game.world.block(pos[0], pos[1], pos[2]);
        let Some(old) = game.pack.assets.registry.state(state) else {
            continue;
        };
        let present = old.name == FAKE_TRACK;
        if remove {
            if present {
                let replacement = if old
                    .properties
                    .get("waterlogged")
                    .is_some_and(|v| v == "true")
                {
                    "minecraft:water"
                } else {
                    "minecraft:air"
                };
                if let Some(state) = game.pack.assets.registry.default_state(replacement) {
                    game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL);
                }
            }
            continue;
        }
        let fluid = game.res.behaviours().fluid(state);
        if fluid.kind() != FluidKind::Empty
            && !(fluid.kind() == FluidKind::Water && fluid.is_source())
        {
            continue;
        }
        if !present && game.res.behaviours().is_replaceable(state) {
            let registry = game.pack.assets.registry;
            let Some(default) = registry
                .default_state(FAKE_TRACK)
                .and_then(|id| registry.state(id))
            else {
                continue;
            };
            let mut next = default.clone();
            next.properties.insert(
                "waterlogged".into(),
                (fluid.kind() == FluidKind::Water).to_string(),
            );
            if let Some(state) = registry.id(&next) {
                game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL);
            }
        }
        game.native_with_mod_block_entity(pos, |entity| {
            if entity.id == FAKE_TRACK {
                entity.data = vec![3];
            }
        });
    }
}

pub(super) fn remove_markers(
    level: &mut super::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    curve: Curve,
) {
    use horizon_world::level::flags;
    for at in rasterise(curve) {
        let state = level.world.block(at[0], at[1], at[2]);
        let Some(block) = level.registry.state(state) else {
            continue;
        };
        if block.name != FAKE_TRACK {
            continue;
        }
        let replacement = if block
            .properties
            .get("waterlogged")
            .is_some_and(|v| v == "true")
        {
            "minecraft:water"
        } else {
            "minecraft:air"
        };
        if let Some(state) = level.registry.default_state(replacement) {
            let behaviours = level.behaviours;
            behaviours.set_block(
                level,
                ticks,
                horizon_core::position::BlockPos::new(at[0], at[1], at[2]),
                state,
                flags::UPDATE_ALL,
            );
        }
    }
}
