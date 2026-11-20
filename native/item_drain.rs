use horizon_assets::item_model::DisplayContext;
use horizon_core::geometry::{Direction, Vec3};
use horizon_core::position::BlockPos;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;
use horizon_client::first_person::Hand;

use super::create_depot::{compound, encode};
use super::create_fluids::{self, Fluid};
use super::create_machines::{float, ingredient_matches, int, mod_entity, offset, set_float};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const DRAIN: &str = "create:item_drain";
const CAPACITY: i32 = 1500;
const PROCESSING: i32 = 20;
const STEP: f32 = 0.125;

fn held(nbt: &Compound) -> Option<&Compound> {
    compound(nbt, "HeldItem")
}

fn entrance(nbt: &Compound) -> Direction {
    Direction::ALL[int(nbt, "InDirection").unwrap_or(2).rem_euclid(6) as usize]
}

fn position(nbt: &Compound) -> f32 {
    float(nbt, "Pos").unwrap_or(0.0)
}

pub(super) fn contents(entity: &ModBlockEntity) -> Option<Fluid> {
    super::create_spout::contents(entity)
}

fn write_contents(entity: &mut ModBlockEntity, fluid: Fluid) {
    let mut content = Compound::new();
    if fluid.amount > 0 {
        content.insert("Fluid".into(), fluid.nbt());
    }
    entity.nbt.insert(
        "Tanks".into(),
        Tag::List(vec![Tag::Compound(Compound::from([(
            "TankContent".into(), Tag::Compound(content),
        )]))]),
    );
}

pub(super) fn write(game: &mut Game<'_>, pos: [i32; 3], fluid: Fluid) {
    game.native_with_mod_block_entity(pos, |entity| write_contents(entity, fluid));
    game.container_changed((pos[0], pos[1], pos[2]));
    game.native_block_entity_sync(pos);
}

pub(super) fn operation(game: &Game<'_>, stack: &ItemStack) -> Option<(Fluid, Option<ItemStack>)> {
    let (amount, empty) = match stack.item.as_ref() {
        "minecraft:water_bucket" | "minecraft:lava_bucket" | "minecraft:milk_bucket" => (1000, "minecraft:bucket"),
        item if horizon_world::fluid::FluidKind::of_bucket(item).is_some() => (1000, "minecraft:bucket"),
        "minecraft:potion" | "minecraft:splash_potion" | "minecraft:lingering_potion" => {
            (250, "minecraft:glass_bottle")
        }
        _ => {
            for recipe in game.native_recipes_of_type("create:emptying") {
                let ingredients = recipe.json["ingredients"].as_array()?;
                let Some(item) = ingredients.first() else {
                    continue;
                };
                if !ingredient_matches(game, item, &stack.item) {
                    continue;
                }
                let results = recipe.json["results"].as_array()?;
                let liquid = results.iter().find(|output| output.get("amount").is_some())?;
                let fluid = Fluid {
                    id: liquid["id"].as_str()?.to_owned(),
                    amount: liquid["amount"].as_i64()?.try_into().ok()?,
                    components: None,
                };
                let item = results.iter().find(|output| output.get("amount").is_none())
                    .and_then(|result| game.native_recipe_result(result));
                return Some((fluid, item));
            }
            return None;
        }
    };
    create_fluids::liquid_from_stack(stack, amount)
        .map(|fluid| (fluid, Some(ItemStack::new(empty, 1))))
}

fn set_item(entity: &mut ModBlockEntity, previous: f32, pos: f32, motion: Direction) {
    let Some(Some(stack)) = entity.items.first() else {
        entity.nbt.remove(&"HeldItem".into());
        return;
    };
    let mut nbt = Compound::from([
        ("Item".into(), encode(stack)),
        ("InDirection".into(), Tag::Int(motion as i32)),
    ]);
    set_float(&mut nbt, "PrevPos", previous);
    set_float(&mut nbt, "Pos", pos);
    entity.nbt.insert("HeldItem".into(), Tag::Compound(nbt));
}

