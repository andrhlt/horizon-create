//! Horizon host adapter for the selected kinetic graph. Calculation lives in
//! `kinetic_slice`; this file owns only typed-Part registration and world IO.

use std::collections::{HashMap, VecDeque};
use std::sync::OnceLock;

use super::create_kinetic_slice::{self, Node};

static KINETIC_PART: OnceLock<KineticPart> = OnceLock::new();
use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockKey,
    BlockPart, BlockState, Compound, HostBlockStates, HostSide, LevelHost, LevelRef, ServerHost,
    Tag,
};

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let motor = registrar
        .block_entity_type("create:motor")
        .blocks(&["create:creative_motor"])
        .build();
    let kinetic = registrar
        .block_entity_type("create:simple_kinetic")
        .blocks(&["create:shaft", "create:cogwheel", "create:large_cogwheel"])
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
    let sequencer = registrar
        .block_entity_type("create:sequenced_gearshift")
        .blocks(&["create:sequenced_gearshift"])
        .build();
    let speed_controller = registrar
        .block_entity_type("create:rotation_speed_controller")
        .blocks(&["create:rotation_speed_controller"])
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
        encased_andesite_cogwheel: registrar.block_key("create:andesite_encased_cogwheel"),
        encased_large_cogwheel: registrar.block_key("create:brass_encased_large_cogwheel"),
        encased_andesite_large_cogwheel: registrar
            .block_key("create:andesite_encased_large_cogwheel"),
        andesite_shaft: registrar.block_key("create:andesite_encased_shaft"),
        brass_shaft: registrar.block_key("create:brass_encased_shaft"),
        girder_shaft: registrar.block_key("create:metal_girder_encased_shaft"),
        chain_drive: registrar.block_key("create:encased_chain_drive"),
        chain_gearshift: registrar.block_key("create:adjustable_chain_gearshift"),
        sequencer: registrar.block_key("create:sequenced_gearshift"),
        speed_controller: registrar.block_key("create:rotation_speed_controller"),
    };
    let _ = KINETIC_PART.set(part);
    registrar.block_entity_part(&motor, part).unwrap();
    registrar.block_entity_part(&kinetic, part).unwrap();
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
    registrar.block_entity_part(&sequencer, part).unwrap();
    registrar.block_entity_part(&speed_controller, part).unwrap();
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
    sequencer: BlockKey,
    speed_controller: BlockKey,
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
        if node(host, level, pos, *self)
            .is_some_and(|n| matches!(n, Node::SequencedGearshift { .. }))
        {
            if !data.contains_key(&"Instructions".into()) {
                data.insert("Instructions".into(), Tag::List(vec![
                    Tag::Compound(Compound::from([
                        ("Type".into(), Tag::String("TURN_ANGLE".into())),
                        ("Modifier".into(), Tag::String("FORWARD".into())),
                        ("Value".into(), Tag::Int(90)),
                    ])),
                    Tag::Compound(Compound::from([
                        ("Type".into(), Tag::String("END".into())),
                        ("Modifier".into(), Tag::String("FORWARD".into())),
                        ("Value".into(), Tag::Int(0)),
                    ])),
                ]));
                data.insert("InstructionIndex".into(), Tag::Int(-1));
                data.insert("InstructionDuration".into(), Tag::Int(-1));
                data.insert("Timer".into(), Tag::Int(0));
                changed = true;
            }
        }
        if changed {
            let _ = event.entity.merge_data(host, data.clone());
        }
        // A kinetic network has a meaningful direction only from its source.
        // Resolving on load from every shaft/consumer loses directional
        // transmission context and lets whichever BE loads last overwrite the
        // motor-root result.
        if !node(host, level, pos, *self)
            .is_some_and(|node| matches!(node, Node::Motor { .. }))
        {
            return;
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
        let node_here = node(host, level, event.pos, *self);
        if node_here.is_some_and(|node| matches!(node, Node::ChainDrive { .. }))
            && level.block(host, event.pos) == Some(self.chain_gearshift)
        {
            let signal = level.best_neighbor_signal(host, event.pos).unwrap_or(0).clamp(0, 15);
            event.entity.nbt.insert("Signal".into(), Tag::Int(signal));
        }
        if node_here.is_some_and(|node| matches!(node, Node::SequencedGearshift { .. })) {
            super::kinetic_controls::tick_sequencer(
                host,
                level,
                event.pos,
                &mut event.entity.nbt,
            );
        }
        // Directional ratios and source arbitration must be evaluated from a
        // motor, never from an arbitrary block entity in the network.
        if !node_here.is_some_and(|node| matches!(node, Node::Motor { .. })) {
            return;
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
    if block == part.sequencer {
        let axis = if level.block_property(host, pos, "vertical").as_deref() == Some("true") {
            1
        } else {
            kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?
        };
        let data = host.block_entity(level, pos).and_then(|entity| entity.data(host));
        let input_side = data.as_ref().and_then(|data| int(data, "InputSide")).unwrap_or(0);
        let active = data.as_ref().and_then(|data| int(data, "InstructionIndex")).unwrap_or(-1);
        let modifier = data.as_ref().and_then(|data| instruction_modifier(data, active)).unwrap_or(0);
        return Some(Node::SequencedGearshift { axis, input_side, modifier });
    }
    if block == part.speed_controller {
        let target = host
            .block_entity(level, pos)
            .and_then(|entity| entity.data(host))
            .and_then(|data| int(&data, "ScrollValue"))
            .unwrap_or(16)
            .clamp(-256, 256);
        return Some(Node::RotationSpeedController {
            axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)?,
            target,
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

fn int(data: &Compound, key: &str) -> Option<i32> {
    match data.get(&key.into()) {
        Some(Tag::Int(value)) => Some(*value),
        Some(Tag::Byte(value)) => Some(i32::from(*value)),
        _ => None,
    }
}

fn instruction_modifier(data: &Compound, index: i32) -> Option<i32> {
    let rows = match data.get(&"Instructions".into()) {
        Some(Tag::List(rows)) => rows,
        _ => return (index == 0).then_some(1),
    };
    let row = match rows.get(usize::try_from(index).ok()?)? {
        Tag::Compound(row) => row,
        _ => return None,
    };
    let text = |key: &str| match row.get(&key.into()) {
        Some(Tag::String(value)) => Some(value.to_string_lossy()),
        _ => None,
    };
    match text("Type")?.as_str() {
        "TURN_ANGLE" | "TURN_DISTANCE" => Some(match text("Modifier").as_deref() {
            Some("FORWARD_FAST") => 2,
            Some("BACK") => -1,
            Some("BACK_FAST") => -2,
            _ => 1,
        }),
        _ => Some(0),
    }
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
    let root_speed = match start_node {
        Node::Motor { facing } => current_data
            .map(|data| kinetic_slice::motor_speed(facing, scroll_value(data)))
            .unwrap_or(0.0),
        _ => 0.0,
    };
    let mut ratios = HashMap::from([(start, 1.0f32)]);
    let mut parents = HashMap::from([(start, None)]);
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
            let controller_link =
                kinetic_slice::controller_links_large_cog(block, other, delta);
            let edge = if controller_link { Some(1.0) } else { block.ratio_to(other, delta) };
            let Some(edge) = edge else { continue };
            if edge == 0.0 {
                continue;
            }
            if parents.get(&pos).copied().flatten() == Some(next) {
                continue;
            }
            let direction = block.direction_ratio(entered, delta);
            let next_ratio = if controller_link {
                let Node::RotationSpeedController { target, .. } = block else { unreachable!() };
                let Some(output_ratio) = kinetic_slice::controller_output_ratio(root_speed, target) else {
                    continue;
                };
                output_ratio
            } else {
                ratio * direction / edge
            };
            if let Some(previous_ratio) = ratios.get(&next).copied() {
                topology_conflict |=
                    kinetic_slice::inconsistent_loop_ratio(next_ratio, previous_ratio);
                continue;
            }
            ratios.insert(next, next_ratio);
            parents.insert(next, Some(pos));
            pending.push_back((next, other, delta.map(|value| -value)));
        }
    }
    let mut sources = Vec::new();
    let mut impact_per_rpm = 0.0;
    for pos in order {
        let ratio = ratios[&pos];
        if ratio == 0.0 {
            continue;
        }
        let Some(block) = node(host, level, pos, part) else {
            continue;
        };
        if matches!(block, Node::Millstone) {
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
            if ratio == 0.0 {
                return (pos, kinetic_slice::Network::default());
            }
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
