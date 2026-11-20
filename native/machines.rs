use std::collections::{HashSet, VecDeque};
use std::sync::{Mutex, OnceLock};

use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_core::random::RandomSource;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, JavaString, Tag};

use crate::containers::{BlockEntity, ModBlockEntity, ModContainer};
use crate::items::ItemStack;

use super::create_andesite_tunnel::TUNNEL;
use super::create_arm::{self, ARM};
use super::create_bearing::{self, WINDMILL};
use super::create_belt::{BELT, Part};
use super::create_belt_funnel::{self, ANDESITE, BRASS, CRATE, FUNNEL};
use super::create_crafter::{self, CRAFTER};
use super::create_crushing::{self, CASED_SHAFT, CONTROLLER, WHEEL as CRUSHING_WHEEL};
use super::create_depot::{DEPOT, NIXIE};
use super::create_ejector::{self, EJECTOR};
use super::create_fan::FAN;
use super::create_fluid_tank::{self, CREATIVE, TANK};
use super::create_fluids::{self, BASIN, GLASS_PIPE, PIPE, PUMP, SMART_PIPE};
use super::create_hose::{self, HOSE};
use super::create_mixer::{self, MIXER};
use super::create_press::PRESS;
use super::create_rope::{self, PULLEY};
use super::create_schematicannon::{self, CANNON};
use super::create_sequencer::{self, SEQUENCER};
use super::create_smart_observer::OBSERVER;
use super::create_steam::{self, ENGINE, SHAFT as POWERED_SHAFT};
use super::create_threshold_switch::THRESHOLD_SWITCH;
use super::create_vault::{self, VAULT};
use super::{Game, GameLevel};

const MOTOR: &str = "create:creative_motor";
pub(super) const COG: &str = "create:cogwheel";
pub(super) const LARGE_COG: &str = "create:large_cogwheel";
pub(super) const SHAFT: &str = "create:shaft";
const MILL: &str = "create:millstone";
pub(super) const LARGE_WHEEL: &str = "create:large_water_wheel";
pub(super) const WHEEL: &str = "create:water_wheel";
pub(super) const SPEEDOMETER: &str = "create:speedometer";
pub(super) const CONVEYOR: &str = "create:chain_conveyor";
pub(super) const FROGPORT: &str = "create:package_frogport";
pub(super) const STRESSOMETER: &str = "create:stressometer";
pub(super) const CHUTE: &str = "create:smart_chute";
pub(super) const PLAIN_CHUTE: &str = "create:chute";
pub(super) const CLUTCH: &str = "create:clutch";
pub(super) const GEARSHIFT: &str = "create:gearshift";
const BRASS_SHAFT: &str = "create:brass_encased_shaft";
const CHAIN_DRIVE: &str = "create:encased_chain_drive";
const BEARING: &str = "create:mechanical_bearing";
pub(super) const GEARBOX: &str = "create:gearbox";
const GEARBOX_MOVED_TICK: &str = "PistonPlacedTick";
const GEARBOX_WRENCH_TICK: &str = "WrenchDetachedTick";
const GEARBOX_ATTACH_TICKS: [&str; 2] = [GEARBOX_MOVED_TICK, GEARBOX_WRENCH_TICK];
use super::create_chain_gearshift::{self, ADJUSTABLE as CHAIN_GEARSHIFT};
use super::create_clockwork::{self, CLOCKWORK};
use super::create_cogwheel::{
    CASED_ANDESITE_COG, CASED_ANDESITE_LARGE_COG, CASED_COG, CASED_COG_ENTITY, CASED_LARGE_COG,
    CASED_LARGE_COG_ENTITY, encased_size,
};
use super::create_hand_crank::{self, CRANK};
use super::create_speed_controller::{self, CONTROLLER as SPEED_CONTROLLER};
use super::create_train_signal::{self, SIGNAL};
use super::create_valve::{self, HANDLE_ENTITY, VALVE};

const DEPLOYER: &str = "create:deployer";

pub(super) const DIRECTIONS: [[i32; 3]; 6] = [
    [1, 0, 0],
    [-1, 0, 0],
    [0, 1, 0],
    [0, -1, 0],
    [0, 0, 1],
    [0, 0, -1],
];

// Create walks added kinetic networks in Direction.values() order. Gearbox
// joins can see an existing source and a local motor at the same speed, so
// retain that ordering without changing source selection for other machines.
const GEARBOX_DIRECTIONS: [[i32; 3]; 6] = [
    [0, -1, 0],
    [0, 1, 0],
    [0, 0, -1],
    [0, 0, 1],
    [-1, 0, 0],
    [1, 0, 0],
];

pub(super) fn offset(pos: [i32; 3], delta: [i32; 3]) -> [i32; 3] {
    std::array::from_fn(|i| pos[i] + delta[i])
}

pub(super) fn int(nbt: &Compound, key: &str) -> Option<i32> {
    match nbt.get(&JavaString::from(key)) {
        Some(Tag::Int(value)) => Some(*value),
        Some(Tag::Byte(value)) => Some(i32::from(*value)),
        _ => None,
    }
}

pub(super) fn float(nbt: &Compound, key: &str) -> Option<f32> {
    match nbt.get(&JavaString::from(key)) {
        Some(Tag::Float(bits)) => Some(f32::from_bits(*bits)),
        _ => None,
    }
}

pub(super) fn set_float(nbt: &mut Compound, key: &str, value: f32) {
    nbt.insert(key.into(), Tag::Float(value.to_bits()));
}

fn entity_id(block: &str) -> Option<&'static str> {
    match block {
        MOTOR => Some("create:motor"),
        SPEED_CONTROLLER => Some(SPEED_CONTROLLER),
        COG | LARGE_COG | SHAFT => Some("create:simple_kinetic"),
        super::create_flywheel::FLYWHEEL => Some(super::create_flywheel::FLYWHEEL),
        CASED_SHAFT | BRASS_SHAFT | CHAIN_DRIVE | super::create_shaft::GIRDER_SHAFT => {
            Some("create:encased_shaft")
        }
        CHAIN_GEARSHIFT => Some(CHAIN_GEARSHIFT),
        CONVEYOR => Some(CONVEYOR),
        FROGPORT => Some(FROGPORT),
        super::create_turntable::BLOCK => Some(super::create_turntable::BLOCK),
        super::create_backtank::TANK | super::create_backtank::NETHERITE_TANK => {
            Some(super::create_backtank::ENTITY)
        }
        super::create_placard::ITEM => Some(super::create_placard::ITEM),
        super::create_nozzle::NOZZLE => Some(super::create_nozzle::NOZZLE),
        super::create_item_hatch::HATCH => Some(super::create_item_hatch::HATCH),
        name if super::create_toolbox::block(name) => Some(super::create_toolbox::ENTITY),
        name if super::create_postbox::block(name) => Some(super::create_postbox::ENTITY),
        super::create_clipboard::ITEM => Some(super::create_clipboard::ITEM),
        BEARING => Some(BEARING),
        WINDMILL => Some(WINDMILL),
        CLOCKWORK => Some(CLOCKWORK),
        "create:cuckoo_clock" | "create:mysterious_cuckoo_clock" => Some("create:cuckoo_clock"),
        SIGNAL => Some(SIGNAL),
        super::create_track_observer::OBSERVER => Some(super::create_track_observer::OBSERVER),
        super::create_contraption_controls::CONTROLS => {
            Some(super::create_contraption_controls::CONTROLS)
        }
        super::create_roller::ROLLER => Some(super::create_roller::ROLLER),
        super::create_mechanical_piston::PISTON | super::create_mechanical_piston::STICKY => {
            Some(super::create_mechanical_piston::PISTON)
        }
        super::create_portable_interface::ITEM => Some(super::create_portable_interface::ITEM),
        super::create_portable_interface::FLUID => Some(super::create_portable_interface::FLUID),
        CRUSHING_WHEEL => Some(CRUSHING_WHEEL),
        CONTROLLER => Some(CONTROLLER),
        MILL => Some(MILL),
        WHEEL => Some(WHEEL),
        LARGE_WHEEL => Some(LARGE_WHEEL),
        SPEEDOMETER => Some(SPEEDOMETER),
        STRESSOMETER => Some(STRESSOMETER),
        CHUTE => Some(CHUTE),
        PLAIN_CHUTE => Some(PLAIN_CHUTE),
        CLUTCH => Some(CLUTCH),
        GEARSHIFT => Some(GEARSHIFT),
        SEQUENCER => Some(SEQUENCER),
        GEARBOX => Some(GEARBOX),
        DEPLOYER => Some(DEPLOYER),
        CANNON => Some(CANNON),
        VALVE => Some(VALVE),
        CASED_COG | CASED_ANDESITE_COG => Some(CASED_COG_ENTITY),
        CASED_LARGE_COG | CASED_ANDESITE_LARGE_COG => Some(CASED_LARGE_COG_ENTITY),
        name if create_valve::is_handle(name) => Some(HANDLE_ENTITY),
        CRANK => Some(CRANK),
        DEPOT => Some(DEPOT),
        super::create_item_drain::DRAIN => Some(super::create_item_drain::DRAIN),
        CRAFTER => Some(CRAFTER),
        EJECTOR => Some(EJECTOR),
        PRESS => Some(PRESS),
        super::create_saw::SAW => Some(super::create_saw::ENTITY),
        super::create_drill::DRILL => Some(super::create_drill::ENTITY),
        BELT => Some(BELT),
        ANDESITE | BRASS | super::create_funnel::ANDESITE | super::create_funnel::BRASS => {
            Some(FUNNEL)
        }
        CRATE => Some(CRATE),
        VAULT => Some(VAULT),
        FAN => Some(FAN),
        PUMP => Some(PUMP),
        PIPE => Some(PIPE),
        GLASS_PIPE => Some(GLASS_PIPE),
        super::create_encased_fluid_pipe::BLOCK => Some(super::create_encased_fluid_pipe::BLOCK),
        SMART_PIPE => Some(SMART_PIPE),
        BASIN => Some(BASIN),
        MIXER => Some(MIXER),
        HOSE => Some(HOSE),
        PULLEY => Some(PULLEY),
        super::create_elevator::PULLEY => Some(super::create_elevator::PULLEY),
        super::create_elevator_floors::CONTACT => Some(super::create_elevator_floors::CONTACT),
        super::create_spout::SPOUT => Some(super::create_spout::SPOUT),
        super::create_burner::BURNER => Some(super::create_burner::HEATER),
        ARM => Some(ARM),
        TANK => Some(TANK),
        CREATIVE => Some(CREATIVE),
        ENGINE => Some(ENGINE),
        POWERED_SHAFT => Some(POWERED_SHAFT),
        super::create_cart_assembler::ASSEMBLER => Some(super::create_cart_assembler::ASSEMBLER),
        super::create_gantry::SHAFT => Some(super::create_gantry::SHAFT),
        super::create_gantry::CARRIAGE => Some(super::create_gantry::PINION),
        TUNNEL => Some(TUNNEL),
        super::create_brass_tunnel::TUNNEL => Some(super::create_brass_tunnel::TUNNEL),
        super::create_copycat::PANEL | super::create_copycat::STEP => {
            Some(super::create_copycat::ENTITY)
        }
        name if super::create_depot::nixie_palette(name).is_some() => Some(NIXIE),
        super::create_display_board::BOARD => Some(super::create_display_board::ENTITY),
        super::create_display_link::LINK => Some(super::create_display_link::LINK),
        super::create_redstone_link::LINK => Some(super::create_redstone_link::LINK),
        OBSERVER => Some(OBSERVER),
        THRESHOLD_SWITCH => Some(THRESHOLD_SWITCH),
        super::create_station::STATION => Some(super::create_station::STATION),
        super::create_station::SMALL_BOGEY | super::create_station::LARGE_BOGEY => {
            Some(super::create_bogey::ENTITY)
        }
        name if super::create_linear_chassis::linear(name)
            || name == super::create_linear_chassis::RADIAL_CHASSIS =>
        {
            Some(super::create_chassis_range::ENTITY)
        }
        _ => None,
    }
}

pub(super) fn block_entity(block: &str, entity: &mut Option<(String, Compound)>) {
    if let Some(id) = entity_id(block) {
        let mut nbt = if block == THRESHOLD_SWITCH {
            super::create_threshold_switch::new_tag()
        } else if block == super::create_station::STATION {
            super::create_station::new_tag()
        } else if block == SIGNAL {
            create_train_signal::new_tag()
        } else if block == SEQUENCER {
            create_sequencer::new_tag()
        } else if block == super::create_saw::SAW {
            super::create_saw::new_tag()
        } else if block == super::create_drill::DRILL {
            super::create_drill::new_tag()
        } else if id == super::create_copycat::ENTITY {
            super::create_copycat::new_tag()
        } else if id == super::create_toolbox::ENTITY {
            super::create_toolbox::new_tag()
        } else if block == CANNON {
            create_schematicannon::new_tag()
        } else {
            Compound::new()
        };
        if matches!(block, MOTOR | SPEED_CONTROLLER) {
            nbt.insert("ScrollValue".into(), Tag::Int(16));
        } else if block == CLOCKWORK {
            nbt.insert("ScrollValue".into(), Tag::Int(0));
        } else if id == super::create_chassis_range::ENTITY {
            nbt.insert(
                "ScrollValue".into(),
                Tag::Int(super::create_chassis_range::DEFAULT),
            );
        }
        if block == super::create_elevator_floors::CONTACT {
            nbt.insert("DoorControl".into(), Tag::String("ALL".into()));
        }
        if matches!(block, CHUTE | PLAIN_CHUTE) {
            set_float(&mut nbt, "ItemPosition", 1.0);
        }
        *entity = Some((id.into(), nbt));
    }
}

pub(super) fn block_entity_ticks(block: &str, ticks: &mut bool) {
    *ticks |= entity_id(block).is_some_and(|id| {
        !matches!(
            id,
            super::create_chassis_range::ENTITY
                | super::create_copycat::ENTITY
                | super::create_item_hatch::HATCH
        )
    }) || block == super::create_track::TRACK;
}

