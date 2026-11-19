use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_core::random::RandomSource;
use horizon_world::level::flags;

use crate::items::ItemStack;

use super::Game;
use super::create_clockwork::{self, CLOCKWORK};
use super::create_cogwheel::encased_size;
use super::create_fluids::name;
use super::create_portable_interface::{FLUID as FLUID_PORT, ITEM as ITEM_PORT};
use super::create_speed_controller::{self, CONTROLLER as SPEED_CONTROLLER};

const WRENCH: &str = "create:wrench";

pub(super) fn rotate(direction: Direction, around: Direction) -> Direction {
    let [x, y, z] = direction.normal();
    let normal = match around {
        Direction::East | Direction::West => [x, z, -y],
        Direction::Up | Direction::Down => [-z, y, x],
        Direction::North | Direction::South => [y, -x, z],
    };
    Direction::ALL
        .into_iter()
        .find(|side| side.normal() == normal)
        .unwrap()
}

fn axis(direction: Direction) -> &'static str {
    match direction {
        Direction::East | Direction::West => "x",
        Direction::Up | Direction::Down => "y",
        Direction::North | Direction::South => "z",
    }
}

fn positive_axis(axis: &str) -> Option<Direction> {
    match axis {
        "x" => Some(Direction::East),
        "y" => Some(Direction::Up),
        "z" => Some(Direction::South),
        _ => None,
    }
}

fn change_cased_cog(game: &mut Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    let Some(previous_axis) = game.native_block_property(pos, "axis") else {
        return false;
    };
    let Some(direction) = positive_axis(&previous_axis) else {
        return false;
    };
    let top = game.native_block_property(pos, "top_shaft");
    let bottom = game.native_block_property(pos, "bottom_shaft");
    if axis(face) == previous_axis {
        let (key, prior) = if face == direction {
            ("top_shaft", top)
        } else {
            ("bottom_shaft", bottom)
        };
        let next = if prior.as_deref() == Some("true") {
            "false"
        } else {
            "true"
        };
        return game.native_set_block_property_with(pos, key, next, flags::UPDATE_ALL);
    }

    let rotated = rotate(direction, face);
    let current = game.world.block(pos[0], pos[1], pos[2]);
    let state = game.with_level(|_, level, _| {
        let state = level.native_state_with_property(current, "axis", axis(rotated))?;
        if positive_axis(axis(rotated)) == Some(rotated) {
            return Some(state);
        }
        let state = level.native_state_with_property(state, "top_shaft", bottom.as_deref()?)?;
        level.native_state_with_property(state, "bottom_shaft", top.as_deref()?)
    });
    state.is_some_and(|state| {
        game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)
    })
}

pub(super) fn change_pose(game: &mut Game<'_>, pos: [i32; 3], face: Direction, block: &str) -> bool {
    let update = match block {
        super::create_rose_lamp::LAMP => return super::create_rose_lamp::wrench(game, pos),
        super::create_threshold_switch::THRESHOLD_SWITCH | super::create_smart_observer::OBSERVER => {
            return super::create_threshold_switch::wrench(game, pos, face);
        }
        super::create_sequencer::SEQUENCER => return super::create_sequencer::wrench_pose(game, pos, face),
        super::create_shaft::GIRDER_SHAFT => {
            return super::create_shaft::remove_from_girder(game, pos);
        }
        SPEED_CONTROLLER if axis(face) == "y" => {
            let Some(prior) = game.native_block_property(pos, "axis") else {
                return false;
            };
            ("axis", create_speed_controller::cross_axis(&prior), prior)
        }
        _ if encased_size(block).is_some() => return change_cased_cog(game, pos, face),
        "create:shaft" | "create:cogwheel" | "create:gearbox" | "create:clutch"
        | "create:gearshift" => {
            let Some(prior) = game.native_block_property(pos, "axis") else {
                return false;
            };
            let Some(direction) = positive_axis(&prior) else {
                return false;
            };
            ("axis", axis(rotate(direction, face)), prior)
        }
        "create:sticker" | "create:creative_motor" | "create:encased_fan" | CLOCKWORK | FLUID_PORT | ITEM_PORT => {
            let Some(prior) = game.native_block_property(pos, "facing") else {
                return false;
            };
            let Some(direction) = Direction::ALL.into_iter().find(|&side| name(side) == prior)
            else {
                return false;
            };
            ("facing", name(rotate(direction, face)), prior)
        }
        _ => return false,
    };
    let (key, value, prior) = update;
    let turned =
        prior != value && game.native_set_block_property_with(pos, key, value, flags::UPDATE_ALL);
    if block == CLOCKWORK {
        create_clockwork::stop_after_wrench(game, pos, &prior);
    }
    turned
}

