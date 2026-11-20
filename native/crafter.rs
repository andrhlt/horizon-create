use std::collections::{BTreeMap, BTreeSet};

use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    level::flags,
    nbt::{Compound, Tag},
};

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;

use super::Game;
use super::create_depot::{compound, encode};
use super::create_fan::facing;
use super::create_machines::{DIRECTIONS, ingredient_matches, int, mod_entity, offset, reading};

pub(super) const CRAFTER: &str = "create:mechanical_crafter";
const SLOT_COVER: &str = "create:crafter_slot_cover";
const WRENCH: &str = "create:wrench";
type Pos = [i32; 3];
type Grid = BTreeMap<(i32, i32), Option<ItemStack>>;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Phase {
    Idle,
    Accepting,
    Assembling,
    Exporting,
    Waiting,
    Crafting,
    Inserting,
}

impl Phase {
    fn name(self) -> &'static str {
        match self {
            Self::Idle => "IDLE",
            Self::Accepting => "ACCEPTING",
            Self::Assembling => "ASSEMBLING",
            Self::Exporting => "EXPORTING",
            Self::Waiting => "WAITING",
            Self::Crafting => "CRAFTING",
            Self::Inserting => "INSERTING",
        }
    }

    fn read(entity: &ModBlockEntity) -> Self {
        let Some(Tag::String(name)) = entity.nbt.get(&"Phase".into()) else {
            return Self::Idle;
        };
        match name.to_string_lossy().as_str() {
            "ACCEPTING" => Self::Accepting,
            "ASSEMBLING" => Self::Assembling,
            "EXPORTING" => Self::Exporting,
            "WAITING" => Self::Waiting,
            "CRAFTING" => Self::Crafting,
            "INSERTING" => Self::Inserting,
            _ => Self::Idle,
        }
    }

    fn set(self, entity: &mut ModBlockEntity, countdown: i32) {
        entity
            .nbt
            .insert("Phase".into(), Tag::String(self.name().into()));
        entity.nbt.insert("CountDown".into(), Tag::Int(countdown));
    }
}

fn grid(entity: &ModBlockEntity) -> Grid {
    let Some(Tag::List(items)) =
        compound(&entity.nbt, "GroupedItems").and_then(|tag| tag.get(&"Grid".into()))
    else {
        return Grid::new();
    };
    items
        .iter()
        .filter_map(|tag| {
            let Tag::Compound(entry) = tag else {
                return None;
            };
            let x = int(entry, "x")?;
            let y = int(entry, "y")?;
            Some((
                (x, y),
                compound(entry, "item").and_then(ItemStack::from_nbt),
            ))
        })
        .collect()
}

fn save(entity: &mut ModBlockEntity, grid: &Grid) {
    let list = grid
        .iter()
        .map(|(&(x, y), stack)| {
            Tag::Compound(Compound::from([
                ("x".into(), Tag::Int(x)),
                ("y".into(), Tag::Int(y)),
                (
                    "item".into(),
                    stack
                        .as_ref()
                        .map_or_else(|| Tag::Compound(Compound::new()), encode),
                ),
            ]))
        })
        .collect();
    entity.nbt.insert(
        "GroupedItems".into(),
        Tag::Compound(Compound::from([("Grid".into(), Tag::List(list))])),
    );
}

fn direction(game: &Game<'_>, pos: Pos) -> Option<Direction> {
    if game.native_block(pos) != CRAFTER {
        return None;
    }
    facing(game, game.world.block(pos[0], pos[1], pos[2]))
}

fn pointing(game: &Game<'_>, pos: Pos, front: Direction) -> Option<(Direction, (i32, i32))> {
    let right = match front {
        Direction::North => Direction::West,
        Direction::West => Direction::South,
        Direction::South => Direction::East,
        Direction::East => Direction::North,
        _ => return None,
    };
    Some(
        match game.native_block_property(pos, "pointing")?.as_str() {
            "up" => (Direction::Up, (0, -1)),
            "down" => (Direction::Down, (0, 1)),
            "left" => (right.opposite(), (1, 0)),
            "right" => (right, (-1, 0)),
            _ => return None,
        },
    )
}