fn insert(entity: &mut ModBlockEntity, stack: &ItemStack, count: u32, start: f32, motion: Direction) -> bool {
    if held(&entity.nbt).is_some() {
        return false;
    }
    let Some(slot) = entity.items.first_mut() else { return false };
    if slot.is_some() {
        return false;
    }
    *slot = Some(ItemStack { count, ..stack.clone() });
    set_item(entity, start, start, motion);
    true
}

pub(super) fn accept(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack, motion: Direction) -> u32 {
    if motion.normal()[1] != 0 {
        return 0;
    }
    let count = if operation(game, stack).is_some() {
        1
    } else {
        stack.count.min(game.native_max_stack_size(&stack.item).unwrap_or(64))
    };
    let moved = game.native_with_mod_block_entity(pos, |entity| {
        entity.id == DRAIN && insert(entity, stack, count, 0.0, motion)
    }) == Some(true);
    if moved {
        game.native_block_entity_sync(pos);
    }
    if moved { count } else { 0 }
}

fn landed(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) -> bool {
    let [x, y, z] = pos.map(f64::from);
    let Some(index) = game.dropped.iter().position(|item| {
        let p = item.position;
        item.on_ground && (x..x + 1.0).contains(&p.x)
            && (z..z + 1.0).contains(&p.z)
            && (y..=y + 1.0).contains(&p.y)
    }) else {
        return false;
    };
    let item = &game.dropped[index];
    let stack = item.stack.clone();
    let motion = Direction::approximate_nearest(Vec3 { x: item.velocity.x, y: 0.0, z: item.velocity.z });
    let count = if operation(game, &stack).is_some() { 1 } else { stack.count };
    if !insert(entity, &stack, count, 0.0, motion) {
        return false;
    }
    if count == stack.count {
        game.remove_dropped(index);
    } else {
        game.dropped[index].stack.count -= count;
    }
    true
}

fn put_fluid(entity: &ModBlockEntity, mut incoming: Fluid) -> Option<Fluid> {
    if let Some(existing) = contents(entity) {
        if !existing.same_variant(&incoming) {
            return None;
        }
        incoming.amount += existing.amount;
    }
    (incoming.amount <= CAPACITY).then_some(incoming)
}

