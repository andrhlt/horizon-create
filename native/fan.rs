use std::collections::HashSet;

use horizon_core::geometry::Direction;
use horizon_core::random::RandomSource;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_depot::DEPOT;
use super::create_machines::{
    float, ingredient_matches, insert, int, mod_entity, offset, reading, set_float,
};
use super::create_threshold_switch::delta;
use super::create_visuals::wheel_angle;
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const FAN: &str = "create:encased_fan";
const PROPELLER: &str = "create:block/encased_fan/propeller";
pub(super) const FAN_TIME: i32 = super::create_fan_airflow_math::FAN_PROCESSING_TIME;

#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum Kind {
    Splashing,
    Smoking,
    Haunting,
    Blasting,
}

impl Kind {
    pub(super) fn from_id(id: &str) -> Option<Self> {
        [
            Self::Splashing,
            Self::Smoking,
            Self::Haunting,
            Self::Blasting,
        ]
        .into_iter()
        .find(|kind| kind.id() == id)
    }

    pub(super) fn id(self) -> &'static str {
        match self {
            Self::Splashing => "create:splashing",
            Self::Smoking => "create:smoking",
            Self::Haunting => "create:haunting",
            Self::Blasting => "create:blasting",
        }
    }
}

pub(super) fn facing(game: &Game<'_>, state: BlockStateId) -> Option<Direction> {
    Some(match game.native_block_state_property(state, "facing")? {
        "east" => Direction::East,
        "west" => Direction::West,
        "north" => Direction::North,
        "south" => Direction::South,
        "up" => Direction::Up,
        "down" => Direction::Down,
        _ => return None,
    })
}

fn catalyst(game: &Game<'_>, pos: [i32; 3]) -> Option<Kind> {
    match game.native_block(pos).as_str() {
        "minecraft:water" | "minecraft:bubble_column" => Some(Kind::Splashing),
        "minecraft:lava" => Some(Kind::Blasting),
        "minecraft:fire" => Some(Kind::Smoking),
        "minecraft:soul_fire" => Some(Kind::Haunting),
        "minecraft:campfire"
            if game.native_block_property(pos, "lit").as_deref() == Some("true") =>
        {
            Some(Kind::Smoking)
        }
        "minecraft:soul_campfire"
            if game.native_block_property(pos, "lit").as_deref() == Some("true") =>
        {
            Some(Kind::Haunting)
        }
        _ if game.native_block_property(pos, "waterlogged").as_deref() == Some("true") => {
            Some(Kind::Splashing)
        }
        _ => None,
    }
}

fn air_distance(game: &Game<'_>, source: [i32; 3], direction: Direction, max: f32) -> f32 {
    let along = delta(direction);
    let axis = along.iter().position(|step| *step != 0).unwrap_or(1);
    let x = (axis + 1) % 3;
    let y = (axis + 2) % 3;
    let forward = along[axis] > 0;
    let transparent = game.res.items().block_tags.get("create:fan_transparent");
    for distance in 0..max.ceil() as i32 {
        let pos = offset(source, along.map(|n| n * (distance + 1)));
        if !game.world.loaded(pos[0], pos[2]) {
            return distance as f32;
        }
        let name = game.native_block(pos);
        if name == "create:copycat_panel" || transparent.is_some_and(|set| set.contains(&name)) {
            continue;
        }
        let boxes = game.native_block_collision(pos);
        if boxes.is_empty() {
            continue;
        }
        if boxes.iter().any(|b| *b == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]) {
            return distance as f32;
        }
        let mut depth = 0.0_f64;
        let mut pass = false;
        for (a, b) in [
            (0.25, 0.25),
            (0.25, 0.75),
            (0.5, 0.5),
            (0.75, 0.25),
            (0.75, 0.75),
        ] {
            let nearest = boxes
                .iter()
                .filter(|bounds| {
                    a >= bounds[x] && a < bounds[x + 3] && b >= bounds[y] && b < bounds[y + 3]
                })
                .map(|bounds| {
                    if forward {
                        bounds[axis]
                    } else {
                        1.0 - bounds[axis + 3]
                    }
                })
                .fold(f64::INFINITY, f64::min);
            if nearest.is_infinite() {
                pass = true;
                break;
            }
            depth = depth.max(nearest);
        }
        if !pass {
            return (distance as f32 + depth as f32 + 1.0 / 32.0).min(max);
        }
    }
    max
}

