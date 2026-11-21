use horizon_world::nbt::{Compound, Tag};
use serde_json::Value;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_depot::compound;
use super::create_fluids::{Fluid, read_fluid};
use super::create_machines::{ingredient_matches, int, mod_entity, offset};

pub(super) const SPOUT: &str = "create:spout";
const CYCLE: i32 = 20;
const DISPENSE: i32 = 5;

pub(super) fn contents(entity: &ModBlockEntity) -> Option<Fluid> {
    let Some(Tag::List(tanks)) = entity.nbt.get(&"Tanks".into()) else {
        return None;
    };
    let Tag::Compound(tank) = tanks.first()? else {
        return None;
    };
    read_fluid(compound(compound(tank, "TankContent")?, "Fluid")?)
}

pub(super) fn write(game: &mut Game<'_>, pos: [i32; 3], fluid: Fluid) {
    game.native_with_mod_block_entity(pos, |entity| set_contents(entity, fluid));
    game.native_block_entity_sync(pos);
}

fn set_contents(entity: &mut ModBlockEntity, fluid: Fluid) {
    let tanks = entity
        .nbt
        .entry("Tanks".into())
        .or_insert_with(|| Tag::List(vec![Tag::Compound(Compound::new())]));
    let Tag::List(tanks) = tanks else { return };
    let Some(Tag::Compound(tank)) = tanks.first_mut() else {
        return;
    };
    let mut content = Compound::new();
    if fluid.amount > 0 {
        content.insert("Fluid".into(), fluid.nbt());
    }
    tank.insert("TankContent".into(), Tag::Compound(content));
}

fn matches_value(actual: &Tag, expected: &Value) -> bool {
    match (actual, expected) {
        (Tag::String(value), Value::String(expected)) => value.to_string_lossy() == *expected,
        (Tag::Byte(value), Value::Bool(expected)) => (*value != 0) == *expected,
        (Tag::Byte(value), Value::Number(n)) => Some(i64::from(*value)) == n.as_i64(),
        (Tag::Short(value), Value::Number(n)) => Some(i64::from(*value)) == n.as_i64(),
        (Tag::Int(value), Value::Number(n)) => Some(i64::from(*value)) == n.as_i64(),
        (Tag::Long(value), Value::Number(n)) => Some(*value) == n.as_i64(),
        (Tag::Float(value), Value::Number(n)) => {
            Some(f64::from(f32::from_bits(*value))) == n.as_f64()
        }
        (Tag::Double(value), Value::Number(n)) => Some(f64::from_bits(*value)) == n.as_f64(),
        (Tag::List(actual), Value::Array(expected)) => {
            actual.len() == expected.len()
                && actual
                    .iter()
                    .zip(expected)
                    .all(|(a, b)| matches_value(a, b))
        }
        (Tag::Compound(actual), Value::Object(expected)) => expected.iter().all(|(key, value)| {
            actual
                .get(&key.as_str().into())
                .is_some_and(|tag| matches_value(tag, value))
        }),
        _ => false,
    }
}

pub(super) fn matches_fluid(fluid: &Fluid, requirement: &Value) -> bool {
    let alternatives = requirement
        .get("fluids")
        .or_else(|| requirement.get("fluid"));
    let identity = match alternatives {
        Some(Value::String(id)) => &fluid.id == id,
        Some(Value::Array(ids)) => ids.iter().any(|id| id.as_str() == Some(fluid.id.as_str())),
        _ => false,
    };
    identity
        && requirement.get("components").is_none_or(|expected| {
            fluid
                .components
                .as_ref()
                .is_some_and(|data| matches_value(&Tag::Compound(data.clone()), expected))
        })
}

