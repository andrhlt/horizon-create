use horizon_core::geometry::{Direction, Vec3};
use horizon_core::random::RandomSource;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::items::ItemStack;

use super::Game;
use super::create_bearing::{relative, rotate};
use super::create_fan::facing;
use super::create_machines::{int, offset};

fn projectile(item: &str) -> Option<(f32, f32)> {
    Some(match item {
        "minecraft:arrow"
        | "minecraft:spectral_arrow"
        | "minecraft:tipped_arrow"
        | "minecraft:snowball"
        | "minecraft:egg"
        | "minecraft:blue_egg"
        | "minecraft:brown_egg" => (1.1, 6.0),
        "minecraft:experience_bottle"
        | "minecraft:splash_potion"
        | "minecraft:lingering_potion" => (1.375, 3.0),
        _ => return None,
    })
}

fn top_off(stack: &mut ItemStack, cargo: &mut [Option<ItemStack>], capacity: u32) {
    for source in cargo {
        let Some(item) = source
            .as_mut()
            .filter(|item| item.same_item_same_components(stack))
        else {
            continue;
        };
        let taken = (capacity - stack.count).min(item.count);
        item.count -= taken;
        stack.count += taken;
        if item.count == 0 {
            *source = None;
        }
        if stack.count == capacity {
            break;
        }
    }
}

fn activate(
    game: &mut Game<'_>,
    block: &mut Compound,
    mut refill: impl FnMut(&mut ItemStack, u32),
    at: [i32; 3],
    direction: [f64; 3],
    motion: [f64; 3],
    dispenser: bool,
) {
    let Some(Tag::Compound(inventory)) = block.get_mut(&"VanillaEntity".into()) else {
        return;
    };
    let Some(Tag::List(items)) = inventory.get_mut(&"Items".into()) else {
        return;
    };
    let nearest = Direction::ALL
        .into_iter()
        .max_by(|a, b| {
            let dot = |face: Direction| {
                face.normal()
                    .into_iter()
                    .zip(direction)
                    .map(|(i, n)| f64::from(i) * n)
                    .sum::<f64>()
            };
            dot(*a).total_cmp(&dot(*b))
        })
        .unwrap();
    let mut candidates = Vec::new();
    for (index, entry) in items.iter_mut().enumerate() {
        let Tag::Compound(tag) = entry else { continue };
        let Some(mut stack) = ItemStack::from_nbt(tag).filter(|s| s.count > 0) else {
            continue;
        };
        let maximum = match stack
            .data()
            .and_then(|data| data.other("minecraft:max_stack_size"))
        {
            Some(Tag::Int(size)) => (*size).clamp(1, 99) as u32,
            _ => game
                .items()
                .get(&stack.item)
                .map_or(64, |item| item.max_stack)
                .max(1),
        };
        if stack.count == 1 && maximum > 1 {
            refill(&mut stack, maximum);
            if stack.count == 1 {
                continue;
            }
            tag.insert("count".into(), Tag::Int(stack.count as i32));
        }
        candidates.push((index, stack));
    }
    if candidates.is_empty() {
        game.dispenser_event(1001, (at[0], at[1], at[2]), 0);
        return;
    }
    let random_index = if candidates.len() > 1 {
        game.world
            .random
            .next_int_bound(candidates.len() as i32)
            .unwrap_or(0) as usize
    } else {
        0
    };
    let (index, stack) = candidates.swap_remove(random_index);
    let target = offset(at, nearest.normal());
    let dimension = game.native_dimension();
    let one = ItemStack {
        count: 1,
        ..stack.clone()
    };
    let succeeded = if game
        .native_container_slots(dimension, target, nearest.opposite())
        .is_some()
    {
        game.insert_stack_through(target, nearest.opposite(), one)
            .is_none()
    } else {
        let center = at.map(|coord| f64::from(coord) + 0.5);
        if let Some((power, spread)) = dispenser.then(|| projectile(&stack.item)).flatten() {
            let start: [f64; 3] = std::array::from_fn(|i| center[i] + 0.7 * direction[i]);
            let velocity: [f64; 3] =
                std::array::from_fn(|i| direction[i] * f64::from(power) + motion[i]);
            let speed = velocity
                .iter()
                .map(|value| value * value)
                .sum::<f64>()
                .sqrt() as f32;
            game.shoot_projectile_item(
                Vec3::new(start[0], start[1], start[2]),
                velocity,
                &stack,
                speed,
                spread,
            );
            game.dispenser_event(1002, (at[0], at[1], at[2]), 0);
        } else {
            let mut start = std::array::from_fn(|i| center[i] + direction[i]);
            start[1] -= if nearest.normal()[1] != 0 {
                0.125
            } else {
                0.15625
            };
            let r = &mut game.world.random;
            let speed = r.next_double() * 0.1 + 0.2;
            let velocity = std::array::from_fn(|i| {
                direction[i] * speed + motion[i] + r.next_gaussian() * 0.045
            });
            game.spawn_item_thrown(one, start, velocity);
            game.dispenser_event(1000, (at[0], at[1], at[2]), 0);
        }
        true
    };
    if succeeded {
        if stack.count == 1 {
            items.remove(index);
        } else if let Tag::Compound(data) = &mut items[index] {
            data.insert("count".into(), Tag::Int(stack.count as i32 - 1));
        }
    }
}

