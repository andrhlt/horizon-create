//! Horizon host adapter for the selected kinetic graph. Calculation lives in
//! `kinetic_slice`; this file owns only typed-Part registration and world IO.

use std::collections::{HashMap, VecDeque};

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, Compound,
    BlockKey, LevelRef, ServerHost, Tag,
};
use crate::kinetic_slice::{self, Node};

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let motor = registrar.block_entity_type("create:motor")
        .blocks(&["create:creative_motor"]).build();
    let kinetic = registrar.block_entity_type("create:simple_kinetic")
        .blocks(&["create:shaft", "create:cogwheel", "create:large_cogwheel"]).build();
    let part = KineticPart {
        motor: registrar.block_key("create:creative_motor"),
        shaft: registrar.block_key("create:shaft"),
        cogwheel: registrar.block_key("create:cogwheel"),
        large_cogwheel: registrar.block_key("create:large_cogwheel"),
    };
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

#[mod_api::horizon_part]
impl BlockPart for KineticPart {}

#[mod_api::horizon_part]
impl BlockEntityPart for KineticPart {
    fn block_entity_ticks(&self, _: &dyn mod_api::Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let Some(level) = host.level("minecraft:overworld") else {
            return;
        };
        let graph = network(host, level, event.pos, Some(&event.entity.nbt), *self);
        if graph.is_empty() {
            return;
        }
        for (pos, speed) in graph {
            let Some(entity) = host.block_entity_identity(level, pos) else {
                continue;
            };
            if pos == event.pos {
                event.entity.nbt.insert("Speed".into(), Tag::Float(speed.to_bits()));
                if node(host, level, pos, *self).is_some_and(|n| matches!(n, Node::Motor { .. })) {
                    event.entity.nbt.insert("MotorGeneratedSpeed".into(), Tag::Float(speed.to_bits()));
                }
            } else {
                let mut data = Compound::new();
                data.insert("Speed".into(), Tag::Float(speed.to_bits()));
                let _ = entity.merge_data(host, data);
            }
        }
    }
}

fn node(host: &dyn mod_api::Host, level: LevelRef, pos: [i32; 3], part: KineticPart) -> Option<Node> {
    let block = level.block(host, pos)?;
    if block == part.motor {
        let facing = level.block_property(host, pos, "facing")?;
            let normal = match facing.as_str() {
                "east" => [1, 0, 0], "west" => [-1, 0, 0],
                "up" => [0, 1, 0], "down" => [0, -1, 0],
                "south" => [0, 0, 1], "north" => [0, 0, -1], _ => return None,
            };
        return Some(Node::Motor { facing: normal });
    }
    if block == part.shaft {
        return Some(Node::Shaft { axis: kinetic_slice::axis_index(&level.block_property(host, pos, "axis")?)? });
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
            let Some(other) = node(host, level, next, part) else { continue };
            let Some(edge) = block.ratio_to(other, delta) else { continue };
            if edge == 0.0 { continue; }
            let next_ratio = ratio / edge;
            ratios.insert(next, next_ratio);
            pending.push_back((next, other));
        }
    }
    let mut generated = 0.0;
    for (&pos, &ratio) in &ratios {
        let Some(Node::Motor { facing }) = node(host, level, pos, part) else { continue };
        let Some(entity) = host.block_entity(level, pos) else { continue };
        if pos == start {
            let Some(data) = current_data else { continue };
            generated = kinetic_slice::motor_speed(facing, scroll_value(data)) * ratio;
        } else {
            let Some(data) = entity.data(host) else { continue };
        generated = kinetic_slice::motor_speed(facing, scroll_value(&data)) * ratio;
        }
        break;
    }
    ratios.into_iter().map(|(pos, ratio)| (pos, generated / ratio)).collect()
}

fn scroll_value(data: &Compound) -> i32 {
    match data.get(&"ScrollValue".into()) {
        Some(Tag::Int(value)) => *value,
        _ => 16,
    }
}
