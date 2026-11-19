use glam::Vec3;
use horizon_assets::bake::ModelQuad;
use horizon_assets::model::Direction as ModelDirection;
use horizon_client::models::catalog::BakedFace;
use horizon_client_render::connected::{Pick, TileLayer};
use horizon_core::{
    geometry::Direction,
    position::BlockPos,
    random::{LegacyRandom, RandomSource, position_seed},
};
use horizon_optifine::ctm::connect::{Axes, Face};
use horizon_world::registry::BlockStateId;

use super::Game;
use super::create_fluids::name as direction_name;
use super::native_block_entity_draw::BlockEntityDraw;
use crate::containers::BlockEntity;

#[derive(Clone, Copy)]
struct Piece {
    min: Vec3,
    max: Vec3,
    offset: Vec3,
    hidden: [Option<ModelDirection>; 2],
}

fn model_side(direction: Direction) -> ModelDirection {
    match direction {
        Direction::Up => ModelDirection::Up,
        Direction::Down => ModelDirection::Down,
        Direction::North => ModelDirection::North,
        Direction::South => ModelDirection::South,
        Direction::West => ModelDirection::West,
        Direction::East => ModelDirection::East,
    }
}

fn pieces(draw_shape: Shape) -> Vec<Piece> {
    let facing = draw_shape.facing;
    let front = model_side(facing);
    let rear = model_side(facing.opposite());
    let normal = Vec3::from_array(facing.normal().map(|n| n as f32));
    let mut pieces = Vec::with_capacity(if draw_shape.step { 4 } else { 2 });
    if !draw_shape.step {
        for near in [false, true] {
            let cut = normal * if near { 15.0 / 16.0 } else { 14.0 / 16.0 };
            let sample_start = if near {
                Vec3::ZERO
            } else {
                normal * (14.0 / 16.0)
            };
            pieces.push(Piece {
                min: -cut.min(Vec3::ZERO) + sample_start,
                max: Vec3::ONE - cut.max(Vec3::ZERO) + sample_start,
                offset: if near {
                    Vec3::ZERO
                } else {
                    normal * (-13.0 / 16.0)
                },
                hidden: [Some(if near { front } else { rear }), None],
            });
        }
    } else {
        let cut = normal * -0.75 + Vec3::Y * 0.75;
        for top in [false, true] {
            for near in [false, true] {
                let origin = if near { normal * -0.75 } else { Vec3::ZERO };
                let origin = origin + if top { Vec3::Y * 0.75 } else { Vec3::ZERO };
                let offset = if near { normal * 0.5 } else { Vec3::ZERO };
                let offset = if top == draw_shape.top {
                    offset
                } else {
                    offset + Vec3::Y * if draw_shape.top { 0.5 } else { -0.5 }
                };
                pieces.push(Piece {
                    min: -cut.min(Vec3::ZERO) + origin,
                    max: Vec3::ONE - cut.max(Vec3::ZERO) + origin,
                    offset,
                    hidden: [
                        Some(if near { front } else { rear }),
                        Some(if top {
                            ModelDirection::Down
                        } else {
                            ModelDirection::Up
                        }),
                    ],
                });
            }
        }
    }
    pieces
}

fn uv_rate(b: Vec3, a: Vec3, end: f32, start: f32) -> f32 {
    let length = b.distance(a);
    if length > 0.0 {
        (((end - start) * 16.0 / length) + 0.5).floor() / 16.0
    } else {
        0.0
    }
}

fn crop(quad: &ModelQuad, piece: Piece) -> ModelQuad {
    let points = quad.positions.map(Vec3::from_array);
    let [a, b, c, d] = points;
    let center = (a + b + c + d) * 0.25;
    let mut axes = [(d + c) * 0.5, (b + c) * 0.5];
    let origin = quad.uv[0];
    let mut factors = [
        uv_rate(d, a, quad.uv[3][0], origin[0]),
        uv_rate(b, a, quad.uv[1][1], origin[1]),
    ];
    if factors[0] == 0.0 {
        axes.swap(0, 1);
        factors = [
            uv_rate(b, a, quad.uv[1][0], origin[0]),
            uv_rate(d, a, quad.uv[3][1], origin[1]),
        ];
    }
    let axes = axes.map(|end| (end - center).normalize_or_zero());
    let mut cut = quad.clone();
    for (index, point) in points.into_iter().enumerate() {
        let new = point.clamp(piece.min, piece.max);
        let diff = new - point;
        cut.uv[index][0] += axes[0].dot(diff) * factors[0];
        cut.uv[index][1] += axes[1].dot(diff) * factors[1];
        cut.positions[index] = (new + piece.offset).to_array();
    }
    cut
}

