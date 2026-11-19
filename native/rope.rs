use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_machines::{float, int, mod_entity, offset, set_float};
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const PULLEY: &str = "create:rope_pulley";
const ROPE: &str = "create:rope";
const MAGNET: &str = "create:pulley_magnet";
const MAX_ROPE: i32 = 384;

pub(super) fn at_depth(pos: [i32; 3], depth: i32) -> [i32; 3] {
    offset(pos, [0, -depth, 0])
}

pub(super) fn level_range(game: &Game<'_>, pulley: [i32; 3]) -> i32 {
    (pulley[1] - 1 - game.native_world_height().0).clamp(0, MAX_ROPE)
}

fn remove_rope(game: &mut Game<'_>, pos: [i32; 3], limit: i32) -> i32 {
    let mut removed = 0;
    for depth in 1..=limit {
        let segment = at_depth(pos, depth);
        let block = game.native_block(segment);
        if !matches!(block.as_str(), ROPE | MAGNET) {
            break;
        }
        let wet = game
            .native_block_property(segment, "waterlogged")
            .as_deref()
            == Some("true");
        let replacement = if wet {
            "minecraft:water"
        } else {
            "minecraft:air"
        };
        if let Some(state) = game.native_default_state(replacement) {
            game.native_set_block(
                game.native_dimension(),
                segment,
                state,
                flags::UPDATE_CLIENTS | flags::UPDATE_MOVE_BY_PISTON,
            );
        }
        removed = depth;
        if block == MAGNET {
            break;
        }
    }
    removed
}

fn land(game: &mut Game<'_>, pos: [i32; 3], length: i32) {
    for depth in (1..=length).rev() {
        let at = at_depth(pos, depth);
        let block = game.world.block(at[0], at[1], at[2]);
        if !game.res.behaviours().is_replaceable(block) {
            continue;
        }
        let name = if depth == length { MAGNET } else { ROPE };
        let Some(state) = game.native_default_state(name) else {
            continue;
        };
        let waterlogged = game.native_state_block(block) == Some("minecraft:water");
        let state = game
            .with_level(|_, level, _| {
                level.native_state_with_property(
                    state,
                    "waterlogged",
                    if waterlogged { "true" } else { "false" },
                )
            })
            .unwrap_or(state);
        game.native_set_block(
            game.native_dimension(),
            at,
            state,
            flags::UPDATE_CLIENTS | flags::UPDATE_MOVE_BY_PISTON,
        );
    }
}

const LOAD: &str = "CreateRopeLoad";

pub(super) struct Payload {
    pub(super) id: u32,
    pub(super) blocks: Vec<Compound>,
    glue: Vec<Tag>,
}

fn rope_length(game: &Game<'_>, pos: [i32; 3], max: i32) -> i32 {
    (1..=max)
        .take_while(|&segment| {
            matches!(
                game.native_block(at_depth(pos, segment)).as_str(),
                ROPE | MAGNET
            )
        })
        .count() as i32
}

pub(super) fn payload(game: &Game<'_>, pos: [i32; 3]) -> Option<Payload> {
    game.others.iter().find_map(|entity| {
        let Tag::Compound(raw) = game.persist.raw.get(&entity.id)? else {
            return None;
        };
        let tag = super::create_depot::compound(raw, LOAD)?;
        let Tag::IntArray(pulley) = tag.get(&"Pulley".into())? else {
            return None;
        };
        if pulley.as_slice() != pos {
            return None;
        }
        read_payload(entity.id, tag)
    })
}

fn read_payload(id: u32, tag: &Compound) -> Option<Payload> {
    let Tag::List(blocks) = tag.get(&"Blocks".into())? else {
        return None;
    };
    let blocks = blocks
        .iter()
        .filter_map(|tag| match tag {
            Tag::Compound(data) => Some(data.clone()),
            _ => None,
        })
        .collect();
    let glue = match tag.get(&"Glue".into()) {
        Some(Tag::List(areas)) => areas.clone(),
        _ => Vec::new(),
    };
    Some(Payload { id, blocks, glue })
}

