use horizon_core::{
    geometry::{Aabb, Vec3},
    position::BlockPos,
    random::RandomSource,
};
use horizon_world::level::PlaceContext;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::create_assembly::{self, Action, ResultStack};
use super::create_fluids::BASIN;
use super::create_machines::{
    advancement_owner, facing_axis, float, ingredient_matches, int, offset, reading, set_float,
};
use super::create_mixer::{apply, compacting_recipe};
use super::create_press_processing;
use super::create_visuals::{draw_rotating, wheel_angle};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const PRESS: &str = "create:mechanical_press";
const HEAD_MODEL: &str = "create:block/mechanical_press/head";
const SHAFT_MODEL: &str = "create:block/shaft";
const CYCLE: i32 = create_press_processing::CYCLE;
const WORLD_MODE: i32 = 0;
const BELT_MODE: i32 = 1;
const BASIN_MODE: i32 = 2;
const WORLD_SCAN_TICKS: i32 = 10;
const WORLD_SCAN_SLOT: usize = 3;

pub(super) fn assembly_operator(item: &str) -> bool {
    matches!(item, PRESS | super::create_mixer::MIXER)
}

pub(super) fn operator_support(level: &GameLevel<'_>, pos: BlockPos) -> bool {
    let state = level.world.block(pos.x, pos.y, pos.z);
    let Some(state) = level.registry.state(state) else {
        return false;
    };
    match state.name.as_str() {
        BASIN | super::create_depot::DEPOT | super::create_ejector::EJECTOR => true,
        super::create_belt::BELT => state
            .properties
            .get("slope")
            .is_some_and(|value| value == "horizontal"),
        _ => false,
    }
}

pub(super) fn redirect_placement(game: &mut Game<'_>, context: &mut PlaceContext) {
    if !assembly_operator(&context.item) || context.face != horizon_core::geometry::Direction::Up {
        return;
    }
    let clicked = context.clicked_pos;
    let target = BlockPos::new(clicked.x, clicked.y + 2, clicked.z);
    if game.with_level(|behaviour, level, _| {
        operator_support(level, clicked)
            && behaviour.is_replaceable(level.world.block(target.x, target.y, target.z))
    }) {
        context.clicked_pos = target;
        context.hit = Vec3::new(
            f64::from(target.x) + 0.5,
            f64::from(target.y) + 1.0,
            f64::from(target.z) + 0.5,
        );
    }
}

