use horizon_core::geometry::Direction;
use horizon_world::level::{PlacementContext, flags, ordered_by_nearest};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::player_inventory::EquipmentSlot;
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;

use super::create_machines::{float, int, mod_entity, offset};
use super::create_smart_observer::OBSERVER;
use super::{Game, GameLevel};

pub(super) const THRESHOLD_SWITCH: &str = "create:stockpile_switch";

pub(super) fn configured(nbt: &Compound, current: &str, old: &str, default: i32) -> i32 {
    int(nbt, current)
        .or_else(|| float(nbt, current).map(|n| n as i32))
        .unwrap_or_else(|| {
            if nbt.contains_key(&old.into()) {
                0
            } else {
                default
            }
        })
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<Option<BlockStateId>> {
    let observer = match level.native_state_block(state) {
        Some(OBSERVER) => true,
        Some(THRESHOLD_SWITCH) => false,
        _ => return None,
    };
    let accepts = |direction: Direction| {
        let [x, y, z] = direction.normal();
        let pos = context.pos.offset(x, y, z);
        let state = level.world.block(pos.x, pos.y, pos.z);
        if observer && matches!(level.native_state_block(state), Some(
            super::create_belt::BELT | super::create_depot::DEPOT
            | super::create_belt_funnel::ANDESITE | super::create_belt_funnel::BRASS
            | super::create_funnel::ANDESITE | super::create_funnel::BRASS
            | super::create_fluids::PIPE | super::create_fluids::GLASS_PIPE | super::create_fluids::PUMP
            | super::create_encased_fluid_pipe::BLOCK
        )) {
            return true;
        }
        level
            .world
            .block_entities
            .get(&(pos.x, pos.y, pos.z))
            .is_some_and(|entity| {
                !entity.slots().is_empty()
                    || level.world.block_entities.mod_fluids(state.0).is_some()
                    || matches!(entity, BlockEntity::Mod(mod_entity)
                    if matches!(mod_entity.id.as_str(),
                        super::create_fluid_tank::TANK | super::create_fluid_tank::CREATIVE))
            })
    };
    let clicked = context.face.opposite();
    let preferred = if !context.replace_clicked && accepts(clicked) {
        Some(clicked)
    } else {
        ordered_by_nearest(context.yaw, context.pitch)
            .into_iter()
            .find(|&dir| accepts(dir))
    };
    let direction = preferred.unwrap_or_else(|| {
        let looking = context.nearest_looking_direction();
        if context.sneaking {
            looking
        } else {
            looking.opposite()
        }
    });
    let yaw = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32).rem_euclid(4) as usize;
    let horizontal = ["south", "west", "north", "east"][yaw];
    let (mount, facing) = match direction {
        Direction::Down => ("floor", horizontal),
        Direction::Up => ("ceiling", horizontal),
        Direction::South => ("wall", "south"),
        Direction::West => ("wall", "west"),
        Direction::North => ("wall", "north"),
        Direction::East => ("wall", "east"),
    };
    Some(
        level
            .native_state_with_property(state, "target", mount)
            .and_then(|state| level.native_state_with_property(state, "facing", facing)),
    )
}

pub(super) fn target(attachment: &str, facing: &str) -> Direction {
    match (attachment, facing) {
        ("ceiling", _) => Direction::Up,
        ("floor", _) => Direction::Down,
        (_, "east") => Direction::East,
        (_, "west") => Direction::West,
        (_, "south") => Direction::South,
        _ => Direction::North,
    }
}

pub(super) fn delta(direction: Direction) -> [i32; 3] {
    match direction {
        Direction::East => [1, 0, 0],
        Direction::West => [-1, 0, 0],
        Direction::Up => [0, 1, 0],
        Direction::Down => [0, -1, 0],
        Direction::South => [0, 0, 1],
        Direction::North => [0, 0, -1],
    }
}

fn observed_items(game: &Game<'_>, pos: [i32; 3], filter: Option<&Compound>) -> (i32, i32) {
    let Some(block) = game.world.block_entities.get(&(pos[0], pos[1], pos[2])) else {
        return (-1, -1);
    };
    let slots = block.slots();
    if slots.is_empty() {
        return (-1, -1);
    }
    let mut count = 0;
    let mut capacity = 0;
    for slot in slots {
        let Some(stack) = slot else {
            capacity += 64;
            continue;
        };
        let limit = stack
            .data()
            .and_then(|data| data.other("minecraft:max_stack_size"))
            .and_then(|tag| match tag {
                Tag::Int(n) => Some(*n),
                _ => None,
            })
            .unwrap_or_else(|| {
                game.res
                    .items()
                    .get(&stack.item)
                    .map_or(64, |item| item.max_stack as i32)
            });
        capacity += limit.clamp(1, 64);
        if filter.is_none_or(|filter| {
            super::create_item_filters::matches(game.items(), filter, stack, false)
        }) {
            count += stack.count as i32;
        }
    }
    (count.min(capacity), capacity)
}

