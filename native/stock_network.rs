use std::collections::HashSet;

use horizon_core::{position::BlockPos, random::RandomSource};
use horizon_world::{
    level::{LevelAccess, Ticks},
    nbt::{Compound, Tag},
};

use crate::{containers::BlockEntity, items::ItemStack};

use super::{
    GameLevel,
    create_machines::{insert, int, same_stack},
    create_packager as packager,
    create_packager_inventory::{self as inventory, Payload},
    create_stock_link,
};

struct Source {
    machine: BlockPos,
    barrel: BlockPos,
    power: i32,
}

fn sources(level: &GameLevel<'_>, frequency: &[i32]) -> Vec<Source> {
    let mut sources: Vec<Source> = level.world.block_entities.iter().filter_map(|(&(x, y, z), entity)| {
        let BlockEntity::Mod(link) = entity else { return None };
        if link.id != create_stock_link::LINK
            || !matches!(link.nbt.get(&"Freq".into()), Some(Tag::IntArray(freq)) if freq == frequency)
        {
            return None;
        }
        let power = int(&link.nbt, "Power").unwrap_or(0);
        if power >= 15 {
            return None;
        }
        let pos = BlockPos::new(x, y, z);
        let [dx, dy, dz] = create_stock_link::attachment(level, level.block_state(pos))?.normal();
        let machine = pos.offset(dx, dy, dz);
        let state = level.block_state(machine);
        if level.native_state_block(state) != Some(packager::PACKAGER)
            || !matches!(level.world.block_entities.get(&key(machine)), Some(BlockEntity::Mod(_)))
        {
            return None;
        }
        let barrel = packager::attached_barrel(level, machine, state)?;
        Some(Source { machine, barrel, power })
    }).collect();
    sources.sort_by_key(|source| (source.power, key(source.machine)));
    let mut barrels = HashSet::new();
    sources.retain(|source| barrels.insert(key(source.barrel)));
    sources
}

fn key(pos: BlockPos) -> (i32, i32, i32) {
    (pos.x, pos.y, pos.z)
}

pub(super) fn order_stacks(order: &Tag) -> Vec<ItemStack> {
    let Some(Tag::List(entries)) = order.get("ordered_stacks").unwrap_or(order).get("entries")
    else {
        return Vec::new();
    };
    entries
        .iter()
        .filter_map(|entry| {
            let Tag::Compound(fields) = entry else {
                return None;
            };
            let Tag::Compound(item) = entry.get("item_stack")? else {
                return None;
            };
            let mut stack = ItemStack::from_nbt(item)?;
            let count = int(fields, "count").filter(|&count| count > 0)?;
            stack.count = count as u32;
            Some(stack)
        })
        .collect()
}

fn decode_order(order: &Tag) -> Vec<ItemStack> {
    let mut items: Vec<ItemStack> = Vec::new();
    for stack in order_stacks(order) {
        if let Some(prior) = items.iter_mut().find(|prior| same_stack(prior, &stack)) {
            prior.count = prior.count.saturating_add(stack.count);
        } else {
            items.push(stack);
        }
    }
    items
}

struct Shipment {
    source: Source,
    remaining: Vec<Option<ItemStack>>,
    payloads: Vec<Payload>,
}

fn collect_order(
    slots: &mut [Option<ItemStack>],
    order: &mut [ItemStack],
    limit: impl Fn(&ItemStack) -> u32,
) -> Vec<Payload> {
    let mut packages = Vec::new();
    let mut payload = Payload::default();
    for request in order {
        for slot in slots.iter_mut() {
            let Some(stack) = slot.as_mut().filter(|stack| same_stack(stack, request)) else {
                continue;
            };
            while request.count > 0 && stack.count > 0 {
                let offered = ItemStack {
                    count: request.count.min(stack.count),
                    ..stack.clone()
                };
                let left = insert(&mut payload, &offered, limit(&offered));
                if left == offered.count {
                    packages.push(std::mem::take(&mut payload));
                    continue;
                }
                let transferred = offered.count - left;
                request.count -= transferred;
                stack.count -= transferred;
            }
            if stack.count == 0 {
                *slot = None;
            }
        }
    }
    if payload.iter().any(Option::is_some) {
        packages.push(payload);
    }
    packages
}

pub(super) fn encode_order(items: impl Iterator<Item = ItemStack>) -> Tag {
    let entries = items
        .map(|mut item| {
            let count = item.count.min(i32::MAX as u32) as i32;
            item.count = 1;
            Tag::compound([
                ("item_stack", crate::save::item_to_nbt(&item)),
                ("count", Tag::Int(count)),
            ])
        })
        .collect();
    Tag::compound([
        (
            "ordered_stacks",
            Tag::compound([("entries", Tag::List(entries))]),
        ),
        ("ordered_crafts", Tag::List(Vec::new())),
    ])
}

pub(super) enum Request {
    Redstone { allow_partial: bool },
    Player,
}

