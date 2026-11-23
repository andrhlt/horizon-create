//! Horizon host adapter for the selected kinetic graph. Calculation lives in
//! `kinetic_slice`; this file owns only typed-Part registration and world IO.

use std::collections::{HashMap, VecDeque};
use std::sync::OnceLock;

use crate::kinetic_slice::{self, Node};

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
    let part = KineticPart {
        motor: registrar.block_key("create:creative_motor"),
        shaft: registrar.block_key("create:shaft"),
        cogwheel: registrar.block_key("create:cogwheel"),
        large_cogwheel: registrar.block_key("create:large_cogwheel"),
    };
    let _ = KINETIC_PART.set(part);
    registrar.block_entity_part(&motor, part).unwrap();
    registrar.block_entity_part(&kinetic, part).unwrap();
}

#[derive(Clone, Copy)]
pub struct KineticPart {
    motor: BlockKey,
    shaft: BlockKey,
    cogwheel: BlockKey,
    large_cogwheel: BlockKey,
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
    KINETIC_PART
        .get()
        .is_some_and(|part| part.set_motor_setting(host, level, pos, setting))
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
        let drawn = event
            .draw
            .block(shaft, &[("axis", ["x", "y", "z"][axis])]);
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
        for (pos, speed) in graph {
            let is_motor =
                node(host, level, pos, *self).is_some_and(|n| matches!(n, Node::Motor { .. }));
            if pos == event.pos {
                event
                    .entity
                    .nbt
                    .insert("Speed".into(), Tag::Float(speed.to_bits()));
                if is_motor {
                    event
                        .entity
                        .nbt
                        .insert("MotorGeneratedSpeed".into(), Tag::Float(speed.to_bits()));
                }
            } else if let Some(entity) = host.block_entity_identity(level, pos) {
                let mut data = Compound::new();
                data.insert("Speed".into(), Tag::Float(speed.to_bits()));
                if is_motor {
                    data.insert("MotorGeneratedSpeed".into(), Tag::Float(speed.to_bits()));
                }
                let _ = entity.merge_data(host, data);
            }
        }
    }
}

fn apply_speeds(
    host: &mut dyn ServerHost,
    level: LevelRef,
    graph: HashMap<[i32; 3], f32>,
    part: KineticPart,
) {
    for (pos, speed) in graph {
        let Some(entity) = host.block_entity_identity(level, pos) else {
            continue;
        };
        let mut data = Compound::new();
        data.insert("Speed".into(), Tag::Float(speed.to_bits()));
        if node(host, level, pos, part).is_some_and(|n| matches!(n, Node::Motor { .. })) {
            data.insert("MotorGeneratedSpeed".into(), Tag::Float(speed.to_bits()));
        }
        let _ = entity.merge_data(host, data);
    }
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
    None
}

fn network(
    host: &mut dyn ServerHost,
    level: LevelRef,
    start: [i32; 3],
    current_data: Option<&Compound>,
    part: KineticPart,
) -> HashMap<[i32; 3], f32> {
    let Some(start_node) = node(host, level, start, part) else {
        return HashMap::new();
    };
    let mut ratios = HashMap::from([(start, 1.0f32)]);
    let mut pending = VecDeque::from([(start, start_node)]);
    while let Some((pos, block)) = pending.pop_front() {
        let ratio = ratios[&pos];
        for delta in block.neighbors() {
            let next = [pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2]];
            if ratios.contains_key(&next) {
                continue;
            }
            let Some(other) = node(host, level, next, part) else {
                continue;
            };
            let Some(edge) = block.ratio_to(other, delta) else {
                continue;
            };
            if edge == 0.0 {
                continue;
            }
            let next_ratio = ratio / edge;
            ratios.insert(next, next_ratio);
            pending.push_back((next, other));
        }
    }
    let mut generated = 0.0;
    for (&pos, &ratio) in &ratios {
        let Some(Node::Motor { facing }) = node(host, level, pos, part) else {
            continue;
        };
        if pos == start {
            let Some(data) = current_data else { continue };
            generated = kinetic_slice::motor_speed(facing, scroll_value(data)) * ratio;
        } else {
            let Some(entity) = host.block_entity(level, pos) else {
                continue;
            };
            let Some(data) = entity.data(host) else {
                continue;
            };
            generated = kinetic_slice::motor_speed(facing, scroll_value(&data)) * ratio;
        }
        break;
    }
    ratios
        .into_iter()
        .map(|(pos, ratio)| (pos, generated / ratio))
        .collect()
}

fn scroll_value(data: &Compound) -> i32 {
    match data.get(&"ScrollValue".into()) {
        Some(Tag::Int(value)) => *value,
        _ => 16,
    }
}
