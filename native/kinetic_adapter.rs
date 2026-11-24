//! Horizon host adapter for the selected kinetic graph. Calculation lives in
//! `kinetic_slice`; this file owns only typed-Part registration and world IO.

use std::collections::{HashMap, VecDeque};
use std::sync::OnceLock;

use super::create_kinetic_slice::Node;
use super::create_kinetic_slice as kinetic_slice;

static KINETIC_PART: OnceLock<KineticPart> = OnceLock::new();
const DIRECTIONS: [[i32; 3]; 6] = [
    [0, -1, 0],
    [0, 1, 0],
    [0, 0, -1],
    [0, 0, 1],
    [-1, 0, 0],
    [1, 0, 0],
];
use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockKey,
    BlockMetadata, BlockPart, BlockState, BlockUpdateFlags, Compound, Flow, HostBlockStates, HostSide,
    InteractionResult, LevelHost, LevelRef, LevelTicksHost, LevelWriteHost, ServerHost, Tag,
    UseItemOnEvent,
};

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let motor = registrar
        .block_entity_type("create:motor")
        .blocks(&["create:creative_motor"])
        .build();
    let kinetic = registrar
        .block_entity_type("create:simple_kinetic")
        .blocks(&[
            "create:shaft",
            "create:cogwheel",
            "create:large_cogwheel",
            "create:powered_shaft",
        ])
        .build();
    let hand_crank = registrar
        .block_entity_type("create:hand_crank")
        .blocks(&["create:hand_crank"])
        .build();
    const VALVE_HANDLE_IDS: [&str; 17] = [
        "create:copper_valve_handle",
        "create:white_valve_handle",
        "create:orange_valve_handle",
        "create:magenta_valve_handle",
        "create:light_blue_valve_handle",
        "create:yellow_valve_handle",
        "create:lime_valve_handle",
        "create:pink_valve_handle",
        "create:gray_valve_handle",
        "create:light_gray_valve_handle",
        "create:cyan_valve_handle",
        "create:purple_valve_handle",
        "create:blue_valve_handle",
        "create:brown_valve_handle",
        "create:green_valve_handle",
        "create:red_valve_handle",
        "create:black_valve_handle",
    ];
    let valve_handle = registrar
        .block_entity_type("create:valve_handle")
        .blocks(&VALVE_HANDLE_IDS)
        .build();
    let water_wheel = registrar
        .block_entity_type("create:water_wheel")
        .blocks(&["create:water_wheel"])
        .build();
    let large_water_wheel = registrar
        .block_entity_type("create:large_water_wheel")
        .blocks(&["create:large_water_wheel"])
        .build();
    let steam_engine = registrar
        .block_entity_type("create:steam_engine")
        .blocks(&["create:steam_engine"])
        .build();
    let fluid_tank = registrar
        .block_entity_type("create:fluid_tank")
        .blocks(&["create:fluid_tank", "create:creative_fluid_tank"])
        .build();
    let tank_key = registrar.block_key("create:fluid_tank");
    let creative_tank_key = registrar.block_key("create:creative_fluid_tank");
    let mut tanks = mod_api::ModFluidTanks::default();
    tanks.tanks.push(8_000);
    tanks.faces = std::array::from_fn(|_| vec![0]);
    tanks.inputs.push(0);
    tanks.outputs.push(0);
    registrar.block_fluids(&tank_key, tanks.clone());
    registrar.block_fluids(&creative_tank_key, tanks);
    let steam_whistle = registrar
        .block_entity_type("create:steam_whistle")
        .blocks(&["create:steam_whistle", "create:steam_whistle_extension"])
        .build();
    let encased_cogwheel = registrar
        .block_entity_type("create:encased_cogwheel")
        .blocks(&[
            "create:brass_encased_cogwheel",
            "create:andesite_encased_cogwheel",
        ])
        .build();
    let encased_large_cogwheel = registrar
        .block_entity_type("create:encased_large_cogwheel")
        .blocks(&[
            "create:brass_encased_large_cogwheel",
            "create:andesite_encased_large_cogwheel",
        ])
        .build();
    let encased_shaft = registrar
        .block_entity_type("create:encased_shaft")
        .blocks(&[
            "create:andesite_encased_shaft",
            "create:brass_encased_shaft",
            "create:metal_girder_encased_shaft",
            "create:encased_chain_drive",
        ])
        .build();
    let flywheel = registrar
        .block_entity_type("create:flywheel")
        .blocks(&["create:flywheel"])
        .build();
    let gearbox = registrar
        .block_entity_type("create:gearbox")
        .blocks(&["create:gearbox"])
        .build();
    let clutch = registrar
        .block_entity_type("create:clutch")
        .blocks(&["create:clutch"])
        .build();
    let gearshift = registrar
        .block_entity_type("create:gearshift")
        .blocks(&["create:gearshift"])
        .build();
    let chain_gearshift = registrar
        .block_entity_type("create:adjustable_chain_gearshift")
        .blocks(&["create:adjustable_chain_gearshift"])
        .build();
    let rim = registrar.block_key("create:water_wheel_structure");
    registrar.block_part(rim, WheelRimPart { rim });
    let part = KineticPart {
        motor: registrar.block_key("create:creative_motor"),
        shaft: registrar.block_key("create:shaft"),
        cogwheel: registrar.block_key("create:cogwheel"),
        large_cogwheel: registrar.block_key("create:large_cogwheel"),
        millstone: registrar.block_key("create:millstone"),
        flywheel: registrar.block_key("create:flywheel"),
        gearbox: registrar.block_key("create:gearbox"),
        clutch: registrar.block_key("create:clutch"),
        gearshift: registrar.block_key("create:gearshift"),
        encased_cogwheel: registrar.block_key("create:brass_encased_cogwheel"),
        encased_andesite_cogwheel: registrar.block_key("create:andesite_encased_cogwheel"),
        encased_large_cogwheel: registrar.block_key("create:brass_encased_large_cogwheel"),
        encased_andesite_large_cogwheel: registrar
            .block_key("create:andesite_encased_large_cogwheel"),
        andesite_shaft: registrar.block_key("create:andesite_encased_shaft"),
        brass_shaft: registrar.block_key("create:brass_encased_shaft"),
        girder_shaft: registrar.block_key("create:metal_girder_encased_shaft"),
        chain_drive: registrar.block_key("create:encased_chain_drive"),
        chain_gearshift: registrar.block_key("create:adjustable_chain_gearshift"),
        hand_crank: registrar.block_key("create:hand_crank"),
        valve_handles: VALVE_HANDLE_IDS.map(|id| registrar.block_key(id)),
        water_wheel: registrar.block_key("create:water_wheel"),
        large_water_wheel: registrar.block_key("create:large_water_wheel"),
        powered_shaft: registrar.block_key("create:powered_shaft"),
        steam_engine: registrar.block_key("create:steam_engine"),
        fluid_tank: registrar.block_key("create:fluid_tank"),
        creative_fluid_tank: registrar.block_key("create:creative_fluid_tank"),
        steam_whistle: registrar.block_key("create:steam_whistle"),
        steam_whistle_extension: registrar.block_key("create:steam_whistle_extension"),
        bubble_column: registrar.block_key("minecraft:bubble_column"),
        whistle_item: registrar.item_key("create:steam_whistle"),
        wrench_item: registrar.item_key("create:wrench"),
        rim,
    };
    let _ = KINETIC_PART.set(part);
    registrar.block_entity_part(&motor, part).unwrap();
    registrar.block_entity_part(&kinetic, part).unwrap();
    registrar.block_entity_part(&hand_crank, part).unwrap();
    registrar.block_entity_part(&valve_handle, part).unwrap();
    registrar.block_entity_part(&water_wheel, part).unwrap();
    registrar
        .block_entity_part(&large_water_wheel, part)
        .unwrap();
    registrar.block_entity_part(&steam_engine, part).unwrap();
    registrar.block_entity_part(&fluid_tank, part).unwrap();
    registrar.block_entity_part(&steam_whistle, part).unwrap();
    registrar
        .block_entity_part(&encased_cogwheel, part)
        .unwrap();
    registrar
        .block_entity_part(&encased_large_cogwheel, part)
        .unwrap();
    registrar.block_entity_part(&encased_shaft, part).unwrap();
    registrar.block_entity_part(&flywheel, part).unwrap();
    registrar.block_entity_part(&gearbox, part).unwrap();
    registrar.block_entity_part(&clutch, part).unwrap();
    registrar.block_entity_part(&gearshift, part).unwrap();
    registrar.block_entity_part(&chain_gearshift, part).unwrap();
}