fn next(game: &Game<'_>, pos: Pos, front: Direction) -> Option<Pos> {
    let (out, _) = pointing(game, pos, front)?;
    let target = offset(pos, out.normal());
    (direction(game, target) == Some(front)).then_some(target)
}

fn preceding(game: &Game<'_>, pos: Pos, front: Direction) -> Vec<Pos> {
    let own_target = next(game, pos, front);
    DIRECTIONS
        .into_iter()
        .map(|step| offset(pos, step))
        .filter(|&other| {
            Some(other) != own_target
                && direction(game, other) == Some(front)
                && next(game, other, front) == Some(pos)
        })
        .collect()
}

fn chain(game: &Game<'_>, pos: Pos, front: Direction) -> Option<Vec<Pos>> {
    let mut current = pos;
    let mut seen = BTreeSet::new();
    while let Some(target) = next(game, current, front) {
        if !seen.insert(current) {
            return None;
        }
        current = target;
    }
    let mut crafters = vec![current];
    let mut index = 0;
    while index < crafters.len() {
        crafters.extend(preceding(game, crafters[index], front));
        index += 1;
    }
    Some(crafters)
}

fn input_data(game: &Game<'_>, pos: Pos) -> Option<(bool, Vec<Pos>)> {
    let crafter = mod_entity(game, pos)?;
    let Some(data) = compound(&crafter.nbt, "ConnectedInput") else {
        return Some((true, vec![pos]));
    };
    let controller = int(data, "Controller") == Some(1);
    let Some(Tag::List(offsets)) = data.get(&"Data".into()) else {
        return Some((true, vec![pos]));
    };
    let slots = offsets
        .iter()
        .filter_map(|entry| {
            let Tag::Compound(entry) = entry else {
                return None;
            };
            Some(offset(
                pos,
                [int(entry, "X")?, int(entry, "Y")?, int(entry, "Z")?],
            ))
        })
        .collect();
    Some((controller, slots))
}

fn targets(game: &Game<'_>, pos: Pos) -> Vec<Pos> {
    let Some((controller, mut targets)) = input_data(game, pos) else {
        return Vec::new();
    };
    let controller_pos = if controller {
        pos
    } else {
        let Some(&at) = targets.first() else {
            return Vec::new();
        };
        let Some((true, connected)) = input_data(game, at) else {
            return Vec::new();
        };
        targets = connected;
        at
    };
    let Some(front) = direction(game, controller_pos) else {
        return Vec::new();
    };
    let right = match front {
        Direction::North => [-1, 0, 0],
        Direction::West => [0, 0, 1],
        Direction::East => [0, 0, -1],
        _ => [1, 0, 0],
    };
    targets.sort_by_key(|at| (-at[1], right[0] * at[0] + right[2] * at[2]));
    targets
}