pub(super) fn block_entity_container(block: &str, container: &mut Option<ModContainer>) {
    if super::create_toolbox::block(block) {
        super::create_toolbox::container(block, container);
        return;
    }
    let (slots, outputs) = match block {
        super::create_station::STATION
        | super::create_brass_tunnel::TUNNEL
        | super::create_display_link::LINK => (1, Vec::new()),
        // A bearing's mounted slots are sized by its assembled payload.
        // Its own block is hidden from container lookup.
        BEARING | WINDMILL => (1, Vec::new()),
        MILL => (10, (1..10).collect()),
        super::create_saw::SAW => (super::create_saw::SLOTS, Vec::new()),
        CANNON => (5, vec![1, 3]),
        CHUTE | PLAIN_CHUTE | DEPLOYER => (1, vec![0]),
        DEPOT | EJECTOR => (9, (0..9).collect()),
        name if name == FROGPORT || super::create_postbox::block(name) => {
            let slots = super::create_chain_conveyor_packages::PORT_SLOTS;
            (slots, (0..slots).collect())
        }
        super::create_item_drain::DRAIN => (1, vec![0]),
        CRAFTER => (1, Vec::new()),
        BELT => (1, vec![]),
        BASIN => (18, (9..18).collect()),
        VAULT => (create_vault::SLOTS, (0..create_vault::SLOTS).collect()),
        CONTROLLER => (
            create_crushing::SLOTS,
            (1..create_crushing::SLOTS).collect(),
        ),
        _ => return,
    };
    *container = Some(ModContainer {
        slots,
        faces: std::array::from_fn(|face| {
            if block == super::create_item_drain::DRAIN && face < 2
                || block == super::create_saw::SAW && face == Direction::Down as usize
            {
                Vec::new()
            } else {
                (0..slots).collect()
            }
        }),
        inputs: if block == FROGPORT || super::create_postbox::block(block) {
            (0..slots).collect()
        } else if block == BASIN {
            (0..9).collect()
        } else if block == CANNON {
            vec![0, 2, 4]
        } else {
            vec![0]
        },
        outputs,
        menu: if super::create_postbox::block(block) {
            Some(FROGPORT.to_owned())
        } else {
            matches!(
                block,
                super::create_station::STATION
                    | super::create_brass_tunnel::TUNNEL
                    | super::create_display_link::LINK
                    | FROGPORT
            )
            .then(|| block.to_owned())
        },
    });
}

pub(super) fn container_accepts(
    game: &Game<'_>,
    entity: &ModBlockEntity,
    slot: usize,
    stack: &ItemStack,
    cancel: &mut bool,
) {
    match entity.id.as_str() {
        MILL => *cancel |= milling_recipe(game, stack).is_none(),
        super::create_saw::ENTITY => {
            *cancel |= slot != 0 || entity.items.iter().any(Option::is_some);
        }
        CANNON => {
            *cancel |= !matches!(
                (slot, stack.item.as_ref()),
                (0, create_schematicannon::SCHEMATIC) | (4, create_schematicannon::GUNPOWDER)
            );
        }
        DEPOT | CONTROLLER | super::create_item_drain::DRAIN => {
            *cancel |= entity.items.iter().any(Option::is_some);
        }
        BASIN => {
            let matching = entity
                .items
                .iter()
                .take(9)
                .enumerate()
                .any(|(index, item)| {
                    index != slot && item.as_ref().is_some_and(|item| same_stack(item, stack))
                });
            let first_empty = entity.items.iter().take(9).position(Option::is_none);
            if matching
                || entity.items.get(slot).is_some_and(Option::is_none) && first_empty != Some(slot)
            {
                *cancel = true;
            }
        }
        CRAFTER => *cancel |= !create_crafter::available(entity),
        EJECTOR => *cancel |= !create_ejector::charged(entity) || slot != 0,
        super::create_toolbox::ENTITY => {
            *cancel |= !super::create_toolbox::accepts(game.items(), entity, slot, stack);
        }
        FROGPORT | super::create_postbox::ENTITY => {
            *cancel |= !super::create_chain_conveyor_packages::package(game, stack)
        }
        CHUTE => *cancel |= !super::create_item_filters::accepts(game.items(), &entity.nbt, stack),
        _ => {}
    }
}

pub(super) fn mod_entity<'a>(game: &'a Game<'_>, pos: [i32; 3]) -> Option<&'a ModBlockEntity> {
    match game.world.block_entities.get(&(pos[0], pos[1], pos[2])) {
        Some(BlockEntity::Mod(entity)) => Some(entity),
        _ => None,
    }
}

#[derive(Clone, Copy)]
enum Kinetic {
    Motor([i32; 3]),
    Handle(Direction),
    HandCrank(Direction),
    Valve(usize),
    CasedCog(usize, bool, bool, bool),
    Display(usize),
    Cog(usize, bool),
    Shaft(usize),
    SpeedController(usize),
    PoweredShaft(usize),
    CrushingWheel(usize),
    Press(usize),
    Saw(Direction, usize),
    Drill(Direction),
    Fan(Direction),
    Pump(usize),
    Belt(Direction, Part, i32),
    Mill,
    Turntable,
    Backtank,
    Mixer,
    Arm(bool),
    Wheel(usize, bool),
    Gauge(usize),
    Clutch(usize, bool),
    Gearshift(usize, bool),
    Sequencer(usize, i32, i32, Option<create_sequencer::Motion>),
    Gearbox(usize),
    ChainDrive(usize, usize, i8),
    Conveyor,
    Bearing(Direction),
    CuckooClock(Direction),
    Windmill(Direction),
    Piston(usize),
    Hose(Direction),
    RopePulley(usize),
    Deployer(usize),
    Crafter(usize),
    Ejector(usize),
}

impl Kinetic {
    fn at(game: &Game<'_>, pos: [i32; 3]) -> Option<Self> {
        match game.native_block(pos).as_str() {
            MOTOR => {
                let facing = game.native_block_property(pos, "facing")?;
                motor_facing(&facing).map(Self::Motor)
            }
            name if create_valve::is_handle(name) => Some(Self::Handle(super::create_fan::facing(
                game,
                game.world.block(pos[0], pos[1], pos[2]),
            )?)),
            CRANK => Some(Self::HandCrank(super::create_fan::facing(
                game,
                game.world.block(pos[0], pos[1], pos[2]),
            )?)),
            VALVE => Some(Self::Valve(create_valve::shaft_axis(game, pos)?)),
            SPEED_CONTROLLER => Some(Self::SpeedController(axis_index(
                &game.native_block_property(pos, "axis")?,
            )?)),
            block @ (CASED_COG
            | CASED_ANDESITE_COG
            | CASED_LARGE_COG
            | CASED_ANDESITE_LARGE_COG) => Some(Self::CasedCog(
                axis_index(&game.native_block_property(pos, "axis")?)?,
                encased_size(block)?,
                game.native_block_property(pos, "top_shaft").as_deref() == Some("true"),
                game.native_block_property(pos, "bottom_shaft").as_deref() == Some("true"),
            )),
            WHEEL => {
                let facing = game.native_block_property(pos, "facing")?;
                Some(Self::Wheel(facing_axis(&facing)?, false))
            }
            LARGE_WHEEL => {
                let axis = axis_index(&game.native_block_property(pos, "axis")?)?;
                Some(Self::Wheel(axis, true))
            }
            CLUTCH => Some(Self::Clutch(
                axis_index(&game.native_block_property(pos, "axis")?)?,
                game.native_block_property(pos, "powered").as_deref() == Some("true"),
            )),
            GEARSHIFT => Some(Self::Gearshift(
                axis_index(&game.native_block_property(pos, "axis")?)?,
                game.native_block_property(pos, "powered").as_deref() == Some("true"),
            )),
            SEQUENCER => {
                let axis = if game.native_block_property(pos, "vertical").as_deref() == Some("true")
                {
                    1
                } else {
                    axis_index(&game.native_block_property(pos, "axis")?)?
                };
                let (modifier, side, sequence) = create_sequencer::output(mod_entity(game, pos));
                Some(Self::Sequencer(axis, modifier, side, sequence))
            }
            GEARBOX => Some(Self::Gearbox(axis_index(
                &game.native_block_property(pos, "axis")?,
            )?)),
            CHAIN_DRIVE | CHAIN_GEARSHIFT => {
                let axis = axis_index(&game.native_block_property(pos, "axis")?)?;
                let first = game.native_block_property(pos, "axis_along_first")? == "true";
                let connection = [0, 1, 2]
                    .into_iter()
                    .filter(|candidate| *candidate != axis)
                    .nth(usize::from(!first))?;
                let part = match game.native_block_property(pos, "part")?.as_str() {
                    "start" => 1,
                    "middle" => 0,
                    "end" => -1,
                    _ => 2,
                };
                Some(Self::ChainDrive(axis, connection, part))
            }
            super::create_elevator::PULLEY => {
                let axis = facing_axis(&game.native_block_property(pos, "facing")?)?;
                Some(Self::RopePulley(if axis == 0 { 2 } else { 0 }))
            }
            PULLEY => Some(Self::RopePulley(axis_index(
                &game.native_block_property(pos, "axis")?,
            )?)),
            HOSE => Some(Self::Hose(create_hose::pipe_face(game, pos)?)),
            WINDMILL => Some(Self::Windmill(super::create_fan::facing(
                game,
                game.world.block(pos[0], pos[1], pos[2]),
            )?)),
            "create:cuckoo_clock" | "create:mysterious_cuckoo_clock" => Some(Self::CuckooClock(
                super::create_fan::facing(game, game.world.block(pos[0], pos[1], pos[2]))?,
            )),
            BEARING | CLOCKWORK => Some(Self::Bearing(super::create_fan::facing(
                game,
                game.world.block(pos[0], pos[1], pos[2]),
            )?)),
            super::create_mechanical_piston::PISTON | super::create_mechanical_piston::STICKY => {
                let facing = game.native_block_property(pos, "facing")?;
                let first = game.native_block_property(pos, "axis_along_first")? == "true";
                Some(Self::Piston(gauge_axis(&facing, first)?))
            }
            SPEEDOMETER | STRESSOMETER | DEPLOYER => {
                let facing = game.native_block_property(pos, "facing")?;
                let first = game.native_block_property(pos, "axis_along_first")?;
                let axis = gauge_axis(&facing, first == "true")?;
                if game.native_block(pos) == DEPLOYER {
                    Some(Self::Deployer(axis))
                } else {
                    Some(Self::Gauge(axis))
                }
            }
            super::create_display_board::BOARD => Some(Self::Display(facing_axis(
                &game.native_block_property(pos, "facing")?,
            )?)),
            COG | LARGE_COG => Some(Self::Cog(
                axis_index(&game.native_block_property(pos, "axis")?)?,
                game.native_block(pos) == LARGE_COG,
            )),
            super::create_gantry::SHAFT => Some(Self::Shaft(facing_axis(
                &game.native_block_property(pos, "facing")?,
            )?)),
            SHAFT
            | CASED_SHAFT
            | BRASS_SHAFT
            | super::create_shaft::GIRDER_SHAFT
            | super::create_flywheel::FLYWHEEL => Some(Self::Shaft(axis_index(
                &game.native_block_property(pos, "axis")?,
            )?)),
            POWERED_SHAFT => Some(Self::PoweredShaft(axis_index(
                &game.native_block_property(pos, "axis")?,
            )?)),
            CRUSHING_WHEEL => Some(Self::CrushingWheel(axis_index(
                &game.native_block_property(pos, "axis")?,
            )?)),
            PUMP => Some(Self::Pump(facing_axis(
                &game.native_block_property(pos, "facing")?,
            )?)),
            FAN => Some(Self::Fan(super::create_fan::facing(
                game,
                game.world.block(pos[0], pos[1], pos[2]),
            )?)),
            BELT => {
                let (direction, part) = super::create_belt::segment(game, pos)?;
                Some(Self::Belt(
                    direction,
                    part,
                    super::create_belt::rise(game, pos),
                ))
            }
            CRAFTER => Some(Self::Crafter(facing_axis(
                &game.native_block_property(pos, "facing")?,
            )?)),
            EJECTOR => {
                let facing = facing_axis(&game.native_block_property(pos, "facing")?)?;
                Some(Self::Ejector(if facing == 0 { 2 } else { 0 }))
            }
            PRESS => Some(Self::Press(facing_axis(
                &game.native_block_property(pos, "facing")?,
            )?)),
            super::create_drill::DRILL => Some(Self::Drill(super::create_fan::facing(
                game,
                game.world.block(pos[0], pos[1], pos[2]),
            )?)),
            super::create_saw::SAW => {
                let state = game.world.block(pos[0], pos[1], pos[2]);
                let (facing, axis) = super::create_saw::geometry(game, state)?;
                Some(Self::Saw(facing, axis))
            }
            CONVEYOR => Some(Self::Conveyor),
            MILL => Some(Self::Mill),
            super::create_turntable::BLOCK => Some(Self::Turntable),
            super::create_backtank::TANK | super::create_backtank::NETHERITE_TANK => {
                Some(Self::Backtank)
            }
            MIXER => Some(Self::Mixer),
            ARM => Some(Self::Arm(
                game.native_block_property(pos, "ceiling").as_deref() == Some("true"),
            )),
            _ => None,
        }
    }

    fn shaft(self, face: [i32; 3]) -> bool {
        match self {
            Self::Motor(facing) => face == facing,
            Self::Handle(direction) | Self::HandCrank(direction) => {
                face == direction.opposite().normal()
            }
            Self::CasedCog(axis, _, top, bottom) => {
                face[axis] > 0 && top || face[axis] < 0 && bottom
            }
            Self::Fan(facing)
            | Self::Bearing(facing)
            | Self::CuckooClock(facing)
            | Self::Windmill(facing)
            | Self::Hose(facing)
            | Self::Drill(facing) => face == facing.opposite().normal(),
            Self::Pump(_) | Self::Display(_) => false,
            Self::Saw(facing, axis) => match facing {
                Direction::Up | Direction::Down => face[axis] != 0,
                _ => face == facing.opposite().normal(),
            },
            Self::Cog(axis, _)
            | Self::Shaft(axis)
            | Self::SpeedController(axis)
            | Self::Piston(axis)
            | Self::RopePulley(axis)
            | Self::ChainDrive(axis, _, _)
            | Self::PoweredShaft(axis)
            | Self::CrushingWheel(axis)
            | Self::Press(axis)
            | Self::Ejector(axis)
            | Self::Wheel(axis, _)
            | Self::Valve(axis)
            | Self::Gauge(axis)
            | Self::Crafter(axis)
            | Self::Deployer(axis) => face[axis] != 0,
            Self::Clutch(axis, _) | Self::Gearshift(axis, _) | Self::Sequencer(axis, _, _, _) => {
                face[axis] != 0
            }
            Self::Gearbox(axis) => face[axis] == 0,
            Self::Belt(direction, part, _) => {
                part != Part::Middle && face[super::create_belt::pulley_axis(direction)] != 0
            }
            Self::Conveyor => face[1] != 0,
            Self::Mill => face == [0, -1, 0],
            Self::Turntable => super::create_turntable::connects(face),
            Self::Backtank => face == [0, 1, 0],
            Self::Mixer => false,
            Self::Arm(ceiling) => face == [0, if ceiling { 1 } else { -1 }, 0],
        }
    }

    fn gear(self) -> Option<(usize, bool)> {
        match self {
            Self::Cog(axis, large) => Some((axis, large)),
            Self::CasedCog(axis, large, _, _) => Some((axis, large)),
            Self::Pump(axis) | Self::Crafter(axis) | Self::Display(axis) => Some((axis, false)),
            Self::Mill | Self::Mixer | Self::Arm(_) => Some((1, false)),
            _ => None,
        }
    }