fn eject(game: &mut Game<'_>, pos: [i32; 3], stack: ItemStack, motion: Direction) -> Option<ItemStack> {
    let direction = motion.normal();
    let next = offset(pos, direction);
    match game.native_block(next).as_str() {
        DRAIN => {
            let count = accept(game, next, &stack, motion);
            let left = stack.count - count;
            (left > 0).then_some(ItemStack { count: left, ..stack })
        }
        super::create_depot::DEPOT => super::create_depot::receive_stack(game, next, stack),
        super::create_belt::BELT => {
            if let Some((start, index, belt, speed)) = super::create_belt::feed_point(game, next)
                && super::create_belt::can_feed(game, start, index, belt, motion, speed)
            {
                super::create_belt::feed(game, start, index, belt, motion, speed, stack);
                None
            } else {
                Some(stack)
            }
        }
        _ if game.native_block_collision(next).is_empty() => {
            let [x, _, z] = direction.map(f64::from);
            game.spawn_item(
                stack,
                [f64::from(pos[0]) + 0.5 + 0.75 * x,
                 f64::from(pos[1]) + 0.875,
                 f64::from(pos[2]) + 0.5 + 0.75 * z],
                [x * f64::from(STEP), 0.125, z * f64::from(STEP)],
                10,
            );
            None
        }
        _ => Some(stack),
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let fluid_changed = advance_fluid_display(entity);
    if entity.items.is_empty() {
        return;
    }
    if entity.items[0].is_none() {
        let was_occupied = entity.nbt.remove(&"HeldItem".into()).is_some();
        entity.nbt.insert("ProcessingTicks".into(), Tag::Int(0));
        if landed(game, pos, entity) || was_occupied || fluid_changed {
            game.native_block_entity_sync(pos);
        }
        return;
    }
    let (previous, motion) = held(&entity.nbt).map_or((0.0, Direction::North), |state| {
        (position(state), entrance(state))
    });
    let mut current = previous;
    let mut ticks = int(&entity.nbt, "ProcessingTicks").unwrap_or(0);
    if ticks > 0 {
        ticks -= 1;
        if ticks >= 5 {
            if let Some((fluid, output)) = operation(game, entity.items[0].as_ref().unwrap()) {
                if let Some(contents) = put_fluid(entity, fluid) {
                    if ticks == 5 {
                        write_contents(entity, contents);
                        game.container_changed((pos[0], pos[1], pos[2]));
                        entity.items[0] = output;
                    }
                } else {
                    ticks = PROCESSING;
                }
            } else {
                ticks = 0;
            }
        }
    } else {
        current += STEP;
        if current > 1.0 {
            current = 1.0;
            entity.items[0] = eject(game, pos, entity.items[0].take().unwrap(), motion);
        } else if previous < 0.5 && current >= 0.5
            && operation(game, entity.items[0].as_ref().unwrap()).is_some()
        {
            current = 0.5;
            ticks = PROCESSING;
        }
    }
    set_item(entity, previous, current, motion);
    entity.nbt.insert("ProcessingTicks".into(), Tag::Int(ticks));
    game.native_block_entity_sync(pos);
}

fn give(game: &mut Game<'_>, pos: [i32; 3], item: ItemStack) {
    if let Some(left) = game.give(item) {
        game.with_level(|_, level, _| {
            level.drop_lost_contents(BlockPos::new(pos[0], pos[1], pos[2]), vec![Some(left)])
        });
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if *canceled || game.native_block(pos) != DRAIN {
        return;
    }
    if game.hand != Hand::Main && game.held().is_none() {
        return;
    }
    let action = game.held().and_then(|stack| operation(game, stack));
    if let Some((incoming, output)) = action {
        if let Some(fluid) = mod_entity(game, pos).and_then(|entity| put_fluid(entity, incoming)) {
            write(game, pos, fluid);
            if !game.creative {
                let in_hand = game.held_mut();
                if let Some(held) = in_hand.as_mut() {
                    if held.count > 1 {
                        held.count -= 1;
                        if let Some(output) = output {
                            give(game, pos, output);
                        }
                    } else {
                        *in_hand = output;
                    }
                }
            }
        }
    } else {
        // Non-fluid block items retain normal placement priority. Other held
        // items fall through to cargo collection, as in ItemDrainBlock.useItemOn.
        if game.held().is_some_and(|stack| game.native_default_state(&stack.item).is_some()) {
            return;
        }
        let item = game.native_with_mod_block_entity(pos, |entity| {
            let item = entity.items.first_mut().and_then(Option::take);
            entity.nbt.remove(&"HeldItem".into());
            item
        }).flatten();
        if let Some(item) = item {
            give(game, pos, item);
            game.native_block_entity_sync(pos);
        }
    }
    game.swing_arm();
    *canceled = true;
}

pub(super) fn has_output(level: &GameLevel<'_>, state: BlockStateId, out: &mut bool) {
    *out |= level.registry.state(state).is_some_and(|block| block.name == DRAIN);
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, out: &mut i32) {
    if !level.registry.state(state).is_some_and(|block| block.name == DRAIN) {
        return;
    }
    if let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z)) {
        let amount = contents(entity).map_or(0, |fluid| fluid.amount);
        *out = if amount > 0 { 1 + 14 * amount / CAPACITY } else { 0 };
    }
}

pub(super) fn render(game: &Game<'_>, pos: [i32; 3], entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    draw_fluid(game, entity, draw);
    trace_visual(game, pos, entity);
    let Some(nbt) = held(&entity.nbt) else { return };
    let Some(stack) = compound(nbt, "Item").and_then(ItemStack::from_nbt) else { return };
    let current = position(nbt);
    let prior = float(nbt, "PrevPos").unwrap_or(current);
    let offset = prior + (current - prior) * draw.partial;
    let [x, _, z] = entrance(nbt).normal().map(|value| value as f32);
    draw.push();
    draw.translate([0.5 + x * (offset - 0.5), 15.0 / 16.0, 0.5 + z * (offset - 0.5)]);
    draw.rotate_about([z, 0.0, -x], offset * 360.0, [0.0; 3]);
    draw.scale([0.5; 3]);
    draw.rotate_about([1.0, 0.0, 0.0], 90.0, [0.0; 3]);
    game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0);
    draw.pop();
}

