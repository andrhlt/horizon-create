use std::sync::Arc;

use horizon_client::text::Text;
use horizon_core::random::RandomSource;
use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::create_bearing::{relative, rotate};
use super::create_depot::compound;
use super::create_machines::{int, offset};
use super::create_train::{CARRIAGE, CONTROLS, controls_facing, state_name};
use super::{Game, Hand};

const OCCUPANT: &str = "SeatOccupant";
const DIRECTIONS: &str = "ConductorDirections";
const SCHEDULE: &str = "create:schedule";
const COMPONENT: &str = "create:train_schedule";
const ASSIGNED: &str = "Schedule";
const PAUSED: &str = "SchedulePaused";
const COMPLETED: &str = "ScheduleCompleted";
const RUNTIME: &str = "ScheduleRuntime";

fn uuid(block: &Compound) -> Option<[i32; 4]> {
    let Tag::IntArray(id) = block.get(&OCCUPANT.into())? else {
        return None;
    };
    id.as_slice().try_into().ok()
}

fn facing(block: &Compound) -> Option<&horizon_world::nbt::JavaString> {
    let Tag::String(facing) =
        compound(compound(block, "BlockState")?, "Properties")?.get(&"facing".into())?
    else {
        return None;
    };
    Some(facing)
}

pub(super) fn capture(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    axis: [i32; 3],
    blocks: &mut [Compound],
) {
    let controls: Vec<_> = blocks
        .iter()
        .filter_map(|block| {
            if state_name(block).as_deref() != Some(CONTROLS) {
                return None;
            }
            Some((relative(block), facing(block)?.to_string_lossy()))
        })
        .collect();
    let backward_axis = axis.map(|dir| -dir);
    for block in blocks
        .iter_mut()
        .filter(|block| state_name(block).as_deref().is_some_and(super::create_elevator_seats::is_seat))
    {
        let seat = relative(block);
        let controls_match = |direction: [i32; 3]| {
            let pos = offset(seat, direction.map(|value| -value));
            controls.iter().any(|(controls_pos, facing)| {
                *controls_pos == pos && facing == controls_facing(direction)
            })
        };
        let forwards = controls_match(axis);
        let backwards = controls_match(backward_axis);
        if forwards || backwards {
            block.insert(
                DIRECTIONS.into(),
                Tag::Byte(i8::from(forwards) | (i8::from(backwards) << 1)),
            );
        }
        let at = offset(anchor, seat);
        let rider = game.mobs.iter().find(|mob| {
            mob.alive() && !mob.removed && matches!(
                game.persist.raw.get(&mob.id),
                Some(Tag::Compound(data)) if matches!(
                    data.get(&"CreateSeat".into()), Some(Tag::IntArray(pos)) if pos.as_slice() == at
                )
            )
        }).map(|mob| mob.id);
        if let Some(id) = rider {
            let occupant = game.uuid_for(id);
            block.insert(OCCUPANT.into(), Tag::IntArray(occupant.to_vec()));
        }
    }
}

pub(super) fn present(game: &Game<'_>, data: &Compound, backwards: bool) -> bool {
    let Some(Tag::List(blocks)) = data.get(&"Blocks".into()) else {
        return false;
    };
    let side = if backwards { 2 } else { 1 };
    blocks.iter().any(|block| {
        let Tag::Compound(block) = block else {
            return false;
        };
        matches!(block.get(&DIRECTIONS.into()), Some(Tag::Byte(sides)) if sides & side != 0)
            && uuid(block)
                .and_then(|uuid| game.mob_by_uuid(uuid))
                .is_some_and(|id| {
                    game.mobs
                        .iter()
                        .any(|mob| mob.id == id && mob.alive() && !mob.removed)
                })
    })
}

pub(super) fn move_riders(
    game: &mut Game<'_>,
    blocks: &[Tag],
    position: impl Fn([i32; 3]) -> [f64; 3],
) {
    let dimension = game.native_dimension();
    for block in blocks {
        let Tag::Compound(block) = block else {
            continue;
        };
        let Some(id) = uuid(block).and_then(|id| game.mob_by_uuid(id)) else {
            continue;
        };
        let [x, y, z] = position(relative(block));
        game.native_teleport_mob(dimension, id, [x, y + 0.4125, z]);
    }
}

