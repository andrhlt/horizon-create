use horizon_core::position::BlockPos;
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{PlacementContext, flags},
    nbt::{Compound, JavaString, Tag},
    registry::BlockStateId,
};

use crate::{
    containers::{BlockEntity, ModBlockEntity, ModContainer},
    crafting::toolbox_dye_color,
    items::{ItemStack, Items},
    save::item_to_nbt,
};

use super::{Game, GameLevel, create_machines::mod_entity, create_packager::max_stack};

pub(super) const ENTITY: &str = "create:toolbox";
pub(super) const COMPARTMENTS: usize = 8;
pub(super) const STACKS_PER_COMPARTMENT: usize = 4;
pub(super) const SLOTS: usize = COMPARTMENTS * STACKS_PER_COMPARTMENT;
pub(super) const FILTERS: &str = "Compartments";

pub(super) const COLORS: [&str; 16] = [
    "white",
    "orange",
    "magenta",
    "light_blue",
    "yellow",
    "lime",
    "pink",
    "gray",
    "light_gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
];

pub(super) fn block(name: &str) -> bool {
    name.strip_prefix("create:")
        .and_then(|name| name.strip_suffix("_toolbox"))
        .is_some_and(|color| COLORS.contains(&color))
}

pub(super) fn container(block_name: &str, result: &mut Option<ModContainer>) {
    if block(block_name) {
        *result = Some(ModContainer {
            slots: SLOTS,
            faces: std::array::from_fn(|_| (0..SLOTS).collect()),
            inputs: (0..SLOTS).collect(),
            outputs: (0..SLOTS).collect(),
            menu: Some(ENTITY.to_owned()),
        });
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
    fluid: FluidState,
) -> Option<BlockStateId> {
    if !level.native_state_block(state).is_some_and(block) {
        return None;
    }
    let yaw = (f64::from(ctx.yaw) / 90.0 + 0.5).floor() as i32;
    let facing = ["north", "east", "south", "west"][yaw.rem_euclid(4) as usize];
    let state = level.native_state_with_property(state, "facing", facing)?;
    let waterlogged = fluid.kind() == FluidKind::Water && fluid.is_source();
    level.native_state_with_property(
        state,
        "waterlogged",
        if waterlogged { "true" } else { "false" },
    )
}

pub(super) fn dye(game: &mut Game<'_>, pos: [i32; 3], held: &ItemStack) -> bool {
    let current = game.native_block(pos);
    if !block(&current) || game.native_sneaking() {
        return false;
    }
    let Some(color) = toolbox_dye_color(&held.item, |color| {
        game.items()
            .item_tags
            .get(&format!("c:dyes/{color}"))
            .is_some_and(|dyes| dyes.contains(held.item.as_ref()))
    }) else {
        return false;
    };
    let replacement = format!("create:{color}_toolbox");
    if replacement == current {
        return false;
    }
    let Some(facing) = game.native_block_property(pos, "facing") else {
        return false;
    };
    let Some(waterlogged) = game.native_block_property(pos, "waterlogged") else {
        return false;
    };
    let Some(state) = game.native_default_state(&replacement) else {
        return false;
    };
    let state = game.with_level(|_, level, _| {
        let state = level.native_state_with_property(state, "facing", &facing)?;
        level.native_state_with_property(state, "waterlogged", &waterlogged)
    });
    state.is_some_and(|state| {
        game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)
    })
}

pub(super) fn saved_filter(nbt: &Compound, compartment: usize) -> Option<ItemStack> {
    let Some(Tag::List(filters)) = nbt.get(&FILTERS.into()) else {
        return None;
    };
    let Tag::Compound(stack) = filters.get(compartment)? else {
        return None;
    };
    ItemStack::from_nbt(stack).filter(|stack| stack.count > 0)
}

pub(super) fn compatible(items: &Items, filter: &ItemStack, incoming: &ItemStack) -> bool {
    if filter.item != incoming.item {
        return false;
    }
    filter.item.as_ref() == "create:belt_connector"
        || filter.same_item_same_components(incoming)
        || (max_stack(items, filter) == 1
            && max_stack(items, incoming) == 1
            && horizon_client::stations::max_damage(items, filter) > 0
            && horizon_client::stations::max_damage(items, incoming) > 0)
}

