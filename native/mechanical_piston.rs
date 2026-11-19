use horizon_core::geometry::Direction;
use horizon_world::level::{LevelAccess, PlacementContext, flags};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;

use super::create_bearing::{
    attached_glue, capture_from, display, move_glue, relative, restore, saved_block,
};
use super::create_depot::compound;
use super::create_fan::facing;
use super::create_machines::{float, int, offset, set_float, string};
use super::{Game, GameLevel};

pub(super) const PISTON: &str = "create:mechanical_piston";
pub(super) const STICKY: &str = "create:sticky_mechanical_piston";
pub(super) const POLE: &str = "create:piston_extension_pole";
pub(super) const HEAD: &str = "create:mechanical_piston_head";

const MAX_POLES: i32 = 64;
const CHASSIS_RANGE: i32 = 16;
const MOVE_FLAGS: i32 = flags::UPDATE_ALL | flags::UPDATE_SKIP_BLOCK_ENTITY_SIDEEFFECTS;

pub(super) fn set_mode(game: &mut Game<'_>, pos: [i32; 3], mode: i32) {
    let updated = game.native_with_mod_block_entity(pos, |entity| {
        if !matches!(entity.id.as_str(), PISTON | STICKY) || int(&entity.nbt, "ScrollValue").unwrap_or(0) == mode { return false; }
        entity.nbt.insert("ScrollValue".into(), Tag::Int(mode.clamp(0, 2)));
        entity.nbt.remove(&"Waiting".into());
        true
    });
    if updated == Some(true) { game.native_block_entity_sync(pos); }
}

fn position(origin: [i32; 3], normal: [i32; 3], distance: i32) -> [i32; 3] {
    offset(origin, normal.map(|step| step * distance))
}

fn axis(direction: Direction) -> usize {
    direction
        .normal()
        .iter()
        .position(|&step| step != 0)
        .unwrap()
}

fn read_face(game: &Game<'_>, at: [i32; 3]) -> Option<Direction> {
    facing(game, game.world.block(at[0], at[1], at[2]))
}

fn is_pole(game: &Game<'_>, at: [i32; 3], side: Direction) -> bool {
    game.native_block(at) == POLE
        && read_face(game, at).is_some_and(|direction| axis(direction) == axis(side))
}

fn pole(side: Direction, at: [i32; 3], anchor: [i32; 3], block: &str, sticky: bool) -> Compound {
    let mut props = Compound::from([
        (
            "facing".into(),
            Tag::String(super::create_fluids::name(side).into()),
        ),
        ("waterlogged".into(), Tag::String("false".into())),
    ]);
    if block == HEAD {
        props.insert(
            "type".into(),
            Tag::String(if sticky {
                "sticky".into()
            } else {
                "normal".into()
            }),
        );
    }
    Compound::from([
        (
            "BlockState".into(),
            Tag::Compound(Compound::from([
                ("Name".into(), Tag::String(block.into())),
                ("Properties".into(), Tag::Compound(props)),
            ])),
        ),
        (
            "Pos".into(),
            Tag::IntArray(std::array::from_fn::<_, 3, _>(|i| at[i] - anchor[i]).to_vec()),
        ),
    ])
}

fn has_clearance(
    game: &Game<'_>,
    anchor: [i32; 3],
    blocks: &[Compound],
    piston: [i32; 3],
    sources: &[[i32; 3]],
) -> bool {
    blocks.iter().all(|block| {
        let at = offset(anchor, relative(block));
        at == piston || sources.contains(&at) || game.native_block_collision(at).is_empty()
    })
}