    fn neighbors(self) -> impl Iterator<Item = [i32; 3]> {
        const DIAGONALS: [[i32; 3]; 12] = [
            [-1, -1, 0],
            [-1, 1, 0],
            [1, -1, 0],
            [1, 1, 0],
            [-1, 0, -1],
            [-1, 0, 1],
            [1, 0, -1],
            [1, 0, 1],
            [0, -1, -1],
            [0, -1, 1],
            [0, 1, -1],
            [0, 1, 1],
        ];
        let directions = if matches!(self, Self::Gearbox(_)) {
            &GEARBOX_DIRECTIONS[..]
        } else {
            &DIRECTIONS[..]
        };
        directions.iter().copied().chain(
            (self.gear().is_some() || matches!(self, Self::Belt(..)))
                .then_some(DIAGONALS)
                .into_iter()
                .flatten(),
        )
    }

    fn direction_ratio(self, from: [i32; 3], to: [i32; 3]) -> f32 {
        if let Self::Sequencer(axis, modifier, input, _) = self
            && from != [0; 3]
            && from != to
        {
            return if modifier == 0 {
                0.0
            } else if from[axis] == input {
                1.0 / modifier as f32
            } else {
                modifier as f32
            };
        }
        if from != [0; 3] && from != to {
            match self {
                Self::Clutch(_, true) => return 0.0,
                Self::Gearshift(_, true) => return -1.0,
                _ => {}
            }
        }
        if matches!(self, Self::Gearbox(_)) {
            gearbox_multiplier(from, to)
        } else {
            1.0
        }
    }

    fn speed_controller_link(self, other: Self, delta: [i32; 3]) -> Option<bool> {
        match (self, other, delta) {
            (Self::SpeedController(axis), Self::Cog(gear, true), [0, 1, 0])
                if gear != 1 && gear != axis =>
            {
                Some(true)
            }
            (Self::Cog(gear, true), Self::SpeedController(axis), [0, -1, 0])
                if gear != 1 && gear != axis =>
            {
                Some(false)
            }
            _ => None,
        }
    }

    fn ratio_to(self, other: Self, offset: [i32; 3]) -> Option<f32> {
        let adjacent = offset.iter().map(|value| value.abs()).sum::<i32>() == 1;
        if adjacent && self.shaft(offset) && other.shaft(offset.map(|v| -v)) {
            return Some(1.0);
        }
        if let (Self::ChainDrive(_, axis, part), Self::ChainDrive(_, other_axis, other_part)) =
            (self, other)
            && adjacent
            && axis == other_axis
            && offset[axis] != 0
            && part != 2
            && other_part != 2
            && (part == 0 || i32::from(part) == offset[axis])
            && (other_part == 0 || i32::from(other_part) == -offset[axis])
        {
            return Some(1.0);
        }
        if let (
            Self::Belt(direction, part, rise),
            Self::Belt(other_direction, other_part, other_rise),
        ) = (self, other)
            && direction == other_direction
        {
            let ahead = super::create_belt::step(direction, rise);
            let behind = super::create_belt::step(direction, other_rise).map(|n| -n);
            if offset == ahead && part != Part::End && other_part != Part::Start
                || offset == behind && part != Part::Start && other_part != Part::End
            {
                return Some(1.0);
            }
        }
        let ((axis, large), (other_axis, other_large)) = (self.gear()?, other.gear()?);
        match (large, other_large) {
            (true, true)
                if !adjacent
                    && axis != other_axis
                    && offset[axis] != 0
                    && offset[other_axis] != 0 =>
            {
                Some(if offset[axis].signum() == offset[other_axis].signum() {
                    1.0
                } else {
                    -1.0
                })
            }
            (true, false) | (false, true)
                if !adjacent && axis == other_axis && offset[axis] == 0 =>
            {
                Some(if large { -2.0 } else { -0.5 })
            }
            (false, false) if adjacent && axis == other_axis && offset[axis] == 0 => Some(-1.0),
            _ => None,
        }
    }
}

pub(super) fn gearbox_multiplier(from: [i32; 3], to: [i32; 3]) -> f32 {
    if from == [0; 3] || from == to {
        return 1.0;
    }
    if from == to.map(|component| -component) || from.iter().sum::<i32>() == to.iter().sum::<i32>()
    {
        -1.0
    } else {
        1.0
    }
}

fn gearbox_input_direction(side: [i32; 3]) -> i32 {
    Direction::ALL
        .iter()
        .position(|face| face.normal() == side)
        .map_or(-1, |index| index as i32)
}

fn conflicting_gearbox_join(game: &Game<'_>, pos: [i32; 3], state: &Network) -> bool {
    let Some(Kinetic::Gearbox(box_axis)) = Kinetic::at(game, pos) else {
        return false;
    };
    let gearbox = Kinetic::Gearbox(box_axis);
    let linked_gearbox = GEARBOX_DIRECTIONS.iter().any(|&delta| {
        let other_pos = offset(pos, delta);
        Kinetic::at(game, other_pos).is_some_and(|other| {
            matches!(other, Kinetic::Gearbox(_)) && gearbox.ratio_to(other, delta).is_some()
        })
    });
    if !linked_gearbox || state.rpm == 0.0 {
        return false;
    }

    GEARBOX_DIRECTIONS.iter().any(|&delta| {
        let other_pos = offset(pos, delta);
        let Some(Kinetic::Motor(facing)) = Kinetic::at(game, other_pos) else {
            return false;
        };
        if gearbox.ratio_to(Kinetic::Motor(facing), delta).is_none() {
            return false;
        }
        let Some(motor) = mod_entity(game, other_pos) else {
            return false;
        };
        let incoming =
            motor_speed(facing, &motor.nbt) / gearbox_multiplier(state.source_side, delta);
        incoming != 0.0 && incoming.signum() != state.rpm.signum()
    })
}

pub(super) fn valve_rear_link(game: &Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    let rear = face.opposite().normal();
    Kinetic::at(game, offset(pos, rear))
        .is_some_and(|other| Kinetic::Handle(face).ratio_to(other, rear).is_some())
}

fn motor_speed(facing: [i32; 3], nbt: &Compound) -> f32 {
    let configured = int(nbt, "ScrollValue").unwrap_or(16).clamp(-256, 256);
    (facing.iter().sum::<i32>() * configured) as f32
}

pub(super) fn axis_index(axis: &str) -> Option<usize> {
    match axis {
        "x" => Some(0),
        "y" => Some(1),
        "z" => Some(2),
        _ => None,
    }
}

pub(super) fn facing_axis(facing: &str) -> Option<usize> {
    match facing {
        "east" | "west" => Some(0),
        "up" | "down" => Some(1),
        "south" | "north" => Some(2),
        _ => None,
    }
}

pub(super) fn gauge_axis(facing: &str, first: bool) -> Option<usize> {
    match (facing_axis(facing)?, first) {
        (0, true) | (2, false) => Some(1),
        (0 | 1, false) => Some(2),
        (1 | 2, true) => Some(0),
        _ => None,
    }
}

#[derive(Default)]
struct Network {
    rpm: f32,
    capacity: f32,
    stress: f32,
    new_load: f32,
    source_side: [i32; 3],
    clutch_reconnected: bool,
    sequence: Option<create_sequencer::Motion>,
}

impl Network {
    fn speed(&self) -> f32 {
        if self.stress > self.capacity {
            0.0
        } else {
            self.rpm
        }
    }

    fn stress_target(&self, stress: f32) -> f32 {
        if stress > self.capacity {
            1.125
        } else if self.capacity > 0.0 {
            stress / self.capacity
        } else {
            0.0
        }
    }
}

const MILL_ATTACH_TICK: std::ops::Range<usize> = 3..5;

fn mill_just_attached(entity: &ModBlockEntity, time: i64) -> bool {
    if let Some(words) = entity.data.get(MILL_ATTACH_TICK) {
        let attach_tick = (i64::from(words[1]) << 32) | i64::from(words[0] as u32);
        attach_tick == time
    } else {
        !entity.nbt.contains_key(&JavaString::from("Network"))
    }
}

pub(super) fn sequencer_input(game: &Game<'_>, pos: [i32; 3]) -> (f32, [i32; 3]) {
    mod_entity(game, pos).map_or((0.0, [0; 3]), |entity| {
        let state = network(game, pos, entity);
        (state.speed(), state.source_side)
    })
}

pub(super) fn rpm_at(game: &Game<'_>, pos: [i32; 3]) -> f32 {
    mod_entity(game, pos).map_or(0.0, |entity| network(game, pos, entity).speed())
}

pub(super) fn crank_input_rpm(game: &Game<'_>, pos: [i32; 3]) -> f32 {
    // The crank's generation is zero without its InUse tag.
    network(game, pos, &ModBlockEntity::default()).rpm
}

type TickingKinetic<'a> = ([i32; 3], &'a ModBlockEntity);

fn kinetic_entity<'a>(
    game: &'a Game<'_>,
    pos: [i32; 3],
    ticking: TickingKinetic<'a>,
) -> Option<&'a ModBlockEntity> {
    if pos == ticking.0 {
        Some(ticking.1)
    } else {
        mod_entity(game, pos)
    }
}

fn network(game: &Game<'_>, start: [i32; 3], ticking: &ModBlockEntity) -> Network {
    walk_network(game, start, (start, ticking), true, |_, _| {})
}

fn walk_network(
    game: &Game<'_>,
    start: [i32; 3],
    ticking: TickingKinetic<'_>,
    controller_links: bool,
    mut visit: impl FnMut([i32; 3], f32),
) -> Network {
    let Some(block) = Kinetic::at(game, start) else {
        return Network::default();
    };
    let gearbox_start = matches!(block, Kinetic::Gearbox(_));
    let mut pending = VecDeque::from([(start, block, 1.0, [0; 3], [0; 3], None, false)]);
    let mut visited = HashSet::from([start]);
    let mut network = Network::default();
    let mut impact_per_rpm = 0.0;
    let mut new_impact_per_rpm = 0.0;
    while let Some((pos, block, ratio, entered, first_step, sequence, mut clutch_reconnected)) =
        pending.pop_front()
    {
        let data = kinetic_entity(game, pos, ticking);
        if matches!(block, Kinetic::Gearbox(_))
            && data.is_some_and(|entity| {
                GEARBOX_ATTACH_TICKS.into_iter().any(|key| {
                    matches!(entity.nbt.get(&JavaString::from(key)), Some(Tag::Long(tick))
                        if *tick == game.world.game_time)
                })
            })
        {
            continue;
        }
        visit(pos, ratio);
        if let Some(entity) = data {
            if matches!(block, Kinetic::Clutch(_, false)) {
                let now = game.world.game_time;
                clutch_reconnected |= matches!(entity.nbt.get(&"ClutchReconnected".into()),
                    Some(Tag::Long(tick)) if (now.saturating_sub(1)..=now).contains(tick));
            }
            let (generated, capacity_per_rpm) = match block {
                Kinetic::Motor(facing) => (motor_speed(facing, &entity.nbt), 16384.0),
                Kinetic::Handle(face) => create_valve::generator(game, pos, &entity.nbt, face),
                Kinetic::HandCrank(face) => (create_hand_crank::generated(&entity.nbt, face), 8.0),
                Kinetic::Wheel(_, large) => {
                    let sign = int(&entity.nbt, "FlowScore").unwrap_or(0).signum() as f32;
                    if large {
                        (sign * 4.0, 128.0)
                    } else {
                        (sign * 8.0, 32.0)
                    }
                }
                Kinetic::PoweredShaft(axis) => create_steam::generator(game, pos, axis),
                Kinetic::Windmill(_) => (create_bearing::windmill_generated(&entity.nbt), 512.0),
                _ => (0.0, 0.0),
            };
            let supplied = generated * ratio;
            if supplied.abs() > network.rpm.abs() {
                network.rpm = supplied;
                network.source_side = first_step;
                network.clutch_reconnected = clutch_reconnected;
                network.sequence = sequence;
            }
            network.capacity += generated.abs() * capacity_per_rpm;
            if matches!(
                block,
                Kinetic::Mill
                    | Kinetic::Turntable
                    | Kinetic::Backtank
                    | Kinetic::Deployer(_)
                    | Kinetic::Press(_)
                    | Kinetic::Saw(..)
                    | Kinetic::Drill(_)
                    | Kinetic::Hose(_)
                    | Kinetic::RopePulley(_)
                    | Kinetic::Fan(_)
                    | Kinetic::CrushingWheel(_)
                    | Kinetic::Pump(_)
                    | Kinetic::Mixer
                    | Kinetic::Arm(_)
                    | Kinetic::Ejector(_)
                    | Kinetic::Crafter(_)
                    | Kinetic::Bearing(_)
                    | Kinetic::CuckooClock(_)
                    | Kinetic::Piston(_)
                    | Kinetic::Conveyor
            ) {
                let base = match block {
                    Kinetic::Press(_) | Kinetic::CrushingWheel(_) => 8.0,
                    Kinetic::Conveyor | Kinetic::CuckooClock(_) => 1.0,
                    Kinetic::Turntable => super::create_turntable::STRESS_IMPACT,
                    Kinetic::Fan(_)
                    | Kinetic::Arm(_)
                    | Kinetic::Ejector(_)
                    | Kinetic::Crafter(_) => 2.0,
                    _ => 4.0,
                };
                let impact = base / ratio.abs();
                impact_per_rpm += impact;
                if matches!(block, Kinetic::Mill)
                    && mill_just_attached(entity, game.world.game_time)
                {
                    new_impact_per_rpm += impact;
                }
            }
        }

        let detached = data.is_some_and(|entity| {
            matches!(entity.nbt.get(&"TransmissionDetachTime".into()),
                Some(Tag::Long(tick)) if *tick == game.world.game_time)
        });
        let clutch_source = (pos == start
            && (matches!(block, Kinetic::Clutch(_, true))
                || detached && matches!(block, Kinetic::Clutch(..))))
        .then(|| data.and_then(|entity| int(&entity.nbt, "ClutchInputSide")))
        .flatten();
        let chain_connections = data
            .filter(|_| matches!(block, Kinetic::Conveyor))
            .into_iter()
            .flat_map(|entity| super::create_chain_conveyor_connect::links(&entity.nbt));
        let mut neighbors = block
            .neighbors()
            .map(|delta| (delta, false))
            .chain(chain_connections.map(|delta| (delta, true)))
            .collect::<Vec<_>>();
        if gearbox_start {
            // Create resolves a new Gearbox against the existing network
            // before considering a tied source attached directly to the new
            // block. A depth-first walk preserves that source precedence.
            neighbors.reverse();
        }
        for (delta, chain_link) in neighbors {
            if clutch_source.is_some_and(|side| delta.into_iter().sum::<i32>() != side) {
                continue;
            }
            let other = offset(pos, delta);
            if visited.contains(&other) {
                continue;
            }
            if let Some(neighbor) = Kinetic::at(game, other) {
                let edge = if chain_link {
                    let reverse = delta.map(|axis| -axis);
                    if !matches!(neighbor, Kinetic::Conveyor)
                        || !kinetic_entity(game, other, ticking).is_some_and(|entity| {
                            super::create_chain_conveyor_connect::links(&entity.nbt)
                                .any(|link| link == reverse)
                        })
                    {
                        continue;
                    }
                    1.0
                } else if let Some(controller_first) = block.speed_controller_link(neighbor, delta)
                {
                    if !controller_links {
                        continue;
                    }
                    let Some(edge) =
                        speed_controller_edge(game, pos, other, ticking, controller_first)
                    else {
                        continue;
                    };
                    edge
                } else {
                    let Some(edge) = block.ratio_to(neighbor, delta) else {
                        continue;
                    };
                    edge
                };
                let edge = match (block, neighbor) {
                    (Kinetic::ChainDrive(_, axis, _), Kinetic::ChainDrive(..))
                        if delta[axis] != 0 =>
                    {
                        let a = data.map_or(1.0, create_chain_gearshift::modifier);
                        let b =
                            mod_entity(game, other).map_or(1.0, create_chain_gearshift::modifier);
                        edge * a / b
                    }
                    _ => edge,
                };
                let direction_ratio = block.direction_ratio(entered, delta);
                let detaching = detached && entered != [0; 3] && entered != delta;
                if direction_ratio == 0.0 || detaching {
                    continue;
                }
                visited.insert(other);
                let next_sequence = match block {
                    Kinetic::Sequencer(axis, _, input, motion)
                        if entered[axis] != input && delta[axis] == input =>
                    {
                        motion
                    }
                    _ => sequence,
                };
                let next = (
                    other,
                    neighbor,
                    ratio * direction_ratio / edge,
                    delta.map(|n| -n),
                    if pos == start { delta } else { first_step },
                    next_sequence,
                    clutch_reconnected,
                );
                if gearbox_start {
                    pending.push_front(next);
                } else {
                    pending.push_back(next);
                }
            }
        }
    }
    network.stress = impact_per_rpm * network.rpm.abs();
    network.new_load = new_impact_per_rpm * network.rpm.abs();
    network
}