#[derive(Clone, Copy)]
pub struct KineticPart {
    motor: BlockKey,
    shaft: BlockKey,
    cogwheel: BlockKey,
    large_cogwheel: BlockKey,
    millstone: BlockKey,
    flywheel: BlockKey,
    gearbox: BlockKey,
    clutch: BlockKey,
    gearshift: BlockKey,
    encased_cogwheel: BlockKey,
    encased_andesite_cogwheel: BlockKey,
    encased_large_cogwheel: BlockKey,
    encased_andesite_large_cogwheel: BlockKey,
    andesite_shaft: BlockKey,
    brass_shaft: BlockKey,
    girder_shaft: BlockKey,
    chain_drive: BlockKey,
    chain_gearshift: BlockKey,
    hand_crank: BlockKey,
    valve_handles: [BlockKey; 17],
    water_wheel: BlockKey,
    large_water_wheel: BlockKey,
    powered_shaft: BlockKey,
    steam_engine: BlockKey,
    fluid_tank: BlockKey,
    creative_fluid_tank: BlockKey,
    steam_whistle: BlockKey,
    steam_whistle_extension: BlockKey,
    bubble_column: BlockKey,
    whistle_item: mod_api::ItemKey,
    wrench_item: mod_api::ItemKey,
    rim: BlockKey,
}

#[derive(Clone, Copy)]
struct WheelRimPart {
    rim: BlockKey,
}

#[mod_api::horizon_part]
impl BlockPart for WheelRimPart {
    fn neighbor_changed(
        &self,
        level: &mut dyn LevelTicksHost,
        event: &mut mod_api::NeighborChangedEvent,
    ) {
        if level.state_block(event.state) == Some("create:water_wheel_structure") {
            let _ = level.schedule_block_tick([event.pos.x, event.pos.y, event.pos.z], self.rim, 1);
        }
    }

    fn tick_block(
        &self,
        level: &mut dyn LevelWriteHost,
        event: &mut mod_api::TickBlockEvent,
    ) -> Flow {
        if level.state_block(event.state) != Some("create:water_wheel_structure") {
            return Flow::Continue;
        }
        let pos = [event.pos.x, event.pos.y, event.pos.z];
        let supported = wheel_rim_supported(level, pos);
        if !supported {
            for dx in -1..=1 {
                for dy in -1..=1 {
                    for dz in -1..=1 {
                        let orphan = [pos[0] + dx, pos[1] + dy, pos[2] + dz];
                        if level.block_state(orphan)
                            .and_then(|state| level.state_block(state))
                            == Some("create:water_wheel_structure")
                        {
                            let _ = level.remove_block(orphan, false);
                        }
                    }
                }
            }
            return Flow::Cancel;
        }
        Flow::Continue
    }
}

impl KineticPart {
    /// Apply a motor board selection from the server-side interaction adapter.
    /// The selected speed is saved on the motor and the connected graph is
    /// updated immediately; later ticks keep it in sync with block changes.
    pub fn set_motor_setting(
        &self,
        host: &mut dyn ServerHost,
        level: LevelRef,
        pos: [i32; 3],
        setting: i32,
    ) -> bool {
        if !matches!(node(host, level, pos, *self), Some(Node::Motor { .. })) {
            return false;
        }
        let Some(entity) = host.block_entity_identity(level, pos) else {
            return false;
        };
        let Some(mut data) = entity.data(host) else {
            return false;
        };
        let value = setting.clamp(-256, 256);
        if scroll_value(&data) == value {
            return false;
        }
        data.insert("ScrollValue".into(), Tag::Int(value));
        if let Some(dimension) = level.dimension().id(host) {
            data.insert(
                "KineticDimension".into(),
                Tag::String(dimension.as_str().into()),
            );
        }
        let _ = entity.merge_data(host, data.clone());
        let graph = network(host, level, pos, Some(&data), *self);
        apply_speeds(host, level, graph, *self);
        true
    }
}

/// Entry point for the motor settings interaction. Call on the authoritative
/// server with the level and position from the interaction event.
pub fn set_motor_setting(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    setting: i32,
) -> bool {
    match KINETIC_PART.get() {
        Some(part) => part.set_motor_setting(host, level, pos, setting),
        None => false,
    }
}

#[mod_api::horizon_part]
impl BlockPart for KineticPart {
    fn use_item_on(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseItemOnEvent<'_>,
    ) -> Option<InteractionResult> {
        let click = event.click;
        let player = host.player(click.player)?;
        let level = player.level(host)?;
        let block = level.block(host, click.pos)?;
        if click.hand != mod_api::Hand::Main {
            return (block == self.hand_crank
                || self.valve_handles.contains(&block)
                || block == self.fluid_tank
                || block == self.creative_fluid_tank
                || block == self.steam_whistle
                || block == self.steam_whistle_extension)
                .then_some(InteractionResult::Success);
        }
        if block == self.fluid_tank || block == self.creative_fluid_tank {
            return mod_api::fluid_util::interact_with_fluid_handler(
                host,
                player,
                click.hand,
                level,
                click.pos,
                None,
            )
            .then_some(InteractionResult::Success);
        }
        if (block == self.steam_whistle || block == self.steam_whistle_extension)
            && let Some(stack) = click.stack
        {
            if stack.item() == self.whistle_item {
                grow_whistle(host, level, click.pos, *self);
                return Some(InteractionResult::Success);
            }
            if stack.item() == self.wrench_item {
                cycle_whistle_size(host, level, click.pos, *self);
                return Some(InteractionResult::Success);
            }
        }
        if block == self.steam_engine
            && click.stack.is_some_and(|stack| stack.item() == self.wrench_item)
        {
            let entity = host.block_entity_identity(level, click.pos)?;
            let mut data = entity.data(host)?;
            let reverse = int(&data, "ScrollValue") != Some(1);
            data.insert("ScrollValue".into(), Tag::Int(i32::from(reverse)));
            let _ = entity.merge_data(host, data.clone());
            let graph = network(host, level, click.pos, Some(&data), *self);
            apply_speeds(host, level, graph, *self);
            return Some(InteractionResult::Success);
        }
        if block != self.hand_crank && !self.valve_handles.contains(&block) {
            return None;
        }
        let entity = host.block_entity_identity(level, click.pos)?;
        let mut data = entity.data(host)?;
        let backwards = player.entity().is_shift_key_down(host).unwrap_or(false);
        if block == self.hand_crank {
            data.insert("InUse".into(), Tag::Int(10));
            data.insert("Backwards".into(), Tag::Byte(i8::from(backwards)));
        } else {
            let remaining = int(&data, "InUse").unwrap_or(0);
            let cooldown = int(&data, "Cooldown").unwrap_or(0);
            if remaining > 0 || cooldown > 0 {
                return Some(InteractionResult::Success);
            }
            let configured = int(&data, "ScrollValue").unwrap_or(45).clamp(-180, 180);
            let degrees = configured.unsigned_abs() as f32;
            let ticks = (degrees / (32.0 * 0.3)).ceil() as i32 + 2;
            let target = if degrees > 135.0 { 180 } else { 90 } * configured.signum();
            let start = int(&data, "TargetAngle").unwrap_or(0).rem_euclid(90);
            data.insert("StartAngle".into(), Tag::Int(start));
            data.insert("TargetAngle".into(), Tag::Int(start + target));
            data.insert("InUse".into(), Tag::Int(ticks));
            data.insert("TotalUseTicks".into(), Tag::Int(ticks));
            data.insert("Backwards".into(), Tag::Byte(i8::from(backwards)));
            data.insert("Cooldown".into(), Tag::Int(4));
        }
        let _ = entity.merge_data(host, data.clone());
        let graph = network(host, level, click.pos, Some(&data), *self);
        apply_speeds(host, level, graph, *self);
        Some(InteractionResult::Success)
    }

