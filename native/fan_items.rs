use std::sync::{Mutex, OnceLock};

use horizon_core::geometry::Direction;
use horizon_core::random::{LegacyRandom, RandomSource};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_fan::{FAN_TIME, Kind, recipe};
use super::create_threshold_switch::delta;

struct AirItem {
    id: u32,
    kind: Option<Kind>,
    remaining: i32,
}

pub(super) fn roll(
    game: &mut Game<'_>,
    input_count: u32,
    results: &[(ItemStack, f32)],
) -> Vec<ItemStack> {
    static FIXTURE: OnceLock<Option<Mutex<LegacyRandom>>> = OnceLock::new();
    let mut seeded = FIXTURE
        .get_or_init(|| {
            let seed = std::env::var("CREATE_FAN_TRACE_SEED").ok()?.parse().ok()?;
            Some(Mutex::new(LegacyRandom::new(seed)))
        })
        .as_ref()
        .map(|random| random.lock().expect("fan fixture RNG"));
    let mut output = Vec::<ItemStack>::new();
    for _ in 0..input_count {
        for (item, chance) in results {
            let mut made = item.clone();
            if *chance < 1.0 {
                made.count = (0..item.count)
                    .filter(|_| {
                        let random = seeded.as_mut().map_or_else(
                            || game.world.random.next_float(),
                            |random| random.next_float(),
                        );
                        random <= *chance
                    })
                    .count() as u32;
            }
            if made.count == 0 {
                continue;
            }
            let max = game.native_max_stack_size(&made.item).unwrap_or(64);
            for stack in output
                .iter_mut()
                .filter(|stack| stack.item == made.item && stack.extra == made.extra)
            {
                let add = made.count.min(max.saturating_sub(stack.count));
                stack.count += add;
                made.count -= add;
            }
            if made.count > 0 {
                output.push(made);
            }
        }
    }
    output
}

pub(super) fn tick(
    game: &mut Game<'_>,
    fan: &mut ModBlockEntity,
    source: [i32; 3],
    direction: Direction,
    rpm: f32,
    distance: f32,
    pushing: bool,
    segments: &[Option<Kind>],
) {
    // Extra data slots are runtime-only. The first three are rotation,
    // capacity, and stress, followed by the six-tick entity scan counter.
    if fan.data.len() < 4 {
        fan.data.resize(4, 0);
    }
    let scan = fan.data[3] == 0;
    fan.data[3] = if scan { 5 } else { fan.data[3] - 1 };
    let mut caught: Vec<_> = fan.data[4..]
        .chunks_exact(3)
        .map(|data| AirItem {
            id: data[0] as u32,
            kind: match data[1] {
                1 => Some(Kind::Splashing),
                2 => Some(Kind::Smoking),
                3 => Some(Kind::Haunting),
                4 => Some(Kind::Blasting),
                _ => None,
            },
            remaining: data[2],
        })
        .collect();

    let along = delta(direction);
    let axis = along.iter().position(|step| *step != 0).unwrap_or(1);
    let normal = if pushing { along } else { along.map(|n| -n) };
    let mut min = source.map(f64::from);
    let mut max = min.map(|n| n + 1.0);
    if along[axis] > 0 {
        min[axis] += 1.0;
        max[axis] += f64::from(distance);
    } else {
        max[axis] -= 1.0;
        min[axis] -= f64::from(distance);
    }
    if distance < 0.25 {
        fan.data.truncate(4);
        return;
    }

    let within = game.native_item_entities(game.native_dimension(), min, max);
    caught.retain(|item| within.iter().any(|entity| entity.id == item.id));
    if scan {
        for item in &within {
            if caught.iter().all(|entity| entity.id != item.id) {
                caught.push(AirItem {
                    id: item.id,
                    kind: None,
                    remaining: -1,
                });
            }
        }
    }
    for item in &mut caught {
        let Some(index) = game.dropped.iter().position(|entity| entity.id == item.id) else {
            continue;
        };
        let entity = &mut game.dropped[index];
        let p = entity.position;
        let at = [p.x, p.y, p.z];
        let difference = std::array::from_fn::<_, 3, _>(|i| at[i] - (f64::from(source[i]) + 0.5));
        let range = difference.iter().map(|d| d * d).sum::<f64>().sqrt();
        let acceleration =
            f64::from((f64::from(rpm.abs() / 512.0) / (range / f64::from(distance))) as f32);
        let velocity = [entity.velocity.x, entity.velocity.y, entity.velocity.z];
        let next = std::array::from_fn::<_, 3, _>(|i| {
            velocity[i] + (f64::from(normal[i]) * acceleration - velocity[i]).clamp(-5.0, 5.0) / 8.0
        });
        entity.velocity.x = next[0];
        entity.velocity.y = next[1];
        entity.velocity.z = next[2];
        entity.fall_distance = 0.0;
        // Create's change at a catalyst takes effect after its plane. At the
        // plane itself the earlier segment in the airflow traversal owns it.
        let align = if along[axis] > 0 {
            at[axis] - min[axis]
        } else {
            max[axis] - at[axis]
        };
        if align < 0.0 || align > f64::from(distance) {
            continue;
        }
        let cell = if pushing {
            (align.ceil() as usize).saturating_sub(1)
        } else {
            align.floor() as usize
        };
        let Some(kind) = segments.get(cell).copied().flatten() else {
            continue;
        };
        if item.kind != Some(kind) {
            if recipe(game, kind, &game.dropped[index].stack).is_none() {
                continue;
            }
            item.kind = Some(kind);
            item.remaining =
                FAN_TIME * (((game.dropped[index].stack.count - 1) / 16 + 1) as i32) + 1;
        }
        if item.remaining < 0 {
            continue;
        }
        item.remaining -= 1;
        if item.remaining != 0 {
            continue;
        }
        let stack = game.dropped[index].stack.clone();
        let Some(results) = recipe(game, kind, &stack) else {
            continue;
        };
        let mut output = roll(game, stack.count, &results).into_iter();
        let Some(first) = output.next() else {
            game.remove_dropped(index);
            continue;
        };
        game.dropped[index].stack = first;
        for extra in output {
            game.add_item_entity(extra, at, Some(next), 0);
        }
    }

    fan.data.truncate(4);
    for item in caught {
        fan.data.extend([
            item.id as i32,
            item.kind.map_or(0, |kind| kind as i32 + 1),
            item.remaining,
        ]);
    }
}