#[derive(Clone, Copy)]
struct Shape {
    facing: Direction,
    step: bool,
    top: bool,
}

fn copycat_facing(state: &horizon_world::chunk::BlockState) -> Option<Direction> {
    let name = state.properties.get("facing")?;
    Direction::ALL
        .into_iter()
        .find(|&direction| direction_name(direction) == name)
}

fn copied_material(game: &Game<'_>, [x, y, z]: [i32; 3]) -> Option<BlockStateId> {
    let Some(BlockEntity::Mod(copycat)) = game.world.block_entities.get(&(x, y, z)) else {
        return None;
    };
    super::create_copycat::material(game, &copycat.nbt)
}

fn vertical(direction: Direction) -> bool {
    matches!(direction, Direction::Up | Direction::Down)
}

fn can_occlude(shape: Shape, face: Direction) -> bool {
    if shape.step {
        if vertical(face) {
            shape.top == (face == Direction::Up)
        } else {
            shape.facing == face
        }
    } else {
        shape.facing.opposite() == face
    }
}

fn wrapper_hides_face(
    shape: Shape,
    neighbour: &horizon_world::chunk::BlockState,
    facing: Direction,
    face: Direction,
) -> bool {
    let towards_own = if shape.step { face.opposite() } else { face };
    if shape.step {
        let top = neighbour
            .properties
            .get("half")
            .is_some_and(|half| half == "top");
        if top != shape.top {
            return vertical(towards_own) && top == (towards_own == Direction::Up);
        }
        if vertical(towards_own) {
            return false;
        }
    }
    if facing == shape.facing.opposite() {
        towards_own == facing
    } else {
        facing == shape.facing && towards_own != facing && towards_own != facing.opposite()
    }
}

fn material_face_hidden(
    game: &Game<'_>,
    pos: [i32; 3],
    shape: Shape,
    material: BlockStateId,
    face: Direction,
) -> bool {
    // Create draws the face opposite an occludable side in the unculled list.
    if can_occlude(shape, face.opposite()) {
        return false;
    }
    let [dx, dy, dz] = face.normal();
    let target = [pos[0] + dx, pos[1] + dy, pos[2] + dz];
    let raw = game.world.block(target[0], target[1], target[2]);
    let Some(neighbour) = game.pack.assets.registry.state(raw) else {
        return false;
    };
    let table = &game.pack.context.tables.visibility;
    let skips = |first, second| {
        table
            .skip_rendering(first, second, face, true)
            .unwrap_or(false)
    };
    let panel = neighbour.name == super::create_copycat::PANEL;
    let step = neighbour.name == super::create_copycat::STEP;
    if (panel || step)
        && let Some(facing) = copycat_facing(neighbour)
        && let Some(other) = copied_material(game, target)
        && skips(other, material)
    {
        if (step && shape.step || panel && !shape.step)
            && wrapper_hides_face(shape, neighbour, facing, face)
        {
            return true;
        }
        if panel && facing == face && can_occlude(shape, face) {
            return true;
        }
    }
    can_occlude(shape, face)
        && (skips(material, raw)
            || table
                .occlusion_face(raw, face.opposite())
                .is_some_and(|(id, _)| id == 1))
}