fn speed_controller_edge(
    game: &Game<'_>,
    from: [i32; 3],
    to: [i32; 3],
    ticking: TickingKinetic<'_>,
    controller_first: bool,
) -> Option<f32> {
    let controller = if controller_first { from } else { to };
    let configured = create_speed_controller::target(kinetic_entity(game, controller, ticking));
    if configured == 0.0 {
        return None;
    }
    // The large cog joins two components with different shaft speeds.
    // Determine the input with this edge cut, then express the configured
    // output as the actual ratio across the edge for load accounting.
    let source = |pos| walk_network(game, pos, ticking, false, |_, _| {}).rpm;
    let mut from_speed = source(from);
    let mut to_speed = source(to);
    if from_speed == 0.0 && to_speed == 0.0 {
        let cut = (from, to);
        from_speed = regulated_input(game, from, cut, ticking).unwrap_or(0.0);
        to_speed = regulated_input(game, to, cut, ticking).unwrap_or(0.0);
    }
    if from_speed != 0.0 && to_speed != 0.0 && from_speed.signum() == to_speed.signum() {
        return Some(to_speed / from_speed);
    }
    if from_speed != 0.0 && from_speed.abs() >= to_speed.abs() {
        Some(configured / from_speed)
    } else if to_speed != 0.0 {
        Some(to_speed / configured)
    } else {
        None
    }
}

type ControllerEdge = ([i32; 3], [i32; 3]);

fn regulated_input(
    game: &Game<'_>,
    start: [i32; 3],
    cut: ControllerEdge,
    ticking: TickingKinetic<'_>,
) -> Option<f32> {
    // A regulator immediately upstream fixes the RPM in the first section.
    // Follow additional sections only to find whether a generator powers it.
    let mut pending = VecDeque::from([(start, None)]);
    let mut visited = HashSet::new();
    while let Some((anchor, target)) = pending.pop_front() {
        if visited.contains(&anchor) {
            continue;
        }
        let mut section = Vec::new();
        let source = walk_network(game, anchor, ticking, false, |member, ratio| {
            section.push((member, ratio));
        });
        if source.rpm != 0.0 {
            return Some(target.unwrap_or(source.rpm));
        }

        for &(member, _) in &section {
            visited.insert(member);
        }
        for (pos, ratio) in section {
            let Some(kinetic) = Kinetic::at(game, pos) else {
                continue;
            };
            for delta in kinetic.neighbors() {
                let other = offset(pos, delta);
                if visited.contains(&other) || cut == (pos, other) || cut == (other, pos) {
                    continue;
                }
                let Some(neighbor) = Kinetic::at(game, other) else {
                    continue;
                };
                let Some(controller_first) = kinetic.speed_controller_link(neighbor, delta) else {
                    continue;
                };
                let controller = if controller_first { pos } else { other };
                let setting =
                    create_speed_controller::target(kinetic_entity(game, controller, ticking));
                if setting != 0.0 {
                    let target = target.unwrap_or(setting * ratio);
                    pending.push_back((other, Some(target)));
                }
            }
        }
    }
    None
}

fn motor_facing(facing: &str) -> Option<[i32; 3]> {
    Direction::ALL
        .into_iter()
        .find(|&side| create_fluids::name(side) == facing)
        .map(|side| side.normal())
}

const SEEN_MOTOR_SPEED: usize = 3;

pub(super) fn resolve_motor_changes(game: &mut Game<'_>) {
    if !game.native_authoritative() {
        return;
    }
    let ticking = game.block_ticking_area();
    let changes: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            let entity = mod_entity(game, pos)?;
            if !ticking(x, z) || entity.id != "create:motor" {
                return None;
            }
            let Kinetic::Motor(facing) = Kinetic::at(game, pos)? else {
                return None;
            };
            let speed = motor_speed(facing, &entity.nbt);
            (speed != reading(entity, SEEN_MOTOR_SPEED)).then_some((pos, speed))
        })
        .collect();

    for (pos, speed) in changes {
        resolve_motor_speed(game, pos, speed);
    }
}

fn resolve_motor_speed(game: &mut Game<'_>, pos: [i32; 3], speed: f32) {
    let Some(entity) = mod_entity(game, pos) else {
        return;
    };
    if speed != 0.0 && opposing_controller_output(game, pos, entity, speed) {
        game.native_machine_destroy_block(pos, None, false);
        return;
    }
    game.native_with_mod_block_entity(pos, |entity| {
        if entity.data.len() <= SEEN_MOTOR_SPEED {
            entity.data.resize(SEEN_MOTOR_SPEED + 1, 0);
        }
        entity.data[SEEN_MOTOR_SPEED] = speed.to_bits() as i32;
    });
}

pub(super) fn motor_setting_changed(game: &mut Game<'_>, pos: [i32; 3]) {
    if game.native_block(pos) != MOTOR || !game.native_authoritative() {
        return;
    }
    let Some(Kinetic::Motor(facing)) = Kinetic::at(game, pos) else {
        return;
    };
    let Some(entity) = mod_entity(game, pos) else {
        return;
    };
    let speed = motor_speed(facing, &entity.nbt);
    if speed != reading(entity, SEEN_MOTOR_SPEED) {
        resolve_motor_speed(game, pos, speed);
        refresh_connected_network(game, pos);
    }
}

fn opposing_controller_output(
    game: &Game<'_>,
    source: [i32; 3],
    entity: &ModBlockEntity,
    speed: f32,
) -> bool {
    let ticking = (source, entity);
    let mut section = Vec::new();
    walk_network(game, source, ticking, false, |pos, ratio| {
        section.push((pos, ratio));
    });
    let connected: HashSet<_> = section.iter().map(|(pos, _)| *pos).collect();
    for (pos, ratio) in section {
        let Some(kinetic) = Kinetic::at(game, pos) else {
            continue;
        };
        let old_speed = mod_entity(game, pos)
            .and_then(|entity| float(&entity.nbt, "Speed"))
            .unwrap_or(0.0);
        let attempted_speed = speed / ratio;
        if old_speed == 0.0 || old_speed.signum() == attempted_speed.signum() {
            continue;
        }
        for delta in kinetic.neighbors() {
            let other = offset(pos, delta);
            if connected.contains(&other) {
                continue;
            }
            let Some(other_block) = Kinetic::at(game, other) else {
                continue;
            };
            if kinetic.speed_controller_link(other_block, delta).is_some()
                && walk_network(game, other, ticking, false, |_, _| {}).rpm != 0.0
            {
                return true;
            }
        }
    }
    false
}

pub(super) fn advancement_owner(nbt: &Compound) -> Option<u128> {
    let Tag::IntArray(owner) = nbt.get(&"Owner".into())? else {
        return None;
    };
    let owner = <[i32; 4]>::try_from(owner.as_slice()).ok()?;
    Some(horizon_client::lan::playerdata::ints_uuid(owner))
}

pub(super) fn award_wheel(game: &mut Game<'_>, player: u128, lava: bool) {
    let criterion = if lava {
        "create:lava_wheel_00000_builtin"
    } else {
        "create:water_wheel_builtin"
    };
    game.native_trigger_criterion(player, criterion, |_| true);
}

pub(super) fn water_flow_score(
    game: &Game<'_>,
    pos: [i32; 3],
    axis: usize,
    arms: impl IntoIterator<Item = [i32; 3]>,
) -> i32 {
    let next_axis = (axis + 1) % 3;
    let last_axis = (axis + 2) % 3;
    arms.into_iter()
        .map(|arm| {
            let at = offset(pos, arm);
            let mut flow = game
                .native_fluid_flow(game.dim.id(), at)
                .unwrap_or([0.0; 3]);
            if game.native_block(at) == "minecraft:bubble_column" {
                let drags_down = game.native_block_property(at, "drag").as_deref() == Some("true");
                flow = [0.0, if drags_down { -1.0 } else { 1.0 }, 0.0];
            }
            let length = flow[next_axis].hypot(flow[last_axis]);
            let arm_length = f64::from(arm[next_axis]).hypot(f64::from(arm[last_axis]));
            let tangent = flow[last_axis] * f64::from(arm[next_axis])
                - flow[next_axis] * f64::from(arm[last_axis]);
            if tangent.abs() > length * arm_length * 0.5 {
                tangent.signum() as i32
            } else {
                0
            }
        })
        .sum()
}

// A neighbouring shape change schedules a one-tick update in Create. Read
// the six adjacent states before Horizon's fluid pass so indirect changes
// to the current only take effect at the wheel's periodic refresh.
pub(super) fn wheel_updates(game: &mut Game<'_>) {
    super::create_large_wheel::prepare_tick(game);
    super::create_depot::tick_nixies(game);
    const NEIGHBORS: std::ops::Range<usize> = 3..9;
    const WHEEL_STATE: usize = 9;
    const LAZY_TICKS: usize = 10;
    const LAZY_RATE: i32 = 60;
    let ticking = game.block_ticking_area();
    let wheels: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            if !ticking(x, z) {
                return None;
            }
            let pos = [x, y, z];
            let wheel = mod_entity(game, pos)?;
            if wheel.id != WHEEL {
                return None;
            }
            let Kinetic::Wheel(axis, false) = Kinetic::at(game, pos)? else {
                return None;
            };
            let neighbors = DIRECTIONS.map(|arm| {
                let [x, y, z] = offset(pos, arm);
                game.world.block(x, y, z).0 as i32
            });
            let state = game.world.block(x, y, z).0 as i32;
            let remaining = wheel.data.get(LAZY_TICKS).copied().unwrap_or(LAZY_RATE);
            let refresh = remaining == 0
                || wheel.data.get(NEIGHBORS) != Some(&neighbors)
                || wheel.data.get(WHEEL_STATE) != Some(&state);
            let score = refresh.then(|| {
                water_flow_score(
                    game,
                    pos,
                    axis,
                    DIRECTIONS.into_iter().filter(|arm| arm[axis] == 0),
                )
            });
            let remaining = if remaining == 0 {
                LAZY_RATE
            } else {
                remaining - 1
            };
            let lava = score.filter(|&score| score != 0).map(|_| {
                DIRECTIONS.into_iter().any(|arm| {
                    arm[axis] == 0 && game.native_block(offset(pos, arm)) == "minecraft:lava"
                })
            });
            Some((entry.0, neighbors, state, remaining, score, lava))
        })
        .collect();
    for (pos, neighbors, state, remaining, score, lava) in wheels {
        let Some(BlockEntity::Mod(wheel)) = game.world.block_entities.get_mut(&pos) else {
            continue;
        };
        wheel.data.resize(LAZY_TICKS + 1, 0);
        wheel.data[NEIGHBORS].copy_from_slice(&neighbors);
        wheel.data[WHEEL_STATE] = state;
        wheel.data[LAZY_TICKS] = remaining;
        if let Some(score) = score.filter(|&score| int(&wheel.nbt, "FlowScore") != Some(score)) {
            wheel.nbt.insert("FlowScore".into(), Tag::Int(score));
            game.world.modified.insert((pos.0 >> 4, pos.2 >> 4));
        }
        if let (Some(lava), Some(owner)) = (lava, advancement_owner(&wheel.nbt)) {
            award_wheel(game, owner, lava);
        }
    }
}

pub(super) fn block_spread(
    level: &GameLevel<'_>,
    kind: &str,
    from: BlockPos,
    to: BlockPos,
    canceled: &mut bool,
) {
    if kind != "fluid" || from.y != to.y {
        return;
    }
    let below = level.world.block(from.x, from.y - 1, from.z);
    let Some(wheel) = level.registry.state(below) else {
        return;
    };
    let axis = if wheel.name == WHEEL {
        wheel
            .properties
            .get("facing")
            .and_then(|facing| facing_axis(facing))
    } else {
        super::create_large_wheel::rim_master(level, [from.x, from.y - 1, from.z])
            .map(|(_, axis)| axis)
    };
    let direction = if from.x != to.x { 0 } else { 2 };
    *canceled |= axis == Some(direction);
}

pub(super) fn ingredient_matches(game: &Game<'_>, value: &serde_json::Value, item: &str) -> bool {
    if value["type"].as_str() == Some("neoforge:block_tag") {
        let Some(block) = game.items().get(item).and_then(|item| item.block) else {
            return false;
        };
        let name = &game.res.facts().get(block).name;
        return value["tag"]
            .as_str()
            .and_then(|tag| game.items().block_tags.get(tag))
            .is_some_and(|blocks| blocks.contains(name.as_ref()));
    }
    let ingredient = if let Some(item) = value.get("item") {
        item.clone()
    } else if let Some(tag) = value["tag"].as_str() {
        serde_json::Value::String(format!("#{tag}"))
    } else {
        value.clone()
    };
    game.native_recipe_ingredient(&ingredient)
        .is_some_and(|ingredient| ingredient.items.contains(item))
}