fn value(nbt: &Compound, key: &str) -> i32 {
    int(nbt, key).unwrap_or(0)
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    press: &mut ModBlockEntity,
    rpm: f32,
    speed_changed: bool,
) {
    let fields = &mut **press;
    let nbt = &mut fields.nbt;
    let data = &mut fields.data;
    let basin = offset(pos, [0, -2, 0]);
    let mut running = value(nbt, "Running") != 0;
    let mut changed = running || speed_changed;
    let mut ticks = value(nbt, "Ticks");
    let mut mode = value(nbt, "Mode");
    let active = match nbt.get(&"CompactingRecipe".into()) {
        Some(Tag::String(id)) => Some(id.to_string_lossy()),
        _ => None,
    };

    if running && mode == BASIN_MODE && game.native_block(basin) != BASIN {
        nbt.insert("Running".into(), Tag::Byte(0));
        nbt.insert("Ticks".into(), Tag::Int(0));
        nbt.insert("PrevTicks".into(), Tag::Int(0));
        nbt.remove(&"CompactingRecipe".into());
        game.native_block_entity_sync(pos);
        return;
    }
    if !running && rpm != 0.0 {
        let check = nbt.remove(&"CompactingCheck".into()).is_some();
        if let Some(plan) = compacting_recipe(game, basin, None) {
            if check || speed_changed {
                start_basin(nbt, &plan.id);
                running = true;
                changed = true;
                ticks = 0;
                mode = BASIN_MODE;
            } else {
                // Basin contents notify the machine after the current cycle of block entity ticks.
                nbt.insert("CompactingCheck".into(), Tag::Byte(1));
            }
        }
        if !running && scan_world(game, pos, data) {
            start(nbt, WORLD_MODE);
            changed = true;
        }
    }

    if running {
        if ticks > CYCLE {
            nbt.insert("Running".into(), Tag::Byte(0));
            nbt.insert("Finished".into(), Tag::Byte(1));
            if mode == BASIN_MODE {
                nbt.remove(&"CompactingRecipe".into());
                if let Some(id) = active
                    && compacting_recipe(game, basin, Some(&id)).is_some()
                {
                    start_basin(nbt, &id);
                } else {
                    nbt.insert("CompactingCheck".into(), Tag::Byte(1));
                }
            }
        } else {
            if ticks == CYCLE / 2 && rpm != 0.0 {
                let surface = game.native_block(basin);
                match mode {
                    BASIN_MODE => {
                        if let Some(id) = active
                            && let Some(plan) = compacting_recipe(game, basin, Some(&id))
                            && apply(game, basin, plan)
                        {
                            game.native_block_entity_sync(basin);
                        }
                        impact(game, pos, rpm, false);
                    }
                    BELT_MODE => impact(game, pos, rpm, surface == super::create_belt::BELT),
                    WORLD_MODE => {
                        if apply_world(game, pos, data) {
                            award_press(game, advancement_owner(nbt));
                        }
                        impact(game, pos, rpm, surface.ends_with("_wool"));
                    }
                    _ => {}
                }
            }
            let advanced = create_press_processing::advance(ticks, rpm).next;
            nbt.insert("PrevTicks".into(), Tag::Int(ticks));
            nbt.insert("Ticks".into(), Tag::Int(advanced));
        }
    }
    if changed {
        game.native_block_entity_sync(pos);
    }
}

fn impact(game: &mut Game<'_>, pos: [i32; 3], rpm: f32, wool: bool) {
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    if wool {
        game.native_play_sound_in_place(
            "create:mechanical_press_activation_belt",
            at,
            4,
            0.75,
            1.0,
        );
        game.native_play_sound_in_place(
            "create:mechanical_press_activation_belt_compounded_1",
            at,
            4,
            0.15,
            0.75,
        );
    } else {
        let pitch = 0.75 + rpm.abs() / 1024.0;
        game.native_play_sound_in_place("create:mechanical_press_activation", at, 4, 0.0625, pitch);
        game.native_play_sound_in_place(
            "create:mechanical_press_activation_compounded_1",
            at,
            4,
            0.25,
            pitch,
        );
    }
}

fn world_press_area([x, y, z]: [i32; 3]) -> Aabb {
    Aabb::block(BlockPos::new(x, y - 1, z))
}

fn world_scan_delay(data: &mut Vec<i32>) -> &mut i32 {
    if data.len() <= WORLD_SCAN_SLOT {
        data.resize(WORLD_SCAN_SLOT + 1, WORLD_SCAN_TICKS);
    }
    &mut data[WORLD_SCAN_SLOT]
}

fn scan_world(game: &Game<'_>, pos: [i32; 3], data: &mut Vec<i32>) -> bool {
    let cooldown = world_scan_delay(data);
    *cooldown = (*cooldown - 1).max(0);
    if *cooldown > 0 {
        return false;
    }
    *cooldown = WORLD_SCAN_TICKS;
    if matches!(
        game.native_block(offset(pos, [0, -2, 0])).as_str(),
        BASIN
            | super::create_belt::BELT
            | super::create_depot::DEPOT
            | super::create_ejector::EJECTOR
    ) {
        return false;
    }
    let area = world_press_area(pos).deflate(Vec3::new(0.125, 0.125, 0.125));
    game.dropped.iter().any(|item| {
        item.on_ground
            && item.bounds().intersects(area)
            && pressing_result(game, &item.stack).is_some()
    })
}