fn filter_side(bottom: bool, observed: Direction, facing: Direction, side: Direction) -> bool {
    use Direction::{Down, Up};
    if side == observed {
        return false;
    }
    if side == observed.opposite() {
        return true;
    }
    if !matches!(observed, Up | Down) {
        return side == Up || bottom && side == Down;
    }
    if !bottom {
        return side
            == if observed == Up {
                facing.opposite()
            } else {
                facing
            };
    }
    let across = super::create_wrench::rotate(facing, Up);
    side == across || side == across.opposite()
}

pub(super) fn filter_hit(game: &Game<'_>, hit: &super::Hit, bottom: bool) -> bool {
    let Some(side) = Direction::ALL
        .into_iter()
        .find(|side| side.normal() == hit.face)
    else {
        return false;
    };
    let center: [f64; 3] = std::array::from_fn(|index| {
        f64::from(hit.pos[index]) + 0.5 + f64::from(hit.face[index]) * (7.5 / 16.0)
    });
    if hit
        .point
        .into_iter()
        .zip(center)
        .map(|(point, center)| (point - center).powi(2))
        .sum::<f64>()
        >= 0.25f64.powi(2)
    {
        return false;
    }
    let [x, y, z] = hit.pos;
    let state = game.world.block(x, y, z);
    let state = mod_entity(game, hit.pos).map_or(state, |entity| observed_state(entity, state));
    let facing = game
        .native_block_state_property(state, "facing")
        .unwrap_or("north");
    let attachment = game
        .native_block_state_property(state, "target")
        .unwrap_or("wall");
    filter_side(
        bottom,
        target(attachment, facing),
        target("wall", facing),
        side,
    )
}

pub(super) fn filter_click(game: &mut Game<'_>, pos: [i32; 3], normal: [i32; 3]) -> bool {
    let bottom = match game.native_block(pos).as_str() {
        THRESHOLD_SWITCH => true,
        OBSERVER => false,
        _ => return false,
    };
    if !game.may_build() || game.native_sneaking() {
        return false;
    }
    if game
        .native_equipment(EquipmentSlot::MainHand)
        .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
    {
        return false;
    }
    let selected = game.held().cloned();
    if selected.as_ref().is_some_and(|stack| {
        matches!(
            stack.item.as_ref(),
            "create:wrench" | "create:mechanical_arm" | "create:clipboard"
        )
    }) {
        return false;
    }
    if !game
        .pick()
        .is_some_and(|hit| hit.pos == pos && hit.face == normal && filter_hit(game, &hit, bottom))
    {
        return false;
    }
    let Some(mut entity) = mod_entity(game, pos).cloned() else {
        return false;
    };
    let previous_filter = super::create_depot::compound(&entity.nbt, "Filter")
        .and_then(ItemStack::from_nbt)
        .filter(is_filter_item);
    let consumes = !game.creative && selected.as_ref().is_some_and(is_filter_item);
    let filter = selected.map_or_else(
        || Tag::Compound(Compound::new()),
        |mut selected| {
            if is_filter_item(&selected) {
                selected.count = 1;
            }
            let mut encoded = super::create_depot::encode(&selected);
            if let Tag::Compound(fields) = &mut encoded {
                fields.remove(&"Slot".into());
            }
            encoded
        },
    );
    entity.nbt.insert("Filter".into(), filter);
    let resultant = if bottom {
        let previous = game.world.block(pos[0], pos[1], pos[2]);
        let observed = observed_state(&entity, previous);
        let display = sample(game, pos, &mut entity, observed);
        display.and_then(|(level, _)| sampled_state(game, previous, observed, level))
    } else {
        None
    };
    game.native_with_mod_block_entity(pos, |live| {
        live.nbt = std::mem::take(&mut entity.nbt);
        if resultant.is_some() {
            live.data.clear();
        }
    });
    if let Some(state) = resultant {
        game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_CLIENTS);
    }
    let had_filter_item = previous_filter.is_some();
    if let Some(old) = previous_filter {
        let already_held = game
            .inventory
            .iter()
            .chain(std::iter::once(&game.offhand))
            .flatten()
            .any(|stack| {
                stack.item == old.item && stack.extra == old.extra && stack.damage == old.damage
            });
        if (!game.creative || !already_held)
            && let Some(leftover) = game.give(old)
        {
            game.pop_resource(pos, leftover);
        }
    }
    if consumes {
        game.consume_held();
    }
    if consumes || had_filter_item {
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    game.native_block_entity_sync(pos);
    game.native_play_sound_in_place(
        "minecraft:entity.item_frame.add_item",
        pos.map(|v| f64::from(v) + 0.5),
        4,
        0.25,
        0.1,
    );
    game.swing_arm();
    true
}