pub(super) fn recipe(
    game: &Game<'_>,
    kind: Kind,
    input: &ItemStack,
) -> Option<Vec<(ItemStack, f32)>> {
    let cook = |recipe: &str| game.res.recipes().cook(recipe, input);
    match kind {
        Kind::Smoking => Some(vec![(cook("minecraft:smoking")?.result.clone(), 1.0)]),
        Kind::Blasting => {
            let smelt = cook("minecraft:smelting").or_else(|| cook("minecraft:blasting"));
            let smoke = cook("minecraft:smoking");
            match smelt {
                Some(smelt) if smoke.is_none_or(|smoke| smoke.result.item != smelt.result.item) => {
                    Some(vec![(smelt.result.clone(), 1.0)])
                }
                _ if !game
                    .res
                    .items()
                    .get(&input.item)
                    .is_some_and(|item| item.fire_resistant) =>
                {
                    Some(Vec::new())
                }
                _ => None,
            }
        }
        Kind::Haunting | Kind::Splashing => {
            let recipe = game
                .native_recipes_of_type(kind.id())
                .iter()
                .find(|recipe| {
                    recipe.json["ingredients"]
                        .as_array()
                        .and_then(|ingredients| ingredients.first())
                        .is_some_and(|ingredient| ingredient_matches(game, ingredient, &input.item))
                })?;
            let outputs: Vec<_> = recipe.json["results"]
                .as_array()?
                .iter()
                .filter_map(|result| {
                    let stack = game.native_recipe_result(result)?;
                    let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
                    Some((stack, chance))
                })
                .collect();
            (!outputs.is_empty()).then_some(outputs)
        }
    }
}

fn string_matches(nbt: &Compound, key: &str, name: &str) -> bool {
    matches!(nbt.get(&key.into()), Some(Tag::String(value)) if value.to_string_lossy() == name)
}

pub(super) fn clear(nbt: &mut Compound) {
    for key in [
        "FanProcessingType",
        "FanProcessingTime",
        "FanProcessingItem",
    ] {
        nbt.remove(&key.into());
    }
}