pub(super) fn restore_riders(
    game: &mut Game<'_>,
    anchor: [i32; 3],
    blocks: &[Compound],
    angle: f64,
) {
    let dimension = game.native_dimension();
    let now = game.world.game_time;
    let angle = (angle / std::f64::consts::FRAC_PI_2).round() * std::f64::consts::FRAC_PI_2;
    for block in blocks {
        let Some(id) = uuid(block).and_then(|id| game.mob_by_uuid(id)) else {
            continue;
        };
        let seat = offset(
            anchor,
            rotate(relative(block).map(f64::from), 1, angle).map(|v| v.round() as i32),
        );
        let [x, y, z] = seat.map(f64::from);
        game.native_teleport_mob(dimension, id, [x + 0.5, y + 0.4125, z + 0.5]);
        if let Some(Tag::Compound(data)) = game.persist.raw.get_mut(&id) {
            data.insert("CreateSeat".into(), Tag::IntArray(seat.to_vec()));
            data.insert("CreateSeatAt".into(), Tag::Long(now));
        }
    }
}

fn return_item(game: &Game<'_>, data: &Compound) -> Option<ItemStack> {
    let mut stack = ItemStack::new(SCHEDULE, 1);
    let Tag::Compound(mut schedule) = data.get(&ASSIGNED.into())?.clone() else {
        return None;
    };
    if let Some(entry) = compound(data, RUNTIME).and_then(|runtime| int(runtime, "Entry")) {
        if entry > 0 {
            schedule.insert("Progress".into(), Tag::Int(entry));
        } else {
            schedule.remove(&"Progress".into());
        }
    }
    game.native_set_component(&mut stack, COMPONENT, Tag::Compound(schedule))
        .ok()?;
    Some(stack)
}

fn collect_or_drop(game: &mut Game<'_>, stack: ItemStack, at: [i32; 3]) {
    if game.native_acting_player().is_some() && game.inventory[game.selected].is_none() {
        game.give_or_drop(stack);
    } else {
        game.spawn_item(stack, at.map(|v| f64::from(v) + 0.5), [0.0; 3], 0);
    }
}

pub(super) fn drop_assigned(game: &mut Game<'_>, data: &Compound, at: [i32; 3]) {
    if let Some(stack) = return_item(game, data) {
        collect_or_drop(game, stack, at);
    }
}

fn schedule_data<'a>(game: &'a Game<'_>, id: u32) -> Option<&'a Compound> {
    let Tag::Compound(train) = game.persist.raw.get(&id)?.get(CARRIAGE)? else {
        return None;
    };
    Some(train)
}

pub(super) fn has_schedule(game: &Game<'_>, id: u32) -> bool {
    schedule_data(game, id).is_some_and(|train| train.contains_key(&ASSIGNED.into()))
}

pub(super) fn retrieve(game: &mut Game<'_>, id: u32, at: [i32; 3]) {
    if game.spectator() || game.mode_id() == 2 {
        return;
    }
    let Some(stack) = schedule_data(game, id).and_then(|train| return_item(game, train)) else {
        return;
    };
    change_train(game, id, clear_schedule);
    collect_or_drop(game, stack, at);
}

fn clear_schedule(train: &mut Compound) {
    for key in [ASSIGNED, PAUSED, COMPLETED, RUNTIME] {
        train.remove(&key.into());
    }
}

fn change_train(game: &mut Game<'_>, id: u32, change: impl FnOnce(&mut Compound)) {
    if let Some(Tag::Compound(entity)) = game.persist.raw.get_mut(&id)
        && let Some(Tag::Compound(train)) = entity.get_mut(&CARRIAGE.into())
    {
        change(train);
    }
}