pub(super) fn click(game: &mut Game<'_>, pos: Pos, face: Pos) -> bool {
    let Some(front) = direction(game, pos) else {
        return false;
    };
    if !game.may_build()
        || (!game.native_authoritative() && game.lan_acting.is_none())
        || front.normal() != face
    {
        return false;
    }
    let held = game.held().cloned();
    if held
        .as_ref()
        .is_some_and(|stack| stack.item.as_ref() == "create:mechanical_arm")
    {
        return false;
    }
    if held
        .as_ref()
        .is_some_and(|stack| stack.item.as_ref() == WRENCH)
    {
        if game.native_sneaking() {
            return false;
        }
        let next = match game.native_block_property(pos, "pointing").as_deref() {
            Some("up") => "left",
            Some("left") => "down",
            Some("down") => "right",
            Some("right") => "up",
            _ => return false,
        };
        game.native_set_block_property_with(pos, "pointing", next, flags::UPDATE_ALL);
        game.swing_arm();
        return true;
    }
    if game.native_sneaking()
        || (held.is_none() && game.hand != horizon_client::first_person::Hand::Main)
    {
        return false;
    }

    let Some(entity) = mod_entity(game, pos) else {
        return false;
    };
    if Phase::read(entity) != Phase::Idle {
        if let Some(positions) = chain(game, pos, front) {
            for at in positions {
                eject_at(game, at, front);
            }
        }
    } else {
        let covered = int(&entity.nbt, "Cover") == Some(1);
        let item = entity.items.first().and_then(Option::as_ref);
        let installing = held
            .as_ref()
            .is_some_and(|stack| stack.item.as_ref() == SLOT_COVER);
        if installing || (held.is_none() && covered) {
            if covered == installing || item.is_some() {
                return false;
            }
            game.native_with_mod_block_entity(pos, |entity| {
                entity
                    .nbt
                    .insert("Cover".into(), Tag::Byte(i8::from(installing)));
            });
            if !game.creative {
                if installing {
                    game.consume_held();
                } else {
                    game.give_or_drop(ItemStack::new(SLOT_COVER, 1));
                }
            }
        } else if let Some(stack) = held {
            let count = stack.count;
            let remainder = insert(game, pos, stack);
            if remainder.as_ref().map_or(0, |stack| stack.count) != count {
                *game.held_mut() = remainder;
            }
        } else if let Some(item) = item.cloned() {
            game.native_with_mod_block_entity(pos, |entity| entity.items[0] = None);
            game.give_or_drop(item);
        } else {
            return false;
        }
        game.native_block_entity_sync(pos);
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.swing_arm();
    true
}

pub(super) fn drop_cover(level: &mut super::GameLevel<'_>, pos: BlockPos, side_effects: bool) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    if level
        .world
        .block_entities
        .get(&(pos.x, pos.y, pos.z))
        .is_some_and(|entity| {
            matches!(entity, BlockEntity::Mod(entity)
            if entity.id == CRAFTER && int(&entity.nbt, "Cover") == Some(1))
        })
    {
        level.drop_lost_contents(pos, vec![Some(ItemStack::new(SLOT_COVER, 1))]);
    }
}

pub(super) fn available(entity: &ModBlockEntity) -> bool {
    entity.id == CRAFTER
        && Phase::read(entity) == Phase::Idle
        && int(&entity.nbt, "Cover").unwrap_or(0) == 0
        && entity.items.first().is_none_or(Option::is_none)
}

pub(super) fn room(game: &Game<'_>, pos: Pos) -> u32 {
    targets(game, pos)
        .into_iter()
        .filter(|&at| mod_entity(game, at).is_some_and(available))
        .count() as u32
}

fn ready_to_begin(
    game: &Game<'_>,
    pos: Pos,
    front: Direction,
    local: &ModBlockEntity,
    powered_start: bool,
) -> Option<Vec<Pos>> {
    let positions = chain(game, pos, front)?;
    let mut has_item = false;
    for &at in &positions {
        let entity = if at == pos {
            local
        } else {
            mod_entity(game, at)?
        };
        let filled = entity.items.first().is_some_and(Option::is_some);
        if Phase::read(entity) != Phase::Idle
            || (!powered_start && !filled && int(&entity.nbt, "Cover") != Some(1))
        {
            return None;
        }
        has_item |= filled;
    }
    has_item.then_some(positions)
}

fn begin(
    game: &mut Game<'_>,
    positions: Vec<Pos>,
    front: Direction,
    mut local: Option<(Pos, &mut ModBlockEntity)>,
) {
    for at in positions {
        let leaf = preceding(game, at, front).is_empty();
        let start = |entity: &mut ModBlockEntity| {
            let item = entity.items.first_mut().and_then(Option::take);
            save(entity, &Grid::from([((0, 0), item)]));
            if leaf {
                Phase::Assembling.set(entity, 1);
            } else {
                Phase::Accepting.set(entity, 0);
            }
        };
        if let Some((_, entity)) = local.as_mut().filter(|(pos, _)| *pos == at) {
            start(entity);
        } else {
            game.native_with_mod_block_entity(at, start);
        }
        game.native_block_entity_sync(at);
    }
}

pub(super) fn insert(game: &mut Game<'_>, pos: Pos, mut stack: ItemStack) -> Option<ItemStack> {
    let mut received = Vec::new();
    for at in targets(game, pos) {
        if stack.count == 0 {
            break;
        }
        if game.native_with_mod_block_entity(at, |entity| {
            if !available(entity) {
                return false;
            }
            if entity.items.is_empty() {
                entity.items.push(None);
            }
            entity.items[0] = Some(ItemStack {
                count: 1,
                ..stack.clone()
            });
            true
        }) == Some(true)
        {
            stack.count -= 1;
            received.push(at);
            game.native_block_entity_sync(at);
        }
    }
    for at in received {
        if let (Some(front), Some(entity)) = (direction(game, at), mod_entity(game, at))
            && reading(entity, 0) != 0.0
            && let Some(positions) = ready_to_begin(game, at, front, entity, false)
        {
            begin(game, positions, front, None);
        }
    }
    (stack.count != 0).then_some(stack)
}

fn recipe(game: &Game<'_>, grid: &Grid) -> Option<ItemStack> {
    let coords: Vec<_> = grid
        .iter()
        .filter_map(|(coord, stack)| stack.as_ref().map(|_| *coord))
        .collect();
    let left = coords.iter().map(|(x, _)| *x).min()?;
    let bottom = coords.iter().map(|(_, y)| *y).min()?;
    let top = coords.iter().map(|(_, y)| *y).max()?;
    let width = 1 + coords.iter().map(|(x, _)| *x).max()? - left;
    let height = 1 + top - bottom;
    game.native_recipes_of_type("create:mechanical_crafting")
        .iter()
        .find_map(|recipe| {
            let json = &recipe.json;
            let pattern = json["pattern"].as_array()?;
            if pattern.len() != height as usize {
                return None;
            }
            let fits = |mirrored| {
                pattern.iter().enumerate().all(|(y, row)| {
                    let Some(row) = row
                        .as_str()
                        .filter(|row| row.chars().count() == width as usize)
                    else {
                        return false;
                    };
                    row.chars().enumerate().all(|(x, key)| {
                        let col = if mirrored {
                            width - 1 - x as i32
                        } else {
                            x as i32
                        };
                        let stack = grid
                            .get(&(left + col, top - y as i32))
                            .and_then(Option::as_ref);
                        match (stack, key) {
                            (None, ' ') => true,
                            (Some(stack), key) if key != ' ' => {
                                ingredient_matches(game, &json["key"][key.to_string()], &stack.item)
                            }
                            _ => false,
                        }
                    })
                })
            };
            (fits(false) || json["accept_mirrored"].as_bool().unwrap_or(true) && fits(true))
                .then(|| game.native_recipe_result(&json["result"]))
                .flatten()
        })
}

fn spread(game: &mut Game<'_>, pos: Pos, front: Direction, entity: &mut ModBlockEntity) {
    let Some(target) = next(game, pos, front) else {
        finish(game, pos, front, entity);
        return;
    };
    let Some((_, (dx, dy))) = pointing(game, pos, front) else {
        return;
    };
    let incoming = grid(entity);
    let ready = preceding(game, target, front)
        .into_iter()
        .filter(|&source| source != pos)
        .all(|source| {
            mod_entity(game, source).is_some_and(|source| Phase::read(source) == Phase::Waiting)
        });
    game.native_with_mod_block_entity(target, |node| {
        let mut combined = grid(node);
        combined.extend(
            incoming
                .into_iter()
                .map(|((x, y), item)| ((x + dx, y + dy), item)),
        );
        save(node, &combined);
        if ready {
            Phase::Assembling.set(node, 1);
        }
    });
    Phase::Waiting.set(entity, 0);
    save(entity, &Grid::new());
    game.native_block_entity_sync(target);
}

fn take_contents(entity: &mut ModBlockEntity) -> Vec<ItemStack> {
    let mut stacks: Vec<_> = grid(entity).into_values().flatten().collect();
    stacks.extend(entity.items.first_mut().and_then(Option::take));
    Phase::Idle.set(entity, 0);
    save(entity, &Grid::new());
    stacks
}

fn eject(game: &mut Game<'_>, pos: Pos, front: Direction, stacks: Vec<ItemStack>) {
    let normal = front.normal();
    let drop_at = std::array::from_fn(|i| f64::from(pos[i]) + 0.5 + 0.75 * f64::from(normal[i]));
    for stack in stacks {
        game.add_item_entity(stack, drop_at, None, 10);
    }
}

fn eject_at(game: &mut Game<'_>, pos: Pos, front: Direction) {
    if let Some(stacks) = game.native_with_mod_block_entity(pos, take_contents) {
        eject(game, pos, front, stacks);
        game.native_block_entity_sync(pos);
    }
}

fn finish(game: &mut Game<'_>, pos: Pos, front: Direction, entity: &mut ModBlockEntity) {
    if let Some(positions) = chain(game, pos, front) {
        for at in positions.into_iter().filter(|&at| at != pos) {
            eject_at(game, at, front);
        }
    }
    eject(game, pos, front, take_contents(entity));
}

fn output(game: &mut Game<'_>, pos: Pos, front: Direction, entity: &mut ModBlockEntity) {
    let Some((direction, _)) = pointing(game, pos, front) else {
        return;
    };
    let to = offset(pos, direction.normal());
    let can_insert = game
        .native_container_slots(game.native_dimension(), to, direction.opposite())
        .is_some();
    let belt = super::create_belt::feed_point(game, to);
    if !can_insert && belt.is_none() {
        finish(game, pos, front, entity);
        return;
    }
    let rest: Grid = grid(entity)
        .into_iter()
        .filter_map(|(key, stack)| {
            let stack = stack?;
            if let Some((start, index, move_to, speed)) = belt {
                if super::create_belt::can_feed(game, start, index, move_to, direction, speed) {
                    super::create_belt::feed(game, start, index, move_to, direction, speed, stack);
                    None
                } else {
                    Some((key, Some(stack)))
                }
            } else {
                game.native_insert_item(to, direction.opposite(), stack)
                    .map(|stack| (key, Some(stack)))
            }
        })
        .collect();
    save(entity, &rest);
    if rest.is_empty() {
        finish(game, pos, front, entity);
    } else {
        Phase::Inserting.set(entity, 0);
    }
    game.native_block_entity_sync(pos);
}

pub(super) fn tick(game: &mut Game<'_>, pos: Pos, entity: &mut ModBlockEntity, rpm: f32) {
    if int(&entity.nbt, "CountDown").is_none() {
        Phase::Idle.set(entity, 0);
    }
    let Some(front) = direction(game, pos) else {
        return;
    };
    let phase = Phase::read(entity);
    if phase == Phase::Accepting {
        return;
    }
    let powered = game.native_neighbor_signal(game.native_dimension(), pos) != 0;
    let was_powered = int(&entity.nbt, "WasPowered").unwrap_or(1) != 0;
    if powered != was_powered {
        entity
            .nbt
            .insert("WasPowered".into(), Tag::Byte(i8::from(powered)));
    }
    let powered_start = powered && !was_powered;
    if phase == Phase::Idle && rpm != 0.0 {
        let lazy_start =
            game.world.game_time % 20 == 0 && entity.items.first().is_some_and(Option::is_some);
        if (powered_start || lazy_start)
            && let Some(positions) = ready_to_begin(game, pos, front, entity, powered_start)
        {
            begin(game, positions, front, Some((pos, entity)));
        }
        return;
    }
    if phase == Phase::Inserting {
        if game.world.game_time % 20 == 0
            || pointing(game, pos, front).is_some_and(|(direction, _)| {
                super::create_belt::feed_point(game, offset(pos, direction.normal())).is_some()
            })
        {
            output(game, pos, front, entity);
        }
    }
    if !matches!(
        phase,
        Phase::Assembling | Phase::Exporting | Phase::Crafting
    ) || rpm == 0.0
    {
        return;
    }
    let remaining = int(&entity.nbt, "CountDown").unwrap_or(0) - (rpm.abs() as i32).clamp(4, 250);
    if remaining >= 0 {
        phase.set(entity, remaining);
    } else {
        match phase {
            Phase::Assembling if next(game, pos, front).is_some() => {
                let wait = if grid(entity).values().any(Option::is_some) {
                    1000
                } else {
                    0
                };
                Phase::Exporting.set(entity, wait);
            }
            Phase::Assembling => {
                if let Some(created) = recipe(game, &grid(entity)) {
                    save(entity, &Grid::from([((0, 0), Some(created))]));
                    Phase::Crafting.set(entity, 2000);
                } else {
                    finish(game, pos, front, entity);
                }
            }
            Phase::Exporting => spread(game, pos, front, entity),
            Phase::Crafting => output(game, pos, front, entity),
            _ => unreachable!(),
        }
    }
    game.native_block_entity_sync(pos);
}