pub(super) fn save_payload(game: &mut Game<'_>, pos: [i32; 3], payload: Payload) {
    let tag = Compound::from([
        ("Pulley".into(), Tag::IntArray(pos.to_vec())),
        ("Glue".into(), Tag::List(payload.glue)),
        (
            "Blocks".into(),
            Tag::List(payload.blocks.into_iter().map(Tag::Compound).collect()),
        ),
    ]);
    if let Some(Tag::Compound(raw)) = game.persist.raw.get_mut(&payload.id) {
        raw.insert(LOAD.into(), Tag::Compound(tag));
    }
}

fn room_for_load(
    game: &Game<'_>,
    blocks: &[Compound],
    next: [i32; 3],
    source: &[[i32; 3]],
) -> bool {
    blocks.iter().all(|block| {
        let at = offset(next, super::create_bearing::relative(block));
        let state = game.world.block(at[0], at[1], at[2]);
        source.contains(&at) || game.res.behaviours().is_replaceable(state)
    })
}

fn assemble_payload(game: &mut Game<'_>, pos: [i32; 3], depth: i32, rpm: f32) -> Option<Payload> {
    let anchor = at_depth(pos, depth + 1);
    let blocks = super::create_bearing::capture(game, pos, anchor);
    if blocks.is_empty() {
        return None;
    }
    let sources: Vec<_> = blocks
        .iter()
        .map(|b| offset(anchor, super::create_bearing::relative(b)))
        .collect();
    let next = at_depth(pos, depth + 1 + rpm.signum() as i32);
    let mut removable = sources.clone();
    removable.extend((1..=depth).map(|distance| at_depth(pos, distance)));
    if !room_for_load(game, &blocks, next, &removable) {
        return None;
    }
    spawn_payload(game, pos, anchor, blocks)
}

pub(super) fn spawn_payload(
    game: &mut Game<'_>,
    pos: [i32; 3],
    anchor: [i32; 3],
    mut blocks: Vec<Compound>,
) -> Option<Payload> {
    let sources: Vec<_> = blocks
        .iter()
        .map(|b| offset(anchor, super::create_bearing::relative(b)))
        .collect();
    let glue = super::create_bearing::attached_glue(game, &sources, anchor);
    let air = game.native_default_state("minecraft:air")?;
    let dimension = game.native_dimension();
    let id = game.native_summon(
        dimension,
        "minecraft:marker",
        anchor.map(f64::from),
        Compound::from([
            (LOAD.into(), Tag::Compound(Compound::new())),
            (
                "Tags".into(),
                Tag::List(vec![Tag::String(
                    if game.native_block(pos) == super::create_elevator::PULLEY {
                        "create_elevator_cabin"
                    } else {
                        "create_rope_load"
                    }
                    .into(),
                )]),
            ),
        ]),
    )?;
    for [x, y, z] in sources {
        // The moving load already owns the captured inventory.
        game.world.block_entities.remove(&(x, y, z));
        game.native_set_block(
            dimension,
            [x, y, z],
            air,
            flags::UPDATE_ALL | flags::UPDATE_MOVE_BY_PISTON,
        );
    }
    for block in &mut blocks {
        super::create_bearing::display(game, anchor, block, 1, 0.0);
    }
    Some(Payload { id, blocks, glue })
}

fn move_payload(game: &mut Game<'_>, pos: [i32; 3], payload: &mut Payload, length: f32) {
    let anchor = at_depth(pos, 1);
    let mut location = anchor.map(f64::from);
    location[1] -= f64::from(length);
    move_payload_at(game, anchor, payload, location);
}

