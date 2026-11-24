//! Horizon host adapter for the selected kinetic graph. Calculation lives in
//! `kinetic_slice`; this file owns only typed-Part registration and world IO.

use std::collections::{HashMap, VecDeque};
use std::sync::OnceLock;

use super::create_kinetic_slice::{self, Node};

static KINETIC_PART: OnceLock<KineticPart> = OnceLock::new();
use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockKey,
    BlockPart, BlockState, Compound, Host, HostBlockStates, HostSide, LevelHost, LevelRef,
    ServerHost, Tag,
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
            "create:speedometer",
            "create:stressometer",
            "create:turntable",
        ])
        .build();
    let encased_cogwheel = registrar
        .block_entity_type("create:encased_cogwheel")
        .blocks(&["create:brass_encased_cogwheel"])
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
        andesite_shaft: registrar.block_key("create:andesite_encased_shaft"),
        brass_shaft: registrar.block_key("create:brass_encased_shaft"),
        girder_shaft: registrar.block_key("create:metal_girder_encased_shaft"),
        chain_drive: registrar.block_key("create:encased_chain_drive"),
        chain_gearshift: registrar.block_key("create:adjustable_chain_gearshift"),
        speedometer: registrar.block_key("create:speedometer"),
        stressometer: registrar.block_key("create:stressometer"),
        turntable: registrar.block_key("create:turntable"),
    };
    let _ = KINETIC_PART.set(part);
    registrar.block_entity_part(&motor, part).unwrap();
    registrar.block_entity_part(&kinetic, part).unwrap();
    registrar
        .block_entity_part(&encased_cogwheel, part)
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
    andesite_shaft: BlockKey,
    brass_shaft: BlockKey,
    girder_shaft: BlockKey,
    chain_drive: BlockKey,
    chain_gearshift: BlockKey,
    speedometer: BlockKey,
    stressometer: BlockKey,
    turntable: BlockKey,
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
    fn state_for_placement(
        &self,
        host: &dyn LevelHost,
        event: &mut mod_api::StateForPlacementEvent<'_>,
    ) -> Option<Option<BlockState>> {
        if host.state_block(event.state) != Some("create:creative_motor") {
            return None;
        }
        let context = &event.context;
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
        if event.block == "create:speedometer" || event.block == "create:stressometer" {
            let speed = match event.entity.nbt.get(&"Speed".into()) {
                Some(Tag::Float(bits)) => f32::from_bits(*bits),
                _ => 0.0,
            };
            let network = match event.entity.nbt.get(&"Network".into()) {
                Some(Tag::Compound(network)) => network,
                _ => return,
            };
            let stress = match network.get(&"Stress".into()) {
                Some(Tag::Float(bits)) => f32::from_bits(*bits),
                _ => 0.0,
            };
            let capacity = match network.get(&"Capacity".into()) {
                Some(Tag::Float(bits)) => f32::from_bits(*bits),
                _ => 0.0,
            };
            let target = if event.block == "create:speedometer" {
                super::gauge_logic::speed_target(kinetic_slice::effective_speed(
                    speed, capacity, stress,
                ))
            } else {
                if stress > capacity {
                    1.125
                } else if capacity > 0.0 {
                    stress / capacity
                } else {
                    0.0
                }
            };
            draw_gauge_needle(host, event, target * 360.0);
            return;
        }
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
        let graph = network(host, level, event.pos, Some(&event.entity.nbt), *self);
        if graph.is_empty() {
            return;
        }
        for (pos, state) in graph {
            let is_motor =
                node(host, level, pos, *self).is_some_and(|n| matches!(n, Node::Motor { .. }));
            if pos == event.pos {
                persist_network(&mut event.entity.nbt, state, is_motor);
            } else if let Some(entity) = host.block_entity_identity(level, pos) {
                let mut data = Compound::new();
                persist_network(&mut data, state, is_motor);
                let _ = entity.merge_data(host, data);
            }
        }
        let rpm = graph_speed_at(&event.entity.nbt);
        if node(host, level, event.pos, *self) == Some(Node::Turntable) && rpm != 0.0 {
            turn_players(host, level, event.pos, rpm);
        }
    }
}

fn draw_gauge_needle(
    host: &dyn mod_api::ClientHost,
    event: &mut mod_api::BlockEntitySubmitEvent<'_>,
    angle: f32,
) {
    let metadata = host.block_states();
    let Ok(Some(facing)) = event.state.property(&metadata, "facing") else {
        return;
    };
    let Some(needle) = host.block_key("minecraft:redstone_torch") else {
        return;
    };
    let (axis, sign) = match facing {
        "north" => ([0.0, 0.0, 1.0], 1.0),
        "south" => ([0.0, 0.0, 1.0], -1.0),
        "east" => ([1.0, 0.0, 0.0], 1.0),
        "west" => ([1.0, 0.0, 0.0], -1.0),
        "up" => ([0.0, 1.0, 0.0], 1.0),
        "down" => ([0.0, 1.0, 0.0], -1.0),
        _ => return,
    };
    let [x, y, z] = event.pos;
    let offset = match facing {
        "north" => [0.4375, 0.22, 0.0625],
        "south" => [0.4375, 0.22, 0.9375],
        "east" => [0.4375, 0.22, 0.9375],
        "west" => [0.4375, 0.22, 0.0625],
        "up" => [0.4375, 0.22, 0.0625],
        "down" => [0.4375, 0.22, 0.9375],
        _ => return,
    };
    event.draw.push();
    if facing == "up" || facing == "down" {
        event.draw.rotate_about([1.0, 0.0, 0.0], 90.0, [0.5; 3]);
    } else if facing == "east" || facing == "west" {
        event.draw.rotate_about([0.0, 1.0, 0.0], 90.0, [0.5; 3]);
    }
    event.draw.rotate_about(axis, angle * sign, [0.5; 3]);
    event.draw.translate(offset);
    event.draw.scale([0.125, 0.68, 0.125]);
    let drawn = event.draw.block(needle, &[]);
    event.draw.pop();
    if std::env::var_os("CREATE_GAUGE_RENDER").is_some() {
        eprintln!("CREATE_GAUGE_FRAME {x},{y},{z},{facing},{angle:.4},{drawn}");
    }
}

