use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_bearing::{relative, rotate};
use super::create_depot::{compound, encode};
use super::create_machines::{int, string};
use crate::items::ItemStack;

pub(super) const CONTROLS: &str = "create:contraption_controls";
const DISABLED: &str = "DisabledActors";

pub(super) fn filter(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if game.native_block(pos) != CONTROLS {
        return false;
    }
    game.native_with_mod_block_entity(pos, |entity| {
        let sample = ItemStack {
            count: 1,
            ..stack.clone()
        };
        entity.nbt.insert("Filter".into(), encode(&sample));
    });
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn disabled(data: &Compound, actor: &str) -> bool {
    matches!(data.get(&DISABLED.into()), Some(Tag::List(filters)) if filters.iter().any(
        |value| matches!(value, Tag::String(id) if id.0.is_empty() || id.to_string_lossy() == actor)))
}

pub(super) fn position(
    game: &mut Game<'_>,
    bearing: [i32; 3],
    anchor: [i32; 3],
    block: &mut Compound,
    axis: usize,
    angle: f64,
) {
    let name = compound(block, "BlockState").and_then(|state| string(state, "Name"));
    if name.as_deref() != Some(CONTROLS) {
        return;
    }
    let local = relative(block);
    let center = rotate(local.map(f64::from), axis, angle);
    let location =
        std::array::from_fn(|i| f64::from(anchor[i]) + center[i] + if i == 1 { 0.0 } else { 0.5 });
    let dim = game.native_dimension();
    let id = int(block, "ControlHitbox")
        .map(|id| id as u32)
        .filter(|id| {
            game.others
                .iter()
                .any(|entity| entity.id == *id && entity.kind == "minecraft:interaction")
        });
    if let Some(id) = id {
        game.native_move_entity(dim, id, location, 0.0, 0.0);
        return;
    }
    let filter = compound(block, "Entity")
        .and_then(|data| compound(data, "Filter"))
        .and_then(|stack| string(stack, "id"))
        .unwrap_or_default();
    let tags = Tag::List(vec![Tag::String("create_actor_controls".into())]);
    let data = Compound::from([
        ("width".into(), Tag::Float(0.75_f32.to_bits())),
        ("height".into(), Tag::Float(0.875_f32.to_bits())),
        ("response".into(), Tag::Byte(1)),
        ("Tags".into(), tags),
        ("CreateBearing".into(), Tag::IntArray(bearing.to_vec())),
        ("CreateControlPos".into(), Tag::IntArray(local.to_vec())),
        (
            "CreateActorFilter".into(),
            Tag::String(filter.as_str().into()),
        ),
    ]);
    if let Some(id) = game.native_summon(dim, "minecraft:interaction", location, data) {
        block.insert("ControlHitbox".into(), Tag::Int(id as i32));
    }
}

pub(super) fn click(game: &mut Game<'_>, id: u32) -> bool {
    let Some(Tag::Compound(raw)) = game.persist.raw.get(&id) else {
        return false;
    };
    let (Some(Tag::IntArray(bearing)), Some(Tag::IntArray(local)), Some(filter)) = (
        raw.get(&"CreateBearing".into()),
        raw.get(&"CreateControlPos".into()),
        string(raw, "CreateActorFilter"),
    ) else {
        return false;
    };
    let (Ok(bearing), Ok(local)) = (
        bearing.as_slice().try_into(),
        <[i32; 3]>::try_from(local.as_slice()),
    ) else {
        return false;
    };
    game.native_with_mod_block_entity(bearing, |entity| {
        if int(&entity.nbt, "Running") != Some(1) {
            return false;
        }
        let Some(Tag::List(blocks)) = entity.nbt.get(&"MovedBlocks".into()) else { return false };
        let Some(block) = blocks.iter().find_map(|entry| match entry {
            Tag::Compound(block) if relative(block) == local && int(block, "ControlHitbox") == Some(id as i32) => Some(block),
            _ => None,
        }) else { return false };
        if compound(block, "BlockState").and_then(|state| string(state, "Name")).as_deref() != Some(CONTROLS) {
            return false;
        }
        let was_disabled = disabled(&entity.nbt, &filter);
        let disabled_all = disabled(&entity.nbt, "");
        let mut filters = match entity.nbt.get(&DISABLED.into()).cloned() {
            Some(Tag::List(filters)) => filters,
            _ => Vec::new(),
        };
        if filter.is_empty() {
            filters.clear();
        } else {
            filters.retain(|tag| !matches!(tag, Tag::String(item) if item.0.is_empty() || item.to_string_lossy() == filter));
            if disabled_all {
                for actor in blocks {
                    let Tag::Compound(block) = actor else { continue };
                    let Some(actor) = compound(block, "BlockState").and_then(|state| string(state, "Name")) else { continue };
                    if actor != filter && actor != CONTROLS && !filters.iter().any(
                        |item| matches!(item, Tag::String(item) if item.to_string_lossy() == actor))
                    {
                        filters.push(Tag::String(actor.as_str().into()));
                    }
                }
            }
        }
        if !was_disabled {
            filters.push(Tag::String(filter.as_str().into()));
        }
        entity.nbt.insert(DISABLED.into(), Tag::List(filters));
        true
    }).unwrap_or(false)
}