pub(super) fn accepts(
    items: &Items,
    entity: &ModBlockEntity,
    slot: usize,
    incoming: &ItemStack,
) -> bool {
    if slot >= SLOTS || !horizon_client::bundle::fits_inside_container_items(items, incoming) {
        return false;
    }
    let compartment = slot / STACKS_PER_COMPARTMENT;
    let start = compartment * STACKS_PER_COMPARTMENT;
    // One automation call can deposit multiple stacks before this block next ticks.
    let saved = saved_filter(&entity.nbt, compartment);
    let in_slots = entity
        .items
        .iter()
        .skip(start)
        .take(STACKS_PER_COMPARTMENT)
        .flatten()
        .next();
    saved
        .as_ref()
        .or(in_slots)
        .is_none_or(|filter| compatible(items, filter, incoming))
}

pub(super) fn settle(items: &Items, slots: &mut [Option<ItemStack>]) {
    let mut remainder_seen = false;
    let mut displaced = None;
    for stack in slots.iter() {
        if let Some(stack) = stack {
            if remainder_seen {
                displaced = Some(stack);
            } else if stack.count != max_stack(items, stack) {
                remainder_seen = true;
            }
        } else {
            remainder_seen = true;
        }
    }
    let Some(sample) = displaced.cloned() else {
        return;
    };
    let limit = max_stack(items, &sample);
    if limit == 1 || horizon_client::stations::max_damage(items, &sample) > 0 && sample.damage > 0 {
        let mut packed = slots
            .iter()
            .flatten()
            .cloned()
            .map(Some)
            .collect::<Vec<_>>();
        packed.resize(STACKS_PER_COMPARTMENT, None);
        slots.clone_from_slice(&packed);
        return;
    }
    let mut total: u32 = slots.iter().flatten().map(|stack| stack.count).sum();
    for slot in slots {
        let count = total.min(limit);
        total -= count;
        *slot = (count > 0).then(|| ItemStack {
            count,
            ..sample.clone()
        });
    }
}

fn signal(items: &Items, slots: &[Option<ItemStack>]) -> i32 {
    let mut fraction = 0.0_f32;
    let mut occupied = false;
    for stack in slots
        .iter()
        .take(SLOTS)
        .flatten()
        .filter(|stack| stack.count > 0)
    {
        fraction += stack.count as f32 / max_stack(items, stack) as f32;
        occupied = true;
    }
    (fraction / SLOTS as f32 * 14.0).floor() as i32 + i32::from(occupied)
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, out: &mut i32) {
    if level.native_state_block(state).is_some_and(block)
        && let Some(BlockEntity::Mod(entity)) =
            level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    {
        *out = signal(level.items, &entity.items);
    }
}

pub(super) fn inventory_tick(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some(entity) = mod_entity(game, pos).filter(|entity| entity.id == ENTITY) else {
        return;
    };
    let mut slots = entity.items.clone();
    slots.resize(SLOTS, None);
    let mut filters = (0..COMPARTMENTS)
        .map(|index| saved_filter(&entity.nbt, index))
        .collect::<Vec<_>>();
    let mut learned_filter = false;
    for (group, filter) in slots
        .chunks_exact_mut(STACKS_PER_COMPARTMENT)
        .zip(&mut filters)
    {
        if filter.is_none()
            && let Some(stack) = group.iter().flatten().next()
        {
            *filter = Some(ItemStack {
                count: 1,
                ..stack.clone()
            });
            learned_filter = true;
        }
        settle(game.items(), group);
    }
    let old_signal = entity.data.first().copied().unwrap_or_default();
    let output = signal(game.items(), &slots);
    if !learned_filter && slots == entity.items && output == old_signal {
        return;
    }
    game.native_with_mod_block_entity(pos, |entity| {
        if slots != entity.items {
            entity.items = slots;
        }
        if learned_filter {
            let saved = filters
                .iter()
                .map(|stack| {
                    stack
                        .as_ref()
                        .map_or(Tag::Compound(Compound::new()), item_to_nbt)
                })
                .collect();
            entity.nbt.insert(FILTERS.into(), Tag::List(saved));
        }
        if output != old_signal {
            if let Some(previous) = entity.data.first_mut() {
                *previous = output;
            } else {
                entity.data.push(output);
            }
        }
    });
    game.native_block_entity_sync(pos);
    if output != old_signal {
        game.native_update_output_neighbors(game.native_dimension(), pos);
    }
}

pub(super) const INVENTORY_COMPONENT: &str = "create:toolbox_inventory";
pub(super) const UUID_COMPONENT: &str = "create:toolbox_uuid";
const UUID: &str = "UniqueId";
const NAME: &str = "CustomName";

fn new_uuid() -> Tag {
    Tag::IntArray(crate::save::random_uuid().to_vec())
}

pub(super) fn new_tag() -> Compound {
    [(UUID.into(), new_uuid())].into_iter().collect()
}