fn milling_recipe<'a>(game: &'a Game<'_>, input: &ItemStack) -> Option<&'a serde_json::Value> {
    game.native_recipes_of_type("create:milling")
        .iter()
        .find(|recipe| {
            recipe.json["ingredients"]
                .as_array()
                .and_then(|ingredients| ingredients.first())
                .is_some_and(|ingredient| ingredient_matches(game, ingredient, &input.item))
        })
        .map(|recipe| recipe.json.as_ref())
}

pub(super) fn same_stack(left: &ItemStack, right: &ItemStack) -> bool {
    left.item == right.item && left.damage == right.damage && left.extra == right.extra
}

pub(super) fn insert(slots: &mut [Option<ItemStack>], stack: &ItemStack, limit: u32) -> u32 {
    let mut remaining = stack.count;
    for slot in slots.iter_mut().filter_map(Option::as_mut) {
        if same_stack(slot, stack) {
            let amount = remaining.min(limit.saturating_sub(slot.count));
            slot.count += amount;
            remaining -= amount;
        }
    }
    for slot in slots.iter_mut().filter(|slot| slot.is_none()) {
        if remaining == 0 {
            break;
        }
        let count = remaining.min(limit);
        *slot = Some(ItemStack {
            count,
            ..stack.clone()
        });
        remaining -= count;
    }
    remaining
}

fn read_inventory(nbt: &mut Compound, key: &str, slots: &mut [Option<ItemStack>]) {
    let items = match nbt.remove(&JavaString::from(key)) {
        Some(Tag::List(items)) => items,
        Some(Tag::Compound(mut saved)) => match saved.remove(&"Items".into()) {
            Some(Tag::List(items)) => items,
            _ => return,
        },
        _ => return,
    };
    for item in items {
        if let Tag::Compound(item) = item
            && let Some(slot) = int(&item, "Slot").and_then(|i| slots.get_mut(i as usize))
            && slot.is_none()
        {
            *slot = ItemStack::from_nbt(&item);
        }
    }
}

pub(super) fn collect_landed_items(
    game: &mut Game<'_>,
    pos: [i32; 3],
    slot: &mut Option<ItemStack>,
    block: &str,
) {
    let x = f64::from(pos[0]);
    let y = f64::from(pos[1]);
    let z = f64::from(pos[2]);
    let mut i = 0;
    while i < game.dropped.len() {
        let item = &game.dropped[i];
        let p = item.position;
        // A descending item can enter a belt's block before it touches the
        // conveyor surface. Java inserts it during that entity-inside pass.
        let entered = if block == BELT {
            item.velocity.y <= 0.0
        } else {
            item.on_ground
        };
        if entered
            && (x..x + 1.0).contains(&p.x)
            && (z..z + 1.0).contains(&p.z)
            && (y..=y + 1.0 + 1e-6).contains(&p.y)
            && (matches!(block, DEPOT | BELT) || milling_recipe(game, &item.stack).is_some())
        {
            let limit = game.native_max_stack_size(&item.stack.item).unwrap_or(64);
            let left = insert(std::slice::from_mut(slot), &item.stack, limit);
            if left == 0 {
                game.remove_dropped(i);
                continue;
            }
            game.dropped[i].stack.count = left;
        }
        i += 1;
    }
}

fn publish_network(entity: &mut ModBlockEntity, network: &Network) {
    publish_network_nbt(entity, network);
    if entity.data.len() < 3 {
        entity.data.resize(3, 0);
    }
    entity.data[0] = network.speed().to_bits() as i32;
    entity.data[1] = network.capacity.to_bits() as i32;
    entity.data[2] = network.stress.to_bits() as i32;
}

pub(super) fn reset_moved_gearbox(entity: &mut ModBlockEntity, tick: i64) {
    // Java clears the saved kinetics on a moved block before it can attach again.
    publish_network(entity, &Network::default());
    entity.nbt.remove(&"KineticsTick".into());
    entity
        .nbt
        .insert(GEARBOX_MOVED_TICK.into(), Tag::Long(tick));
}

fn publish_network_nbt(entity: &mut ModBlockEntity, network: &Network) {
    if entity.id == VALVE && saved_speed(&entity.nbt) != network.speed() {
        create_valve::retarget(entity, network.speed());
    }
    set_float(&mut entity.nbt, "Speed", network.rpm);
    if matches!(entity.id.as_str(), CLUTCH | GEARSHIFT) {
        let input = network.source_side.into_iter().sum::<i32>();
        entity.nbt.insert("ShaftInputSide".into(), Tag::Int(input));
    } else if entity.id == GEARBOX {
        let input = gearbox_input_direction(network.source_side);
        entity
            .nbt
            .insert("ShaftInputDirection".into(), Tag::Int(input));
    }
    let mut saved = Compound::new();
    set_float(&mut saved, "Capacity", network.capacity);
    set_float(&mut saved, "Stress", network.stress);
    entity.nbt.insert("Network".into(), Tag::Compound(saved));
}

fn disconnect_crank_network(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let mut members = Vec::new();
    let stopped = walk_network(game, pos, (pos, entity), true, |member, _| {
        members.push(member);
    });
    publish_network(entity, &stopped);
    // Java disconnects the last generator immediately, even for
    // shafts that already had their block entity turn this tick.
    if stopped.capacity == 0.0 {
        for member in members.into_iter().filter(|member| *member != pos) {
            let changed = game.native_with_mod_block_entity(member, |linked| {
                let changed = reading(linked, 0) != 0.0 || reading(linked, 1) != 0.0;
                if changed {
                    publish_network(linked, &stopped);
                }
                changed
            });
            if changed == Some(true) {
                game.native_block_entity_sync(member);
            }
        }
    }
}

pub(super) fn network_values(nbt: &Compound) -> [f32; 3] {
    let rpm = float(nbt, "Speed").unwrap_or(0.0);
    let Some(Tag::Compound(network)) = nbt.get(&"Network".into()) else {
        return [rpm, 0.0, 0.0];
    };
    [
        rpm,
        float(network, "Capacity").unwrap_or(0.0),
        float(network, "Stress").unwrap_or(0.0),
    ]
}

pub(super) fn saved_speed(nbt: &Compound) -> f32 {
    let [rpm, capacity, stress] = network_values(nbt);
    if stress > capacity { 0.0 } else { rpm }
}

pub(super) fn reading(entity: &ModBlockEntity, index: usize) -> f32 {
    entity
        .data
        .get(index)
        .map_or(0.0, |bits| f32::from_bits(*bits as u32))
}

pub(super) fn refresh_connected_network(game: &mut Game<'_>, pos: [i32; 3]) {
    let members = kinetic_members(game, pos);
    publish_kinetic_members(game, members, publish_network);
}

pub(super) fn wrench_gearbox(game: &mut Game<'_>, pos: [i32; 3], axis: &str) -> bool {
    let members = kinetic_members(game, pos);
    if !game.native_set_block_property_with(pos, "axis", axis, flags::UPDATE_ALL) {
        return false;
    }

    // Java detaches the old network during Wrench use and attaches on the next tick.
    let tick = game.world.game_time;
    game.native_with_mod_block_entity(pos, |entity| {
        entity
            .nbt
            .insert(GEARBOX_WRENCH_TICK.into(), Tag::Long(tick));
    });
    publish_kinetic_members(game, members, publish_network);
    true
}

fn kinetic_members(game: &Game<'_>, pos: [i32; 3]) -> Vec<[i32; 3]> {
    let mut members = Vec::new();
    if let Some(entity) = mod_entity(game, pos) {
        walk_network(game, pos, (pos, entity), true, |member, _| {
            members.push(member)
        });
    }
    members
}

fn publish_kinetic_members(
    game: &mut Game<'_>,
    members: Vec<[i32; 3]>,
    publish: fn(&mut ModBlockEntity, &Network),
) {
    for member in members {
        let Some(state) = mod_entity(game, member).map(|entity| network(game, member, entity))
        else {
            continue;
        };
        game.native_with_mod_block_entity(member, |entity| publish(entity, &state));
        game.native_block_entity_sync(member);
    }
}

pub(super) fn refresh_windmill_network(
    game: &mut Game<'_>,
    pos: [i32; 3],
    mill: &mut ModBlockEntity,
) {
    let mut members = Vec::new();
    let state = walk_network(game, pos, (pos, mill), true, |member, _| {
        members.push(member)
    });
    publish_network(mill, &state);
    for member in members.into_iter().filter(|member| *member != pos) {
        let state = walk_network(game, member, (pos, mill), true, |_, _| {});
        game.native_with_mod_block_entity(member, |linked| publish_network(linked, &state));
        game.native_block_entity_sync(member);
    }
    game.native_block_entity_sync(pos);
}

fn tick_mill(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if entity.items.len() < 10 {
        return;
    }
    let state = network(game, pos, entity);
    let rpm = state.speed();
    let time = game.world.game_time;
    let attaching = mill_just_attached(entity, time);
    publish_network(entity, &state);
    if attaching {
        entity.data.resize(MILL_ATTACH_TICK.end, 0);
        entity.data[MILL_ATTACH_TICK].copy_from_slice(&[time as i32, (time >> 32) as i32]);
    }
    let fields = &mut **entity;
    let (input, outputs) = fields.items.split_at_mut(1);
    read_inventory(&mut fields.nbt, "InputInventory", input);
    read_inventory(&mut fields.nbt, "OutputInventory", outputs);
    collect_landed_items(game, pos, &mut input[0], MILL);

    if rpm == 0.0
        || outputs
            .iter()
            .flatten()
            .any(|stack| stack.count == game.native_max_stack_size(&stack.item).unwrap_or(64))
    {
        return;
    }
    let mut timer = int(&fields.nbt, "Timer").unwrap_or(0);
    if timer > 0 {
        timer -= ((rpm / 16.0).abs() as i32).clamp(1, 512);
        fields.nbt.insert("Timer".into(), Tag::Int(timer));
        if timer <= 0
            && let Some(stack) = &mut input[0]
        {
            let Some(recipe) = milling_recipe(game, stack).cloned() else {
                return;
            };
            stack.count -= 1;
            if stack.count == 0 {
                input[0] = None;
            }
            let Some(results) = recipe["results"].as_array() else {
                return;
            };
            for result in results {
                let Some(mut output) = game.native_recipe_result(result) else {
                    continue;
                };
                let chance = result["chance"].as_f64().unwrap_or(1.0) as f32;
                if chance < 1.0 {
                    output.count = (0..output.count)
                        .filter(|_| recipe_roll(game, pos) <= chance)
                        .count() as u32;
                }
                let limit = game.native_max_stack_size(&output.item).unwrap_or(64);
                insert(outputs, &output, limit);
            }
        }
    } else if let Some(stack) = &input[0] {
        timer = milling_recipe(game, stack)
            .and_then(|recipe| recipe["processing_time"].as_i64())
            .unwrap_or(100) as i32;
        fields.nbt.insert("Timer".into(), Tag::Int(timer));
    }
}

pub(super) fn chute_exposes_filter_amount(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let pressure = chute_air(game, pos, Direction::Up) + chute_air(game, pos, Direction::Down);
    let [x, y, z] = offset(
        pos,
        if pressure > 0.0 {
            Direction::Down.normal()
        } else {
            Direction::Up.normal()
        },
    );
    if matches!(game.native_block([x, y, z]).as_str(), CHUTE | PLAIN_CHUTE) {
        return false;
    }
    game.with_level(|behaviour, level, _| !behaviour.is_replaceable(level.world.block(x, y, z)))
}

pub(super) fn chute_has_open_top(game: &Game<'_>, pos: [i32; 3]) -> bool {
    let kind = game.native_block(pos);
    if kind != CHUTE
        && (kind != PLAIN_CHUTE
            || game.native_block_property(pos, "facing").as_deref() != Some("down")
                && game.native_block_property(pos, "shape").as_deref() != Some("intersection"))
    {
        return false;
    }
    !matches!(
        game.native_block(offset(pos, [0, 1, 0])).as_str(),
        CHUTE | PLAIN_CHUTE
    ) && chute_air(game, pos, Direction::Up) + chute_air(game, pos, Direction::Down) <= 0.0
}

