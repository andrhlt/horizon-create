// The portable item shares the mounted payload's entity lifecycle.
// This first codec handles ordinary solid blocks;
// mounted inventories, actors and glue must remain mounted until supported.
use super::Game;
use super::create_bearing::{display, relative};
use super::create_cart_assembler::{cell, payload_ref, save};
use super::create_depot::compound;
use super::create_machines::{int, string};
use super::minecarts::CartKind;
use crate::items::ItemStack;
use horizon_world::nbt::{Compound, Tag};

const ANCHOR: &str = "create:minecart_anchor";
const PORTABLE_CART: &str = "create:minecart_contraption";
const PORTABLE_DATA: &str = "create:minecart_contraption_data";

fn packed_pos([x, y, z]: [i32; 3]) -> i64 {
    (((x as i64) & 0x3ffffff) << 38) | (((z as i64) & 0x3ffffff) << 12) | ((y as i64) & 0xfff)
}

fn unpacked_pos(p: i64) -> [i32; 3] {
    [
        (p >> 38) as i32,
        (p << 52 >> 52) as i32,
        (p << 26 >> 38) as i32,
    ]
}

// In pinned Create, these are the vanilla blocks with movement behaviours.
// Other vanilla states already captured without block-entity data are plain blocks.
fn plain_state(name: &str) -> bool {
    name == ANCHOR
        || name.starts_with("minecraft:")
            && !matches!(
                name,
                "minecraft:bell"
                    | "minecraft:campfire"
                    | "minecraft:soul_campfire"
                    | "minecraft:dispenser"
                    | "minecraft:dropper"
            )
}

fn portable_blocks(data: &Compound) -> Option<Vec<Compound>> {
    let Tag::List(saved) = data.get(&"Blocks".into())? else {
        return None;
    };
    if matches!(data.get(&"Glue".into()), Some(Tag::List(glue)) if !glue.is_empty()) {
        return None;
    }
    saved
        .iter()
        .map(|entry| {
            let Tag::Compound(block) = entry else {
                return None;
            };
            // Do not silently discard block entities, inventories, or movement actors.
            let state = compound(block, "BlockState")?;
            let name = string(state, "Name")?;
            if !plain_state(&name) {
                return None;
            }
            if block.contains_key(&"Entity".into())
                || block.contains_key(&"VanillaEntity".into())
                || block.contains_key(&"Items".into())
            {
                return None;
            }
            Some(block.clone())
        })
        .collect()
}

fn encode_portable(blocks: &[Compound], anchor: [i32; 3], orientation: &str) -> Option<Compound> {
    let mut palette: Vec<Tag> = Vec::new();
    let mut entries = Vec::new();
    for block in blocks {
        let state = Tag::Compound(compound(block, "BlockState")?.clone());
        let index = palette
            .iter()
            .position(|known| *known == state)
            .unwrap_or_else(|| {
                palette.push(state);
                palette.len() - 1
            });
        entries.push(Tag::Compound(Compound::from([
            ("Pos".into(), Tag::Long(packed_pos(relative(block)))),
            ("State".into(), Tag::Int(index as i32)),
        ])));
    }
    let mut low = [0; 3];
    let mut high = [1; 3];
    for block in blocks {
        let pos = relative(block);
        for axis in 0..3 {
            low[axis] = low[axis].min(pos[axis]);
            high[axis] = high[axis].max(pos[axis] + 1);
        }
    }
    // MountedContraption expands its bounds around the Y axis before pickup.
    let radius = blocks
        .iter()
        .map(|block| {
            let [x, _, z] = relative(block);
            f64::from(x).hypot(f64::from(z))
        })
        .fold(0.0_f64, f64::max)
        .ceil() as i32;
    low[0] = -radius - 1;
    low[2] = -radius - 1;
    high[0] = radius + 2;
    high[2] = radius + 2;
    let bounds = low
        .into_iter()
        .chain(high)
        .map(|v| Tag::Float((v as f32).to_bits()))
        .collect();
    let mut tag = Compound::from([
        ("Type".into(), Tag::String("create:mounted".into())),
        (
            "Blocks".into(),
            Tag::Compound(Compound::from([
                ("Palette".into(), Tag::List(palette)),
                ("BlockList".into(), Tag::List(entries)),
            ])),
        ),
        ("Anchor".into(), Tag::IntArray(anchor.to_vec())),
        ("InitialOrientation".into(), Tag::String(orientation.into())),
        ("RotationMode".into(), Tag::String("ROTATE".into())),
        ("BoundsFront".into(), Tag::List(bounds)),
        ("Stalled".into(), Tag::Byte(0)),
        ("BottomlessSupply".into(), Tag::Byte(0)),
    ]);
    for key in [
        "Actors",
        "CapturedMultiblocks",
        "DisabledActors",
        "Interactors",
        "Superglue",
        "Seats",
        "Passengers",
        "SubContraptions",
    ] {
        tag.insert(key.into(), Tag::List(Vec::new()));
    }
    Some(tag)
}