pub(super) fn render_filter(
    game: &Game<'_>,
    pos: [i32; 3],
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    use horizon_assets::item_model::DisplayContext;

    if game.player.as_ref().is_some_and(|player| {
        [player.position.x, player.position.y, player.position.z]
            .into_iter()
            .zip(pos)
            .map(|(view, block)| (view - f64::from(block) - 0.5).powi(2))
            .sum::<f64>()
            > 100.0
    }) {
        return;
    }
    let Some(stack) =
        super::create_depot::compound(&entity.nbt, "Filter").and_then(ItemStack::from_nbt)
    else {
        return;
    };
    let state = observed_state(entity, state);
    let attachment = game
        .native_block_state_property(state, "target")
        .unwrap_or("wall");
    let facing = game
        .native_block_state_property(state, "facing")
        .unwrap_or("north");
    let facing = target("wall", facing);
    let observed = target(attachment, super::create_fluids::name(facing));
    let model = game.resolve_item(&stack, DisplayContext::Fixed, None, 0);
    let block = model.uses_block_light();
    let item_scale = if block { 1.0 } else { 0.5 } + 1.0 / 64.0;
    let item_id = stack.item.as_ref();
    let is_narrow = matches!(
        item_id,
        "create:shaft" | "create:cogwheel" | "create:large_cogwheel" | "minecraft:end_rod"
    ) || ["minecraft:fences", "minecraft:buttons"]
        .into_iter()
        .any(|tag| {
            game.items()
                .block_tags
                .get(tag)
                .is_some_and(|blocks| blocks.contains(item_id))
        });
    let item_depth = if block { 0.0 } else { -0.15 } - if is_narrow { 0.1 } else { 0.0 };
    let trace = std::env::var_os("CREATE_STOCKPILE_FILTER_RENDER").is_some();
    for side in Direction::ALL
        .into_iter()
        .filter(|&side| filter_side(entity.id == THRESHOLD_SWITCH, observed, facing, side))
    {
        let center = filter_offset(side);
        let yaw = 180.0 + filter_horizontal_angle(side);
        let pitch = match side {
            Direction::Up => 90.0,
            Direction::Down => 270.0,
            _ => 0.0,
        };
        let roll = if side == Direction::Up {
            180.0 - filter_horizontal_angle(facing)
        } else {
            0.0
        };
        draw.push();
        draw.translate(center);
        draw.rotate_about([0., 1., 0.], yaw, [0.; 3]);
        draw.rotate_about([1., 0., 0.], pitch, [0.; 3]);
        draw.rotate_about([0., 0., 1.], roll, [0.; 3]);
        draw.scale([0.5 * item_scale; 3]);
        draw.translate([0.0, 0.0, item_depth]);
        let before = if trace { draw.vertices_mut().len() } else { 0 };
        if game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0) && trace {
            let [x, y, z] = pos;
            let [ox, oy, oz] = center;
            let name = super::create_fluids::name;
            let vertices = draw.vertices_mut().len() - before;
            println!(
                "CREATE_STOCKPILE_FILTER_FRAME {x},{y},{z},{},{},{ox},{oy},{oz},{yaw},{pitch},{roll},0.5,{item_scale},{item_depth},{item_id},{vertices}",
                name(observed),
                name(side)
            );
        }
        draw.pop();
    }
}

fn filter_horizontal_angle(side: Direction) -> f32 {
    match side {
        Direction::North => 180.0,
        Direction::West => -90.0,
        Direction::East => -270.0,
        _ => 0.0,
    }
}

fn filter_offset(side: Direction) -> [f32; 3] {
    side.normal()
        .map(|component| 0.5 + (component as f32) * (7.5 / 16.0))
}

pub(super) fn release_observer_filter(
    level: &mut GameLevel<'_>,
    pos: horizon_core::position::BlockPos,
    side_effects: bool,
) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z)) else {
        return;
    };
    if entity.id != OBSERVER {
        return;
    }
    let Some(stack) = super::create_depot::compound(&entity.nbt, "Filter")
        .and_then(ItemStack::from_nbt).filter(is_filter_item) else {
        return;
    };
    level.spill.spawns.push(super::spill::Spawn {
        stack,
        pos: [pos.x, pos.y, pos.z].map(|coordinate| f64::from(coordinate) + 0.5),
        motion: None,
        delay: 0,
    });
}

