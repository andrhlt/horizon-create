//! Player configuration screens for the kinetic sequencer and speed controller.

use mod_api::{
    BlockEntityPart, BlockPart, BlockUpdateFlags, Compound, InteractionResult, LevelRef,
    MenuReplace, ServerHost, Tag, Text, UseWithoutItemEvent,
};

const CONTROLLER: &str = "create:rotation_speed_controller";
const SEQUENCER: &str = "create:sequenced_gearshift";

#[derive(Clone, Copy, Default)]
struct KineticControls;

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let controller = registrar.block_entity_type_key(CONTROLLER);
    let sequencer = registrar.block_entity_type_key(SEQUENCER);
    registrar.block_entity_part(&controller, KineticControls).unwrap();
    registrar.block_entity_part(&sequencer, KineticControls).unwrap();
    for id in [CONTROLLER, SEQUENCER] {
        let block = registrar.block_key(id);
        registrar.block_container(&block, mod_api::ModContainer {
            slots: 1,
            faces: std::array::from_fn(|_| Vec::new()),
            inputs: Vec::new(),
            outputs: Vec::new(),
            menu: Some(id.to_owned()),
        });
    }
}

pub fn tick_sequencer(
    host: &mut dyn ServerHost,
    level: LevelRef,
    pos: [i32; 3],
    data: &mut Compound,
) -> bool {
    if level.block(host, pos) != host.block_key(SEQUENCER) {
        return false;
    }
    let axis = if level.block_property(host, pos, "vertical").as_deref() == Some("true") {
        1
    } else {
        match level.block_property(host, pos, "axis").as_deref() {
            Some("x") => 0,
            Some("y") => 1,
            Some("z") => 2,
            _ => return false,
        }
    };
    let powered = level.has_neighbor_signal(host, pos);
    let was_powered = int(data, "PrevPowered").unwrap_or(0) != 0;
    let mut active = int(data, "InstructionIndex").unwrap_or(-1);
    let mut duration = int(data, "InstructionDuration").unwrap_or(-1);
    let mut timer = int(data, "Timer").unwrap_or(0);
    let input_side = [(-1, 1), (1, -1)].into_iter().find_map(|(side, _)| {
        let neighbor = match axis {
            0 => [pos[0] + side, pos[1], pos[2]],
            1 => [pos[0], pos[1] + side, pos[2]],
            _ => [pos[0], pos[1], pos[2] + side],
        };
        let speed = host.block_entity(level, neighbor)
            .and_then(|entity| entity.data(host))
            .and_then(|neighbor| float(&neighbor, "Speed"))
            .unwrap_or(0.0);
        (speed != 0.0).then_some(-side)
    }).unwrap_or_else(|| int(data, "InputSide").filter(|side| *side == -1 || *side == 1).unwrap_or(1));
    let input_offset = -input_side;
    let input_pos = match axis {
        0 => [pos[0] + input_offset, pos[1], pos[2]],
        1 => [pos[0], pos[1] + input_offset, pos[2]],
        _ => [pos[0], pos[1], pos[2] + input_offset],
    };
    let input_speed = host.block_entity(level, input_pos)
        .and_then(|entity| entity.data(host))
        .and_then(|neighbor| float(&neighbor, "Speed"))
        .unwrap_or(0.0);
    let rows = match data.get(&"Instructions".into()) {
        Some(Tag::List(rows)) => rows.clone(),
        _ => vec![
            Tag::Compound(default_instruction("TURN_ANGLE", 90)),
            Tag::Compound(default_instruction("END", 0)),
        ],
    };
    let mut next_active = None;
    if active < 0 && powered && !was_powered && input_speed != 0.0 {
        next_active = Some(0);
    } else if active >= 0 {
        let Some(Tag::Compound(row)) = usize::try_from(active).ok().and_then(|index| rows.get(index)) else {
            next_active = Some(-1);
            data.insert("InstructionIndex".into(), Tag::Int(-1));
            return false;
        };
        let kind = tag_string(row, "Type").unwrap_or_default();
        if kind == "AWAIT" {
            if powered && !was_powered { next_active = Some(active + 1); }
        } else if kind == "END" {
            next_active = Some(-1);
        } else {
            if duration < 0 {
                let value = int(row, "Value").unwrap_or(90).max(1);
                duration = if kind == "DELAY" {
                    value
                } else if input_speed == 0.0 {
                    i32::MAX
                } else {
                    (value as f32 / (input_speed.abs() * 0.3)).ceil() as i32 + 2
                };
            }
            if timer < duration {
                timer += 1;
            } else {
                next_active = Some(active + 1);
            }
        }
    }
    if let Some(index) = next_active {
        if index < 0 || usize::try_from(index).ok().is_none_or(|index| index >= rows.len()) {
            active = -1;
            duration = -1;
            timer = 0;
            data.insert("InstructionProgress".into(), Tag::Float(0.0f32.to_bits()));
            let _ = host.set_block_property_with(
                pos,
                "state",
                "0",
                (BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS).bits(),
            );
        } else {
            active = index;
            duration = -1;
            timer = 0;
            let step = (index + 1).to_string();
            let _ = host.set_block_property_with(
                pos,
                "state",
                &step,
                (BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS).bits(),
            );
        }
    }
    data.insert("Instructions".into(), Tag::List(rows));
    data.insert("InstructionIndex".into(), Tag::Int(active));
    data.insert("InstructionDuration".into(), Tag::Int(duration));
    data.insert("Timer".into(), Tag::Int(timer));
    data.insert("PrevPowered".into(), Tag::Byte(i8::from(powered)));
    data.insert("InputSide".into(), Tag::Int(input_side));
    data.insert("InputSpeed".into(), Tag::Float(input_speed.to_bits()));
    true
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

fn tag_string(data: &Compound, key: &str) -> Option<String> {
    match data.get(&key.into()) {
        Some(Tag::String(value)) => Some(value.to_string_lossy()),
        _ => None,
    }
}

fn open(host: &mut dyn ServerHost, event: &UseWithoutItemEvent<'_>) -> Option<InteractionResult> {
    let block = match event.state.block() {
        key if host.block_key(CONTROLLER) == Some(key) => CONTROLLER,
        key if host.block_key(SEQUENCER) == Some(key) => SEQUENCER,
        _ => return None,
    };
    let menu_id = match block {
        CONTROLLER => CONTROLLER,
        SEQUENCER => SEQUENCER,
        _ => return None,
    };
    let menu = host.menu_keys().into_iter().find(|key| {
        mod_api::__private::menu_key_id(*key).as_deref() == Some(menu_id)
    })?;
    let player = host.player(event.click.player)?;
    let result = player.open_mod_menu(
        host,
        menu,
        Text::literal(if block == CONTROLLER { "Rotation Speed Controller" } else { "Sequenced Gearshift" }),
        Vec::new(),
        Some(event.click.pos),
        MenuReplace::InPlace,
    ).ok()?;
    result.map(|_| InteractionResult::SuccessServer)
}

#[mod_api::horizon_part]
impl BlockPart for KineticControls {
    fn use_without_item(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseWithoutItemEvent<'_>,
    ) -> Option<InteractionResult> {
        open(host, event)
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for KineticControls {
    fn screen(
        &self,
        _: &dyn mod_api::Host,
        event: &mut mod_api::ScreenEvent<'_>,
    ) -> Option<mod_api::Screen> {
        matches!(event.block, CONTROLLER | SEQUENCER).then(|| {
            let (height, slot, inventory_y) = if event.block == CONTROLLER {
                (166.0, [8.0, 56.0], 80.0)
            } else {
                (240.0, [8.0, 136.0], 162.0)
            };
            mod_api::Screen {
                width: 220.0,
                height,
                slots: vec![Some(slot)],
                inventory_x: 8.0,
                inventory_y,
                own_labels: true,
                own_background: true,
                ..Default::default()
            }
        })
    }

    fn screen_draw(
        &self,
        _: &dyn mod_api::ClientHost,
        event: &mut mod_api::ScreenDrawEvent<'_>,
    ) {
        if event.block == CONTROLLER {
            let _ = event.draw.widget_button(
                [event.origin[0] + 8.0, event.origin[1] + 26.0, 204.0, 24.0],
                &Text::literal("Rotation speed: click to adjust"),
                true,
                false,
            );
        } else if event.block == SEQUENCER {
            for row in 0..5 {
                let y = event.origin[1] + 8.0 + row as f32 * 25.0;
                for col in 0..4 {
                    let label = match col {
                        0 => "Turn +90",
                        1 => "Turn -90",
                        2 => "Wait",
                        _ => "End",
                    };
                    let _ = event.draw.widget_button(
                        [event.origin[0] + 8.0 + col as f32 * 52.0, y, 50.0, 22.0],
                        &Text::literal(format!("{row}: {label}")),
                        true,
                        false,
                    );
                }
            }
        }
    }

    fn screen_click(
        &self,
        _: &dyn mod_api::ClientHost,
        event: &mut mod_api::ScreenClickEvent<'_>,
    ) -> Option<i32> {
        if std::env::var_os("CREATE_KINETIC_CONTROLS_TRACE").is_some() {
            eprintln!("CREATE_KINETIC_CONTROLS_CLICK block={} at={:?} right={}", event.block, event.at, event.right);
        }
        if event.right {
            return None;
        }
        let [x, y] = event.at;
        if event.block == CONTROLLER {
            if !(26.0..50.0).contains(&y) || !(8.0..212.0).contains(&x) {
                return None;
            }
            let speed = (((x - 8.0) / 204.0) * 512.0).round() as i32;
            return Some(speed.clamp(0, 512));
        }
        if event.block == SEQUENCER {
            let row = ((y - 8.0) / 25.0).floor() as i32;
            let col = ((x - 8.0) / 52.0).floor() as i32;
            if (0..5).contains(&row) && (0..4).contains(&col) {
                return Some(1024 + row * 4 + col);
            }
        }
        None
    }

    fn menu_button(&self, host: &mut dyn ServerHost, event: &mut mod_api::MenuButtonEvent<'_>) {
        let _ = host;
        let id = event.context.id;
        if std::env::var_os("CREATE_KINETIC_CONTROLS_TRACE").is_some() {
            eprintln!("CREATE_KINETIC_CONTROLS_BUTTON id={} pos={:?}", id, event.context.pos);
        }
        if !(0..=512).contains(&id) && !(1024..1044).contains(&id) {
            return;
        }
        match event.entity.id() {
            CONTROLLER if (0..=512).contains(&id) => {
                event.entity.nbt.insert("ScrollValue".into(), Tag::Int(id - 256));
            }
            SEQUENCER if (1024..1044).contains(&id) => {
                let row = ((id - 1024) / 4) as usize;
                let mode = (id - 1024) % 4;
                let mut instructions = match event.entity.nbt.get(&"Instructions".into()) {
                    Some(Tag::List(rows)) => rows.clone(),
                    _ => Vec::new(),
                };
                while instructions.len() < 5 {
                    instructions.push(Tag::Compound(default_instruction("TURN_ANGLE", 90)));
                }
                let instruction = match mode {
                    0 => default_instruction("TURN_ANGLE", 90),
                    1 => default_instruction("TURN_ANGLE", -90),
                    2 => default_instruction("AWAIT", 1),
                    _ => default_instruction("END", 0),
                };
                instructions[row] = Tag::Compound(instruction);
                event.entity.nbt.insert("Instructions".into(), Tag::List(instructions));
                event.entity.nbt.insert("InstructionIndex".into(), Tag::Int(-1));
                event.entity.nbt.insert("InstructionDuration".into(), Tag::Int(-1));
                event.entity.nbt.insert("Timer".into(), Tag::Int(0));
            }
            _ => {}
        }
    }
}

fn default_instruction(kind: &str, value: i32) -> mod_api::Compound {
    let modifier = if value < 0 { "BACK" } else { "FORWARD" };
    mod_api::Compound::from([
        ("Type".into(), Tag::String(kind.into())),
        ("Modifier".into(), Tag::String(modifier.into())),
        ("Value".into(), Tag::Int(value.abs())),
    ])
}