pub(super) fn chute_landing(
    game: &mut Game<'_>,
    state: horizon_world::registry::BlockStateId,
    item_pos: [f64; 3],
    stack: &mut ItemStack,
) {
    if !matches!(game.native_state_block(state), Some(CHUTE | PLAIN_CHUTE)) {
        return;
    }
    let [x, y, z] = item_pos;
    let pos = [
        x.floor() as i32,
        (y + 0.5).floor() as i32 - 1,
        z.floor() as i32,
    ];
    let above = offset(pos, [0, 1, 0]);
    if matches!(game.native_block(above).as_str(), CHUTE | PLAIN_CHUTE) {
        return;
    }
    let Some(chute) = mod_entity(game, pos) else {
        return;
    };
    // An upward chute with no input chute cannot take items landing on top.
    if chute_air(game, pos, Direction::Up) + chute_air(game, pos, Direction::Down) > 0.0 {
        return;
    }
    let smart = chute.id == CHUTE;
    if !matches!(chute.id.as_str(), CHUTE | PLAIN_CHUTE)
        || chute.items.first().is_some_and(Option::is_some)
        || smart && !super::create_item_filters::accepts(game.items(), &chute.nbt, stack)
    {
        return;
    }
    if smart && game.native_neighbor_signal(game.native_dimension(), pos) > 0 {
        return;
    }
    let max_stack = game.native_max_stack_size(&stack.item).unwrap_or(64);
    if let Some(remaining) = game.native_with_mod_block_entity(pos, |chute| {
        if chute.items.is_empty() {
            chute.items.resize(1, None);
        }
        let remaining = insert(&mut chute.items, stack, max_stack);
        set_float(&mut chute.nbt, "ItemPosition", 1.0);
        remaining
    }) {
        stack.count = remaining;
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn insert_chute(
    game: &mut Game<'_>,
    pos: [i32; 3],
    mut stack: ItemStack,
) -> Option<ItemStack> {
    let Some(chute) = mod_entity(game, pos) else {
        return Some(stack);
    };
    if chute.items.first().is_some_and(Option::is_some)
        || super::create_depot::compound(&chute.nbt, "Item").is_some_and(|saved| !saved.is_empty())
        || chute.id == CHUTE
            && !super::create_item_filters::accepts(game.items(), &chute.nbt, &stack)
    {
        return Some(stack);
    }
    if game.native_block(pos) == CHUTE
        && game.native_neighbor_signal(game.native_dimension(), pos) > 0
    {
        return Some(stack);
    }
    let upward = chute_air(game, pos, Direction::Up) + chute_air(game, pos, Direction::Down) > 0.0;
    let accepted = stack
        .count
        .min(game.native_max_stack_size(&stack.item).unwrap_or(64));
    if game
        .native_with_mod_block_entity(pos, |chute| {
            chute.items.resize(1, None);
            chute.items[0] = Some(ItemStack {
                count: accepted,
                ..stack.clone()
            });
            set_float(
                &mut chute.nbt,
                "ItemPosition",
                if upward { 0.0 } else { 1.0 },
            );
        })
        .is_none()
    {
        return Some(stack);
    }
    game.native_block_entity_sync(pos);
    stack.count -= accepted;
    (stack.count > 0).then_some(stack)
}

fn chute_air(game: &Game<'_>, start: [i32; 3], direction: Direction) -> f32 {
    let mut pos = offset(start, direction.normal());
    while matches!(game.native_block(pos).as_str(), CHUTE | PLAIN_CHUTE) {
        pos = offset(pos, direction.normal());
    }
    if game.native_block(pos) == FAN
        && super::create_fan::facing(game, game.world.block(pos[0], pos[1], pos[2]))
            == Some(direction.opposite())
    {
        rpm_at(game, pos)
    } else {
        0.0
    }
}

fn tick_chute(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if entity.items.is_empty() {
        return;
    }
    let stored = entity.nbt.remove(&"Item".into());
    if entity.items[0].is_none() {
        entity.items[0] = read_create_stack(stored);
    }
    let dimension = game.native_dimension();
    let powered = entity.id == CHUTE && game.native_neighbor_signal(dimension, pos) > 0;
    let was_powered = game.native_block_property(pos, "powered").as_deref() == Some("true");
    if powered != was_powered {
        game.native_set_block_property_with(
            pos,
            "powered",
            if powered { "true" } else { "false" },
            2,
        );
    }
    let pull = chute_air(game, pos, Direction::Up);
    let push = chute_air(game, pos, Direction::Down);
    set_float(&mut entity.nbt, "Pull", pull);
    set_float(&mut entity.nbt, "Push", push);
    let pressure = (pull + push) / 64.0;
    let motion = (pressure.clamp(-20.0, 20.0) + if pressure <= 0.0 { -4.0 } else { 0.0 }) / 20.0;
    if motion > 0.0 {
        tick_upward_chute(game, pos, entity, powered, motion);
        return;
    }
    if entity.items[0].is_none() {
        if powered {
            return;
        }
        let above = offset(pos, [0, 1, 0]);
        if matches!(game.native_block(above).as_str(), CHUTE | PLAIN_CHUTE) {
            return;
        }
        let smart = entity.id == CHUTE;
        let desired = if smart {
            int(&entity.nbt, "FilterAmount").unwrap_or(0)
        } else {
            16
        };
        let limit = if desired > 0 { desired as u32 } else { 64 };
        let exact = smart && desired > 0 && int(&entity.nbt, "UpTo") == Some(0);
        let extracted = if game.native_block(above) == BELT {
            super::create_belt::extract_at(game, above, limit, exact, &entity.nbt)
        } else {
            super::create_belt_funnel::extract(game, above, Direction::Down, entity, limit, exact)
        };
        if let Some(stack) = extracted {
            entity.items[0] = Some(stack);
            set_float(&mut entity.nbt, "ItemPosition", 1.0);
        }
        return;
    }

    let below = offset(pos, [0, -1, 0]);
    let target_block = game.native_block(below);
    let into_crafter = target_block == CRAFTER;
    let bare_inventory = matches!(
        target_block.as_str(),
        DEPLOYER | CRAFTER | "minecraft:barrel"
    );
    let into_chute = matches!(game.native_block(below).as_str(), CHUTE | PLAIN_CHUTE);
    let into_container = super::create_creative_crate::accepts_items(game, below)
        || game
            .native_container_slots(dimension, below, Direction::Up)
            .is_some();
    let position = float(&entity.nbt, "ItemPosition").unwrap_or(1.0);
    let mut next = position + motion;
    let blocked = !into_container
        && game.native_block_collision(below).iter().any(|bounds| {
            bounds[4] == 1.0
                && bounds[0] == 0.0
                && bounds[2] == 0.0
                && bounds[3] == 1.0
                && bounds[5] == 1.0
        });
    let deployer_full = game.native_block(below) == DEPLOYER
        && entity.items[0].as_ref().is_some_and(|item| {
            let limit = game.native_max_stack_size(&item.item).unwrap_or(64);
            mod_entity(game, below)
                .and_then(|target| target.items.first()?.as_ref())
                .is_some_and(|tool| tool.count >= limit || !same_stack(tool, item))
        });
    let crafter_full = into_crafter && create_crafter::room(game, below) == 0;
    if next < 0.5 && (powered || blocked || deployer_full || crafter_full) {
        next = 0.5;
    }
    if next < 0.0
        && let Some(stack) = entity.items[0].take()
    {
        if into_container {
            if into_chute {
                entity.items[0] = game
                    .native_with_mod_block_entity(below, |target| {
                        let slot = target.items.first_mut()?;
                        if slot.is_some() {
                            return None;
                        }
                        *slot = Some(stack.clone());
                        set_float(&mut target.nbt, "ItemPosition", 1.0);
                        Some(())
                    })
                    .flatten()
                    .is_none()
                    .then_some(stack);
            } else if into_crafter {
                entity.items[0] = create_crafter::insert(game, below, stack);
            } else {
                entity.items[0] =
                    super::create_creative_crate::insert(game, below, Direction::Up, stack);
            }
            next = if bare_inventory {
                float(&entity.nbt, "PrevItemPosition").unwrap_or(position)
            } else if entity.items[0].is_some() {
                0.5
            } else {
                1.0
            };
        } else {
            let [x, y, z] = pos.map(f64::from);
            game.add_item_entity(
                stack,
                [x + 0.5, y - 0.25, z + 0.5],
                Some([0.0, -0.25, 0.0]),
                10,
            );
            next = 1.0;
        }
    }
    set_float(&mut entity.nbt, "PrevItemPosition", position);
    set_float(&mut entity.nbt, "ItemPosition", next);
}

fn tick_upward_chute(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    powered: bool,
    motion: f32,
) {
    let Some(item) = entity.items[0].as_ref() else {
        if powered {
            return;
        }
        let below = offset(pos, Direction::Down.normal());
        if !matches!(game.native_block(below).as_str(), CHUTE | PLAIN_CHUTE) {
            let maximum = if entity.id == CHUTE {
                int(&entity.nbt, "FilterAmount").unwrap_or(64).clamp(1, 64) as u32
            } else {
                16
            };
            let exact = entity.id == CHUTE && int(&entity.nbt, "UpTo") == Some(0);
            entity.items[0] = super::create_belt_funnel::extract(
                game,
                below,
                Direction::Up,
                entity,
                maximum,
                exact,
            );
            if entity.items[0].is_some() {
                set_float(&mut entity.nbt, "ItemPosition", 0.0);
            }
        }
        return;
    };

    let above = offset(pos, Direction::Up.normal());
    let upper = game.native_block(above);
    let into_chute = matches!(upper.as_str(), CHUTE | PLAIN_CHUTE);
    let blocked_chute = into_chute
        && mod_entity(game, above).is_none_or(|target| {
            target.items.first().is_some_and(Option::is_some)
                || !super::create_item_filters::accepts(game.items(), &target.nbt, item)
        });
    let solid = game.native_block_collision(above).iter().any(|bounds| {
        bounds[1] == 0.0
            && bounds[0] == 0.0
            && bounds[2] == 0.0
            && bounds[3] == 1.0
            && bounds[5] == 1.0
    });
    let voiding = super::create_creative_crate::accepts_items(game, above);
    let container = voiding
        || game
            .native_container_slots(game.native_dimension(), above, Direction::Down)
            .is_some();
    let position = float(&entity.nbt, "ItemPosition").unwrap_or(0.0);
    let mut next = position + motion;
    if next > 0.5 {
        let blocked_output = if container {
            !voiding && !super::create_belt_funnel::fits(game, above, Direction::Down, item, 1)
        } else {
            !into_chute && solid
        };
        if powered || blocked_chute || blocked_output {
            next = 0.5;
        }
    }
    if next > 1.0
        && let Some(stack) = entity.items[0].take()
    {
        if into_chute {
            let transferred = game
                .native_with_mod_block_entity(above, |target| {
                    target.items.resize(1, None);
                    target.items[0] = Some(stack.clone());
                    set_float(&mut target.nbt, "ItemPosition", 0.0);
                })
                .is_some();
            if !transferred {
                entity.items[0] = Some(stack);
            }
        } else if container {
            let count = stack.count;
            entity.items[0] =
                super::create_creative_crate::insert(game, above, Direction::Down, stack);
            let remaining = entity.items[0].as_ref().map_or(0, |item| item.count);
            // Java retains the incoming position after a capability accepts items.
            let settled = if remaining < count { position } else { 0.5 };
            set_float(&mut entity.nbt, "ItemPosition", settled);
            return;
        } else {
            let [x, y, z] = pos.map(f64::from);
            game.add_item_entity(
                stack,
                [x + 0.5, y + 1.0, z + 0.5],
                Some([0.0, f64::from(motion) * 2.0, 0.0]),
                10,
            );
        }
        next = if entity.items[0].is_none() { 0.0 } else { 0.5 };
    }
    set_float(&mut entity.nbt, "ItemPosition", next);
}

fn read_create_stack(saved: Option<Tag>) -> Option<ItemStack> {
    let Tag::Compound(mut stack) = saved? else {
        return None;
    };
    // Create's nested inventory tags bypass the vanilla item data fixer.
    // ItemStack.parseOptional reads the modern count, defaulting to one.
    stack.remove(&"Count".into());
    if let Some(Tag::Compound(components)) = stack.get_mut(&"components".into())
        && let Some(Tag::Compound(enchantments)) =
            components.get_mut(&"minecraft:enchantments".into())
        && let Some(Tag::Compound(levels)) = enchantments.remove(&"levels".into())
    {
        *enchantments = levels;
    }
    ItemStack::from_nbt(&stack)
}

fn deployer_punch(game: &mut Game<'_>, at: [i32; 3], entity: &mut ModBlockEntity) {
    use horizon_items::mining::{self, DestroySpeedModifiers};

    let state = game.world.block(at[0], at[1], at[2]);
    let facts = game.res.facts().get(state);
    let Some(tool) = entity.items.first().and_then(Option::as_ref) else {
        return;
    };
    if game.res.behaviours().is_air(state) || facts.hardness == -1.0 {
        entity.nbt.remove(&"BreakingProgress".into());
        return;
    }
    let tool_speed = game.items().mining_speed(Some(tool), &facts.name);
    let harvest =
        game.items()
            .has_correct_tool_for_drops(Some(tool), facts.requires_tool, &facts.name);
    let level = tool.enchantment_level("minecraft:efficiency") as f32;
    let modifiers = DestroySpeedModifiers {
        mining_efficiency: if level > 0.0 {
            level * level + 1.0
        } else {
            0.0
        },
        on_ground: false,
        ..DestroySpeedModifiers::default()
    };
    let per_punch = mining::destroy_progress(
        facts.hardness,
        harvest,
        mining::destroy_speed(tool_speed, &modifiers),
    ) * 16.0;
    let signature = [at[0], at[1], at[2], state.0 as i32];
    let previous = if matches!(entity.nbt.get(&"BreakingBlock".into()), Some(Tag::IntArray(id)) if id.as_slice() == signature)
    {
        float(&entity.nbt, "BreakingProgress").unwrap_or(0.0)
    } else {
        0.0
    };
    let progress = previous + per_punch;
    if progress < 1.0 {
        entity
            .nbt
            .insert("BreakingBlock".into(), Tag::IntArray(signature.to_vec()));
        set_float(&mut entity.nbt, "BreakingProgress", progress);
        return;
    }
    let Some(drops) = game.native_machine_destroy_block(at, Some(tool), true) else {
        return;
    };
    let (capacity, wear) = (
        game.items().mining_damage_capacity(tool),
        game.items().mining_damage(tool),
    );
    if capacity > 0
        && let Some(amount) = wear
    {
        let damage = tool.damage.saturating_add(game.wear(tool, amount));
        if damage >= capacity {
            entity.items[0] = None;
        } else if let Some(tool) = entity.items[0].as_mut() {
            tool.damage = damage;
        }
    }
    entity.nbt.remove(&"BreakingProgress".into());
    entity.nbt.remove(&"BreakingBlock".into());
    if harvest && !drops.is_empty() {
        let key = "Overflow".into();
        let mut overflow = match entity.nbt.remove(&key) {
            Some(Tag::List(stacks)) => stacks,
            _ => Vec::new(),
        };
        overflow.extend(drops.iter().map(super::create_depot::encode));
        entity.nbt.insert(key, Tag::List(overflow));
    }
}

fn tick_deployer(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let state = network(game, pos, entity);
    let rpm = state.speed();
    let was_stopped = float(&entity.nbt, "Speed").unwrap_or(0.0) == 0.0;
    let punch = string(&entity.nbt, "Mode").as_deref() == Some("PUNCH");
    publish_network(entity, &state);
    let loaded = entity.nbt.remove(&"AttachOnFirstTick".into()).is_some();
    let saved = entity.nbt.remove(&"HeldItem".into());
    if let Some(slot) = entity.items.first_mut()
        && slot.is_none()
    {
        *slot = read_create_stack(saved);
    }
    let mut inventory = std::mem::take(&mut entity.items);
    read_inventory(&mut entity.nbt, "Inventory", &mut inventory);
    entity.items = inventory;
    if loaded
        && int(&entity.nbt, "Timer").is_some_and(|timer| timer != 0)
        && game.native_block_property(pos, "facing").as_deref() == Some("down")
        && game.native_block(offset(pos, [0, -2, 0])) == BELT
    {
        return;
    }
    if rpm == 0.0 || punch && was_stopped {
        return;
    }
    let per_tick = (rpm * 2.0).abs().clamp(8.0, 512.0) as i32;
    let timer = int(&entity.nbt, "Timer").unwrap_or(0);
    if timer > 0 {
        entity
            .nbt
            .insert("Timer".into(), Tag::Int(timer - per_tick));
        return;
    }
    let facing = game
        .native_block_property(pos, "facing")
        .unwrap_or_default();
    let normal = match facing.as_str() {
        "east" => [1, 0, 0],
        "west" => [-1, 0, 0],
        "up" => [0, 1, 0],
        "down" => [0, -1, 0],
        "south" => [0, 0, 1],
        "north" => [0, 0, -1],
        _ => return,
    };
    let target = offset(pos, normal.map(|n| n * 2));
    let phase = string(&entity.nbt, "State").unwrap_or_else(|| "WAITING".into());
    let (next, timer) = match phase.as_str() {
        "EXPANDING" => {
            if punch {
                deployer_punch(game, target, entity);
            } else if let Some(stack) = entity.items.first_mut().and_then(Option::as_mut)
                && !super::create_wheel_material::use_planks(game, target, stack)
                && super::create_item_application::apply(game, target, stack)
            {
                stack.count -= 1;
                if stack.count == 0 {
                    entity.items[0] = None;
                }
            }
            ("RETRACTING", 1000)
        }
        "RETRACTING" => ("WAITING", 500),
        _ => {
            if facing == "down" && game.native_block(target) == BELT {
                entity.nbt.insert("Timer".into(), Tag::Int(per_tick * 10));
                return;
            }
            if game.native_neighbor_signal(game.dim.id(), pos) > 0 {
                return;
            }
            if entity
                .items
                .first()
                .and_then(Option::as_ref)
                .is_some_and(|held| game.native_block(target) == held.item.as_ref())
            {
                entity.nbt.insert("Timer".into(), Tag::Int(per_tick * 10));
                return;
            }
            ("EXPANDING", 1000)
        }
    };
    entity.nbt.insert("State".into(), Tag::String(next.into()));
    entity.nbt.insert("Timer".into(), Tag::Int(timer));
}

pub(super) fn string(nbt: &Compound, key: &str) -> Option<String> {
    match nbt.get(&JavaString::from(key))? {
        Tag::String(value) => Some(value.to_string_lossy()),
        _ => None,
    }
}

pub(super) fn block_entity_tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if entity.id == LARGE_WHEEL {
        super::create_large_wheel::tick(game, pos, entity);
    }
    match entity.id.as_str() {
        super::create_portable_interface::ITEM | super::create_portable_interface::FLUID => {
            super::create_train_portable_items::tick_stationary(game, pos, entity);
        }
        super::create_item_drain::DRAIN => super::create_item_drain::tick(game, pos, entity),
        CONVEYOR => {
            let rpm = saved_speed(&entity.nbt);
            let state = network(game, pos, entity);
            publish_network(entity, &state);
            super::create_chain_conveyor_packages::tick(game, pos, &mut entity.nbt, rpm);
            if rpm != state.speed() {
                game.native_block_entity_sync(pos);
            }
        }
        FROGPORT => super::create_chain_conveyor_packages::tick_port(game, pos, entity),
        super::create_nozzle::NOZZLE => super::create_nozzle::tick(game, pos, entity),
        super::create_backtank::ENTITY => {
            let was_powered = reading(entity, 0) != 0.0;
            let state = network(game, pos, entity);
            publish_network(entity, &state);
            if was_powered {
                super::create_backtank::tick(game, pos, entity, state.speed());
            }
        }
        super::create_turntable::BLOCK => {
            let state = network(game, pos, entity);
            let speed_changed = reading(entity, 0) != state.speed();
            publish_network(entity, &state);
            if speed_changed {
                game.native_block_entity_sync(pos);
            }
        }
        super::create_flywheel::FLYWHEEL => {
            let state = network(game, pos, entity);
            let speed_changed = reading(entity, 0) != state.speed();
            publish_network(entity, &state);
            super::create_flywheel::tick(game, pos, entity, speed_changed);
        }
        "create:motor"
        | "create:simple_kinetic"
        | WHEEL
        | LARGE_WHEEL
        | SPEEDOMETER
        | STRESSOMETER
        | "create:cuckoo_clock" => {
            let state = network(game, pos, entity);
            let speed_changed = reading(entity, 0) != state.speed();
            let gauge_changed = matches!(entity.id.as_str(), SPEEDOMETER | STRESSOMETER)
                && network_values(&entity.nbt) != [state.rpm, state.capacity, state.stress];
            publish_network(entity, &state);
            match entity.id.as_str() {
                WHEEL | LARGE_WHEEL | "create:simple_kinetic" if speed_changed => {
                    game.native_block_entity_sync(pos);
                }
                SPEEDOMETER => {
                    let target = super::create_visuals::speed_target(state.speed());
                    super::create_visuals::tick_dial(
                        game,
                        pos,
                        entity,
                        target,
                        target,
                        gauge_changed,
                    );
                }
                STRESSOMETER => {
                    // New mills attach during the block-entity pass, after the
                    // established gauge has advanced. Publish the updated target
                    // with the needle position for this tick. Removed mills are
                    // already absent when the gauge advances.
                    let target = state.stress_target(state.stress);
                    let easing_target = state.stress_target(state.stress - state.new_load);
                    super::create_visuals::tick_dial(
                        game,
                        pos,
                        entity,
                        target,
                        easing_target,
                        gauge_changed,
                    );
                }
                _ => {}
            }
        }
        super::create_gantry::SHAFT => super::create_gantry::shaft_shape(game, pos),
        TUNNEL => super::create_andesite_tunnel::tick(game, pos),
        super::create_brass_tunnel::TUNNEL => super::create_brass_tunnel::tick(game, pos, entity),
        FUNNEL => {
            if matches!(game.native_block(pos).as_str(), ANDESITE | BRASS) {
                create_belt_funnel::tick(game, pos, entity);
            } else {
                super::create_funnel::tick(game, pos, entity);
            }
        }

        VAULT => create_vault::tick(game, pos, entity),
        PUMP => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            create_fluids::pump(game, pos, entity, rpm, changed);
            if changed {
                game.native_block_entity_sync(pos);
            }
        }
        CHAIN_GEARSHIFT | SPEED_CONTROLLER => {
            let state = network(game, pos, entity);
            let changed = reading(entity, 0) != state.speed();
            publish_network(entity, &state);
            if changed {
                game.native_block_entity_sync(pos);
            }
        }
        CRANK => {
            if !create_hand_crank::retain_support(game, pos) {
                return;
            }
            let state = network(game, pos, entity);
            let rpm = state.speed();
            publish_network(entity, &state);
            if create_hand_crank::tick(game, pos, entity, rpm) {
                disconnect_crank_network(game, pos, entity);
            }
            create_hand_crank::trace_tick(game, pos, entity);
        }
        HANDLE_ENTITY | VALVE | CASED_COG_ENTITY | CASED_LARGE_COG_ENTITY => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let speed_changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            if entity.id == HANDLE_ENTITY {
                if create_valve::tick_handle(game, pos, entity, rpm) {
                    disconnect_crank_network(game, pos, entity);
                }
            } else if entity.id == VALVE {
                create_valve::tick_valve(game, pos, entity, rpm);
            } else if speed_changed {
                game.native_block_entity_sync(pos);
            }
        }
        PIPE | GLASS_PIPE | SMART_PIPE | super::create_encased_fluid_pipe::BLOCK => {
            create_fluids::tick(game, pos, entity)
        }
        ENGINE => create_steam::tick_engine(game, pos, entity),
        POWERED_SHAFT => {
            let state = network(game, pos, entity);
            let changed = reading(entity, 0) != state.speed();
            publish_network(entity, &state);
            if let Some(Kinetic::PoweredShaft(axis)) = Kinetic::at(game, pos) {
                let (_, power, direction) = create_steam::shaft_power(game, pos, axis);
                set_float(&mut entity.nbt, "EnginePower", power);
                entity.nbt.insert("Direction".into(), Tag::Int(direction));
            }
            if changed {
                game.native_block_entity_sync(pos);
            }
        }
        super::create_mechanical_piston::PISTON => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            publish_network(entity, &state);
            super::create_mechanical_piston::tick(game, pos, entity, rpm);
        }
        WINDMILL => {
            let state = network(game, pos, entity);
            publish_network(entity, &state);
            create_bearing::windmill_advance(game, pos, entity);
        }
        SIGNAL => create_train_signal::tick(game, pos, entity),
        super::create_track_observer::OBSERVER => {
            super::create_track_observer::tick(game, pos, entity)
        }
        CLOCKWORK => {
            let state = network(game, pos, entity);
            let previous = reading(entity, 0);
            let rpm = state.speed();
            publish_network(entity, &state);
            create_clockwork::tick(game, pos, entity, previous, rpm);
        }
        BEARING => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            publish_network(entity, &state);
            let source = offset(pos, state.source_side);
            // A chain drive transmits the clutch's scheduled reconnection
            // even though the drive itself has no kinetic ticker.
            let chain_reconnected = state.clutch_reconnected
                && matches!(Kinetic::at(game, source), Some(Kinetic::ChainDrive(..)));
            // A configured motor announces the new speed before the next
            // bearing tick. An initialized bearing can assemble on that tick.
            let adjacent_motor_started = rpm != 0.0
                && int(&entity.nbt, "AssembleNextTick") == Some(0)
                && matches!(Kinetic::at(game, source), Some(Kinetic::Motor(_)));
            let source_ticked = adjacent_motor_started || chain_reconnected
                || mod_entity(game, source).is_some_and(|drive| {
                    matches!(drive.nbt.get(&"KineticsTick".into()), Some(Tag::Long(tick)) if *tick == game.world.game_time)
                });
            let angle = match state.sequence {
                Some(create_sequencer::Motion::Angle(angle)) => Some(angle * f64::from(rpm.abs())),
                _ => None,
            };
            super::create_bearing::tick(game, pos, entity, rpm, source_ticked, angle);
        }
        super::create_burner::HEATER => super::create_burner::tick(game, pos, entity),
        ARM => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            publish_network(entity, &state);
            create_arm::tick(game, pos, entity, rpm);
        }
        super::create_spout::SPOUT => super::create_spout::tick(game, pos, entity),
        super::create_track::TRACK => super::create_track::tick(game, pos, entity),
        super::create_elevator::PULLEY => {
            let rpm = network(game, pos, entity).speed();
            let changed = float(&entity.nbt, "VisualSpeed") != Some(rpm);
            set_float(&mut entity.nbt, "VisualSpeed", rpm);
            super::create_elevator::tick(game, pos, entity, rpm);
            if changed {
                game.native_block_entity_sync(pos);
            }
        }
        PULLEY => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            let distance = match state.sequence {
                Some(create_sequencer::Motion::Distance(distance)) => Some(distance),
                _ => None,
            };
            create_rope::tick(game, pos, entity, rpm, changed, distance);
        }
        HOSE => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            create_hose::tick(game, pos, entity, rpm, changed);
        }
        MIXER => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            create_mixer::tick(game, pos, entity, rpm, changed);
        }
        BASIN if entity.items.len() >= 18 => {
            let mut items = std::mem::take(&mut entity.items);
            let (input, output) = items.split_at_mut(9);
            read_inventory(&mut entity.nbt, "InputItems", input);
            read_inventory(&mut entity.nbt, "OutputItems", output);
            entity.items = items;
            create_mixer::basin_tick(game, pos, entity);
        }
        CONTROLLER => create_crushing::tick(game, pos, entity),
        CRUSHING_WHEEL | "create:encased_shaft" => {
            let state = network(game, pos, entity);
            let changed = reading(entity, 0) != state.speed();
            publish_network(entity, &state);
            if entity.id == CRUSHING_WHEEL {
                create_crushing::maintain_pair(game, pos);
            }
            if changed {
                game.native_block_entity_sync(pos);
            }
        }

        FAN => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let speed_changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            super::create_fan::tick(game, pos, entity, rpm);
            if speed_changed {
                game.native_block_entity_sync(pos);
            }
        }
        BELT => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let speed_changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            if int(&entity.nbt, "NeedsSpeedUpdate") == Some(1) {
                entity.nbt.remove(&"NeedsSpeedUpdate".into());
                game.native_block_entity_sync(pos);
            } else {
                super::create_belt::tick(game, pos, entity, rpm, speed_changed);
            }
        }
        PRESS => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let speed_changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            super::create_press::tick(game, pos, entity, rpm, speed_changed);
        }
        super::create_drill::ENTITY => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let speed_changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            super::create_drill::tick(game, pos, entity, rpm);
            if speed_changed {
                game.native_block_entity_sync(pos);
            }
        }
        super::create_saw::ENTITY => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            let speed_changed = reading(entity, 0) != rpm;
            publish_network(entity, &state);
            super::create_saw::tick(game, pos, entity, rpm);
            if speed_changed {
                game.native_block_entity_sync(pos);
            }
        }
        MILL => tick_mill(game, pos, entity),
        DEPLOYER => tick_deployer(game, pos, entity),
        CANNON => create_schematicannon::tick(game, pos, entity),
        DEPOT => super::create_depot::tick_depot(game, pos, entity),
        CRAFTER => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            publish_network(entity, &state);
            create_crafter::tick(game, pos, entity, rpm);
        }
        EJECTOR => {
            let state = network(game, pos, entity);
            let rpm = state.speed();
            publish_network(entity, &state);
            if int(&entity.nbt, "NeedsSpeedUpdate") == Some(1) {
                entity.nbt.remove(&"NeedsSpeedUpdate".into());
                game.native_block_entity_sync(pos);
            } else {
                create_ejector::tick(game, pos, entity, rpm);
            }
        }

        super::create_display_board::ENTITY => {
            let state = network(game, pos, entity);
            let changed_speed = float(&entity.nbt, "Speed") != Some(state.speed());
            publish_network(entity, &state);
            super::create_display_board::tick(game, pos, entity, state.speed(), changed_speed);
        }
        OBSERVER => super::create_smart_observer::tick_live_target(game, pos, entity),
        super::create_display_link::LINK => super::create_display_link::tick(game, pos, entity),
        THRESHOLD_SWITCH => super::create_threshold_switch::tick(game, pos, entity),
        super::create_station::STATION => super::create_station::tick(game, pos, entity),
        CHUTE | PLAIN_CHUTE => tick_chute(game, pos, entity),
        CLUTCH | GEARSHIFT | GEARBOX => {
            if entity.id == GEARBOX {
                for key in GEARBOX_ATTACH_TICKS.map(JavaString::from) {
                    if matches!(entity.nbt.get(&key), Some(Tag::Long(tick)) if *tick != game.world.game_time)
                    {
                        entity.nbt.remove(&key);
                    }
                }
            }
            let state = network(game, pos, entity);
            if entity.id == GEARBOX
                && !entity.nbt.contains_key(&"KineticsTick".into())
                && conflicting_gearbox_join(game, pos, &state)
            {
                // Create rejects an incompatible network join at the newly
                // attached kinetic block. Do this only on the Gearbox's first
                // kinetic tick so an established neighboring network survives.
                game.native_machine_destroy_block(pos, None, true);
                for delta in GEARBOX_DIRECTIONS {
                    refresh_connected_network(game, offset(pos, delta));
                }
                return;
            }
            let input_changed = if entity.id == GEARBOX {
                int(&entity.nbt, "ShaftInputDirection").unwrap_or(-1)
                    != gearbox_input_direction(state.source_side)
            } else {
                let input = state.source_side.into_iter().sum::<i32>();
                int(&entity.nbt, "ShaftInputSide").unwrap_or(0) != input
            };
            let changed = reading(entity, 0) != state.speed() || input_changed;
            publish_network(entity, &state);
            entity
                .nbt
                .insert("KineticsTick".into(), Tag::Long(game.world.game_time));
            if changed {
                game.native_block_entity_sync(pos);
            }
        }
        _ => {}
    }
}