pub(super) fn move_payload_at(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    payload: &mut Payload,
    location: [f64; 3],
) {
    let dimension = game.native_dimension();
    game.native_move_entity(dimension, payload.id, location, 0.0, 0.0);
    super::create_bearing::move_glue(game, &payload.glue, location);
    for block in &mut payload.blocks {
        super::create_bearing::display(game, anchor, block, 1, 0.0);
        if let Some(id) = int(block, "Display") {
            game.native_move_entity(dimension, id as u32, location, 0.0, 0.0);
        }
    }
}

pub(super) fn land_payload(game: &mut Game<'_>, payload: &Payload, anchor: [i32; 3]) -> bool {
    if !super::create_bearing::restore(game, anchor, &payload.blocks, 1, 0.0) {
        return false;
    }
    super::create_bearing::move_glue(game, &payload.glue, anchor.map(f64::from));
    game.native_remove_entity(game.native_dimension(), payload.id);
    true
}

pub(super) fn recover_detached_payloads(game: &mut Game<'_>) {
    let orphaned: Vec<_> = game
        .others
        .iter()
        .filter_map(|entity| {
            let Tag::Compound(raw) = game.persist.raw.get(&entity.id)? else {
                return None;
            };
            let tag = super::create_depot::compound(raw, LOAD)?;
            let Tag::IntArray(pos) = tag.get(&"Pulley".into())? else {
                return None;
            };
            let pulley: [i32; 3] = pos.as_slice().try_into().ok()?;
            (!matches!(
                game.native_block(pulley).as_str(),
                PULLEY | super::create_elevator::PULLEY
            ))
            .then(|| {
                let extension = f64::from(pulley[1]) - 1.0 - entity.position.components()[1];
                let length = (extension.round() as i32).clamp(0, level_range(game, pulley));
                Some((at_depth(pulley, length + 1), read_payload(entity.id, tag)?))
            })?
        })
        .collect();
    for (at, payload) in orphaned {
        land_payload(game, &payload, at);
    }
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    rpm: f32,
    changed: bool,
    sequence_ratio: Option<f32>,
) {
    // Network propagation can publish slot 0 before this pulley ticks. Keep
    // the speed last observed by the pulley so that transition still reaches
    // its assembly logic.
    let previous = entity
        .data
        .get(3)
        .map_or(0.0, |bits| f32::from_bits(*bits as u32));
    let changed = changed || previous != rpm;
    if entity.data.len() < 4 {
        entity.data.resize(4, 0);
    }
    entity.data[3] = rpm.to_bits() as i32;
    let mut running = int(&entity.nbt, "Running") == Some(1);
    let mut length = float(&entity.nbt, "Offset").unwrap_or(0.0);
    let max = level_range(game, pos);
    let mut limit = float(&entity.nbt, "SequencedOffsetLimit");
    let mut load = payload(game, pos);
    let mut depth = None;
    if changed && !running && rpm != 0.0 {
        let found = rope_length(game, pos, max);
        let at = at_depth(pos, found + 1);
        if (rpm > 0.0 && found < max || rpm < 0.0 && found > 0)
            && !game
                .res
                .behaviours()
                .is_replaceable(game.world.block(at[0], at[1], at[2]))
        {
            depth = Some(found);
        }
    }
    if changed {
        entity.nbt.insert("ApplySpeed".into(), Tag::Byte(1));
        limit = sequence_ratio.map(|ratio| ratio * rpm.abs());
    }
    let apply = int(&entity.nbt, "ApplySpeed") == Some(1)
        && (!changed || load.is_some() || depth.is_some());
    if apply {
        entity.nbt.remove(&"ApplySpeed".into());
        if running && rpm == 0.0 {
            length = length.round().clamp(0.0, max as f32);
            let anchor = at_depth(pos, length as i32 + 1);
            if load
                .as_ref()
                .is_none_or(|load| land_payload(game, load, anchor))
            {
                land(game, pos, length as i32);
                load = None;
                running = false;
            }
        } else if !running && rpm != 0.0 {
            let found = depth.unwrap_or_else(|| rope_length(game, pos, max));
            load = assemble_payload(game, pos, found, rpm);
            if depth.is_some() && load.is_none() {
                return;
            }
            length = remove_rope(game, pos, found) as f32;
            running = true;
            entity
                .nbt
                .insert("InitialOffset".into(), Tag::Int(length as i32));
        }
    } else if running && !changed {
        let mut step = rpm / 512.0;
        if let Some(available) = &mut limit {
            step = step.clamp(-*available, *available);
            *available = (*available - step.abs()).max(0.0);
        }
        let next = (length + step).clamp(0.0, max as f32);
        let depth = next.ceil() as i32;
        let hit = at_depth(pos, depth);
        let room = depth == 0
            || game
                .res
                .behaviours()
                .is_replaceable(game.world.block(hit[0], hit[1], hit[2]));
        let load_room = load.as_ref().is_none_or(|load| {
            let limit = if step > 0.0 {
                next.ceil()
            } else {
                next.floor()
            };
            room_for_load(game, &load.blocks, at_depth(pos, limit as i32 + 1), &[])
        });
        if room && load_room {
            length = next;
        }
        if !room || !load_room || length <= 0.0 || length >= max as f32 {
            length = length.round();
            let anchor = at_depth(pos, length as i32 + 1);
            if load
                .as_ref()
                .is_none_or(|load| land_payload(game, load, anchor))
            {
                land(game, pos, length as i32);
                load = None;
                running = false;
            }
        }
    } else if !changed {
        return;
    }

    if let Some(mut load) = load {
        move_payload(game, pos, &mut load, length);
        save_payload(game, pos, load);
    }
    if let Some(limit) = limit {
        set_float(&mut entity.nbt, "SequencedOffsetLimit", limit);
    } else {
        entity.nbt.remove(&"SequencedOffsetLimit".into());
    }
    set_float(&mut entity.nbt, "Offset", length);
    entity
        .nbt
        .insert("Running".into(), Tag::Byte(i8::from(running)));
    game.native_block_entity_sync(pos);
}