pub(super) fn pickup(game: &mut Game<'_>, pos: [i32; 3], block: &str) {
    let at = BlockPos::new(pos[0], pos[1], pos[2]);
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let removed =
        game.with_level(|behaviour, level, ticks| behaviour.destroy_block(level, ticks, at, false));
    let _ = game.process_level_events();
    if removed && !game.creative {
        let drops = if block == super::create_shaft::GIRDER_SHAFT {
            let wrench = game.held().cloned();
            game.block_loot_at(pos, state, wrench.as_ref(), None)
        } else {
            let item = match block {
                "minecraft:redstone_wire" => "minecraft:redstone",
                "minecraft:redstone_wall_torch" => "minecraft:redstone_torch",
                "minecraft:tripwire" => "minecraft:string",
                "create:gearbox" => super::create_shaft::gearbox_item(game, state),
                super::create_encased_fluid_pipe::BLOCK => super::create_fluids::PIPE,
                _ => block,
            };
            game.native_max_stack_size(item)
                .map(|_| ItemStack::new(item, 1))
                .into_iter()
                .collect()
        };
        for stack in drops {
            if let Some(leftover) = game.give(stack) {
                game.pop_resource(pos, leftover);
            }
        }
        if game.lan_acting.is_some() {
            game.guest_inventory_resend = true;
        }
    }
}

pub(super) fn apply(game: &mut Game<'_>, pos: [i32; 3], normal: [i32; 3]) -> bool {
    if !game.may_build()
        || !game
            .held()
            .is_some_and(|stack| stack.item.as_ref() == WRENCH)
    {
        return false;
    }
    let block = game.native_block(pos);
    if !game.native_sneaking() && super::create_steam_whistle::wrench(game, pos) { return true; }
    let ladder = super::create_metal_ladder::metal_ladder(&block);
    let supported = matches!(
        block.as_str(),
        "create:sticker"
            | "create:shaft"
            | "create:cogwheel"
            | "create:gearbox"
            | "create:clutch"
            | "create:gearshift"
            | SPEED_CONTROLLER
            | "create:creative_motor"
            | "create:encased_fan"
            | "create:item_drain"
            | FLUID_PORT
            | ITEM_PORT
            | super::create_sequencer::SEQUENCER
            | super::create_threshold_switch::THRESHOLD_SWITCH
            | super::create_smart_observer::OBSERVER
            | CLOCKWORK
            | super::create_shaft::GIRDER_SHAFT
            | super::create_controller_rail::RAIL
            | super::create_rose_lamp::LAMP
            | super::create_encased_fluid_pipe::BLOCK
    ) || encased_size(&block).is_some() || ladder;
    let sneaking = game.native_sneaking();
    if !sneaking && matches!(block.as_str(), super::create_fluid_tank::TANK | super::create_fluid_tank::CREATIVE) {
        if game.native_authoritative() { super::create_tank_windows::wrench(game, pos); }
        game.swing_arm();
        return true;
    }
    if !sneaking && block == super::create_encased_fluid_pipe::BLOCK {
        if game.native_authoritative() && super::create_encased_fluid_pipe::uncase(game, pos) {
            game.swing_arm();
        }
        return true;
    }
    if !sneaking && super::create_funnel::wrench_mode(game, pos, &block) {
        game.swing_arm();
        return true;
    }
    if !sneaking && block == super::create_shaft::GIRDER {
        if game.native_authoritative() && super::create_shaft::wrench_girder(game, pos) {
            game.swing_arm();
        }
        return true;
    }
    if !sneaking && block == super::create_controller_rail::RAIL {
        if game.native_authoritative() {
            super::create_controller_rail::wrench(game, pos);
            game.swing_arm();
        }
        return true;
    }
    if !sneaking && block == super::create_train_signal::SIGNAL {
        super::create_train_signal::wrench(game, pos);
        game.swing_arm();
        return true;
    }
    if !sneaking && super::create_bracket::remove(game, pos) {
        game.swing_arm();
        return true;
    }

    if sneaking && super::create_shaft::uncase(game, pos, &block) {
        game.swing_arm();
        return true;
    }
    let tagged = sneaking
        && (block == super::create_nozzle::NOZZLE || game
            .items()
            .block_tags
            .get("create:wrench_pickup")
            .is_some_and(|blocks| blocks.contains(&block)));
    if !supported && !tagged {
        return false;
    }
    let Some(face) = Direction::ALL
        .into_iter()
        .find(|side| side.normal() == normal)
    else {
        return false;
    };
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    if sneaking {
        pickup(game, pos, &block);
        let pitch = (game.world.random.next_float() * 0.5 + 0.5) * 0.75;
        game.native_play_sound_in_place("create:wrench_remove", at, 4, 0.25, pitch);
        game.native_play_sound_in_place("create:wrench_remove_compounded_1", at, 4, 0.25, pitch);
    } else {
        let turned = if ladder {
            let Some(turned) = super::create_metal_ladder::wrench(game, pos, face) else {
                return false;
            };
            turned
        } else {
            change_pose(game, pos, face, &block)
        };
        if turned {
            let pitch = (game.world.random.next_float() + 0.5) * 1.25;
            game.native_play_sound_in_place("create:wrench_rotate", at, 4, 0.25, pitch);
        }
    }
    game.swing_arm();
    true
}