fn plan(
    game: &Game<'_>,
    stack: &ItemStack,
    fluid: Option<&Fluid>,
) -> (bool, Option<(i32, super::create_assembly::ResultStack)>) {
    use super::create_assembly::{self, ResultStack};
    let (mut fillable, sequenced) = create_assembly::fill(game, stack, fluid);
    if sequenced.is_some() {
        return (true, sequenced);
    }
    for recipe in game.native_recipes_of_type("create:filling") {
        let Some(ingredients) = recipe.json["ingredients"].as_array() else {
            continue;
        };
        let [item, required] = ingredients.as_slice() else {
            continue;
        };
        if !ingredient_matches(game, item, &stack.item) {
            continue;
        }
        fillable = true;
        if fluid.is_some_and(|fluid| matches_fluid(fluid, required))
            && let Some(amount) = required["amount"]
                .as_i64()
                .and_then(|n| i32::try_from(n).ok())
            && let Some(result) = recipe.json["results"]
                .as_array()
                .and_then(|list| list.first())
                .and_then(|result| game.native_recipe_result(result))
        {
            return (true, Some((amount, ResultStack::Item(result))));
        }
    }
    let generic = match stack.item.as_ref() {
        "minecraft:bucket" => fluid.and_then(|fluid| match fluid.id.as_str() {
            "minecraft:water" => Some((1000, ItemStack::new("minecraft:water_bucket", 1))),
            "minecraft:lava" => Some((1000, ItemStack::new("minecraft:lava_bucket", 1))),
            id => horizon_world::fluid::FluidKind::from_name(id)
                .and_then(|kind| kind.info().bucket)
                .map(|bucket| (1000, ItemStack::new(bucket, 1))),
        }),
        "minecraft:glass_bottle" => fluid.and_then(bottle),
        _ => return (fillable, None),
    };
    (
        true,
        generic.map(|(amount, item)| (amount, ResultStack::Item(item))),
    )
}

pub(super) fn bottle(fluid: &Fluid) -> Option<(i32, ItemStack)> {
    if fluid.id == "create:tea" { return Some((250, ItemStack::new("create:builders_tea", 1))); }
    let (item, contents) = match fluid.id.as_str() {
        "minecraft:water" => (
            "minecraft:potion",
            Tag::Compound(Compound::from([(
                "potion".into(),
                Tag::String("minecraft:water".into()),
            )])),
        ),
        "create:potion" => {
            let components = fluid.components.as_ref()?;
            let item = match components.get(&"create:potion_fluid_bottle_type".into()) {
                Some(Tag::String(kind)) if kind.to_string_lossy() == "splash" => {
                    "minecraft:splash_potion"
                }
                Some(Tag::String(kind)) if kind.to_string_lossy() == "lingering" => {
                    "minecraft:lingering_potion"
                }
                _ => "minecraft:potion",
            };
            (
                item,
                components.get(&"minecraft:potion_contents".into())?.clone(),
            )
        }
        _ => return None,
    };
    let stack = Compound::from([
        ("id".into(), Tag::String(item.into())),
        ("count".into(), Tag::Int(1)),
        (
            "components".into(),
            Tag::Compound(Compound::from([(
                "minecraft:potion_contents".into(),
                contents,
            )])),
        ),
    ]);
    ItemStack::from_nbt(&stack).map(|stack| (250, stack))
}

pub(super) enum Action {
    Pass,
    Hold,
    Output(ItemStack),
}

pub(super) fn offer(
    game: &mut Game<'_>,
    pos: [i32; 3],
    stack: &mut ItemStack,
    at_center: bool,
) -> Action {
    let Some(spout) = mod_entity(game, pos).filter(|entity| entity.id == SPOUT) else {
        return Action::Pass;
    };
    let timer = int(&spout.nbt, "ProcessingTicks").unwrap_or(-1);
    let tank = contents(spout);
    let (fillable, recipe) = plan(game, stack, tank.as_ref());

    if !at_center && !fillable {
        return Action::Pass;
    }
    if at_center && timer != -1 && timer != DISPENSE && fillable {
        return Action::Hold;
    }
    if !fillable || tank.is_some() && recipe.is_none() {
        return Action::Pass;
    }
    let (Some(mut fluid), Some((amount, result))) = (tank, recipe) else {
        return Action::Hold;
    };
    if !at_center || fluid.amount < amount {
        return Action::Hold;
    }
    if timer == -1 {
        game.native_with_mod_block_entity(pos, |spout| {
            spout.nbt.insert("ProcessingTicks".into(), Tag::Int(CYCLE));
        });
        game.native_block_entity_sync(pos);
        return Action::Hold;
    }
    fluid.amount -= amount;
    write(game, pos, fluid);
    stack.count -= 1;
    game.native_block_entity_sync(pos);
    Action::Output(result.stack(game))
}