fn projected(
    game: &Game<'_>,
    pos: [i32; 3],
    shape: Shape,
    surface: Direction,
    offset: [i32; 3],
) -> BlockStateId {
    let facing = shape.facing;
    let normal = facing.normal();
    let [dx, dy, dz] = offset;
    let target = [pos[0] + dx, pos[1] + dy, pos[2] + dz];
    let raw = game.world.block(target[0], target[1], target[2]);
    let Some(state) = game.pack.assets.registry.state(raw) else {
        return raw;
    };
    let toward_front: i32 = (0..3).map(|axis| offset[axis] * normal[axis]).sum();
    let surface_normal = surface.normal();
    let blocker = (0..3).any(|axis| offset[axis] * surface_normal[axis] != 0);

    if shape.step {
        if state.name != super::create_copycat::STEP || offset == facing.opposite().normal() {
            return game.world.air;
        }
        let other_top = state
            .properties
            .get("half")
            .is_some_and(|half| half == "top");
        if dy != 0 {
            if other_top == shape.top || other_top != (dy < 0) {
                return game.world.air;
            }
        } else {
            let other = copycat_facing(state);
            let opposed = other == Some(facing.opposite());
            if other_top != shape.top || !(opposed || other == Some(facing) && toward_front == 0) {
                return game.world.air;
            }
            if opposed && toward_front != 1 {
                return raw;
            }
        }
        // A half-height Step cannot block the long side of this window.
        if blocker {
            return raw;
        }
    } else {
        if offset == normal {
            return game.world.air;
        }
        if state.name != super::create_copycat::PANEL {
            return if toward_front == 1 {
                game.world.air
            } else {
                raw
            };
        }
        let Some(other) = copycat_facing(state) else {
            return raw;
        };
        if other != facing.opposite() && !(other == facing && toward_front == 0) {
            return game.world.air;
        }
        // An opposed Panel exposes its material when queried across its aligned side.
        if other == facing.opposite() && toward_front != -1 {
            return raw;
        }
        if blocker && other != surface {
            return raw;
        }
    }
    copied_material(game, target).unwrap_or(raw)
}

fn connected_tile(
    game: &Game<'_>,
    pos: [i32; 3],
    shape: Shape,
    material: BlockStateId,
    face: &BakedFace,
    model_variant: usize,
) -> Option<(u32, bool, bool)> {
    let direction = Direction::ALL[face.quad.facing as usize];
    let texture_face = Face::ALL[face.quad.facing as usize];
    let result = game.pack.render.connected.pick_with_model_variant(
        material.0,
        face.layer as u16,
        texture_face,
        pos,
        |offset| projected(game, pos, shape, direction, offset).0,
        || None,
        || Axes::texture(&face.quad.positions, &face.quad.uv),
        |_| {},
        model_variant,
    );
    match result {
        Pick::Tile(TileLayer::Layer {
            layer,
            opaque,
            translucent,
        }) => Some((u32::from(layer), opaque, translucent)),
        _ => None,
    }
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    material: BlockStateId,
    draw: &mut BlockEntityDraw,
    pos: [i32; 3],
) {
    let Some(facing) = game
        .native_block_state_property(state, "facing")
        .and_then(|label| {
            Direction::ALL
                .into_iter()
                .find(|side| direction_name(*side) == label)
        })
    else {
        return;
    };
    let half = game.native_block_state_property(state, "half");
    let shape = Shape {
        facing,
        step: half.is_some(),
        top: half == Some("top"),
    };
    let facts = game.res.facts().get(material);
    let trapdoor = !shape.step && facts.has_class("TrapDoorBlock");
    let mut model_state = material;
    let bars = !shape.step && super::create_copycat::is_bars(&facts.name, facts);
    if bars {
        let registry = &game.pack.assets.registry;
        if let Some(mut state) = registry
            .default_state("create:copycat_bars")
            .and_then(|id| registry.state(id))
            .cloned()
        {
            state
                .properties
                .insert("facing".into(), direction_name(facing).into());
            if let Some(bars_state) = registry.id(&state) {
                model_state = bars_state;
            }
        }
    }
    let name = facts.name.as_ref();
    let connected_window = name.starts_with("create:")
        && (name.ends_with("framed_glass") || name.ends_with("_window"));
    let slices = pieces(shape);
    let seed = position_seed(BlockPos::new(pos[0], pos[1], pos[2]));
    let variant = if game
        .pack
        .render
        .connected
        .uses_java_model_random(material.0)
    {
        let mut random = LegacyRandom::new(seed);
        // A vanilla WeightedBakedModel chooses its model before the face chooses its texture.
        random.next_long();
        random
            .next_int_bound(4)
            .expect("four Weathered Iron variants") as usize
    } else {
        0
    };
    game.native_draw_transformed_block(draw, model_state, seed, |face, out| {
        let quad = &face.quad;
        if trapdoor || bars {
            out.push(quad.clone());
            return None;
        }
        if connected_window
            && quad.cull.is_some_and(|cull| {
                material_face_hidden(game, pos, shape, material, Direction::ALL[cull as usize])
            })
        {
            return None;
        }
        for &piece in &slices {
            if !piece.hidden.contains(&Some(quad.facing)) {
                out.push(crop(quad, piece));
            }
        }
        if connected_window {
            connected_tile(game, pos, shape, material, face, variant)
        } else {
            None
        }
    });
    if !connected_window {
        draw.keep();
    }
}