    fn state_for_placement(
        &self,
        host: &dyn LevelHost,
        event: &mut mod_api::StateForPlacementEvent<'_>,
    ) -> Option<Option<BlockState>> {
        let context = &event.context;
        match host.state_block(event.state)? {
            "create:water_wheel" => {
                return Some(host.state_with_property(
                    event.state,
                    "facing",
                    direction_name(context.face),
                ));
            }
            "create:large_water_wheel" => {
                let axis = axis_of(context.face.normal())?;
                let center = [context.pos.x, context.pos.y, context.pos.z];
                if wheel_rim_parts(axis).into_iter().any(|(offset, _)| {
                    let at = add3(center, offset);
                    !matches!(
                        host.block_state(at).and_then(|state| host.state_block(state)),
                        Some("minecraft:air" | "minecraft:cave_air" | "minecraft:void_air" | "minecraft:water" | "create:water_wheel_structure")
                    )
                }) {
                    return Some(None);
                }
                return Some(host.state_with_property(event.state, "axis", ["x", "y", "z"][axis]));
            }
            "create:steam_engine" => {
                let normal = context.face.normal();
                let face = if normal == [0, 1, 0] {
                    "floor"
                } else if normal == [0, -1, 0] {
                    "ceiling"
                } else {
                    "wall"
                };
                let facing = if face == "wall" {
                    direction_name(context.face)
                } else {
                    let rotation = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32)
                        .rem_euclid(4) as usize;
                    ["south", "west", "north", "east"][rotation]
                };
                let Some(state) = host.state_with_property(event.state, "face", face) else {
                    return Some(None);
                };
                return Some(host.state_with_property(state, "facing", facing));
            }
            "create:steam_whistle" => {
                let normal = context.face.normal();
                let wall = normal != [0, 1, 0] && normal != [0, -1, 0];
                let support = if wall { normal.map(|n| -n) } else { [0, -1, 0] };
                let tank_pos = [context.pos.x + support[0], context.pos.y + support[1], context.pos.z + support[2]];
                let Some(tank_state) = host.block_state(tank_pos) else {
                    return Some(None);
                };
                if !matches!(host.state_block(tank_state), Some("create:fluid_tank" | "create:creative_fluid_tank")) {
                    return Some(None);
                }
                let facing = if wall {
                    direction_name(context.face.opposite())
                } else {
                    let rotation = ((f64::from(context.yaw) / 90.0 + 0.5).floor() as i32)
                        .rem_euclid(4) as usize;
                    ["south", "west", "north", "east"]
                        [rotation]
                };
                let Some(state) = host.state_with_property(event.state, "facing", facing) else {
                    return Some(None);
                };
                return Some(host.state_with_property(state, "wall", if wall { "true" } else { "false" }));
            }
            "create:creative_motor" => {}
            _ => return None,
        }
        let yaw = f64::from(context.yaw).to_radians();
        let pitch = f64::from(context.pitch).to_radians();
        let look = [
            -yaw.sin() * pitch.cos(),
            -pitch.sin(),
            yaw.cos() * pitch.cos(),
        ];
        let axis = (0..3).max_by(|&a, &b| look[a].abs().total_cmp(&look[b].abs()))?;
        let looking = match (axis, look[axis].is_sign_positive()) {
            (0, true) => "east",
            (0, false) => "west",
            (1, true) => "up",
            (1, false) => "down",
            (2, true) => "south",
            _ => "north",
        };
        let mut facing = if context.sneaking {
            looking
        } else {
            opposite(looking)
        };
        if !context.sneaking && axis != 1 {
            let p = context.pos;
            let has_x_shaft = [p.x - 1, p.x + 1].into_iter().any(|x| {
                host.block_state([x, p.y, p.z])
                    .and_then(|state| host.state_block(state))
                    == Some("create:shaft")
            });
            if has_x_shaft {
                facing = "east";
            }
        }
        Some(host.state_with_property(event.state, "facing", facing))
    }

    fn neighbor_changed(
        &self,
        level: &mut dyn LevelTicksHost,
        event: &mut mod_api::NeighborChangedEvent,
    ) {
        if matches!(level.state_block(event.state), Some("create:steam_whistle" | "create:steam_whistle_extension")) {
            let pos = [event.pos.x, event.pos.y, event.pos.z];
            let block = if level.state_block(event.state) == Some("create:steam_whistle") {
                self.steam_whistle
            } else {
                self.steam_whistle_extension
            };
            let _ = level.schedule_block_tick(pos, block, 1);
        }
    }

    fn tick_block(
        &self,
        level: &mut dyn LevelWriteHost,
        event: &mut mod_api::TickBlockEvent,
    ) -> Flow {
        let pos = [event.pos.x, event.pos.y, event.pos.z];
        match level.state_block(event.state) {
            Some("create:steam_whistle") => {
                let state_name = level.state_string(event.state).unwrap_or_default();
                let wall = serialized_property(&state_name, "wall") == Some("true");
                let support = if wall {
                    direction_normal(serialized_property(&state_name, "facing").unwrap_or("north")).unwrap_or([0, 0, 1])
                } else { [0, -1, 0] };
                let tank = add3(pos, support);
                let supported = level.block_state(tank)
                    .and_then(|state| level.state_block(state))
                    .is_some_and(|block| matches!(block, "create:fluid_tank" | "create:creative_fluid_tank"));
                if !supported {
                    let _ = level.remove_block(pos, false);
                    return Flow::Cancel;
                }
                let powered = level.has_neighbor_signal(pos);
                let desired = if powered { "true" } else { "false" };
                if let Some(state) = level.state_with_property(event.state, "powered", desired)
                    && state != event.state
                {
                    let _ = level.set_block(pos, state, BlockUpdateFlags::CLIENTS);
                }
            }
            Some("create:steam_whistle_extension") => {
                let parent = level.block_state([pos[0], pos[1] - 1, pos[2]])
                    .and_then(|state| level.state_block(state));
                if !matches!(parent, Some("create:steam_whistle" | "create:steam_whistle_extension")) {
                    let _ = level.remove_block(pos, false);
                    return Flow::Cancel;
                }
            }
            _ => return Flow::Continue,
        }
        Flow::Continue
    }
}

fn opposite(direction: &str) -> &'static str {
    match direction {
        "east" => "west",
        "west" => "east",
        "up" => "down",
        "down" => "up",
        "south" => "north",
        _ => "south",
    }
}