fn portable_inventory(entity: &ModBlockEntity) -> Tag {
    let items = entity
        .items
        .iter()
        .take(SLOTS)
        .enumerate()
        .filter_map(|(index, slot)| {
            let index = JavaString::from(index.to_string().as_str());
            Some((index, item_to_nbt(slot.as_ref()?)))
        });
    let filters = (0..COMPARTMENTS)
        .map(|group| {
            let filter = saved_filter(&entity.nbt, group).or_else(|| {
                let start = group * STACKS_PER_COMPARTMENT;
                entity
                    .items
                    .iter()
                    .skip(start)
                    .take(STACKS_PER_COMPARTMENT)
                    .flatten()
                    .next()
                    .map(|stack| ItemStack {
                        count: 1,
                        ..stack.clone()
                    })
            });
            filter
                .as_ref()
                .map_or(Tag::Compound(Compound::new()), item_to_nbt)
        })
        .collect();
    Tag::compound([
        (
            "items",
            Tag::compound([
                ("items", Tag::compound(items)),
                ("size", Tag::Int(SLOTS as i32)),
            ]),
        ),
        ("filters", Tag::List(filters)),
    ])
}

pub(super) fn packed(game: &Game<'_>, at: [i32; 3]) -> Option<ItemStack> {
    let name = game.native_block(at);
    if !block(&name) {
        return None;
    }
    let entity = mod_entity(game, at).filter(|entity| entity.id == ENTITY)?;
    let mut stack = ItemStack::new(&name, 1);
    let uuid = entity
        .nbt
        .get(&UUID.into())
        .cloned()
        .unwrap_or_else(new_uuid);
    game.native_set_component(&mut stack, UUID_COMPONENT, uuid)
        .ok()?;
    game.native_set_component(&mut stack, INVENTORY_COMPONENT, portable_inventory(entity))
        .ok()?;
    if let Some(name) = entity.nbt.get(&NAME.into()) {
        stack.data_mut().custom_name = Some(name.clone());
    }
    Some(stack)
}

pub(super) fn pickup(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    if !block(&game.native_block(pos)) {
        return false;
    }
    super::create_toolbox_links::before_pickup(game, pos);
    let Some(stack) = packed(game, pos) else {
        return false;
    };
    // The inventory travels in the item. Take the slots out of the live
    // container first so Horizon's pre-remove side effects cannot spill them.
    let Some(items) =
        game.native_with_mod_block_entity(pos, |entity| std::mem::take(&mut entity.items))
    else {
        return false;
    };
    let at = BlockPos::new(pos[0], pos[1], pos[2]);
    if !game.with_level(|behaviour, level, ticks| behaviour.destroy_block(level, ticks, at, false))
    {
        game.native_with_mod_block_entity(pos, |entity| entity.items = items);
        return false;
    }
    game.give_or_drop(stack);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub(super) fn placed(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) {
    if !game.native_authoritative()
        || !block(&stack.item)
        || game.native_block(pos) != stack.item.as_ref()
    {
        return;
    }
    let name = stack.data().and_then(|data| data.custom_name.clone());
    let uuid = match game.native_component(stack, UUID_COMPONENT) {
        Ok(Some(Tag::IntArray(words))) if words.len() == 4 => Some(Tag::IntArray(words.clone())),
        _ => None,
    };
    let inventory = game
        .native_component(stack, INVENTORY_COMPONENT)
        .ok()
        .flatten();
    let (slots, filters) = decode_inventory(inventory);
    game.native_with_mod_block_entity(pos, |entity| {
        if let Some(uuid) = uuid {
            entity.nbt.insert(UUID.into(), uuid);
        }
        if let Some(name) = name {
            entity.nbt.insert(NAME.into(), name);
        }
        if let Some(filters) = filters {
            entity.nbt.insert(FILTERS.into(), filters);
        }
        entity.items = slots;
    });
    inventory_tick(game, pos);
    game.native_block_entity_sync(pos);
}

fn decode_inventory(inventory: Option<&Tag>) -> (Vec<Option<ItemStack>>, Option<Tag>) {
    let mut slots = vec![None; SLOTS];
    let Some(components) = inventory else {
        return (slots, None);
    };
    if let Some(Tag::Compound(items)) = components.get("items").and_then(|slots| slots.get("items"))
    {
        for (slot, value) in items.iter() {
            let Ok(index) = slot.to_string_lossy().parse::<usize>() else {
                continue;
            };
            if let Some(target) = slots.get_mut(index)
                && let Tag::Compound(value) = value
            {
                *target = ItemStack::from_nbt(value);
            }
        }
    }
    let filters = components.get("filters").and_then(|filters| {
        matches!(filters, Tag::List(values) if values.len() == COMPARTMENTS)
            .then(|| filters.clone())
    });
    (slots, filters)
}