pub(super) fn observed(game: &Game<'_>, pos: [i32; 3]) -> Option<(i32, i32, i32)> {
    let entity = mod_entity(game, pos).filter(|entity| entity.id == PULLEY)?;
    let stock = pos[1] - float(&entity.nbt, "Offset").unwrap_or(0.0) as i32;
    Some((stock, game.native_world_height().0, pos[1]))
}

const COIL: &str = "create:block/rope_pulley/rope_coil";
const CABLE: [&str; 4] = [
    "create:block/rope_pulley/rope",
    "create:block/rope_pulley/rope_half",
    "create:block/rope_pulley/pulley_magnet",
    "create:block/rope_pulley/rope_half_magnet",
];

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(std::iter::once(COIL).chain(CABLE).map(String::from));
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    ["Offset", "Running", "Speed"]
        .into_iter()
        .filter_map(|key| {
            entity
                .nbt
                .get(&key.into())
                .map(|tag| (key.into(), tag.clone()))
        })
        .collect()
}

pub(super) fn bounds(entity: &ModBlockEntity, bounds: &mut [f32; 6]) {
    bounds[1] = bounds[1].min(-float(&entity.nbt, "Offset").unwrap_or(0.0));
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let length = float(&entity.nbt, "Offset").unwrap_or(0.0);
    draw.push();
    if game.native_block_property(pos, "axis").as_deref() == Some("z") {
        draw.rotate_about([0.0, 1.0, 0.0], 90.0, [0.5; 3]);
    }
    game.native_draw_model(draw, COIL, 0xFFFFFF);
    draw.pop();
    if int(&entity.nbt, "Running") == Some(1) || length == 0.0 {
        super::create_hose::render_cable(game, draw, length, CABLE);
    }
}