enum BlockFill {
    Replace(&'static str),
    Increment(&'static str, i32),
}

fn block_fill(game: &Game<'_>, pos: [i32; 3], fluid: &Fluid) -> Option<(i32, BlockFill)> {
    let block = game.native_block(pos);
    let (amount, action) = match (fluid.id.as_str(), block.as_str()) {
        (
            "minecraft:water",
            "minecraft:dirt" | "minecraft:coarse_dirt" | "minecraft:rooted_dirt",
        ) => (250, BlockFill::Replace("minecraft:mud")),
        ("minecraft:water", "minecraft:cauldron") => {
            (250, BlockFill::Replace("minecraft:water_cauldron"))
        }
        ("minecraft:lava", "minecraft:cauldron") => {
            (1000, BlockFill::Replace("minecraft:lava_cauldron"))
        }
        ("minecraft:water", "minecraft:farmland" | "minecraft:water_cauldron") => {
            let (name, cap, cost) = if block == "minecraft:farmland" {
                ("moisture", 7, 100)
            } else {
                ("level", 3, 250)
            };
            let value = game.native_block_property(pos, name)?.parse::<i32>().ok()?;
            if value >= cap {
                return None;
            }
            (cost, BlockFill::Increment(name, value + 1))
        }
        _ => return None,
    };
    (fluid.amount >= amount).then_some((amount, action))
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    use horizon_world::level::flags;

    let targets = offset(pos, [0, -2, 0]);
    let mut timer = int(&entity.nbt, "ProcessingTicks").unwrap_or(-1);
    let mut fluid = contents(entity);
    if timer == -1
        && fluid
            .as_ref()
            .is_some_and(|fluid| block_fill(game, targets, fluid).is_some())
    {
        timer = CYCLE;
        entity.nbt.insert("BlockCycle".into(), Tag::Byte(1));
    }
    if timer < 0 {
        return;
    }
    timer -= 1;
    entity.nbt.insert("ProcessingTicks".into(), Tag::Int(timer));
    if timer == DISPENSE
        && entity.nbt.remove(&"BlockCycle".into()).is_some()
        && let Some(fluid) = fluid.as_mut()
        && let Some((amount, effect)) = block_fill(game, targets, fluid)
    {
        let changed = match effect {
            BlockFill::Replace(block) => game.native_default_state(block).is_some_and(|state| {
                game.native_set_block(game.native_dimension(), targets, state, flags::UPDATE_ALL)
            }),
            BlockFill::Increment(key, next) => game.native_set_block_property_with(
                targets,
                key,
                &next.to_string(),
                flags::UPDATE_ALL,
            ),
        };
        if changed {
            fluid.amount -= amount;
            set_contents(entity, fluid.clone());
        }
    }
    game.native_block_entity_sync(pos);
}

const NOZZLE_MODELS: [&str; 3] = [
    "create:block/spout/top",
    "create:block/spout/middle",
    "create:block/spout/bottom",
];

const LIQUID_MODELS: [&str; 14] = [
    "create:block/spout/water_still",
    "create:block/spout/water_flow",
    "create:block/spout/lava_still",
    "create:block/spout/lava_flow",
    "create:block/spout/potion_still",
    "create:block/spout/potion_flow",
    "create:block/spout/honey_still",
    "create:block/spout/honey_flow",
    "create:block/spout/chocolate_still",
    "create:block/spout/chocolate_flow",
    "create:block/spout/milk_still",
    "create:block/spout/milk_flow",
    "create:block/spout/tea_still",
    "create:block/spout/tea_flow",
];

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(NOZZLE_MODELS.map(String::from));
    models.extend(LIQUID_MODELS.map(String::from));
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    tag.insert(
        "ProcessingTicks".into(),
        Tag::Int(int(&entity.nbt, "ProcessingTicks").unwrap_or(-1)),
    );
    if let Some(tanks) = entity.nbt.get(&"Tanks".into()) {
        tag.insert("Tanks".into(), tanks.clone());
    }
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    let ticks = int(&entity.nbt, "ProcessingTicks").unwrap_or(-1);
    let partial_ticks = ticks as f32 - draw.partial;
    let progress = (1.0 - (partial_ticks - 5.0) / 10.0).clamp(0.0, 1.0);
    let radius = (2.0 * progress - 1.0).powi(2) - 1.0;
    if let Some(tank) = contents(entity) {
        let (liquid, tint) = liquid_style(&tank);
        let fill = (tank.amount as f32 / 1000.0).clamp(0.175, 1.0);
        draw_liquid(
            game,
            draw,
            LIQUID_MODELS[liquid],
            tint,
            [2.5, 2.5, 2.5],
            [11.0, 11.0 * fill, 11.0],
        );
        if ticks != -1 && radius < 0.0 {
            let width = -radius / 2.0;
            draw_liquid(
                game,
                draw,
                LIQUID_MODELS[liquid + 1],
                tint,
                [8.0 - width, -19.2, 8.0 - width],
                [2.0 * width, 19.2, 2.0 * width],
            );
        }
    }
    let squeeze = if partial_ticks < 0.0 {
        0.0
    } else if partial_ticks < 2.0 {
        -partial_ticks / 2.0
    } else if partial_ticks < 10.0 {
        -1.0
    } else {
        radius
    };
    draw.push();
    for model in NOZZLE_MODELS {
        game.native_draw_model(draw, model, 0xffffff);
        draw.translate([0.0, -3.0 * squeeze / 32.0, 0.0]);
    }
    draw.pop();
}

fn liquid_style(fluid: &Fluid) -> (usize, u32) {
    match fluid.id.as_str() {
        "minecraft:water" => (0, 0x3f76e4),
        "minecraft:lava" => (2, 0xffffff),
        "create:potion" => (4, potion_color(fluid)),
        "create:honey" => (6, 0xffffff),
        "create:chocolate" => (8, 0xffffff),
        "minecraft:milk" => (10, 0xffffff),
        "create:tea" => (12, 0xffffff),
        _ => (0, 0xffffff),
    }
}

pub(super) fn draw_still_fluid(
    game: &Game<'_>,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
    fluid: &Fluid,
    at: [f32; 3],
    size: [f32; 3],
) -> bool {
    let (liquid, tint) = liquid_style(fluid);
    draw_liquid(game, draw, LIQUID_MODELS[liquid], tint, at, size)
}

fn draw_liquid(
    game: &Game<'_>,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
    model: &str,
    tint: u32,
    at: [f32; 3],
    size: [f32; 3],
) -> bool {
    draw.push();
    draw.translate(at.map(|n| n / 16.0));
    draw.scale(size.map(|n| n / 16.0));
    let drawn = game.native_draw_model(draw, model, tint);
    draw.pop();
    drawn
}

fn potion_color(fluid: &Fluid) -> u32 {
    let potion = fluid
        .components
        .as_ref()
        .and_then(|components| compound(components, "minecraft:potion_contents"));
    if let Some(color) = potion.and_then(|potion| int(potion, "custom_color")) {
        return color as u32 & 0xffffff;
    }
    match potion.and_then(|potion| potion.get(&"potion".into())) {
        Some(Tag::String(id)) if id.to_string_lossy().ends_with("strength") => 0x932423,
        Some(Tag::String(id)) if id.to_string_lossy().ends_with("harming") => 0x430a09,
        Some(Tag::String(id)) if id.to_string_lossy().ends_with("night_vision") => 0x1f1fa1,
        _ => 0x385dc6,
    }
}