pub(super) fn request(
    level: &mut GameLevel<'_>,
    ticks: &mut Ticks,
    frequency: &[i32],
    context: &Tag,
    address: &str,
    request: Request,
) -> bool {
    let mut order = decode_order(context);
    if order.is_empty() {
        return false;
    }

    let mut shipments = Vec::new();
    for source in sources(level, frequency) {
        let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get(&key(source.barrel))
        else {
            continue;
        };
        let mut remaining = slots.clone();
        let payloads = collect_order(&mut remaining, &mut order, |stack| {
            packager::max_stack(level.items, stack).max(1)
        });
        if !payloads.is_empty() {
            shipments.push(Shipment {
                source,
                remaining,
                payloads,
            });
        }
    }
    let filled = order.iter().all(|stack| stack.count == 0);
    if !filled
        && matches!(
            request,
            Request::Redstone {
                allow_partial: false
            }
        )
    {
        return false;
    }
    let queue_limit = match request {
        Request::Redstone { .. } => 20,
        Request::Player => 50,
    };
    if shipments
        .iter()
        .any(|shipment| packager::queued(level, shipment.source.machine) >= queue_limit)
    {
        // The Requester's indicator uses the stock check and still reports true.
        return matches!(request, Request::Redstone { .. });
    }

    let order_id = level.world.random.next_int();
    let last_link = shipments.len().saturating_sub(1);
    for (link_index, shipment) in shipments.into_iter().enumerate() {
        let last_fragment = shipment.payloads.len() - 1;
        for (fragment, payload) in shipment.payloads.iter().enumerate() {
            let mut metadata = Compound::from([
                ("order_id".into(), Tag::Int(order_id)),
                ("link_index".into(), Tag::Int(link_index as i32)),
                (
                    "is_final_link".into(),
                    Tag::Byte(i8::from(filled && link_index == last_link)),
                ),
                ("fragment_index".into(), Tag::Int(fragment as i32)),
                (
                    "is_final".into(),
                    Tag::Byte(i8::from(fragment == last_fragment)),
                ),
            ]);
            if link_index == 0 && fragment == 0 {
                metadata.insert("order_context".into(), context.clone());
            }
            let package = packager::make_package(
                level,
                inventory::encode_contents(payload),
                address,
                Some(Tag::Compound(metadata)),
            );
            packager::dispatch(level, ticks, shipment.source.machine, &package);
        }
        if let Some(BlockEntity::Chest(slots)) = level
            .world
            .block_entities
            .get_mut(&key(shipment.source.barrel))
        {
            *slots = shipment.remaining;
        }
        packager::notify(level, ticks, shipment.source.barrel);
    }
    true
}

#[derive(Clone, Default)]
pub(super) struct Summary {
    pub(super) items: Vec<ItemStack>,
    pub(super) links: usize,
}

impl Summary {
    pub(super) fn to_tag(&self) -> Tag {
        Tag::compound([
            ("links", Tag::Int(self.links as i32)),
            (
                "items",
                Tag::List(self.items.iter().map(crate::save::item_to_nbt).collect()),
            ),
        ])
    }

    pub(super) fn from_tag(tag: &Tag) -> Self {
        let items = match tag.get("items") {
            Some(Tag::List(items)) => items
                .iter()
                .filter_map(|tag| match tag {
                    Tag::Compound(item) => ItemStack::from_nbt(item),
                    _ => None,
                })
                .collect(),
            _ => Vec::new(),
        };
        let links = match tag.get("links") {
            Some(Tag::Int(count)) => (*count).max(0) as usize,
            _ => 0,
        };
        Self { items, links }
    }
}

struct CachedSummary {
    tick: i64,
    summary: Summary,
}

type CacheKey = (String, [i32; 4], bool);
thread_local! {
    static SUMMARIES: std::cell::RefCell<std::collections::HashMap<CacheKey, CachedSummary>> =
        std::cell::RefCell::new(std::collections::HashMap::new());
}

pub(super) fn clear_summaries() {
    SUMMARIES.with_borrow_mut(|cache| cache.clear());
}

pub(super) fn summary(game: &mut super::Game<'_>, frequency: [i32; 4], accurate: bool) -> Summary {
    let key = (game.native_dimension().to_owned(), frequency, accurate);
    let tick = game.world.game_time;
    SUMMARIES.with_borrow_mut(|cache| {
        cache.retain(|(_, _, accurate), entry| {
            (0..=if *accurate { 1 } else { 20 }).contains(&(tick - entry.tick))
        });
        cache
            .entry(key)
            .or_insert_with(|| {
                let summary = game.with_level(|_, level, _| collect_summary(level, &frequency));
                CachedSummary { tick, summary }
            })
            .summary
            .clone()
    })
}

fn collect_summary(level: &GameLevel<'_>, frequency: &[i32]) -> Summary {
    let mut result = Summary::default();
    for source in sources(level, frequency) {
        let Some(BlockEntity::Chest(slots)) = level.world.block_entities.get(&key(source.barrel))
        else {
            continue;
        };
        result.links += 1;
        for item in slots.iter().flatten() {
            if let Some(entry) = result
                .items
                .iter_mut()
                .find(|entry| same_stack(entry, item))
            {
                entry.count = entry.count.saturating_add(item.count);
            } else {
                result.items.push(item.clone());
            }
        }
    }
    result.items.sort_by(|left, right| {
        right
            .count
            .cmp(&left.count)
            .then_with(|| left.item.cmp(&right.item))
    });
    result
}