fn assemble(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    side: Direction,
    speed: f32,
) -> Option<Vec<Compound>> {
    let normal = side.normal();
    let anchor = offset(pos, normal);
    let sticky = game.native_block(pos) == STICKY;
    let mut front = 0;
    let mut back = 0;
    let mut extensions = Vec::new();
    if game.native_block_property(pos, "state").as_deref() == Some("extended") {
        for distance in 1..=MAX_POLES + 1 {
            let at = position(pos, normal, distance);
            let head = game.native_block(at) == HEAD && read_face(game, at) == Some(side);
            if !head && !is_pole(game, at, side) {
                break;
            }
            extensions.push(at);
            front += 1;
            if head {
                break;
            }
        }
    }
    for distance in 1..=MAX_POLES + 1 {
        let at = position(pos, normal, -distance);
        if !is_pole(game, at, side) {
            break;
        }
        extensions.push(at);
        back += 1;
    }
    let length = front + back;
    if length == 0 || length > MAX_POLES || speed > 0.0 && back == 0 || speed < 0.0 && front == 0 {
        return None;
    }
    let start = position(anchor, normal, front);
    let mut seeds = Vec::new();
    if speed > 0.0 || sticky {
        // Retraction pulls the block directly on a sticky head. Extension can push a row.
        for distance in 0..if speed < 0.0 { 1 } else { CHASSIS_RANGE + 1 } {
            let at = position(start, normal, distance);
            if game.native_block_collision(at).is_empty() {
                break;
            }
            saved_block(game, at, start)?;
            seeds.push(at);
        }
    }
    let mut blocks = capture_from(game, pos, start, seeds);
    let sources: Vec<_> = blocks
        .iter()
        .map(|block| offset(start, relative(block)))
        .collect();
    let glue = attached_glue(game, &sources, start);
    for &at in &extensions {
        let block = if game.native_block(at) == HEAD {
            HEAD
        } else {
            POLE
        };
        blocks.push(pole(side, at, start, block, sticky));
    }
    blocks.push(pole(
        side,
        pos,
        start,
        if front == 0 { HEAD } else { POLE },
        sticky,
    ));
    let sources: Vec<_> = sources.into_iter().chain(extensions).collect();
    let next = position(start, normal, if speed > 0.0 { 1 } else { -1 });
    if !has_clearance(game, next, &blocks, pos, &sources) {
        return None;
    }
    let air = game.native_default_state("minecraft:air")?;
    let dim = game.native_dimension();
    let id = game.native_summon(
        dim,
        "minecraft:marker",
        start.map(f64::from),
        Compound::from([(
            "Tags".into(),
            Tag::List(vec![Tag::String("create_piston_payload".into())]),
        )]),
    )?;
    for source in sources {
        let prior = game.world.block(source[0], source[1], source[2]);
        let fluid = game.res.behaviours().fluid(prior);
        let retained =
            if fluid.kind() == horizon_world::fluid::FluidKind::Water && fluid.is_source() {
                game.res.behaviours().legacy_block(fluid)
            } else {
                air
            };
        game.native_set_block(dim, source, retained, MOVE_FLAGS);
    }
    game.native_set_block_property_with(pos, "state", "moving", flags::UPDATE_ALL);
    entity.nbt.insert("Payload".into(), Tag::Int(id as i32));
    entity.nbt.insert("Range".into(), Tag::Int(length));
    entity.nbt.insert("CreatePistonInitialOffset".into(), Tag::Int(front));
    entity.nbt.remove(&"Waiting".into());
    entity.nbt.insert("Glue".into(), Tag::List(glue));
    set_float(&mut entity.nbt, "Offset", front as f32);
    set_float(&mut entity.nbt, "PreviousOffset", front as f32);
    Some(blocks)
}

fn draw(
    game: &mut Game<'_>,
    entity: &mut ModBlockEntity,
    blocks: &mut [Compound],
    anchor: [i32; 3],
    normal: [i32; 3],
    distance: f32,
) {
    let location =
        std::array::from_fn(|i| f64::from(anchor[i]) + f64::from(normal[i]) * f64::from(distance));
    let dimension = game.native_dimension();
    if let Some(id) = int(&entity.nbt, "Payload") {
        game.native_move_entity(dimension, id as u32, location, 0.0, 0.0);
    }
    for block in blocks {
        display(game, anchor, block, 1, 0.0);
        if let Some(id) = int(block, "Display") {
            game.native_move_entity(dimension, id as u32, location, 0.0, 0.0);
        }
    }
}