fn graph_speed_at(data: &Compound) -> f32 {
    let speed = match data.get(&"Speed".into()) {
        Some(Tag::Float(value)) => f32::from_bits(*value),
        _ => 0.0,
    };
    let (capacity, stress) = match data.get(&"Network".into()) {
        Some(Tag::Compound(network)) => {
            let read = |key: &str| match network.get(&key.into()) {
                Some(Tag::Float(value)) => f32::from_bits(*value),
                _ => 0.0,
            };
            (read("Capacity"), read("Stress"))
        }
        _ => (0.0, 0.0),
    };
    kinetic_slice::effective_speed(speed, capacity, stress)
}

fn turn_players(host: &mut dyn ServerHost, level: LevelRef, pos: [i32; 3], rpm: f32) {
    let center = [
        f64::from(pos[0]) + 0.5,
        f64::from(pos[1]),
        f64::from(pos[2]) + 0.5,
    ];
    for player in host.players().server_players() {
        let entity = player.entity();
        if entity.level(host) != Some(level) || entity.on_ground(host) != Some(true) {
            continue;
        }
        let Some([x, y, z]) = entity.position(host) else {
            continue;
        };
        if (y - center[1]) < 0.25 || (y - center[1]) > 1.5 {
            continue;
        }
        let offset = [x - center[0], 0.0, z - center[2]];
        let radius = offset[0].hypot(offset[2]);
        if radius > 0.5 {
            continue;
        }
        if let Some([yaw, pitch]) = entity.rotation(host) {
            let _ = entity.set_rotation(host, yaw - rpm * 0.3, pitch);
        }
        if radius > 0.25 {
            let delta = super::turntable_motion::edge_velocity(rpm, offset);
            let velocity = entity.velocity(host).unwrap_or([0.0; 3]);
            let _ = player.set_velocity(
                host,
                [
                    velocity[0] + delta[0],
                    velocity[1] + delta[1],
                    velocity[2] + delta[2],
                ],
            );
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
        let is_motor =
            node(host, level, pos, part).is_some_and(|n| matches!(n, Node::Motor { .. }));
        persist_network(&mut data, state, is_motor);
        let _ = entity.merge_data(host, data);
    }
}

fn persist_network(data: &mut Compound, state: kinetic_slice::Network, is_motor: bool) {
    data.insert("Speed".into(), Tag::Float(state.rpm.to_bits()));
    if is_motor {
        data.insert(
            "MotorGeneratedSpeed".into(),
            Tag::Float(state.rpm.to_bits()),
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
    if block == part.shaft {
        return Some(Node::Shaft {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
        });
    }
    if block == part.speedometer || block == part.stressometer {
        let facing = level.block_property(host, pos, "facing")?;
        let along_first = level.block_property(host, pos, "axis_along_first")? == "true";
        let facing_axis = match facing.as_str() {
            "east" | "west" => 0,
            "up" | "down" => 1,
            "north" | "south" => 2,
            _ => return None,
        };
        let axis = match (facing_axis, along_first) {
            (0, true) | (2, false) => 1,
            (0 | 1, false) => 2,
            (1 | 2, true) => 0,
            _ => return None,
        };
        return Some(Node::Gauge { axis });
    }
    if block == part.turntable {
        return Some(Node::Turntable);
    }
    if block == part.cogwheel || block == part.large_cogwheel {
        return Some(Node::Cogwheel {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            large: block == part.large_cogwheel,
        });
    }
    if block == part.encased_cogwheel {
        return Some(Node::EncasedCogwheel {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            large: false,
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
        if matches!(block, Node::Millstone | Node::Turntable) {
            impact_per_rpm += 4.0 / ratio.abs();
        }
        let Node::Motor { facing } = block else {
            continue;
        };
        if pos == start {
            let Some(data) = current_data else { continue };
            let generated = kinetic_slice::motor_speed(facing, scroll_value(data));
            let mut source = kinetic_slice::motor_source(generated);
            source.speed *= ratio;
            sources.push(source);
        } else {
            let Some(entity) = host.block_entity(level, pos) else {
                continue;
            };
            let Some(data) = entity.data(host) else {
                continue;
            };
            let generated = kinetic_slice::motor_speed(facing, scroll_value(&data));
            let mut source = kinetic_slice::motor_source(generated);
            source.speed *= ratio;
            sources.push(source);
        }
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