fn direction_name(direction: mod_api::Direction) -> &'static str {
    match direction {
        mod_api::Direction::East => "east",
        mod_api::Direction::West => "west",
        mod_api::Direction::Up => "up",
        mod_api::Direction::Down => "down",
        mod_api::Direction::South => "south",
        mod_api::Direction::North => "north",
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for KineticPart {
    fn block_entity_update_tag(
        &self,
        event: &mut mod_api::BlockEntityUpdateTagEvent<'_>,
    ) -> Option<Compound> {
        Some(event.entity.nbt.clone())
    }

    fn block_entity_submit(
        &self,
        host: &dyn mod_api::ClientHost,
        event: &mut mod_api::BlockEntitySubmitEvent<'_>,
    ) {
        if event.block != "create:creative_motor" {
            return;
        }
        let metadata = host.block_states();
        let Ok(Some(facing)) = event.state.property(&metadata, "facing") else {
            return;
        };
        let (axis, direction) = match facing {
            "east" => (0, 1),
            "west" => (0, -1),
            "up" => (1, 1),
            "down" => (1, -1),
            "south" => (2, 1),
            "north" => (2, -1),
            _ => return,
        };
        let rpm = ["VisualSpeed", "MotorGeneratedSpeed", "Speed"]
            .into_iter()
            .find_map(|key| match event.entity.nbt.get(&key.into()) {
                Some(Tag::Float(value)) => Some(f32::from_bits(*value)),
                _ => None,
            })
            .unwrap_or(0.0);
        let [x, y, z] = event.pos;
        let coordinates = [x, y, z];
        let parity = coordinates[(axis + 1) % 3].wrapping_add(coordinates[(axis + 2) % 3]);
        let phase = if parity % 2 == 0 { 22.5 } else { 0.0 };
        let angle = (((event.draw.game_time() as f64 + f64::from(event.draw.partial()))
            * f64::from(rpm)
            * 0.3
            + f64::from(phase))
            % 360.0) as f32;
        let mut axis_vector = [0.0; 3];
        axis_vector[axis] = 1.0;
        let Some(shaft) = host.block_key("create:shaft") else {
            return;
        };
        event.draw.push();
        event.draw.spin(axis_vector, [0.5; 3], rpm * 0.3, phase);
        let mut offset = [0.375; 3];
        offset[axis] = if direction > 0 { 0.5 } else { 0.0 };
        let mut scale = [0.25; 3];
        scale[axis] = 0.5;
        event.draw.translate(offset);
        event.draw.scale(scale);
        let drawn = event.draw.block(shaft, &[("axis", ["x", "y", "z"][axis])]);
        event.draw.still();
        event.draw.pop();
        if std::env::var_os("CREATE_MOTOR_RENDER").is_some() {
            println!(
                "CREATE_MOTOR_FRAME {x},{y},{z},{facing},{axis},{direction},{},{:.8},{phase:.4},{rpm:.6},{angle:.8},{}",
                event.draw.game_time(),
                event.draw.partial(),
                if drawn { 24 } else { 0 }
            );
        }
    }

    fn block_entity_on_load(&self, side: HostSide<'_>, event: &mut BlockEntityOnLoadEvent) {
        let HostSide::Server(host) = side else { return };
        let Some(pos) = event.entity.position(host) else {
            return;
        };
        let Some(level) = event.entity.level(host) else {
            return;
        };
        if level.block(host, pos) == Some(self.large_water_wheel)
            && level
                .block_property(host, pos, "axis")
                .as_deref()
                .and_then(kinetic_slice::axis_index)
                .is_some()
        {
            form_large_wheel(host, level, pos, *self);
        }
        let Some(mut data) = event.entity.data(host) else {
            return;
        };
        let mut changed = false;
        if let Some(dimension) = level.dimension().id(host) {
            if data.get(&"KineticDimension".into()) != Some(&Tag::String(dimension.as_str().into()))
            {
                data.insert(
                    "KineticDimension".into(),
                    Tag::String(dimension.as_str().into()),
                );
                changed = true;
            }
        }
        if node(host, level, pos, *self).is_some_and(|n| matches!(n, Node::Motor { .. }))
            && !data.contains_key(&"ScrollValue".into())
        {
            data.insert("ScrollValue".into(), Tag::Int(16));
            changed = true;
        }
        if changed {
            let _ = event.entity.merge_data(host, data.clone());
        }
        let graph = network(host, level, pos, Some(&data), *self);
        if graph.get(&pos).is_some_and(|state| state.source_conflict) {
            // Match Java's kinetic join behavior: the newly added bridge is
            // destroyed with its ordinary drops, then adjacent networks settle
            // independently on their next server tick.
            let _ = level.destroy_block(host, pos, true, None, false);
            return;
        }
        apply_speeds(host, level, graph, *self);
    }

    fn block_entity_ticks(&self, _: &dyn mod_api::Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let dimension = match event.entity.nbt.get(&"KineticDimension".into()) {
            Some(Tag::String(value)) => value.to_string_lossy(),
            _ => String::new(),
        };
        let level = (!dimension.is_empty())
            .then(|| host.level(&dimension))
            .flatten()
            .or_else(|| {
                host.levels()
                    .list_levels()
                    .into_iter()
                    .find(|level| node(host, *level, event.pos, *self).is_some())
            });
        let Some(level) = level else {
            return;
        };
        if level.block(host, event.pos) == Some(self.large_water_wheel) {
            form_large_wheel(host, level, event.pos, *self);
        }
        if let Some(block) = level.block(host, event.pos) {
            if node(host, level, event.pos, *self)
                .is_some_and(|node| matches!(node, Node::Generator { .. }))
            {
                if block == self.hand_crank || self.valve_handles.contains(&block) {
                    let remaining = int(&event.entity.nbt, "InUse").unwrap_or(0);
                    if remaining > 0 {
                        event.entity.nbt.insert("InUse".into(), Tag::Int(remaining - 1));
                    }
                    if self.valve_handles.contains(&block) && remaining <= 1 {
                        let cooldown = int(&event.entity.nbt, "Cooldown").unwrap_or(0);
                        if cooldown > 0 {
                            event.entity.nbt.insert("Cooldown".into(), Tag::Int(cooldown - 1));
                        }
                    }
                }
                if block == self.water_wheel || block == self.large_water_wheel {
                    if let Some(Node::Generator { shaft_axis, .. }) = node(host, level, event.pos, *self) {
                        let score = water_flow_score(
                            host,
                            level,
                            event.pos,
                            shaft_axis,
                            block == self.large_water_wheel,
                            *self,
                        );
                        event.entity.nbt.insert("FlowScore".into(), Tag::Int(score));
                    }
                }
            }
            if block == self.fluid_tank || block == self.creative_fluid_tank {
                let _ = tick_boiler(host, level, event.pos, &mut event.entity.nbt, *self);
            }
            if block == self.steam_whistle || block == self.steam_whistle_extension {
                tick_whistle(host, level, event.pos, &mut event.entity.nbt, *self);
            }
        }
        let graph = network(host, level, event.pos, Some(&event.entity.nbt), *self);
        if graph.is_empty() {
            return;
        }
        for (pos, state) in graph {
            let generated_speed = if pos == event.pos {
                motor_generated_speed(host, level, pos, Some(&event.entity.nbt), *self)
            } else {
                motor_generated_speed(host, level, pos, None, *self)
            };
            if pos == event.pos {
                persist_network(&mut event.entity.nbt, state, generated_speed);
            } else if let Some(entity) = host.block_entity_identity(level, pos) {
                let mut data = Compound::new();
                persist_network(&mut data, state, generated_speed);
                let _ = entity.merge_data(host, data);
            }
        }
    }
}

fn apply_speeds(
    host: &mut dyn ServerHost,
    level: LevelRef,
    graph: HashMap<[i32; 3], kinetic_slice::Network>,
    part: KineticPart,
) {
    for (pos, state) in graph {
        let Some(entity) = host.block_entity_identity(level, pos) else {
            continue;
        };
        let mut data = Compound::new();
        let generated_speed = motor_generated_speed(host, level, pos, None, part);
        persist_network(&mut data, state, generated_speed);
        let _ = entity.merge_data(host, data);
    }
}

fn motor_generated_speed(
    host: &dyn mod_api::Host,
    level: LevelRef,
    pos: [i32; 3],
    current_data: Option<&Compound>,
    part: KineticPart,
) -> Option<f32> {
    let Node::Motor { facing } = node(host, level, pos, part)? else {
        return None;
    };
    let data = current_data
        .cloned()
        .or_else(|| host.block_entity(level, pos)?.data(host))?;
    Some(kinetic_slice::motor_speed(facing, scroll_value(&data)))
}

fn persist_network(
    data: &mut Compound,
    state: kinetic_slice::Network,
    motor_generated_speed: Option<f32>,
) {
    data.insert("Speed".into(), Tag::Float(state.speed().to_bits()));
    if let Some(motor_generated_speed) = motor_generated_speed {
        data.insert(
            "MotorGeneratedSpeed".into(),
            Tag::Float(motor_generated_speed.to_bits()),
        );
    }
    let mut saved = match data.get(&"Network".into()) {
        Some(Tag::Compound(saved)) => saved.clone(),
        _ => Compound::new(),
    };
    saved.insert("Capacity".into(), Tag::Float(state.capacity.to_bits()));
    saved.insert("Stress".into(), Tag::Float(state.stress.to_bits()));
    data.insert("Network".into(), Tag::Compound(saved));
}

fn node(
    host: &dyn mod_api::Host,
    level: LevelRef,
    pos: [i32; 3],
    part: KineticPart,
) -> Option<Node> {
    let block = level.block(host, pos)?;
    if block == part.motor {
        let facing = level.block_property(host, pos, "facing")?;
        let normal = match facing.as_str() {
            "east" => [1, 0, 0],
            "west" => [-1, 0, 0],
            "up" => [0, 1, 0],
            "down" => [0, -1, 0],
            "south" => [0, 0, 1],
            "north" => [0, 0, -1],
            _ => return None,
        };
        return Some(Node::Motor { facing: normal });
    }
    if block == part.hand_crank || part.valve_handles.contains(&block) {
        let facing = direction_normal(&level.block_property(host, pos, "facing")?)?;
        let shaft_face = facing.map(|component| -component);
        let shaft_axis = axis_of(facing)?;
        return Some(Node::Generator {
            shaft_axis,
            shaft_face: Some(shaft_face),
        });
    }
    if block == part.water_wheel {
        let facing = direction_normal(&level.block_property(host, pos, "facing")?)?;
        return Some(Node::Generator {
            shaft_axis: axis_of(facing)?,
            shaft_face: None,
        });
    }
    if block == part.large_water_wheel || block == part.powered_shaft {
        return Some(Node::Generator {
            shaft_axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            shaft_face: None,
        });
    }
    if block == part.shaft {
        return Some(Node::Shaft {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
        });
    }
    if block == part.cogwheel || block == part.large_cogwheel {
        return Some(Node::Cogwheel {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            large: block == part.large_cogwheel,
        });
    }
    if block == part.encased_cogwheel
        || block == part.encased_andesite_cogwheel
        || block == part.encased_large_cogwheel
        || block == part.encased_andesite_large_cogwheel
    {
        return Some(Node::EncasedCogwheel {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            large: block == part.encased_large_cogwheel
                || block == part.encased_andesite_large_cogwheel,
            top_shaft: level.block_property(host, pos, "top_shaft")? == "true",
            bottom_shaft: level.block_property(host, pos, "bottom_shaft")? == "true",
        });
    }
    if block == part.andesite_shaft || block == part.brass_shaft || block == part.girder_shaft {
        return Some(Node::Shaft {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
        });
    }
    if block == part.millstone {
        return Some(Node::Millstone);
    }
    if block == part.flywheel {
        return Some(Node::Flywheel {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
        });
    }
    if block == part.gearbox {
        return Some(Node::Gearbox {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
        });
    }
    if block == part.clutch {
        return Some(Node::Clutch {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            powered: level.block_property(host, pos, "powered")? == "true",
        });
    }
    if block == part.gearshift {
        return Some(Node::Gearshift {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            powered: level.block_property(host, pos, "powered")? == "true",
        });
    }
    if block == part.chain_drive || block == part.chain_gearshift {
        let shaft_axis = kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?;
        let first = level.block_property(host, pos, "axis_along_first")? == "true";
        let link_axis = [0, 1, 2]
            .into_iter()
            .filter(|candidate| *candidate != shaft_axis)
            .nth(usize::from(!first))?;
        let part = match level.block_property(host, pos, "part")?.as_str() {
            "start" => 1,
            "middle" => 0,
            "end" => -1,
            _ => 2,
        };
        let signal = host
            .block_entity(level, pos)
            .and_then(|entity| entity.data(host))
            .and_then(|data| match data.get(&"Signal".into()) {
                Some(Tag::Int(value)) => Some(*value),
                _ => None,
            })
            .unwrap_or(0)
            .clamp(0, 15);
        let modifier = if signal == 0 {
            1.0
        } else {
            1.0 + (signal + 1) as f32 / 16.0
        };
        return Some(Node::ChainDrive {
            shaft_axis,
            link_axis,
            part,
            modifier,
        });
    }
    None
}

fn network(
    host: &mut dyn ServerHost,
    level: LevelRef,
    start: [i32; 3],
    current_data: Option<&Compound>,
    part: KineticPart,
) -> HashMap<[i32; 3], kinetic_slice::Network> {
    let Some(start_node) = node(host, level, start, part) else {
        return HashMap::new();
    };
    let mut ratios = HashMap::from([(start, 1.0f32)]);
    let mut pending = VecDeque::from([(start, start_node, [0; 3])]);
    let mut order = Vec::new();
    let mut topology_conflict = false;
    while let Some((pos, block, entered)) = pending.pop_front() {
        order.push(pos);
        let ratio = ratios[&pos];
        for delta in block.neighbors() {
            let next = [pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2]];
            let Some(other) = node(host, level, next, part) else {
                continue;
            };
            let Some(edge) = block.ratio_to(other, delta) else {
                continue;
            };
            if edge == 0.0 {
                continue;
            }
            let direction = block.direction_ratio(entered, delta);
            if direction == 0.0 {
                continue;
            }
            let next_ratio = ratio * direction / edge;
            if let Some(previous_ratio) = ratios.get(&next).copied() {
                topology_conflict |=
                    kinetic_slice::inconsistent_loop_ratio(next_ratio, previous_ratio);
                continue;
            }
            ratios.insert(next, next_ratio);
            pending.push_back((next, other, delta.map(|value| -value)));
        }
    }
    let mut sources = Vec::new();
    let mut impact_per_rpm = 0.0;
    for pos in order {
        let ratio = ratios[&pos];
        let Some(block) = node(host, level, pos, part) else {
            continue;
        };
        if matches!(block, Node::Millstone) {
            impact_per_rpm += 4.0 / ratio.abs();
        }
        let data = if pos == start {
            current_data.cloned()
        } else {
            host.block_entity(level, pos)
                .and_then(|entity| entity.data(host))
        };
        let Some(data) = data else { continue };
        let source = match block {
            Node::Motor { facing } => Some(kinetic_slice::motor_source(
                kinetic_slice::motor_speed(facing, scroll_value(&data)),
            )),
            Node::Generator { .. } => source_output(host, level, pos, &data, block, part),
            _ => None,
        };
        let Some(mut source) = source else { continue };
        source.speed *= ratio;
        sources.push(source);
    }
    let resolved = kinetic_slice::resolve_network(&sources, impact_per_rpm);
    ratios
        .into_iter()
        .map(|(pos, ratio)| {
            let mut state = resolved;
            state.rpm /= ratio;
            state.topology_conflict = topology_conflict;
            (pos, state)
        })
        .collect()
}

