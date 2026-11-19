use horizon_client::items::ItemStack;
use horizon_core::{geometry::Direction, random::RandomSource};
use horizon_world::{
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_belt;
use super::create_depot::{DEPOT, receive_stack};
use super::create_machines::{
    float, ingredient_matches, insert, int, mod_entity, offset, rpm_at, set_float,
};
use super::create_visuals::{draw_rotating, wheel_angle};
use super::native_block_entity_draw::BlockEntityDraw;

pub(super) const SAW: &str = "create:mechanical_saw";
pub(super) const ENTITY: &str = "create:saw";
pub(super) const SLOTS: usize = 32;
const CENTER: [f32; 3] = [0.5; 3];
const BLADE_MODELS: [[&str; 3]; 2] = [
    [
        "create:block/mechanical_saw/blade_horizontal_inactive",
        "create:block/mechanical_saw/blade_horizontal_active",
        "create:block/mechanical_saw/blade_horizontal_reversed",
    ],
    [
        "create:block/mechanical_saw/blade_vertical_inactive",
        "create:block/mechanical_saw/blade_vertical_active",
        "create:block/mechanical_saw/blade_vertical_reversed",
    ],
];

pub(super) fn new_tag() -> Compound {
    Compound::from([
        ("ProcessingTime".into(), Tag::Float((-1.0_f32).to_bits())),
        ("RecipeTime".into(), Tag::Float(0.0_f32.to_bits())),
        ("AppliedRecipe".into(), Tag::Byte(0)),
        ("RecipeIndex".into(), Tag::Int(0)),
        ("Progress".into(), Tag::Int(0)),
        ("NextTick".into(), Tag::Int(0)),
    ])
}

fn state_at(game: &Game<'_>, pos: [i32; 3]) -> BlockStateId {
    game.world.block(pos[0], pos[1], pos[2])
}

pub(super) fn geometry(game: &Game<'_>, state: BlockStateId) -> Option<(Direction, usize)> {
    let facing = super::create_fan::facing(game, state)?;
    let axis = match facing {
        Direction::East | Direction::West => 0,
        Direction::North | Direction::South => 2,
        _ if game.native_block_state_property(state, "axis_along_first") == Some("true") => 0,
        _ => 2,
    };
    Some((facing, axis))
}

struct Cut {
    time: f32,
    results: Vec<(ItemStack, f32)>,
}

fn cuts(game: &Game<'_>, stack: &ItemStack, filter: Option<&ItemStack>) -> Vec<Cut> {
    let matches = |result: &ItemStack| filter.is_none_or(|filter| filter.item == result.item);
    let cutting = game
        .native_recipes_of_type("create:cutting")
        .iter()
        .filter_map(|recipe| {
            let ingredient = recipe.json["ingredients"].as_array()?.first()?;
            if !ingredient_matches(game, ingredient, &stack.item) {
                return None;
            }
            let results = recipe.json["results"]
                .as_array()?
                .iter()
                .filter_map(|result| {
                    Some((
                        game.native_recipe_result(result)?,
                        result["chance"].as_f64().unwrap_or(1.0) as f32,
                    ))
                })
                .collect::<Vec<_>>();
            if results.first().is_none_or(|(result, _)| !matches(result)) {
                return None;
            }
            Some(Cut {
                time: recipe.json["processing_time"].as_f64().unwrap_or(50.0) as f32,
                results,
            })
        });
    let stone = game
        .stations()
        .recipes
        .stonecutting
        .iter()
        .filter_map(|recipe| {
            (recipe.input.test(stack) && matches(&recipe.result)).then(|| Cut {
                time: 50.0,
                results: vec![(recipe.result.clone(), 1.0)],
            })
        });
    cutting.chain(stone).collect()
}

fn filter(entity: &ModBlockEntity) -> Option<ItemStack> {
    ItemStack::from_nbt(super::create_depot::compound(&entity.nbt, "Filter")?)
}

fn configure_start(entity: &mut ModBlockEntity, cuts: &[Cut]) {
    let prior = int(&entity.nbt, "RecipeIndex").unwrap_or(0).max(0) as usize;
    let time = if cuts.is_empty() {
        10.0
    } else {
        let index = (prior + 1) % cuts.len();
        let count = entity.items[0].as_ref().map_or(1, |stack| stack.count);
        entity
            .nbt
            .insert("RecipeIndex".into(), Tag::Int(index as i32));
        cuts[index].time * (count / 5).max(1) as f32
    };
    set_float(&mut entity.nbt, "ProcessingTime", time);
    set_float(&mut entity.nbt, "RecipeTime", time);
    entity.nbt.insert("AppliedRecipe".into(), Tag::Byte(0));
}

pub(super) fn landing(
    game: &mut Game<'_>,
    state: BlockStateId,
    pos: [i32; 3],
    stack: &mut ItemStack,
) {
    if game.native_state_block(state) != Some(SAW)
        || game.native_block_state_property(state, "facing") != Some("up")
        || stack.count == 0
        || rpm_at(game, pos) == 0.0
    {
        return;
    }
    let Some(entity) =
        mod_entity(game, pos).filter(|entity| entity.items.iter().all(Option::is_none))
    else {
        return;
    };
    let cuts = cuts(game, stack, filter(entity).as_ref());
    let mut one = stack.clone();
    one.count = 1;
    if game
        .native_with_mod_block_entity(pos, |entity| {
            entity.items.resize(SLOTS, None);
            entity.items[0] = Some(one);
            configure_start(entity, &cuts);
        })
        .is_some()
    {
        stack.count -= 1;
        game.native_block_entity_sync(pos);
    }
}

fn apply(game: &mut Game<'_>, entity: &mut ModBlockEntity) {
    let Some(input) = entity.items[0].as_ref() else {
        return;
    };
    let cuts = cuts(game, input, filter(entity).as_ref());
    if cuts.is_empty() {
        return;
    }
    let index = int(&entity.nbt, "RecipeIndex").unwrap_or(0).max(0) as usize;
    let index = if index < cuts.len() { index } else { 0 };
    let rolls = input.count;
    entity
        .nbt
        .insert("RecipeIndex".into(), Tag::Int(index as i32));
    entity.items.fill(None);
    for _ in 0..rolls {
        for (result, chance) in &cuts[index].results {
            let mut result = result.clone();
            if *chance < 1.0 {
                result.count = (0..result.count)
                    .filter(|_| game.world.random.next_float() <= *chance)
                    .count() as u32;
            }
            let limit = game.native_max_stack_size(&result.item).unwrap_or(64);
            insert(&mut entity.items[1..], &result, limit);
        }
    }
}

fn movement(axis: usize, rpm: f32) -> Direction {
    match (axis, rpm < 0.0) {
        (0, false) => Direction::North,
        (0, true) => Direction::South,
        (_, false) => Direction::East,
        (_, true) => Direction::West,
    }
}

fn eject(game: &mut Game<'_>, pos: [i32; 3], direction: Direction, entity: &mut ModBlockEntity) {
    let step = direction.normal();
    let target = offset(pos, step);
    if let Some((start, index, movement, speed)) = create_belt::feed_point(game, target) {
        for slot in &mut entity.items {
            if slot.is_some()
                && create_belt::can_feed(game, start, index, movement, direction, speed)
            {
                create_belt::feed(
                    game,
                    start,
                    index,
                    movement,
                    direction,
                    speed,
                    slot.take().unwrap(),
                );
            }
        }
        return;
    }
    if game.native_block(target) == DEPOT {
        for slot in &mut entity.items {
            if let Some(stack) = slot.take() {
                *slot = receive_stack(game, target, stack);
            }
        }
        return;
    }
    let [x, _, z] = step.map(f64::from);
    let at = [
        f64::from(pos[0]) + 0.5 + x * 0.5,
        f64::from(pos[1]) + 1.0,
        f64::from(pos[2]) + 0.5 + z * 0.5,
    ];
    for stack in entity.items.iter_mut().filter_map(Option::take) {
        game.add_item_entity(stack, at, Some([x * 0.0625, 0.125, z * 0.0625]), 0);
    }
    set_float(&mut entity.nbt, "ProcessingTime", -1.0);
    set_float(&mut entity.nbt, "RecipeTime", 0.0);
    entity.nbt.insert("AppliedRecipe".into(), Tag::Byte(0));
}

fn log(game: &Game<'_>, block: &str) -> bool {
    game.block_in_tag("minecraft:logs", block) || block == "minecraft:mushroom_stem"
}

fn vertical_plant(block: &str) -> bool {
    matches!(
        block,
        "minecraft:bamboo"
            | "minecraft:cactus"
            | "minecraft:sugar_cane"
            | "minecraft:kelp"
            | "minecraft:kelp_plant"
    )
}

fn sawable(game: &Game<'_>, block: &str) -> bool {
    !game.block_in_tag("minecraft:saplings", block)
        && (log(game, block)
            || game.block_in_tag("minecraft:leaves", block)
            || vertical_plant(block)
            || matches!(
                block,
                "minecraft:pumpkin"
                    | "minecraft:melon"
                    | "minecraft:chorus_plant"
                    | "minecraft:mangrove_roots"
                    | "minecraft:muddy_mangrove_roots"
            ))
}

fn break_tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    facing: Direction,
    entity: &mut ModBlockEntity,
    rpm: f32,
) {
    if rpm == 0.0 {
        return;
    }
    let delay = int(&entity.nbt, "NextTick").unwrap_or(0);
    if delay != 0 {
        entity
            .nbt
            .insert("NextTick".into(), Tag::Int((delay - 1).max(0)));
        return;
    }
    let target = offset(pos, facing.normal());
    let block = game.native_block(target);
    let hardness = game.res.behaviours().facts(state_at(game, target)).hardness;
    if hardness < 0.0 || !sawable(game, &block) {
        entity.nbt.insert("Progress".into(), Tag::Int(0));
        entity.nbt.insert("NextTick".into(), Tag::Int(-1));
        return;
    }
    let speed = rpm.abs() / 100.0;
    let progress =
        int(&entity.nbt, "Progress").unwrap_or(0).clamp(0, 9) + ((speed / hardness) as i32).max(1);
    if progress < 10 {
        entity.nbt.insert("Progress".into(), Tag::Int(progress));
        entity
            .nbt
            .insert("NextTick".into(), Tag::Int((hardness / speed) as i32));
        return;
    }
    let _ = game.destroy_block_dropping(target);
    if log(game, &block) || vertical_plant(&block) {
        let mut upper = offset(target, [0, 1, 0]);
        while {
            let current = game.native_block(upper);
            if log(game, &block) {
                log(game, &current)
            } else {
                vertical_plant(&current)
            }
        } {
            let _ = game.destroy_block_dropping(upper);
            upper[1] += 1;
        }
    }
    entity.nbt.insert("Progress".into(), Tag::Int(0));
    entity.nbt.insert("NextTick".into(), Tag::Int(-1));
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity, rpm: f32) {
    let Some((facing, axis)) = geometry(game, state_at(game, pos)) else {
        return;
    };
    if facing == Direction::Down {
        return;
    }
    if facing != Direction::Up {
        break_tick(game, pos, facing, entity, rpm);
        return;
    }
    if rpm == 0.0 || entity.items.len() != SLOTS {
        return;
    }
    let remaining = float(&entity.nbt, "ProcessingTime").unwrap_or(-1.0);
    if remaining == -1.0 {
        if let Some(stack) = &entity.items[0] {
            let recipes = cuts(game, stack, filter(entity).as_ref());
            configure_start(entity, &recipes);
        }
        return;
    }
    let next = remaining - (rpm.abs() / 24.0).clamp(1.0, 128.0);
    let applied = matches!(entity.nbt.get(&"AppliedRecipe".into()), Some(Tag::Byte(1)));
    if next < 5.0 && !applied {
        apply(game, entity);
        entity.nbt.insert("AppliedRecipe".into(), Tag::Byte(1));
        set_float(&mut entity.nbt, "RecipeTime", 20.0);
        set_float(&mut entity.nbt, "ProcessingTime", 20.0);
    } else if next <= 0.0 {
        set_float(&mut entity.nbt, "ProcessingTime", 0.0);
        eject(game, pos, movement(axis, rpm), entity);
    } else {
        set_float(&mut entity.nbt, "ProcessingTime", next);
    }
}

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(BLADE_MODELS.into_iter().flatten().map(String::from));
    models.push("create:block/shaft_half".into());
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some((facing, axis)) = geometry(game, state) else {
        return;
    };
    let rpm = float(&entity.nbt, "Speed").unwrap_or(0.0);
    let vertical = matches!(facing, Direction::Up | Direction::Down);
    let variant = if rpm < 0.0 { 2 } else { usize::from(rpm > 0.0) };
    let yaw = match facing {
        Direction::East => 90.0,
        Direction::North => 180.0,
        Direction::West => 270.0,
        _ => 0.0,
    };
    draw.push();
    if vertical {
        if axis == 0 {
            draw.rotate_about([0.0, 1.0, 0.0], 90.0, CENTER);
        }
        let pitch = if facing == Direction::Up { -90.0 } else { 90.0 };
        draw.rotate_about([1.0, 0.0, 0.0], pitch, CENTER);
    } else {
        draw.rotate_about([0.0, 1.0, 0.0], yaw, CENTER);
    }
    game.native_draw_model(draw, BLADE_MODELS[usize::from(vertical)][variant], 0xFFFFFF);
    draw.pop();
    let angle = wheel_angle(draw.game_time, draw.partial, rpm, 0.0);
    if vertical {
        draw_rotating(game, draw, axis, angle, "create:block/shaft");
    } else {
        draw.push();
        draw.rotate_about([0.0, 1.0, 0.0], yaw + 180.0, CENTER);
        draw.rotate_about([0.0, 0.0, 1.0], angle, CENTER);
        game.native_draw_model(draw, "create:block/shaft_half", 0xFFFFFF);
        draw.pop();
    }
}