fn is_filter_item(stack: &ItemStack) -> bool {
    matches!(
        stack.item.as_ref(),
        "create:filter" | "create:attribute_filter" | "create:package_filter"
    )
}

pub(super) fn observed_state(entity: &ModBlockEntity, state: BlockStateId) -> BlockStateId {
    entity
        .data
        .first()
        .map_or(state, |&id| BlockStateId(id as u32))
}

pub(super) fn wrench(game: &mut Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    let previous = game.world.block(pos[0], pos[1], pos[2]);
    let Some(attachment) = game.native_block_state_property(previous, "target") else {
        return false;
    };
    let Some(facing) = game.native_block_state_property(previous, "facing") else {
        return false;
    };
    let rotate = super::create_wrench::rotate;
    let name = super::create_fluids::name;
    let adjusted = if matches!(face, Direction::Up | Direction::Down) {
        let direction = target("wall", facing);
        (attachment, name(rotate(direction, face)))
    } else {
        let direction = rotate(target(attachment, facing), face);
        let direction = if matches!(face, Direction::West | Direction::North) {
            direction.opposite()
        } else {
            direction
        };
        match direction {
            Direction::Down => ("floor", facing),
            Direction::Up => ("ceiling", facing),
            _ => ("wall", name(direction)),
        }
    };
    let (mount, facing) = (adjusted.0.to_owned(), adjusted.1.to_owned());
    let desired = game.with_level(|_, level, _| {
        let state = level.native_state_with_property(previous, "target", &mount)?;
        level.native_state_with_property(state, "facing", &facing)
    });
    let Some(desired) = desired.filter(|&desired| desired != previous) else {
        return false;
    };
    if game.native_block(pos) == OBSERVER {
        return game.native_set_block(game.native_dimension(), pos, desired, flags::UPDATE_ALL);
    }
    let Some(mut entity) = mod_entity(game, pos).cloned() else {
        return game.native_set_block(game.native_dimension(), pos, desired, flags::UPDATE_ALL);
    };
    // Java's onPlace samples the cached block-entity mount before the entity
    // receives the new block state. Its sample can republish that previous mount.
    let observed = observed_state(&entity, previous);
    let reading = sample(game, pos, &mut entity, observed);
    let visible = reading
        .and_then(|(display, _)| sampled_state(game, previous, observed, display))
        .unwrap_or(desired);
    let remembers_mount = !same_mount(game, visible, desired);
    game.native_with_mod_block_entity(pos, |actual| {
        actual.nbt = std::mem::take(&mut entity.nbt);
        actual.data.clear();
        if remembers_mount {
            actual.data.push(desired.0 as i32);
        }
    });
    let changed = visible != previous
        && game.native_set_block(game.native_dimension(), pos, visible, flags::UPDATE_ALL);
    if reading.is_some_and(|(_, changed)| changed) {
        game.native_block_entity_sync(pos);
    }
    changed
}

fn same_mount(game: &Game<'_>, first: BlockStateId, second: BlockStateId) -> bool {
    ["target", "facing"].into_iter().all(|property| {
        game.native_block_state_property(first, property)
            == game.native_block_state_property(second, property)
    })
}

fn sampled_state(
    game: &mut Game<'_>,
    state: BlockStateId,
    observation: BlockStateId,
    display: i32,
) -> Option<BlockStateId> {
    let target = game
        .native_block_state_property(observation, "target")?
        .to_owned();
    let facing = game
        .native_block_state_property(observation, "facing")?
        .to_owned();
    game.with_level(|_, level, _| {
        let state = level.native_state_with_property(state, "target", &target)?;
        let state = level.native_state_with_property(state, "facing", &facing)?;
        level.native_state_with_property(state, "level", &display.to_string())
    })
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let nbt = &mut entity.nbt;
    let delayed = int(nbt, "PowerDelay").unwrap_or(0);
    if delayed > 0 {
        nbt.insert("PowerDelay".into(), Tag::Int(delayed - 1));
        if delayed == 1 {
            let desired =
                (int(nbt, "Powered").unwrap_or(0) != 0) != (int(nbt, "Inverted").unwrap_or(0) != 0);
            nbt.insert("PoweredAfterDelay".into(), Tag::Byte(i8::from(desired)));
            game.native_set_block_property(pos, "powered", if desired { "true" } else { "false" });
            game.native_block_entity_sync(pos);
        }
    }

    let remaining = int(nbt, "SampleDelay");
    if let Some(remaining @ 1..) = remaining {
        nbt.insert("SampleDelay".into(), Tag::Int(remaining - 1));
        return;
    }
    nbt.insert(
        "SampleDelay".into(),
        Tag::Int(if remaining.is_none() { 9 } else { 10 }),
    );
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let observation = observed_state(entity, state);
    if let Some((display, changed)) = sample(game, pos, entity, observation) {
        if same_mount(game, state, observation) {
            game.native_set_block_property_with(
                pos,
                "level",
                &display.to_string(),
                flags::UPDATE_CLIENTS,
            );
        } else if let Some(landed) = sampled_state(game, state, observation, display) {
            game.native_set_block(game.native_dimension(), pos, landed, flags::UPDATE_ALL);
        }
        entity.data.clear();
        if changed {
            game.native_block_entity_sync(pos);
        }
    }
}