fn decode_portable(data: &Compound) -> Option<Vec<Compound>> {
    if string(data, "Type").as_deref() != Some("create:mounted") {
        return None;
    }
    for key in [
        "items",
        "fluids",
        "Actors",
        "Superglue",
        "Seats",
        "Passengers",
        "SubContraptions",
    ] {
        if matches!(data.get(&key.into()), Some(Tag::List(list)) if !list.is_empty()) {
            return None;
        }
    }
    let encoded = compound(data, "Blocks")?;
    let (Tag::List(palette), Tag::List(entries)) = (
        encoded.get(&"Palette".into())?,
        encoded.get(&"BlockList".into())?,
    ) else {
        return None;
    };
    entries
        .iter()
        .map(|entry| {
            let Tag::Compound(entry) = entry else {
                return None;
            };
            if entry.contains_key(&"Data".into()) || entry.contains_key(&"UpdateTag".into()) {
                return None;
            }
            let Tag::Long(pos) = entry.get(&"Pos".into())? else {
                return None;
            };
            let Tag::Int(index) = entry.get(&"State".into())? else {
                return None;
            };
            let Tag::Compound(state) = palette.get(usize::try_from(*index).ok()?)? else {
                return None;
            };
            let name = string(state, "Name")?;
            if !plain_state(&name) {
                return None;
            }
            Some(Compound::from([
                ("Pos".into(), Tag::IntArray(unpacked_pos(*pos).to_vec())),
                ("BlockState".into(), Tag::Compound(state.clone())),
            ]))
        })
        .collect()
}

pub(super) fn pickup_portable(game: &mut Game<'_>, id: u32, stack: Option<&ItemStack>) -> bool {
    if !stack.is_some_and(|s| s.item.as_ref() == "create:wrench") {
        return false;
    }
    let Some(cart) = game
        .carts
        .iter()
        .find(|cart| cart.id == id && cart.kind == CartKind::Rideable)
    else {
        return false;
    };
    let current_cell = cell(cart.position);
    let Some((marker, data)) = payload_ref(game, id).map(|(marker, data)| (marker, data.clone()))
    else {
        return false;
    };
    let Some(blocks) = portable_blocks(&data) else {
        return true;
    };
    // Older mounted payloads did not save the original assembly position.
    let anchor = match data.get(&"Anchor".into()) {
        Some(Tag::IntArray(pos)) => pos.as_slice().try_into().unwrap_or(current_cell),
        _ => current_cell,
    };
    let fallback_orientation =
        if game.native_block_property(current_cell, "shape").as_deref() == Some("east_west") {
            "WEST"
        } else {
            "NORTH"
        };
    let saved_orientation = string(&data, "InitialOrientation");
    let orientation = saved_orientation
        .as_deref()
        .filter(|value| matches!(*value, "WEST" | "EAST" | "NORTH" | "SOUTH"))
        .unwrap_or(fallback_orientation);
    let Some(tag) = encode_portable(&blocks, anchor, orientation) else {
        return true;
    };
    let mut item = ItemStack::new(PORTABLE_CART, 1);
    item.data_mut()
        .set_other(PORTABLE_DATA, Some(Tag::Compound(tag)));
    let dim = game.native_dimension();
    for block in &blocks {
        if let Some(display) = int(block, "Display") {
            game.native_remove_entity(dim, display as u32);
        }
    }
    game.native_remove_entity(dim, marker);
    game.carts.retain(|cart| cart.id != id);
    game.persist.raw.remove(&id);
    game.give_or_drop(item);
    true
}

pub(super) fn place_portable(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != PORTABLE_CART {
        return false;
    }
    let Some(rail) = game.rail(pos[0], pos[1], pos[2]) else {
        return true;
    };
    let Some(Tag::Compound(data)) = stack.data().and_then(|data| data.other(PORTABLE_DATA)) else {
        return true;
    };
    let Some(mut blocks) = decode_portable(data) else {
        return true;
    };
    let y = if rail.shape.is_slope() { 0.5 } else { 0.0 };
    let location = [
        f64::from(pos[0]) + 0.5,
        f64::from(pos[1]) + 0.0625 + y,
        f64::from(pos[2]) + 0.5,
    ];
    let dim = game.native_dimension();
    let Some(cart) = game.native_summon(dim, "minecraft:minecart", location, Compound::new())
    else {
        return true;
    };
    let Some(marker) = game.native_summon(
        dim,
        "minecraft:marker",
        location,
        Compound::from([(
            "Tags".into(),
            Tag::List(vec![Tag::String("create_cart_payload".into())]),
        )]),
    ) else {
        game.carts.retain(|c| c.id != cart);
        return true;
    };
    let uuid = game.uuid_for(cart);
    for block in &mut blocks {
        display(game, pos, block, 1, 0.0);
    }
    let mut mounted = Compound::from([
        ("Cart".into(), Tag::IntArray(uuid.to_vec())),
        (
            "Anchor".into(),
            data.get(&"Anchor".into())
                .filter(|tag| matches!(tag, Tag::IntArray(anchor) if anchor.len() == 3))
                .cloned()
                .unwrap_or_else(|| Tag::IntArray(pos.to_vec())),
        ),
        ("Glue".into(), Tag::List(Vec::new())),
    ]);
    if let Some(value @ ("WEST" | "EAST" | "NORTH" | "SOUTH")) =
        string(data, "InitialOrientation").as_deref()
    {
        mounted.insert("InitialOrientation".into(), Tag::String(value.into()));
    }
    save(game, marker, mounted, blocks);
    game.consume_held();
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn portable_bounds_expand_around_vertical_axis() {
        let block = Compound::from([
            ("Pos".into(), Tag::IntArray(vec![-2, 1, 1])),
            (
                "BlockState".into(),
                Tag::Compound(Compound::from([(
                    "Name".into(),
                    Tag::String("minecraft:stone".into()),
                )])),
            ),
        ]);
        let data = encode_portable(&[block], [0, 0, 0], "NORTH").unwrap();
        let expected = [-4.0_f32, 0.0, -4.0, 5.0, 2.0, 5.0]
            .into_iter()
            .map(|value| Tag::Float(value.to_bits()))
            .collect();
        assert_eq!(data.get(&"BoundsFront".into()), Some(&Tag::List(expected)));
    }
}