struct WheatTrace {
    origin: [i32; 3],
    start: Option<i64>,
    previous: Option<i64>,
    seed: Option<horizon_core::random::LegacyRandom>,
}

fn wheat_trace() -> Option<&'static Mutex<WheatTrace>> {
    static TRACE: OnceLock<Option<Mutex<WheatTrace>>> = OnceLock::new();
    TRACE
        .get_or_init(|| {
            let origin = std::env::var("CREATE_WHEAT_TRACE_ORIGIN").ok()?;
            let coordinates: Vec<i32> = origin
                .split(',')
                .map(str::parse)
                .collect::<Result<_, _>>()
                .ok()?;
            let origin = coordinates.try_into().ok()?;
            let seed = std::env::var("CREATE_WHEAT_TRACE_SEED")
                .ok()
                .and_then(|value| value.parse().ok())
                .map(horizon_core::random::LegacyRandom::new);
            Some(Mutex::new(WheatTrace {
                origin,
                start: None,
                previous: None,
                seed,
            }))
        })
        .as_ref()
}

fn recipe_roll(game: &mut Game<'_>, pos: [i32; 3]) -> f32 {
    if let Some(trace) = wheat_trace() {
        let mut trace = trace.lock().expect("wheat trace mutex");
        if trace.start.is_some()
            && pos == offset(trace.origin, [2, 2, 1])
            && let Some(random) = &mut trace.seed
        {
            return random.next_float();
        }
    }
    game.world.random.next_float()
}