pub(super) fn rotate_actors(
    game: &mut Game<'_>,
    blocks: &mut [Compound],
    cargo: &mut [Option<ItemStack>],
    anchor: [i32; 3],
    bearing_facing: Direction,
    axis: usize,
    previous: f32,
    angle: f32,
) {
    let theta = f64::from(angle).to_radians();
    let previous_theta = f64::from(previous).to_radians();
    let axis_normal = bearing_facing.normal();
    for block in blocks {
        let Some(state) = block
            .get(&"BlockState".into())
            .and_then(|tag| game.state_from_nbt(tag))
        else {
            continue;
        };
        let kind = block_name(game, state);
        let dispenser = match kind {
            "minecraft:dispenser" => true,
            "minecraft:dropper" => false,
            _ => continue,
        };
        let Some(face) = facing(game, state) else {
            continue;
        };
        let local = relative(block);
        let centered = (0..3).all(|i| i == axis || local[i] == 0);
        let center = |angle| {
            let rotated = rotate(local.map(f64::from), axis, angle);
            std::array::from_fn::<_, 3, _>(|i| f64::from(anchor[i]) + 0.5 + rotated[i])
        };
        let now = center(theta);
        let cell = now.map(|v| v.floor() as i32);
        let mut motion =
            axis_normal.map(|step| f64::from(step) * f64::from(angle - previous) / 360.0);
        if centered {
            let timer = int(block, "StationaryTimer").unwrap_or(0);
            if timer > 0 {
                block.insert("StationaryTimer".into(), Tag::Int(timer - 1));
                continue;
            }
            block.insert("StationaryTimer".into(), Tag::Int(20));
        } else {
            let before = center(previous_theta);
            motion = std::array::from_fn(|i| now[i] - before[i]);
            let first_motion = int(block, "DispenseStarted") != Some(1) && motion != [0.0; 3];
            if !first_motion && cell == before.map(|v| v.floor() as i32) {
                continue;
            }
            block.insert("DispenseStarted".into(), Tag::Byte(1));
        }
        let direction = rotate(face.normal().map(f64::from), axis, theta);
        activate(
            game,
            block,
            |stack, limit| top_off(stack, cargo, limit),
            cell,
            direction,
            motion,
            dispenser,
        );
    }
}

fn refill_saved<'a>(
    stack: &mut ItemStack,
    limit: u32,
    blocks: impl IntoIterator<Item = &'a mut Compound>,
) {
    for block in blocks {
        let Some(state) = super::create_depot::compound(block, "BlockState") else {
            continue;
        };
        let Some(name) = super::create_machines::string(state, "Name") else {
            continue;
        };
        if !super::create_bearing::is_cargo(&name) {
            continue;
        }
        let items = match block.get_mut(&"VanillaEntity".into()) {
            Some(Tag::Compound(entity)) => entity.get_mut(&"Items".into()),
            _ => block.get_mut(&"Items".into()),
        };
        let Some(Tag::List(items)) = items else {
            continue;
        };
        items.retain_mut(|tag| {
            let Tag::Compound(tag) = tag else { return true };
            let Some(item) =
                ItemStack::from_nbt(tag).filter(|item| item.same_item_same_components(stack))
            else {
                return true;
            };
            let taken = (limit - stack.count).min(item.count);
            stack.count += taken;
            if taken < item.count {
                tag.insert("count".into(), Tag::Int((item.count - taken) as i32));
                true
            } else {
                false
            }
        });
        if stack.count >= limit {
            break;
        }
    }
}

pub(super) fn translate_actors(
    game: &mut Game<'_>,
    blocks: &mut [Compound],
    previous: [f64; 3],
    current: [f64; 3],
) {
    let motion = std::array::from_fn::<_, 3, _>(|i| current[i] - previous[i]);
    if motion == [0.0; 3] {
        return;
    }
    for index in 0..blocks.len() {
        let (earlier, rest) = blocks.split_at_mut(index);
        let Some((block, later)) = rest.split_first_mut() else {
            continue;
        };
        let Some(state) = block
            .get(&"BlockState".into())
            .and_then(|tag| game.state_from_nbt(tag))
        else {
            continue;
        };
        let dispenser = match block_name(game, state) {
            "minecraft:dispenser" => true,
            "minecraft:dropper" => false,
            _ => continue,
        };
        let Some(face) = facing(game, state) else {
            continue;
        };
        let local = relative(block);
        let cell = |anchor: [f64; 3]| {
            std::array::from_fn::<_, 3, _>(|i| {
                (anchor[i] + f64::from(local[i]) + 0.5).floor() as i32
            })
        };
        let at = cell(current);
        if at == cell(previous) && int(block, "DispenseStarted") == Some(1) {
            continue;
        }
        block.insert("DispenseStarted".into(), Tag::Byte(1));
        activate(
            game,
            block,
            |stack, limit| refill_saved(stack, limit, earlier.iter_mut().chain(later.iter_mut())),
            at,
            face.normal().map(f64::from),
            motion,
            dispenser,
        );
    }
}

fn block_name<'a>(game: &'a Game<'_>, state: BlockStateId) -> &'a str {
    game.pack
        .assets
        .registry
        .state(state)
        .map_or("", |state| state.name.as_str())
}