fn award_press(game: &mut Game<'_>, owner: Option<u128>) {
    if let Some(player) = owner {
        game.native_trigger_criterion(player, "create:mechanical_press_builtin", |_| true);
    }
}

fn apply_world(game: &mut Game<'_>, pos: [i32; 3], data: &mut Vec<i32>) -> bool {
    let area = world_press_area(pos);
    let Some(index) = game
        .dropped
        .iter()
        .position(|item| {
            item.on_ground
                && item.bounds().intersects(area)
                && pressing_result(game, &item.stack).is_some()
        })
    else {
        return false;
    };
    *world_scan_delay(data) = 0;
    let Some(output) = pressing_result(game, &game.dropped[index].stack) else {
        return false;
    };
    let output = output.stack(game);
    if game.dropped[index].stack.count == 1 {
        game.dropped[index].stack = output;
    } else {
        let position = game.dropped[index].position;
        let impulse =
            std::array::from_fn(|_| f64::from((game.world.random.next_float() - 0.5) * 0.1));
        game.dropped[index].stack.count -= 1;
        game.add_item_entity(
            output,
            [position.x, position.y, position.z],
            Some(impulse),
            10,
        );
    }
    true
}

fn start(nbt: &mut Compound, mode: i32) {
    nbt.insert("Running".into(), Tag::Byte(1));
    nbt.insert("Mode".into(), Tag::Int(mode));
    nbt.insert("PrevTicks".into(), Tag::Int(0));
    nbt.insert("Ticks".into(), Tag::Int(0));
}

fn start_basin(nbt: &mut Compound, recipe: &str) {
    start(nbt, BASIN_MODE);
    nbt.insert("CompactingRecipe".into(), Tag::String(recipe.into()));
}

fn result(game: &Game<'_>, input: &ItemStack) -> Option<ItemStack> {
    game.native_recipes_of_type("create:pressing")
        .iter()
        .find_map(|recipe| {
            let ingredient = recipe.json["ingredients"].as_array()?.first()?;
            if !ingredient_matches(game, ingredient, &input.item) {
                return None;
            }
            let output = recipe.json["results"].as_array()?.first()?;
            game.native_recipe_result(output)
        })
}

fn pressing_result(game: &Game<'_>, stack: &ItemStack) -> Option<ResultStack> {
    create_assembly::result(game, stack, "create:pressing", None)
        .or_else(|| result(game, stack).map(ResultStack::Item))
}

pub(super) fn offer_belt(
    game: &mut Game<'_>,
    pos: [i32; 3],
    stack: &mut ItemStack,
    locked: bool,
) -> Action {
    let Some(entity) = super::create_machines::mod_entity(game, pos) else {
        return Action::Pass;
    };
    if reading(entity, 0) == 0.0 {
        return Action::Pass;
    }
    let running = value(&entity.nbt, "Running") != 0;
    if (running && !locked) || (running && value(&entity.nbt, "Ticks") != CYCLE / 2) {
        return Action::Hold;
    }
    if !running && locked {
        return Action::Pass;
    }
    let output = pressing_result(game, stack);
    let Some(output) = output else {
        return Action::Pass;
    };
    if running {
        let owner = advancement_owner(&entity.nbt);
        award_press(game, owner);
        stack.count -= 1;
        return Action::Output {
            stack: output.stack(game),
            locked: true,
        };
    }
    game.native_with_mod_block_entity(pos, |press| {
        start(&mut press.nbt, BELT_MODE);
    });
    game.native_block_entity_sync(pos);
    Action::Hold
}