fn filter_hit(game: &Game<'_>, position: [i32; 3], axis: usize) -> bool {
    let Some(hit) = game.native_raycast(5.0) else {
        return false;
    };
    let flipped = game.native_block_property(position, "flipped").as_deref() == Some("true");
    let side = if flipped { -3.0 } else { 3.0 } / 16.0;
    let expected = [
        0.5 + if axis == 0 { side } else { 0.0 },
        0.78125,
        0.5 + if axis == 2 { side } else { 0.0 },
    ];
    let actual = [hit.x, hit.y, hit.z];
    (0..3)
        .map(|i| (actual[i] - f64::from(position[i]) - expected[i]).powi(2))
        .sum::<f64>()
        < 0.125_f64.powi(2)
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if *canceled || game.native_block(pos) != SAW || !game.may_build() {
        return;
    }
    let Some((Direction::Up, axis)) = geometry(game, state_at(game, pos)) else {
        return;
    };
    let held = game.held().cloned();
    if filter_hit(game, pos, axis) {
        game.native_with_mod_block_entity(pos, |entity| {
            if let Some(mut stack) = held {
                stack.count = 1;
                entity
                    .nbt
                    .insert("Filter".into(), super::create_depot::encode(&stack));
            } else {
                entity.nbt.remove(&"Filter".into());
            }
        });
    } else if held.is_none() {
        let Some(items) = game.native_with_mod_block_entity(pos, |entity| {
            set_float(&mut entity.nbt, "ProcessingTime", 0.0);
            set_float(&mut entity.nbt, "RecipeTime", 0.0);
            entity.nbt.insert("AppliedRecipe".into(), Tag::Byte(0));
            entity
                .items
                .iter_mut()
                .filter_map(Option::take)
                .collect::<Vec<_>>()
        }) else {
            return;
        };
        for stack in items {
            if let Some(left) = game.give(stack) {
                game.add_item_entity(left, pos.map(|value| f64::from(value) + 0.5), None, 10);
            }
        }
    } else {
        return;
    }
    game.native_block_entity_sync(pos);
    game.swing_arm();
    if game.lan_acting.is_some() && game.held().is_some() {
        game.guest_inventory_resend = true;
    }
    *canceled = true;
}