fn tick_depot(game: &mut Game<'_>, pos: [i32; 3], kind: Kind) {
    let Some(depot) = mod_entity(game, pos) else {
        return;
    };
    let Some(stack) = depot.items.first().and_then(Option::as_ref).cloned() else {
        return;
    };
    let same_item = string_matches(&depot.nbt, "FanProcessingItem", &stack.item);
    let same_type = string_matches(&depot.nbt, "FanProcessingType", kind.id());
    let before = int(&depot.nbt, "FanProcessingTime").unwrap_or(-1);
    if same_item && same_type && before < 0 {
        return;
    }

    let recipe_exists = recipe(game, kind, &stack).is_some();
    let step = super::create_fan_airflow_math::depot_step(
        before,
        same_item,
        same_type,
        recipe_exists,
        stack.count,
    );
    let mut completed = None;
    if step.complete {
        if let Some(results) = recipe(game, kind, &stack) {
            completed = Some(
                results
                    .into_iter()
                    .filter_map(|(mut output, chance)| {
                        let count = output.count * stack.count;
                        output.count = if chance == 1.0 {
                            count
                        } else {
                            (0..count)
                                .filter(|_| game.world.random.next_float() <= chance)
                                .count() as u32
                        };
                        let cap = game.native_max_stack_size(&output.item).unwrap_or(64);
                        (output.count != 0).then_some((output, cap))
                    })
                    .collect::<Vec<_>>(),
            );
        }
    }
    let next = step.timer;
    let transformed = completed.is_some();
    let excess = game
        .native_with_mod_block_entity(pos, |depot| {
            let depot = &mut **depot;
            let nbt = &mut depot.nbt;
            nbt.insert("FanProcessingType".into(), Tag::String(kind.id().into()));
            nbt.insert("FanProcessingTime".into(), Tag::Int(next));
            let mut excess = Vec::new();
            if let Some(results) = completed {
                depot.items[0] = None;
                for (mut output, cap) in results {
                    if depot.items[0].is_none() {
                        let count = output.count.min(cap);
                        depot.items[0] = Some(ItemStack {
                            count,
                            ..output.clone()
                        });
                        output.count -= count;
                    }
                    let remaining = insert(&mut depot.items[1..], &output, cap);
                    if remaining != 0 {
                        excess.push(Some(ItemStack {
                            count: remaining,
                            ..output
                        }));
                    }
                }
                set_float(nbt, "BeltPosition", 0.5);
            }
            let item = depot.items[0]
                .as_ref()
                .map_or("", |item| item.item.as_ref());
            nbt.insert("FanProcessingItem".into(), Tag::String(item.into()));
            excess
        })
        .unwrap_or_default();
    if !excess.is_empty() {
        let at = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
        game.with_level(|_, level, _| level.drop_lost_contents(at, excess));
    }
    if transformed {
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], fan: &mut ModBlockEntity, rpm: f32) {
    if rpm == 0.0 {
        return;
    }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(direction) = facing(game, state) else {
        return;
    };
    let along = delta(direction);
    let max = 3.0 + 17.0 * (rpm.abs() / 256.0).min(1.0);
    let distance = air_distance(game, pos, direction, max);
    let limit = distance.ceil() as i32;
    let positive = along.iter().sum::<i32>() > 0;
    let pushing = (rpm > 0.0) == positive;
    let mut range: Vec<_> = (1..=limit).collect();
    if !pushing {
        range.reverse();
    }
    let mut processing = None;
    let mut segments = vec![None; limit as usize];
    let mut visited = HashSet::new();
    for step in range {
        let at = offset(pos, along.map(|n| n * step));
        if let Some(kind) = catalyst(game, at) {
            processing = Some(kind);
        }
        segments[step as usize - 1] = processing;
        let Some(kind) = processing else {
            continue;
        };
        let below = offset(at, [0, -1, 0]);
        for target in [at, below] {
            if target == below && along[1] != 0 {
                break;
            }
            let block = game.native_block(target);
            if matches!(block.as_str(), DEPOT | super::create_belt::BELT) && visited.insert(target)
            {
                let kind = catalyst(game, target).unwrap_or(kind);
                if block == DEPOT {
                    tick_depot(game, target, kind);
                } else {
                    super::create_belt::fan_tick(game, target, kind);
                }
            }
        }
    }
    super::create_fan_items::tick(game, fan, pos, direction, rpm, distance, pushing, &segments);
}

pub(super) fn register_models(models: &mut Vec<String>) {
    models.push(PROPELLER.into());
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(direction) = facing(game, state) else {
        return;
    };
    let along = delta(direction);
    let angle = wheel_angle(
        draw.game_time,
        draw.partial,
        float(&entity.nbt, "VisualSpeed").unwrap_or(0.0),
        0.0,
    );
    const X: [f32; 3] = [1.0, 0.0, 0.0];
    const Y: [f32; 3] = [0.0, 1.0, 0.0];
    const CENTER: [f32; 3] = [0.5; 3];
    let (axis, base) = match direction {
        Direction::North => (Y, 180.0),
        Direction::East => (Y, 90.0),
        Direction::West => (Y, -90.0),
        Direction::Up => (X, -90.0),
        Direction::Down => (X, 90.0),
        Direction::South => (Y, 0.0),
    };
    draw.push();
    draw.rotate_about(along.map(|n| n.abs() as f32), angle, CENTER);
    draw.rotate_about(axis, base, CENTER);
    game.native_draw_model(draw, PROPELLER, 0xffffff);
    draw.pop();
}