pub(super) fn receive(game: &mut Game<'_>, depot: [i32; 3], entity: &mut ModBlockEntity) {
    let press_pos = offset(depot, [0, 2, 0]);
    if game.native_block(press_pos) != PRESS {
        return;
    }
    let Some(input) = entity.items[0].as_ref() else {
        return;
    };
    let output = pressing_result(game, input);
    let was_locked = value(&entity.nbt, "PressLocked") != 0;
    let Some((locked, pressed, started)) = game.native_with_mod_block_entity(press_pos, |press| {
        if press.id != PRESS || reading(press, 0) == 0.0 {
            return (false, false, false);
        }
        let nbt = &mut press.nbt;
        if value(nbt, "Running") != 0 {
            return (true, value(nbt, "Ticks") == CYCLE / 2 && was_locked, false);
        }
        if was_locked || output.is_none() {
            return (false, false, false);
        }
        start(nbt, BELT_MODE);
        (true, false, true)
    }) else {
        return;
    };
    entity
        .nbt
        .insert("PressLocked".into(), Tag::Byte(i8::from(locked)));
    if started {
        game.native_block_entity_sync(press_pos);
    }
    if pressed && let Some(output) = output {
        let owner = super::create_machines::mod_entity(game, press_pos)
            .and_then(|press| advancement_owner(&press.nbt));
        award_press(game, owner);
        let output = output.stack(game);
        let Some(input) = entity.items[0].as_mut() else {
            return;
        };
        input.count -= 1;
        if input.count == 0 {
            entity.items[0] = Some(output);
        } else {
            let limit = game.native_max_stack_size(&output.item).unwrap_or(64);
            let left = super::create_machines::insert(&mut entity.items[1..], &output, limit);
            if left != 0 {
                let at = horizon_core::position::BlockPos::new(depot[0], depot[1], depot[2]);
                let leftover = ItemStack {
                    count: left,
                    ..output
                };
                game.with_level(|_, level, _| level.drop_lost_contents(at, vec![Some(leftover)]));
            }
        }
        set_float(&mut entity.nbt, "BeltPosition", 0.5);
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    set_float(&mut tag, "VisualSpeed", reading(entity, 0));
    for key in ["Running", "Mode", "PrevTicks", "Ticks"] {
        tag.insert(key.into(), Tag::Int(value(&entity.nbt, key)));
    }
    tag
}

pub(super) fn head_offset(nbt: &Compound, partial: f32) -> f32 {
    if value(nbt, "Running") == 0 {
        return 0.0;
    }
    let current = value(nbt, "Ticks").abs();
    let previous = value(nbt, "PrevTicks") as f32;
    let ticks = previous + (current as f32 - previous) * partial;
    let travel = if current < (CYCLE * 2) / 3 {
        f64::from(ticks / CYCLE as f32 * 2.0)
            .powi(3)
            .clamp(0.0, 1.0) as f32
    } else {
        ((CYCLE as f32 - ticks) / CYCLE as f32 * 3.0).clamp(0.0, 1.0)
    };
    travel
        * match value(nbt, "Mode") {
            BELT_MODE => 19.0 / 16.0,
            BASIN_MODE => 22.0 / 16.0,
            _ => 1.0,
        }
}

pub(super) fn register_models(models: &mut Vec<String>) {
    models.push(HEAD_MODEL.into());
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let facing = game
        .native_block_state_property(state, "facing")
        .unwrap_or("north");
    let Some(axis) = facing_axis(facing) else {
        return;
    };
    let phase = if (pos[(axis + 1) % 3] + pos[(axis + 2) % 3]) % 2 == 0 {
        22.5
    } else {
        0.0
    };
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let angle = wheel_angle(draw.game_time, draw.partial, rpm, phase);
    draw_rotating(game, draw, axis, angle, SHAFT_MODEL);
    let yaw = match facing {
        "east" => -90.0,
        "south" => 180.0,
        "west" => 90.0,
        _ => 0.0,
    };
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.translate([0.0, -head_offset(&entity.nbt, draw.partial), 0.0]);
    game.native_draw_model(draw, HEAD_MODEL, 0xffffff);
    draw.pop();
}