const FLUID_VISUAL: &str = "DrainFluidVisual";

fn advance_fluid_display(entity: &mut ModBlockEntity) -> bool {
    let prior = compound(&entity.nbt, FLUID_VISUAL);
    let previous = prior.and_then(|tag| float(tag, "Level")).unwrap_or(0.0);
    let tank = contents(entity);
    let target = tank.as_ref().map_or(0.0, |fluid| fluid.amount as f32 / CAPACITY as f32);
    let distance = target - previous;
    let current = if distance.abs() < 1.0e-5 {
        target
    } else {
        previous + distance * 0.25
    };
    let liquid = tank.map(|fluid| fluid.nbt())
        .or_else(|| prior.and_then(|tag| tag.get(&"Fluid".into())).cloned());
    let next = liquid
        .filter(|_| previous != 0.0 || current != 0.0)
        .map(|liquid| {
            let mut state = Compound::from([("Fluid".into(), liquid)]);
            set_float(&mut state, "PreviousLevel", previous);
            set_float(&mut state, "Level", current);
            state
        });
    if next.as_ref() == prior {
        return false;
    }
    if let Some(state) = next {
        entity.nbt.insert(FLUID_VISUAL.into(), Tag::Compound(state));
    } else {
        entity.nbt.remove(&FLUID_VISUAL.into());
    }
    true
}

fn fluid_level(entity: &ModBlockEntity, partial: f32) -> f32 {
    let Some(tag) = compound(&entity.nbt, FLUID_VISUAL) else { return 0.0 };
    let previous = float(tag, "PreviousLevel").unwrap_or(0.0);
    let current = float(tag, "Level").unwrap_or(0.0);
    previous + (current - previous) * partial
}

fn stream_radius(ticks: i32, partial: f32) -> f32 {
    let progress = (1.0 - (ticks as f32 - partial - 5.0) / 10.0).clamp(0.0, 1.0);
    (1.0 - (2.0 * progress - 1.0).powi(2)) / 32.0
}

fn draw_fluid(game: &Game<'_>, entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    use super::create_spout::draw_still_fluid;

    let level = fluid_level(entity, draw.partial);
    if level > 0.0
        && let Some(liquid) = compound(&entity.nbt, FLUID_VISUAL)
            .and_then(|tag| compound(tag, "Fluid"))
            .and_then(create_fluids::read_fluid)
    {
        draw_still_fluid(game, draw, &liquid, [2.0, 5.0, 2.0], [12.0, 7.0 * level, 12.0]);
    }
    let ticks = int(&entity.nbt, "ProcessingTicks").unwrap_or(0);
    let radius = stream_radius(ticks, draw.partial) * 16.0;
    if radius > 0.0
        && let Some(item) = held(&entity.nbt).and_then(|tag| compound(tag, "Item"))
            .and_then(ItemStack::from_nbt)
        && let Some(liquid) = operation(game, &item).map(|(fluid, _)| fluid).or_else(|| contents(entity))
    {
        draw_still_fluid(
            game, draw, &liquid,
            [8.0 - radius, 4.0 + radius, 8.0 - radius],
            [2.0 * radius, 12.0 - 2.0 * radius, 2.0 * radius],
        );
    }
}

fn trace_visual(game: &Game<'_>, pos: [i32; 3], entity: &ModBlockEntity) {
    use std::sync::OnceLock;

    static ENABLED: OnceLock<bool> = OnceLock::new();
    if !ENABLED.get_or_init(|| std::env::var_os("CREATE_ITEM_DRAIN_VISUAL").is_some()) {
        return;
    }
    for partial in [0.0, 0.5, 1.0] {
        let level = fluid_level(entity, partial);
        let radius = stream_radius(int(&entity.nbt, "ProcessingTicks").unwrap_or(0), partial);
        eprintln!("CREATE_DRAIN_FRAME {} {} {} {} {partial:.1} {level:.9} {:.9} {radius:.9}",
            game.world.game_time, pos[0], pos[1], pos[2], level * 7.0 / 16.0);
    }
}