fn count(game: &Game<'_>, pos: [i32; 3], item: &str) -> u32 {
    game.native_container_slots(game.native_dimension(), pos, Direction::Up)
        .into_iter()
        .flatten()
        .filter_map(|slot| slot.stack)
        .filter(|stack| stack.item.as_ref() == item)
        .map(|stack| stack.count)
        .sum()
}

thread_local! {
    static CHANGED_SIGNALS: std::cell::RefCell<Vec<(usize, [i32; 3])>> =
        const { std::cell::RefCell::new(Vec::new()) };
}

pub(super) fn observe_clutch_signal(
    level: &GameLevel<'_>,
    pos: [i32; 3],
    state: horizon_world::registry::BlockStateId,
) {
    if level.registry.state(state).is_some_and(|block| {
        matches!(
            block.name.as_str(),
            CLUTCH
                | GEARSHIFT
                | CHAIN_GEARSHIFT
                | super::create_drill::DRILL
                | CLOCKWORK
                | SIGNAL
                | super::create_portable_interface::ITEM
                | super::create_portable_interface::FLUID
        )
    }) {
        let world = std::ptr::from_ref(&*level.world) as usize;
        CHANGED_SIGNALS.with_borrow_mut(|queue| queue.push((world, pos)));
    }
}

fn take_signal_changes(
    game: &Game<'_>,
    mut include: impl FnMut([i32; 3]) -> bool,
) -> std::collections::BTreeSet<[i32; 3]> {
    let world = std::ptr::from_ref(&game.world) as usize;
    CHANGED_SIGNALS.with_borrow_mut(|queue| {
        let mut positions = std::collections::BTreeSet::new();
        queue.retain(|&(owner, pos)| {
            if owner != world || !include(pos) {
                return true;
            }
            positions.insert(pos);
            false
        });
        positions
    })
}

pub(super) fn flush_chain_gearshifts(game: &mut Game<'_>) {
    for pos in take_signal_changes(game, |pos| game.native_block(pos) == CHAIN_GEARSHIFT) {
        create_chain_gearshift::observe_signal(game, pos);
    }
}

fn observe_clockwork_power_loss(game: &mut Game<'_>, pos: [i32; 3]) {
    let Some(entity) = mod_entity(game, pos) else {
        return;
    };
    if reading(entity, 0) == 0.0 {
        return;
    }
    let state = network(game, pos, entity);
    if state.speed() != 0.0 {
        return;
    }
    game.native_with_mod_block_entity(pos, |entity| {
        publish_network(entity, &state);
        create_clockwork::schedule_assembly(entity);
    });
    game.native_block_entity_sync(pos);
}

thread_local! {
    static DISCONNECTED_MOTORS: std::cell::RefCell<Vec<(usize, [i32; 3])>> =
        const { std::cell::RefCell::new(Vec::new()) };
}

pub(super) fn motor_block_changed(
    level: &GameLevel<'_>,
    pos: BlockPos,
    old: horizon_world::registry::BlockStateId,
    new: horizon_world::registry::BlockStateId,
) {
    let Some(motor) = level
        .registry
        .state(old)
        .filter(|state| state.name == MOTOR)
    else {
        return;
    };
    if level.native_state_block(new) == Some(MOTOR) {
        return;
    }
    let Some(direction) = motor
        .properties
        .get("facing")
        .and_then(|face| motor_facing(face))
    else {
        return;
    };
    let neighbor = offset([pos.x, pos.y, pos.z], direction);
    let world = std::ptr::from_ref(&*level.world) as usize;
    DISCONNECTED_MOTORS.with_borrow_mut(|queue| queue.push((world, neighbor)));
}

pub(super) fn flush_disconnected_motors(game: &mut Game<'_>) {
    let world = std::ptr::from_ref(&game.world) as usize;
    let neighbors = DISCONNECTED_MOTORS.with_borrow_mut(|queue| {
        let mut neighbors = std::collections::BTreeSet::new();
        queue.retain(|&(owner, pos)| {
            if owner != world {
                return true;
            }
            neighbors.insert(pos);
            false
        });
        neighbors
    });
    for neighbor in neighbors {
        if game.native_block(neighbor) == CLOCKWORK {
            observe_clockwork_power_loss(game, neighbor);
        }
        refresh_connected_network(game, neighbor);
    }
}

pub(super) fn flush_clutch_signals(game: &mut Game<'_>) {
    let changed = take_signal_changes(game, |_| true);
    let mut changed_speed = false;
    for pos in changed {
        if game.native_block(pos) == CHAIN_GEARSHIFT {
            create_chain_gearshift::observe_signal(game, pos);
        } else if game.native_block(pos) == super::create_drill::DRILL {
            game.native_with_mod_block_entity(pos, super::create_drill::neighbor_changed);
        } else if game.native_block(pos) == CLOCKWORK {
            observe_clockwork_power_loss(game, pos);
        } else if game.native_block(pos) == SIGNAL {
            create_train_signal::neighbor_changed(game, pos);
        } else if super::create_portable_interface::is_port(&game.native_block(pos)) {
            super::create_portable_interface::powered_changed(game, pos);
        } else if update_clutch(game, pos) {
            changed_speed = true;
        } else if game.native_block(pos) == CLUTCH
            && game.native_block_property(pos, "powered").as_deref() == Some("true")
        {
            // A disconnected clutch still loses its own input when that shaft is removed.
            if let Some(state) = mod_entity(game, pos).and_then(|entity| {
                let state = network(game, pos, entity);
                (float(&entity.nbt, "Speed").unwrap_or(0.0) != state.rpm).then_some(state)
            }) {
                game.native_with_mod_block_entity(pos, |entity| {
                    publish_network_nbt(entity, &state)
                });
                game.native_block_entity_sync(pos);
            }
        }
    }
    if !changed_speed {
        return;
    }
    // The arm's movement has already run if the power changed late in a
    // tick. Detach its displayed RPM now and leave its progress where it was.
    let arms: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            mod_entity(game, pos)
                .filter(|entity| entity.id == ARM && int(&entity.nbt, "LazyTicks").is_some())
                .map(|entity| (pos, network(game, pos, entity)))
        })
        .collect();
    for (pos, state) in arms {
        game.native_with_mod_block_entity(pos, |entity| publish_network(entity, &state));
    }
}

pub(super) fn update_clutch(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let powered = game.native_neighbor_signal(game.native_dimension(), pos) > 0;
    let saved = game.native_block_property(pos, "powered").as_deref() == Some("true");
    if powered == saved {
        return false;
    }
    let clutch = game.native_block(pos) == CLUTCH;
    let clutch_input = if clutch && powered {
        mod_entity(game, pos).map(|entity| {
            network(game, pos, entity)
                .source_side
                .into_iter()
                .sum::<i32>()
        })
    } else {
        None
    };
    let members = kinetic_members(game, pos);
    if !game.native_set_block_property_with(
        pos,
        "powered",
        if powered { "true" } else { "false" },
        2,
    ) {
        return false;
    }
    let tick = game.world.game_time;
    game.native_with_mod_block_entity(pos, |entity| {
        if let Some(input) = clutch_input {
            if input == 0 {
                entity.nbt.remove(&"ClutchInputSide".into());
            } else {
                entity.nbt.insert("ClutchInputSide".into(), Tag::Int(input));
            }
        }
        // A new gearshift ratio or a closing clutch connects on its scheduled tick.
        if !clutch || !powered {
            entity
                .nbt
                .insert("TransmissionDetachTime".into(), Tag::Long(tick));
        }
        if clutch && !powered {
            entity
                .nbt
                .insert("ClutchReconnected".into(), Tag::Long(tick));
        }
    });
    // Expose the new network immediately while each machine retains its last
    // sampled RPM for tick effects such as clearing a stopped pump's pressure.
    publish_kinetic_members(game, members, publish_network_nbt);
    true
}

pub(super) fn update_clutches(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let clutches: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            (ticking(x, z)
                && mod_entity(game, pos)
                    .is_some_and(|entity| matches!(entity.id.as_str(), CLUTCH | GEARSHIFT)))
            .then_some(pos)
        })
        .collect();
    for pos in clutches {
        update_clutch(game, pos);
    }
}

pub(super) fn update_tanks(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let tanks: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            (ticking(x, z)
                && mod_entity(game, pos)
                    .is_some_and(|entity| matches!(entity.id.as_str(), TANK | CREATIVE)))
            .then_some(pos)
        })
        .collect();
    for pos in tanks {
        let Some(mut entity) = mod_entity(game, pos).cloned() else {
            continue;
        };
        create_fluid_tank::tick(game, pos, &mut entity);
        game.native_with_mod_block_entity(pos, |live| live.nbt = std::mem::take(&mut entity.nbt));
    }
}

pub(super) fn level_tick_post(game: &mut Game<'_>, dimension: &str) {
    if dimension != "minecraft:overworld" {
        return;
    }
    trace_wheel(game);
    let Some(trace) = wheat_trace() else {
        return;
    };
    let mut trace = trace.lock().expect("wheat trace mutex");
    let lever = offset(trace.origin, [1, 6, 1]);
    if trace.start.is_none()
        && game.native_block_property(lever, "powered").as_deref() != Some("false")
    {
        return;
    }
    let Some(mill) = mod_entity(game, offset(trace.origin, [2, 2, 1])) else {
        return;
    };
    let time = game.world.game_time;
    if trace.previous == Some(time) {
        return;
    }
    trace.previous = Some(time);
    let start = *trace.start.get_or_insert(time);
    let tick = time - start;
    if tick > 200 {
        return;
    }
    let barrel = count(game, offset(trace.origin, [2, 6, 1]), "minecraft:wheat");
    let hopper = count(game, offset(trace.origin, [2, 1, 1]), "create:wheat_flour");
    let chest = count(game, offset(trace.origin, [1, 1, 1]), "create:wheat_flour");
    let timer = int(&mill.nbt, "Timer").unwrap_or(0);
    let rpm = mill
        .data
        .first()
        .map_or(0.0, |bits| f32::from_bits(*bits as u32));
    println!("CREATE_WHEAT {tick} {barrel} {hopper} {chest} {timer} {rpm:.1}");
}

#[derive(Default)]
struct WheelTrace {
    start: Option<i64>,
    previous: Option<i64>,
}

pub(super) fn trace_large_wheel() -> bool {
    static LARGE: OnceLock<bool> = OnceLock::new();
    *LARGE.get_or_init(|| std::env::var_os("CREATE_WHEEL_TRACE_LARGE").is_some())
}

fn trace_wheel(game: &Game<'_>) {
    static ORIGIN: OnceLock<Option<[i32; 3]>> = OnceLock::new();
    static TRACE: Mutex<WheelTrace> = Mutex::new(WheelTrace {
        start: None,
        previous: None,
    });
    let Some(origin) = *ORIGIN.get_or_init(|| {
        let origin = std::env::var("CREATE_WHEEL_TRACE_ORIGIN").ok()?;
        let parts: Vec<i32> = origin
            .split(',')
            .map(str::parse)
            .collect::<Result<_, _>>()
            .ok()?;
        parts.try_into().ok()
    }) else {
        return;
    };
    let (hub, open, left, extent, stream_y) = if trace_large_wheel() {
        ([4, 2, 2], [3, 7, 1], [5, 6, 1], 2, -1)
    } else {
        ([3, 1, 2], [2, 5, 1], [4, 4, 1], 1, 0)
    };
    let open = offset(origin, open);
    let left = offset(origin, left);
    let [wheel, speedometer, stressometer] =
        [hub, offset(hub, [0, 0, -1]), offset(hub, [0, 0, 1])].map(|delta| offset(origin, delta));
    let mut trace = TRACE.lock().expect("wheel trace mutex");
    if trace.start.is_none()
        && game.native_block_property(open, "powered").as_deref() != Some("false")
    {
        return;
    }
    let (Some(wheel), Some(speedometer), Some(stressometer)) = (
        mod_entity(game, wheel),
        mod_entity(game, speedometer),
        mod_entity(game, stressometer),
    ) else {
        return;
    };
    let time = game.world.game_time;
    if trace.previous == Some(time) {
        return;
    }
    trace.previous = Some(time);
    let tick = time - *trace.start.get_or_insert(time);
    let water = |dx, dy, dz| {
        let pos = offset(offset(origin, hub), [dx, dy, dz]);
        if game.native_block(pos) != "minecraft:water" {
            return -1;
        }
        game.native_block_property(pos, "level")
            .and_then(|level| level.parse().ok())
            .unwrap_or(0)
    };
    let left_on = game.native_block_property(left, "powered").as_deref() == Some("true");
    let flow = int(&wheel.nbt, "FlowScore").unwrap_or(0);
    let wheel_rpm = reading(wheel, 0);
    let gauge_rpm = reading(speedometer, 0);
    let capacity = reading(stressometer, 1);
    let stress = reading(stressometer, 2);
    println!(
        "CREATE_WHEEL {tick} {left_on} {} {} {} {} {flow} {wheel_rpm:.1} {gauge_rpm:.1} {capacity:.1} {stress:.1}",
        water(extent, stream_y, 0),
        water(-extent, stream_y, 0),
        water(0, extent, -1) >= 0,
        water(0, extent, 1) >= 0
    );
}