fn scroll_value(data: &Compound) -> i32 {
    match data.get(&"ScrollValue".into()) {
        Some(Tag::Int(value)) => *value,
        _ => 16,
    }
}

fn direction_normal(direction: &str) -> Option<[i32; 3]> {
    Some(match direction {
        "east" => [1, 0, 0],
        "west" => [-1, 0, 0],
        "up" => [0, 1, 0],
        "down" => [0, -1, 0],
        "south" => [0, 0, 1],
        "north" => [0, 0, -1],
        _ => return None,
    })
}

fn serialized_property<'a>(state: &'a str, property: &str) -> Option<&'a str> {
    state
        .split_once('[')?
        .1
        .trim_end_matches(']')
        .split(',')
        .find_map(|pair| {
            pair.split_once('=')
                .filter(|(name, _)| *name == property)
                .map(|(_, value)| value)
        })
}

fn axis_of(direction: [i32; 3]) -> Option<usize> {
    direction.iter().position(|component| *component != 0)
}

fn source_output(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    data: &Compound,
    source_node: Node,
    part: KineticPart,
) -> Option<kinetic_slice::Source> {
    let block = level.block(host, pos)?;
    let face = node_direction(source_node, level, host, pos)?;
    let output = if block == part.hand_crank {
        super::power_sources::hand_crank(
            face,
            int(data, "InUse").unwrap_or(0),
            int(data, "Backwards") == Some(1),
        )
    } else if part.valve_handles.contains(&block) {
        if let Some(rpm) = float(data, "RecolorDrive") {
            let shaft_face = match source_node {
                Node::Generator { shaft_face, .. } => shaft_face?,
                _ => return None,
            };
            let rear = [
                pos[0] + shaft_face[0],
                pos[1] + shaft_face[1],
                pos[2] + shaft_face[2],
            ];
            super::power_sources::recolored_valve_handle(
                node(host, level, rear, part).is_some(),
                rpm,
            )
        } else {
            super::power_sources::valve_handle(
                face,
                int(data, "InUse").unwrap_or(0),
                int(data, "Backwards") == Some(1),
                scroll_value(data),
            )
        }
    } else if block == part.water_wheel || block == part.large_water_wheel {
        super::power_sources::water_wheel(
            int(data, "FlowScore").unwrap_or(0),
            block == part.large_water_wheel,
        )
    } else if block == part.powered_shaft {
        steam_shaft_output(host, level, pos, source_node, part)?
    } else {
        return None;
    };
    Some(kinetic_slice::Source {
        speed: output.rpm,
        capacity: output.capacity,
    })
}