pub(super) fn place(
    level: &super::GameLevel<'_>,
    state: BlockStateId,
    context: &horizon_world::level::PlacementContext,
) -> Option<BlockStateId> {
    use horizon_core::geometry::Vec3;
    use horizon_world::level::LevelAccess;

    if level.registry.state(state)?.name != SAW {
        return None;
    }
    let direction = |pitch| {
        let [x, y, z] = super::view_vector(context.yaw, pitch);
        Direction::approximate_nearest(Vec3::new(x, y, z))
    };
    let horizontal = direction(0.0);
    let mut facing = direction(context.pitch);
    if !context.sneaking {
        facing = facing.opposite();
    }
    let connects = |side: Direction| {
        let [x, y, z] = side.normal();
        let Some(neighbor) = level
            .registry
            .state(level.block_state(context.pos.offset(x, y, z)))
        else {
            return false;
        };
        match neighbor.name.as_str() {
            "create:shaft" | "create:andesite_encased_shaft" | "create:brass_encased_shaft" => {
                let axis = if x != 0 {
                    "x"
                } else if y != 0 {
                    "y"
                } else {
                    "z"
                };
                neighbor
                    .properties
                    .get("axis")
                    .is_some_and(|value| value == axis)
            }
            "create:creative_motor" => neighbor
                .properties
                .get("facing")
                .is_some_and(|value| value.as_str() == super::create_fluids::name(side.opposite())),
            _ => false,
        }
    };
    let vertical = matches!(facing, Direction::Up | Direction::Down);
    let mut first = matches!(facing, Direction::North | Direction::South);
    if vertical {
        let x = connects(Direction::East) || connects(Direction::West);
        let z = connects(Direction::North) || connects(Direction::South);
        first = if x == z {
            matches!(horizontal, Direction::East | Direction::West)
        } else {
            x
        };
    } else if connects(Direction::Up) || connects(Direction::Down) {
        first = !first;
    }
    let flipped = vertical && matches!(horizontal, Direction::East | Direction::South);
    let boolean = |value| if value { "true" } else { "false" };
    let state =
        level.native_state_with_property(state, "facing", super::create_fluids::name(facing))?;
    let state = level.native_state_with_property(state, "axis_along_first", boolean(first))?;
    level.native_state_with_property(state, "flipped", boolean(flipped))
}