fn disassemble(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    blocks: &mut Vec<Compound>,
    start: [i32; 3],
    extended: bool,
) -> bool {
    let dim = game.native_dimension();
    let placed: Vec<_> = blocks
        .iter()
        .filter(|block| offset(start, relative(block)) != pos)
        .cloned()
        .collect();
    // Keep the virtual head/pole inside the controller out of the static block layout.
    if !restore(game, start, &placed, 1, 0.0) {
        return false;
    }
    for block in blocks
        .iter()
        .filter(|block| offset(start, relative(block)) == pos)
    {
        if let Some(id) = int(block, "Display") {
            game.native_remove_entity(dim, id as u32);
        }
    }
    blocks.clear();
    if let Some(id) = int(&entity.nbt, "Payload") {
        game.native_remove_entity(dim, id as u32);
    }
    entity.nbt.remove(&"Payload".into());
    if let Some(Tag::List(glue)) = entity.nbt.remove(&"Glue".into()) {
        move_glue(game, &glue, start.map(f64::from));
    }
    game.native_set_block_property_with(
        pos,
        "state",
        if extended { "extended" } else { "retracted" },
        flags::UPDATE_ALL,
    );
    true
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    let Some(side) = read_face(game, pos) else {
        return;
    };
    let normal = side.normal();
    let sign = normal[axis(side)] as f32 * if axis(side) == 2 { 1.0 } else { -1.0 };
    let speed = (rpm / 512.0).clamp(-0.49, 0.49) * sign;
    let anchor = offset(pos, normal);
    let mut blocks: Vec<_> = match entity.nbt.remove(&"Blocks".into()) {
        Some(Tag::List(blocks)) => blocks
            .into_iter()
            .filter_map(|tag| match tag {
                Tag::Compound(block) => Some(block),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    };
    let previous_speed = float(&entity.nbt, "PistonSpeed").unwrap_or(f32::NAN);
    set_float(&mut entity.nbt, "PistonSpeed", speed);
    if blocks.is_empty() {
        if speed != 0.0 && previous_speed != speed {
            blocks = assemble(game, pos, entity, side, speed).unwrap_or_default();
        }
    } else {
        let mode = int(&entity.nbt, "ScrollValue").unwrap_or(0);
        let previous_mode = int(&entity.nbt, "CreatePistonPreviousMode").unwrap_or(mode);
        entity.nbt.insert("CreatePistonPreviousMode".into(), Tag::Int(mode));
        let changed = previous_speed.is_finite() && previous_speed != speed;
        let waiting = entity.nbt.get(&"Waiting".into()) == Some(&Tag::Byte(1));
        let pause = (waiting && !changed && previous_mode == mode) || (changed && speed != 0.0);
        if waiting && (changed || previous_mode != mode) { entity.nbt.remove(&"Waiting".into()); }
        if !pause {
        let old = float(&entity.nbt, "Offset").unwrap_or_default();
        let range = int(&entity.nbt, "Range").unwrap_or(0) as f32;
        let old_previous = float(&entity.nbt, "PreviousOffset").unwrap_or(old);
        let mut next = (old + speed).clamp(0.0, range);
        let ahead = position(
            anchor,
            normal,
            if speed >= 0.0 {
                next.ceil() as i32
            } else {
                next.floor() as i32
            },
        );
        let mut stopping = speed == 0.0 || next == 0.0 || next == range;
        if !has_clearance(game, ahead, &blocks, pos, &[]) {
            next = old.round();
            stopping = true;
        }
        let from = std::array::from_fn(|i| {
            f64::from(anchor[i]) + f64::from(normal[i]) * f64::from(old_previous)
        });
        let at =
            std::array::from_fn(|i| f64::from(anchor[i]) + f64::from(normal[i]) * f64::from(old));
        let motion = normal.map(|step| f64::from(step) * f64::from(speed));
        for block in &blocks {
            let Some(state) = compound(block, "BlockState") else {
                continue;
            };
            if string(state, "Name").as_deref() == Some(super::create_plough::PLOUGH)
                && let Some(id) = block
                    .get(&"BlockState".into())
                    .and_then(|tag| game.state_from_nbt(tag))
                && let Some(face) = facing(game, id)
            {
                super::create_plough::visit(game, relative(block), face, from, at, motion);
            }
        }
        set_float(&mut entity.nbt, "PreviousOffset", old);
        set_float(&mut entity.nbt, "Offset", next);
        if stopping {
            let target = position(anchor, normal, next.round() as i32);
            let initial = int(&entity.nbt, "CreatePistonInitialOffset").unwrap_or(0);
            if super::create_piston_motion::should_place(mode, initial, next) {
                entity.nbt.remove(&"Waiting".into());
                if !disassemble(game, pos, entity, &mut blocks, target, next >= 0.5) {
                    set_float(&mut entity.nbt, "Offset", old);
                }
            } else {
                entity.nbt.insert("Waiting".into(), Tag::Byte(1));
            }
        }
        }
    }
    if !blocks.is_empty() {
        let distance = float(&entity.nbt, "Offset").unwrap_or_default();
        draw(game, entity, &mut blocks, anchor, normal, distance);
        entity.nbt.insert(
            "Blocks".into(),
            Tag::List(blocks.into_iter().map(Tag::Compound).collect()),
        );
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    let name = level.registry.state(state)?.name.as_str();
    if !matches!(
        name,
        PISTON | STICKY | POLE | super::create_plough::PLOUGH | super::create_roller::ROLLER
    ) {
        return None;
    }
    let look = super::view_vector(context.yaw, context.pitch);
    let nearest = |vertical: bool| {
        Direction::ALL
            .into_iter()
            .filter(|d| vertical || axis(*d) != 1)
            .max_by(|a, b| {
                let dot = |direction: Direction| {
                    direction
                        .normal()
                        .into_iter()
                        .zip(look)
                        .map(|(step, component)| f64::from(step) * component)
                        .sum::<f64>()
                };
                dot(*a).total_cmp(&dot(*b))
            })
    };
    let side = if matches!(
        name,
        super::create_plough::PLOUGH | super::create_roller::ROLLER
    ) {
        if axis(context.face) == 1 {
            nearest(false)?.opposite()
        } else {
            let clicked = level.registry.state(level.block_state(context.hit_pos));
            if let Some(clicked) = clicked.filter(|s| s.name == name) {
                return level.native_state_with_property(
                    state,
                    "facing",
                    clicked.properties.get("facing")?,
                );
            }
            context.face
        }
    } else if name == POLE {
        context.face
    } else if context.sneaking {
        nearest(true)?
    } else {
        nearest(true)?.opposite()
    };
    let state =
        level.native_state_with_property(state, "facing", super::create_fluids::name(side))?;
    if matches!(name, PISTON | STICKY) {
        let first = match axis(side) {
            0 => false,
            1 => axis(nearest(false)?) == 0,
            _ => true,
        };
        level.native_state_with_property(
            state,
            "axis_along_first",
            if first { "true" } else { "false" },
        )
    } else {
        Some(state)
    }
}
