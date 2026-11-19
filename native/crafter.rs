use std::collections::{BTreeMap, BTreeSet};

use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::nbt::{Compound, Tag};

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;

use super::Game;
use super::create_depot::{compound, encode};
use super::create_fan::facing;
use super::create_machines::{DIRECTIONS, ingredient_matches, int, mod_entity, offset, reading};

pub(super) const CRAFTER: &str = "create:mechanical_crafter";
const SLOT_COVER: &str = "create:crafter_slot_cover";
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

pub(super) fn click_cover(game: &mut Game<'_>, pos: Pos, face: Pos) -> bool {
    if (!game.native_authoritative() && game.lan_acting.is_none())
        || direction(game, pos).map(Direction::normal) != Some(face)
    {
        return false;
    }
    let held = game.held().map(|stack| stack.item.as_ref());
    if held.is_some_and(|item| item != SLOT_COVER)
        || (held.is_none() && game.hand != horizon_client::first_person::Hand::Main)
    {
        return false;
    }
    let installing = held.is_some();
    let changed = game.native_with_mod_block_entity(pos, |entity| {
        if entity.id != CRAFTER
            || Phase::read(entity) != Phase::Idle
            || entity.items.first().is_some_and(Option::is_some)
            || (int(&entity.nbt, "Cover") == Some(1)) == installing
        {
            return false;
        }
        entity.nbt.insert("Cover".into(), Tag::Byte(i8::from(installing)));
        true
    });
    if changed != Some(true) {
        return false;
    }
    if !game.creative {
        if installing {
            game.consume_held();
        } else {
            game.give_or_drop(ItemStack::new(SLOT_COVER, 1));
        }
    }
    game.native_block_entity_sync(pos);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.swing_arm();
    true
}

pub(super) fn drop_cover(level: &mut super::GameLevel<'_>, pos: BlockPos, side_effects: bool) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    if level.world.block_entities.get(&(pos.x, pos.y, pos.z)).is_some_and(|entity| {
        matches!(entity, BlockEntity::Mod(entity)
            if entity.id == CRAFTER && int(&entity.nbt, "Cover") == Some(1))
    }) {
        level.drop_lost_contents(pos, vec![Some(ItemStack::new(SLOT_COVER, 1))]);
    }
}

pub(super) fn available(entity: &ModBlockEntity) -> bool {
    entity.id == CRAFTER
        && Phase::read(entity) == Phase::Idle
        && int(&entity.nbt, "Cover").unwrap_or(0) == 0
        && entity.items.first().is_some_and(Option::is_none)
}

pub(super) fn room(game: &Game<'_>, pos: Pos) -> u32 {
    targets(game, pos)
        .into_iter()
        .filter(|&at| mod_entity(game, at).is_some_and(available))
        .count() as u32
}

fn begin(game: &mut Game<'_>, pos: Pos) {
    let Some(front) = direction(game, pos) else {
        return;
    };
    if !mod_entity(game, pos).is_some_and(|entity| reading(entity, 0) != 0.0) {
        return;
    }
    let Some(positions) = chain(game, pos, front) else {
        return;
    };
    if !positions.iter().all(|&at| {
        mod_entity(game, at).is_some_and(|entity| {
            Phase::read(entity) == Phase::Idle
                && (int(&entity.nbt, "Cover") == Some(1)
                    || entity.items.first().is_some_and(Option::is_some))
        })
    }) {
        return;
    }
    for at in positions {
        let leaf = preceding(game, at, front).is_empty();
        game.native_with_mod_block_entity(at, |entity| {
            let item = entity.items.first_mut().and_then(Option::take);
            save(entity, &Grid::from([((0, 0), item)]));
            if leaf {
                Phase::Assembling.set(entity, 1);
            } else {
                Phase::Accepting.set(entity, 0);
            }
        });
        game.native_block_entity_sync(at);
    }
}

pub(super) fn insert(game: &mut Game<'_>, pos: Pos, mut stack: ItemStack) -> Option<ItemStack> {
    let mut received = false;
    for at in targets(game, pos) {
        if stack.count == 0 {
            break;
        }
        if game.native_with_mod_block_entity(at, |entity| {
            if !available(entity) {
                return false;
            }
            entity.items[0] = Some(ItemStack {
                count: 1,
                ..stack.clone()
            });
            true
        }) == Some(true)
        {
            stack.count -= 1;
            received = true;
            game.native_block_entity_sync(at);
        }
    }
    if received {
        begin(game, pos);
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

fn finish(game: &mut Game<'_>, pos: Pos, front: Direction, entity: &mut ModBlockEntity) {
    let stacks = grid(entity);
    let fallback = pos.map(|v| f64::from(v) + 0.5);
    for (_, stack) in stacks {
        if let Some(stack) = stack {
            game.add_item_entity(stack, fallback, None, 10);
        }
    }
    let Some(chain) = chain(game, pos, front) else {
        return;
    };
    for at in chain.into_iter().filter(|&at| at != pos) {
        game.native_with_mod_block_entity(at, |node| {
            Phase::Idle.set(node, 0);
            save(node, &Grid::new());
        });
        game.native_block_entity_sync(at);
    }
    Phase::Idle.set(entity, 0);
    save(entity, &Grid::new());
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
}

pub(super) fn tick(game: &mut Game<'_>, pos: Pos, entity: &mut ModBlockEntity, rpm: f32) {
    if int(&entity.nbt, "CountDown").is_none() {
        Phase::Idle.set(entity, 0);
    }
    let phase = Phase::read(entity);
    let Some(front) = direction(game, pos) else {
        return;
    };
    if phase == Phase::Inserting {
        output(game, pos, front, entity);
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