fn target<'a>(game: &'a Game<'_>, entity: u32) -> Option<(u32, &'a Compound, &'a Compound)> {
    let rider = game.persist.uuid_of(entity)?;
    if !game
        .mobs
        .iter()
        .any(|mob| mob.id == entity && mob.alive() && !mob.removed)
    {
        return None;
    }
    for car in &game.others {
        let Some(Tag::Compound(raw)) = game.persist.raw.get(&car.id) else {
            continue;
        };
        let Some(Tag::Compound(train)) = raw.get(&CARRIAGE.into()) else {
            continue;
        };
        let Some(Tag::List(blocks)) = train.get(&"Blocks".into()) else {
            continue;
        };
        for block in blocks {
            if let Tag::Compound(block) = block
                && uuid(block) == Some(rider)
            {
                return Some((car.id, train, block));
            }
        }
    }
    None
}

struct Cue {
    key: &'static str,
    sound: &'static str,
    volume: f32,
    pitch: f32,
}

impl Cue {
    fn deny(key: &'static str) -> Self {
        Self {
            key,
            sound: "create:deny",
            volume: 1.0,
            pitch: 0.5,
        }
    }

    fn confirm(key: &'static str) -> Self {
        Self {
            key,
            sound: "create:confirm",
            volume: 0.5,
            pitch: 0.8,
        }
    }
}

fn notify(game: &mut Game<'_>, cue: Cue, cooldown: bool) {
    if cooldown {
        game.add_cooldown(Arc::from(SCHEDULE), 5);
    }
    if let Some(player) = game.native_acting_player() {
        game.native_play_sound_in_place(
            cue.sound,
            player.position.map(|v| v.floor() + 0.5),
            7,
            cue.volume,
            cue.pitch,
        );
        let mut text = Text::translate(cue.key, &[]);
        if cue.key == "create.schedule.applied_to_train" {
            text = text.with_color(0x55ff55);
        }
        game.native_action_bar(player.uuid, text);
    }
}

pub(super) fn interact(
    game: &mut Game<'_>,
    entity: u32,
    hand: Hand,
    stack: Option<&ItemStack>,
) -> bool {
    if game.spectator() || game.cooldowns.is_on_cooldown(SCHEDULE) {
        return false;
    }
    let Some((car, train, seat)) = target(game, entity) else {
        return false;
    };
    let controlling = seat.contains_key(&DIRECTIONS.into());
    let schedule = stack
        .filter(|stack| &*stack.item == SCHEDULE)
        .and_then(|stack| {
            game.native_component(stack, COMPONENT)
                .ok()
                .flatten()
                .cloned()
        });
    let assigned = train.contains_key(&ASSIGNED.into());
    if let Some(Tag::Compound(schedule)) = schedule
        && let Some(Tag::List(entries)) = schedule.get(&"Entries".into())
    {
        let cue = if !controlling {
            Cue::deny("create.schedule.non_controlling_seat")
        } else if assigned {
            Cue::deny("create.schedule.remove_with_empty_hand")
        } else if entries.is_empty() {
            Cue::deny("create.schedule.no_stops")
        } else {
            change_train(game, car, |train| {
                clear_schedule(train);
                train.insert(ASSIGNED.into(), Tag::Compound(schedule));
            });
            game.with_hand(hand, |actor| {
                let held = actor.held_mut();
                if let Some(stack) = held.as_mut() {
                    stack.count -= 1;
                    if stack.count == 0 {
                        *held = None;
                    }
                }
            });
            Cue::confirm("create.schedule.applied_to_train")
        };
        notify(game, cue, true);
        return true;
    }
    if hand != Hand::Main || !controlling || !assigned {
        return false;
    }
    if matches!(train.get(&PAUSED.into()), Some(Tag::Byte(1)))
        && !matches!(train.get(&COMPLETED.into()), Some(Tag::Byte(1)))
    {
        change_train(game, car, |train| {
            train.remove(&PAUSED.into());
        });
        notify(game, Cue::confirm("create.schedule.continued"), true);
        return true;
    }
    if stack.is_some() {
        notify(
            game,
            Cue::deny("create.schedule.remove_with_empty_hand"),
            false,
        );
        return true;
    }
    let Some(returned) = return_item(game, train) else {
        return false;
    };
    change_train(game, car, clear_schedule);
    let pitch = 1.0 + game.world.random.next_float();
    notify(
        game,
        Cue {
            key: "create.schedule.removed_from_train",
            sound: "minecraft:entity.item.pickup",
            volume: 0.2,
            pitch,
        },
        true,
    );
    game.give_or_drop(returned);
    true
}