fn water_flow_score(
    host: &dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    axis: usize,
    large: bool,
    part: KineticPart,
) -> i32 {
    let arms = if large {
        const DIRECTIONS: [[i32; 3]; 6] = [
            [0, -1, 0], [0, 1, 0], [0, 0, -1], [0, 0, 1], [-1, 0, 0], [1, 0, 0],
        ];
        DIRECTIONS
            .into_iter()
            .filter(move |arm| arm[axis] == 0)
            .flat_map(move |arm| {
                let mut side = [0; 3];
                side[(axis + 1) % 3] = arm[(axis + 2) % 3];
                side[(axis + 2) % 3] = -arm[(axis + 1) % 3];
                let middle = arm.map(|component| component * 2);
                [middle, add3(middle, side), add3(middle, side.map(|value| -value))]
            })
            .collect::<Vec<_>>()
    } else {
        (0..3)
            .filter(|&candidate| candidate != axis)
            .flat_map(|transverse| [-1, 1].map(move |sign| {
                let mut arm = [0; 3];
                arm[transverse] = sign;
                arm
            }))
            .collect::<Vec<_>>()
    };
    let next_axis = (axis + 1) % 3;
    let last_axis = (axis + 2) % 3;
    arms.into_iter()
        .map(|arm| {
            let at = add3(pos, arm);
            let mut flow = level
                .fluid_flow(host, at)
                .map(|flow| [flow.x, flow.y, flow.z])
                .unwrap_or([0.0; 3]);
            if level.block(host, at) == Some(part.bubble_column) {
                let drags_down = level.block_property(host, at, "drag").as_deref() == Some("true");
                flow = [0.0, if drags_down { -1.0 } else { 1.0 }, 0.0];
            }
            let length = flow[next_axis].hypot(flow[last_axis]);
            let arm_length = (arm[next_axis] as f64).hypot(arm[last_axis] as f64);
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

fn add3(left: [i32; 3], right: [i32; 3]) -> [i32; 3] {
    [left[0] + right[0], left[1] + right[1], left[2] + right[2]]
}

fn wheel_rim_parts(axis: usize) -> Vec<([i32; 3], &'static str)> {
    DIRECTIONS
        .into_iter()
        .filter(|arm| arm[axis] == 0)
        .flat_map(|arm| {
            let a = (axis + 1) % 3;
            let b = (axis + 2) % 3;
            let mut clockwise = [0; 3];
            clockwise[a] = arm[b];
            clockwise[b] = -arm[a];
            [([0; 3], arm), (arm, clockwise)].map(|(start, step)| {
                let reverse = step.map(|value| -value);
                let direction = DIRECTIONS.iter().position(|dir| *dir == reverse).unwrap();
                (add3(start, step), ["down", "up", "north", "south", "west", "east"][direction])
            })
        })
        .collect()
}

fn wheel_rim_supported(level: &dyn LevelHost, pos: [i32; 3]) -> bool {
    for dx in -1..=1 {
        for dy in -1..=1 {
            for dz in -1..=1 {
                let center = [pos[0] + dx, pos[1] + dy, pos[2] + dz];
                let Some(state) = level.block_state(center) else { continue; };
                if level.state_block(state) == Some("create:large_water_wheel") { return true; }
            }
        }
    }
    false
}

fn form_large_wheel(host: &mut dyn ServerHost, level: LevelRef, pos: [i32; 3], part: KineticPart) {
    let Some(axis) = level.block_property(host, pos, "axis").as_deref().and_then(kinetic_slice::axis_index) else { return; };
    let air = host.block_key("minecraft:air");
    let water = host.block_key("minecraft:water");
    let ring = wheel_rim_parts(axis);
    let obstructed = ring.iter().any(|(offset, _)| {
        let block = level.block(host, add3(pos, *offset));
        block != air && block != water && block != Some(part.rim)
    });
    if obstructed {
        let _ = level.destroy_block(host, pos, true, None, false);
        return;
    }
    for (offset, facing) in ring {
        let at = add3(pos, offset);
        if level.block(host, at) == Some(part.rim) { continue; }
        let Ok(state) = BlockState::of(
            &host.block_states(), part.rim,
            &[mod_api::StateConstraint::new("facing", facing)],
        ) else {
            let _ = level.destroy_block(host, pos, true, None, false);
            return;
        };
        if !matches!(level.set_block(
            host,
            at,
            state,
            BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
        ), Ok(true)) {
            let _ = level.destroy_block(host, pos, true, None, false);
            return;
        }
    }
}

fn whistle_root(
    host: &dyn mod_api::Host,
    level: LevelRef,
    mut pos: [i32; 3],
    part: KineticPart,
) -> Option<[i32; 3]> {
    for _ in 0..=6 {
        match level.block(host, pos) {
            Some(block) if block == part.steam_whistle => return Some(pos),
            Some(block) if block == part.steam_whistle_extension => pos[1] -= 1,
            _ => return None,
        }
    }
    None
}

fn grow_whistle(host: &mut dyn ServerHost, level: LevelRef, clicked: [i32; 3], part: KineticPart) {
    let Some(root) = whistle_root(host, level, clicked, part) else { return; };
    let size = level.block_property(host, root, "size").unwrap_or_else(|| "medium".into());
    let air = host.block_key("minecraft:air");
    for y in 1..=6 {
        let at = [root[0], root[1] + y, root[2]];
        if level.block(host, at) == Some(part.steam_whistle_extension) {
            if level.block_property(host, at, "shape").as_deref() == Some("single") {
                let _ = host.set_block_property(at, "shape", "double");
                break;
            }
            continue;
        }
        if level.block(host, at) != air { break; }
        let Ok(state) = BlockState::of(
            &host.block_states(),
            part.steam_whistle_extension,
            &[
                mod_api::StateConstraint::new("size", size.as_str()),
                mod_api::StateConstraint::new("shape", "single"),
            ],
        ) else { break; };
        let flags = BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS;
        if !matches!(level.set_block(host, at, state, flags), Ok(true)) { break; }
        if y > 1 {
            let _ = host.set_block_property([at[0], at[1] - 1, at[2]], "shape", "double_connected");
        }
        break;
    }
}

fn cycle_whistle_size(host: &mut dyn ServerHost, level: LevelRef, clicked: [i32; 3], part: KineticPart) {
    let Some(root) = whistle_root(host, level, clicked, part) else { return; };
    let next = match level.block_property(host, root, "size").as_deref() {
        Some("small") => "medium",
        Some("medium") => "large",
        _ => "small",
    };
    let _ = host.set_block_property(root, "size", next);
    for y in 1..=6 {
        let at = [root[0], root[1] + y, root[2]];
        if level.block(host, at) != Some(part.steam_whistle_extension) { break; }
        let _ = host.set_block_property(at, "size", next);
    }
}

fn node_direction(
    source_node: Node,
    level: LevelRef,
    host: &dyn mod_api::Host,
    pos: [i32; 3],
) -> Option<[i32; 3]> {
    if !matches!(
        source_node,
        Node::Generator {
            shaft_face: Some(_),
            ..
        }
    ) {
        return Some([0, 0, 0]);
    }
    direction_normal(&level.block_property(host, pos, "facing")?)
}

fn int(data: &Compound, key: &str) -> Option<i32> {
    match data.get(&key.into()) {
        Some(Tag::Int(value)) => Some(*value),
        Some(Tag::Byte(value)) => Some(i32::from(*value)),
        _ => None,
    }
}

fn float(data: &Compound, key: &str) -> Option<f32> {
    match data.get(&key.into()) {
        Some(Tag::Float(value)) => Some(f32::from_bits(*value)),
        _ => None,
    }
}

fn stored_water(data: &Compound) -> u32 {
    let stacks = match data.get(&"fluids".into()) {
        Some(Tag::List(stacks)) => stacks,
        Some(Tag::Compound(fluids)) => match fluids.get(&"stacks".into()) {
            Some(Tag::List(stacks)) => stacks,
            _ => return 0,
        },
        _ => return 0,
    };
    stacks
        .iter()
        .filter_map(|stack| match stack {
            Tag::Compound(stack) if fluid_stack_is_water(stack) => fluid_stack_amount(stack)
                .and_then(|amount| u32::try_from(amount).ok()),
            _ => None,
        })
        .sum()
}

fn drain_water(data: &mut Compound, amount: u32) -> u32 {
    let stacks = match data.get_mut(&"fluids".into()) {
        Some(Tag::List(stacks)) => stacks,
        Some(Tag::Compound(fluids)) => match fluids.get_mut(&"stacks".into()) {
            Some(Tag::List(stacks)) => stacks,
            _ => return 0,
        },
        _ => return 0,
    };
    let mut remaining = amount;
    for stack in stacks.iter_mut() {
        let Tag::Compound(stack) = stack else { continue };
        if !fluid_stack_is_water(stack) { continue; }
        let amount_key = if stack.contains_key(&"Amount".into()) { "Amount" } else { "amount" };
        let held = int(stack, amount_key).unwrap_or(0).max(0) as u32;
        let taken = held.min(remaining);
        stack.insert(amount_key.into(), Tag::Int((held - taken) as i32));
        remaining -= taken;
        if remaining == 0 { break; }
    }
    let taken = amount - remaining;
    stacks.retain(|stack| match stack {
        Tag::Compound(stack) => fluid_stack_amount(stack).unwrap_or(0) > 0,
        _ => true,
    });
    taken
}

fn fluid_stack_is_water(stack: &Compound) -> bool {
    ["Fluid", "id"].into_iter().find_map(|key| match stack.get(&key.into()) {
        Some(Tag::String(fluid)) => Some(fluid.to_string_lossy() == "minecraft:water"),
        _ => None,
    }).unwrap_or(false)
}

fn fluid_stack_amount(stack: &Compound) -> Option<i32> {
    int(stack, if stack.contains_key(&"Amount".into()) { "Amount" } else { "amount" })
}

fn tank_group(
    host: &dyn mod_api::Host,
    level: LevelRef,
    pos: [i32; 3],
    part: KineticPart,
) -> Option<([i32; 3], Vec<[i32; 3]>, i32, i32)> {
    let block = level.block(host, pos)?;
    if block != part.fluid_tank && block != part.creative_fluid_tank { return None; }
    let mut members = vec![pos];
    let mut cursor = 0;
    while cursor < members.len() && members.len() < 64 {
        let at = members[cursor];
        cursor += 1;
        for direction in DIRECTIONS {
            let next = add3(at, direction);
            if !members.contains(&next)
                && matches!(level.block(host, next), Some(kind) if kind == part.fluid_tank || kind == part.creative_fluid_tank)
            {
                members.push(next);
            }
        }
    }
    let min = [0, 1, 2].map(|axis| members.iter().map(|at| at[axis]).min().unwrap());
    let max = [0, 1, 2].map(|axis| members.iter().map(|at| at[axis]).max().unwrap());
    let width = max[0] - min[0] + 1;
    let depth = max[2] - min[2] + 1;
    let height = max[1] - min[1] + 1;
    let full_cuboid = width == depth
        && width <= 3
        && height <= 18
        && members.len() == (width * width * height) as usize;
    if !full_cuboid {
        return Some((pos, vec![pos], 1, 1));
    }
    let mut full = Vec::with_capacity(members.len());
    for y in min[1]..=max[1] {
        for x in min[0]..=max[0] {
            for z in min[2]..=max[2] {
                full.push([x, y, z]);
            }
        }
    }
    Some((min, full, width, height))
}

fn tick_boiler(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    current: &mut Compound,
    part: KineticPart,
) -> bool {
    let Some((root, members, width, height)) = tank_group(host, level, pos, part) else {
        return false;
    };
    for &at in &members {
        let mut data = if at == pos {
            current.clone()
        } else {
            host.block_entity(level, at).and_then(|entity| entity.data(host)).unwrap_or_default()
        };
        data.insert("CreateTankController".into(), Tag::IntArray(root.to_vec()));
        if at == root {
            data.insert("Size".into(), Tag::Int(width));
            data.insert("Height".into(), Tag::Int(height));
        }
        if at == pos {
            *current = data;
        } else if let Some(entity) = host.block_entity_identity(level, at) {
            let _ = entity.merge_data(host, data);
        }
    }
    if pos != root { return true; }

    let mut engines = Vec::new();
    let mut whistles = Vec::new();
    for &tank in &members {
        for direction in DIRECTIONS {
            let adjacent = add3(tank, direction);
            if level.block(host, adjacent) == Some(part.steam_engine)
                && level.block_property(host, adjacent, "face").as_deref().is_some_and(|face| {
                    face == if direction[1] == 1 { "floor" } else if direction[1] == -1 { "ceiling" } else { "wall" }
                })
            {
                let facing = if direction[1] != 0 {
                    direction
                } else {
                    direction_normal(&level.block_property(host, adjacent, "facing").unwrap_or_default()).unwrap_or([0; 3])
                };
                if facing == direction { engines.push((adjacent, direction)); }
            }
            if level.block(host, adjacent) == Some(part.steam_whistle) {
                let wall = level.block_property(host, adjacent, "wall").as_deref() == Some("true");
                let support = if wall {
                    direction_normal(&level.block_property(host, adjacent, "facing").unwrap_or_default())
                } else { Some([0, -1, 0]) };
                if support == Some(direction.map(|component| -component)) { whistles.push(adjacent); }
            }
        }
    }

    let mut active_heat = 0;
    let mut passive_heat = false;
    for x in 0..width {
        for z in 0..width {
            let heater = [root[0] + x, root[1] - 1, root[2] + z];
            let heater_name = level
                .block(host, heater)
                .and_then(|block| host.block_states().name(block).ok().map(str::to_owned));
            match heater_name.as_deref() {
                Some("create:blaze_burner") => match level.block_property(host, heater, "blaze").as_deref() {
                    Some("seething") => active_heat += 2,
                    Some("kindled" | "fading") => active_heat += 1,
                    Some("smouldering") => passive_heat = true,
                    _ => {}
                },
                Some("create:lit_blaze_burner" | "minecraft:magma_block" | "minecraft:lava" | "minecraft:fire" | "minecraft:soul_fire") => passive_heat = true,
                Some("minecraft:campfire" | "minecraft:soul_campfire") if level.block_property(host, heater, "lit").as_deref() == Some("true") => passive_heat = true,
                _ => {}
            }
        }
    }
    let creative = level.block(host, root) == Some(part.creative_fluid_tank);
    let total_water: u32 = if creative { 1000 } else { members.iter().map(|&at| {
        if at == root { stored_water(current) }
        else { host.block_entity(level, at).and_then(|entity| entity.data(host)).map_or(0, |data| stored_water(&data)) }
    }).sum() };
    let heat_ready = active_heat > 0 || passive_heat;
    let has_demand = !engines.is_empty() || !whistles.is_empty();
    let supply: f32 = if total_water > 0 && heat_ready && has_demand { 10.0 } else { 0.0 };
    if supply > 0.0 && !creative {
        let mut remaining = 1;
        for &tank in &members {
            if remaining == 0 { break; }
            let mut tank_data = if tank == pos {
                current.clone()
            } else {
                host.block_entity(level, tank).and_then(|entity| entity.data(host)).unwrap_or_default()
            };
            let drained = drain_water(&mut tank_data, remaining);
            if drained > 0 {
                if tank == pos {
                    *current = tank_data;
                } else if let Some(entity) = host.block_entity_identity(level, tank) {
                    let _ = entity.merge_data(host, tank_data);
                }
                remaining -= drained;
            }
        }
    }
    if has_demand {
        let mut boiler = Compound::new();
        boiler.insert("Supply".into(), Tag::Float(supply.to_bits()));
        boiler.insert("Engines".into(), Tag::Int(engines.len() as i32));
        boiler.insert("Whistles".into(), Tag::Int(whistles.len() as i32));
        boiler.insert("ActiveHeat".into(), Tag::Int(active_heat));
        boiler.insert("PassiveHeat".into(), Tag::Byte(i8::from(passive_heat)));
        current.insert("Boiler".into(), Tag::Compound(boiler));
    } else {
        current.remove(&"Boiler".into());
    }
    if let Some(entity) = host.block_entity_identity(level, root) {
        let _ = entity.merge_data(host, current.clone());
    }
    for (engine, direction) in engines {
        let shaft = add3(engine, direction.map(|component| component * 2));
        if level.block(host, shaft) == Some(part.powered_shaft) {
            let graph = network(host, level, shaft, None, part);
            apply_speeds(host, level, graph, part);
        }
    }
    true
}

fn tick_whistle(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    data: &mut Compound,
    part: KineticPart,
) {
    if level.block(host, pos) != Some(part.steam_whistle) { return; }
    let wall = level.block_property(host, pos, "wall").as_deref() == Some("true");
    let support = if wall {
        direction_normal(&level.block_property(host, pos, "facing").unwrap_or_default()).unwrap_or([0, -1, 0])
    } else { [0, -1, 0] };
    let tank = add3(pos, support);
    let Some((root, _, _, _)) = tank_group(host, level, tank, part) else { return; };
    let root_data = host.block_entity(level, root).and_then(|entity| entity.data(host)).unwrap_or_default();
    let boiler = match root_data.get(&"Boiler".into()) { Some(Tag::Compound(boiler)) => boiler, _ => return };
    let steam = int(boiler, "Engines").unwrap_or(0) + int(boiler, "Whistles").unwrap_or(0) > 0
        && float(boiler, "Supply").unwrap_or(0.0) > 0.0
        && (int(boiler, "ActiveHeat").unwrap_or(0) > 0 || int(boiler, "PassiveHeat").unwrap_or(0) > 0);
    let mut pitch = 0;
    for offset in 1..=6 {
        let extension = [pos[0], pos[1] + offset, pos[2]];
        if level.block(host, extension) != Some(part.steam_whistle_extension) { break; }
        pitch += if level.block_property(host, extension, "shape").as_deref() == Some("single") { 1 } else { 2 };
    }
    data.insert("Steam".into(), Tag::Int(i32::from(steam)));
    data.insert("Pitch".into(), Tag::Int(pitch));
}

fn steam_shaft_output(
    host: &mut dyn ServerHost,
    level: LevelRef,
    shaft: [i32; 3],
    node: Node,
    part: KineticPart,
) -> Option<super::power_sources::Output> {
    let Node::Generator { shaft_axis, .. } = node else {
        return None;
    };
    const DIRECTIONS: [[i32; 3]; 6] = [
        [0, -1, 0],
        [0, 1, 0],
        [0, 0, -1],
        [0, 0, 1],
        [-1, 0, 0],
        [1, 0, 0],
    ];
    for direction in DIRECTIONS {
        if direction[shaft_axis] != 0 {
            continue;
        }
        let engine = [
            shaft[0] - direction[0] * 2,
            shaft[1] - direction[1] * 2,
            shaft[2] - direction[2] * 2,
        ];
        if level.block(host, engine) != Some(part.steam_engine) {
            continue;
        }
        let engine_face = match level.block_property(host, engine, "face")?.as_str() {
            "floor" => [0, 1, 0],
            "ceiling" => [0, -1, 0],
            "wall" => direction_normal(&level.block_property(host, engine, "facing")?)?,
            _ => continue,
        };
        if engine_face != direction {
            continue;
        }
        let tank_pos = [
            engine[0] - direction[0],
            engine[1] - direction[1],
            engine[2] - direction[2],
        ];
        let tank_block = level.block(host, tank_pos)?;
        if tank_block != part.fluid_tank && tank_block != part.creative_fluid_tank {
            continue;
        }
        let tank_data = host.block_entity(level, tank_pos)?.data(host)?;
        let root_pos = match tank_data.get(&"CreateTankController".into()) {
            Some(Tag::IntArray(root)) if root.len() == 3 => [root[0], root[1], root[2]],
            _ => tank_pos,
        };
        let root_data = host
            .block_entity(level, root_pos)
            .and_then(|entity| entity.data(host))?;
        let boiler = match root_data.get(&"Boiler".into()) {
            Some(Tag::Compound(boiler)) => boiler,
            _ => return Some(super::power_sources::Output::default()),
        };
        let engines = int(boiler, "Engines").unwrap_or(0);
        let size = int(&root_data, "Size").unwrap_or(1).max(1);
        let height = int(&root_data, "Height").unwrap_or(1).max(1);
        let tank_blocks = size.saturating_mul(size).saturating_mul(height);
        let supply = float(boiler, "Supply").unwrap_or(0.0);
        let active_heat = int(boiler, "ActiveHeat").unwrap_or(0);
        let passive_heat = int(boiler, "PassiveHeat").unwrap_or(0) != 0;
        let efficiency = super::power_sources::boiler_efficiency(
            engines,
            tank_blocks,
            supply,
            active_heat,
            passive_heat,
        );
        let mut rotation = if shaft_axis == 1 || efficiency == 0.0 {
            1
        } else {
            let rotation_direction = if direction[1] != 0 {
                direction_normal(&level.block_property(host, engine, "facing")?)?
            } else {
                direction
            };
            let horizontal = rotation_direction.iter().sum::<i32>();
            if shaft_axis == 2 {
                -horizontal
            } else {
                horizontal
            }
        };
        let engine_data = host.block_entity(level, engine)?.data(host)?;
        if int(&engine_data, "ScrollValue") == Some(1) {
            rotation *= -1;
        }
        return Some(super::power_sources::steam_engine(efficiency, rotation));
    }
    Some(super::power_sources::Output::default())
}