fn sample(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    state: BlockStateId,
) -> Option<(i32, bool)> {
    let nbt = &mut entity.nbt;
    let face = game
        .native_block_state_property(state, "target")
        .unwrap_or("wall");
    let facing = game
        .native_block_state_property(state, "facing")
        .unwrap_or("north");
    let filter = super::create_depot::compound(nbt, "Filter");
    let observed = offset(pos, delta(target(face, facing)));
    let pulley = super::create_rope::observed(game, observed);
    let (stock, minimum, capacity) = pulley.unwrap_or_else(|| {
        let (stock, capacity) = super::create_fluid_tank::storage(game, observed)
            .map(|(_, capacity, fluid)| {
                let retained = fluid.filter(|fluid| super::create_item_filters::accepts_fluid(nbt, fluid));
                (retained.map_or(0, |fluid| fluid.amount), capacity)
            })
            .unwrap_or_else(|| observed_items(game, observed, filter));
        (stock, if stock < 0 { -1 } else { 0 }, capacity)
    });
    let previous_stock = int(nbt, "CurrentAmount");
    if pulley.is_none() && stock < 0 && previous_stock == Some(-1) {
        return None;
    }
    let changed = previous_stock != Some(stock) || int(nbt, "CurrentMaxAmount") != Some(capacity);
    nbt.insert("CurrentMinAmount".into(), Tag::Int(minimum));
    nbt.insert("CurrentAmount".into(), Tag::Int(stock));
    nbt.insert("CurrentMaxAmount".into(), Tag::Int(capacity));

    let was_powered = int(nbt, "Powered").unwrap_or(0) != 0;
    let above = configured(nbt, "OnAboveAmount", "OnAbove", 128);
    let below = configured(nbt, "OffBelowAmount", "OffBelow", 64);
    let powered = if pulley.is_none() && stock < 0 {
        false
    } else if was_powered {
        stock > below
    } else {
        stock >= above
    };
    nbt.insert("Powered".into(), Tag::Byte(i8::from(powered)));
    if powered != was_powered {
        nbt.entry("PowerDelay".into())
            .and_modify(|tag| {
                if matches!(tag, Tag::Int(0)) {
                    *tag = Tag::Int(2);
                }
            })
            .or_insert(Tag::Int(2));
    }

    let level = if stock > 0 {
        1 + (stock - minimum) * 4 / (capacity - minimum).max(1)
    } else {
        0
    };
    Some((level, changed || powered != was_powered))
}

pub(super) fn new_tag() -> Compound {
    let mut nbt = Compound::new();
    nbt.insert("CurrentAmount".into(), Tag::Int(-1));
    nbt.insert("CurrentMaxAmount".into(), Tag::Int(-1));
    nbt.insert("Powered".into(), Tag::Byte(0));
    nbt.insert("PoweredAfterDelay".into(), Tag::Byte(0));
    nbt
}

pub(super) fn source(level: &GameLevel<'_>, state: BlockStateId, source: &mut bool) {
    *source |= level
        .registry
        .state(state)
        .is_some_and(|info| match info.name.as_str() {
            THRESHOLD_SWITCH => true,
            OBSERVER => info
                .properties
                .get("powered")
                .is_some_and(|value| value == "true"),
            _ => false,
        });
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    state: BlockStateId,
    face: Direction,
    direct: bool,
    signal: &mut i32,
) {
    let Some(info) = level.registry.state(state) else {
        return;
    };
    if direct || !matches!(info.name.as_str(), THRESHOLD_SWITCH | OBSERVER) {
        return;
    }
    let prop = |key| info.properties.get(key).map_or("", String::as_str);
    if prop("powered") == "true" && face != target(prop("target"), prop("facing")) {
        *signal = 15;
    }
}
