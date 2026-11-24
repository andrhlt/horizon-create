//! Authoritative redstone behavior for the controls whose state is represented
//! in the content pack. The adapter owns API registration and world writes;
//! the persistent state follows Create's existing NBT/property contract.

use mod_api::{
    BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, BlockPart, BlockSignalEvent,
    BlockUpdateFlags, Compound, InteractionResult, IsSignalSourceEvent, LevelHost,
    BlockMetadata, HostBlockStates, LevelTicksHost, LevelWriteHost, ServerHost, Tag,
    UseItemOnEvent, UseWithoutItemEvent, BlockClick,
};

const ANALOG_LEVER: &str = "create:analog_lever";
const REDSTONE_CONTACT: &str = "create:redstone_contact";
const ELEVATOR_CONTACT: &str = "create:elevator_contact";
const DESK_BELL: &str = "create:desk_bell";
const ROSE_LAMP: &str = "create:rose_quartz_lamp";
const DIODE_BLOCKS: [&str; 5] = [
    "create:powered_latch",
    "create:powered_toggle_latch",
    "create:pulse_repeater",
    "create:pulse_extender",
    "create:pulse_timer",
];

#[derive(Clone, Copy, Default)]
struct RedstoneControls;

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let controls = RedstoneControls;
    for id in [ANALOG_LEVER, REDSTONE_CONTACT, ELEVATOR_CONTACT, DESK_BELL, ROSE_LAMP]
        .into_iter().chain(DIODE_BLOCKS) {
        let key = registrar.block_key(id);
        registrar.block_part(key, controls);
    }

    for id in [ANALOG_LEVER, DESK_BELL] {
        let entity = registrar.block_entity_type(id).blocks(&[id]).build();
        registrar.block_entity_part(&entity, controls).unwrap();
    }
}

fn property(host: &dyn LevelHost, state: mod_api::BlockState, key: &str) -> Option<String> {
    let state = host.state_string(state)?;
    let (_, properties) = state.split_once('[')?;
    let properties = properties.strip_suffix(']')?;
    properties.split(',').find_map(|property| {
        let (name, value) = property.split_once('=')?;
        (name == key).then(|| value.to_owned())
    })
}

fn facing(host: &dyn LevelHost, state: mod_api::BlockState) -> &'static str {
    match property(host, state, "facing").as_deref() {
        Some("down") => "down",
        Some("east") => "east",
        Some("north") => "north",
        Some("south") => "south",
        Some("west") => "west",
        _ => "up",
    }
}

fn direction(name: &str) -> mod_api::Direction {
    match name {
        "down" => mod_api::Direction::Down,
        "east" => mod_api::Direction::East,
        "north" => mod_api::Direction::North,
        "south" => mod_api::Direction::South,
        "west" => mod_api::Direction::West,
        _ => mod_api::Direction::Up,
    }
}

fn signal_face(name: &str) -> mod_api::Direction {
    direction(name).opposite()
}

fn powered(host: &dyn LevelHost, state: mod_api::BlockState, key: &str) -> bool {
    property(host, state, key).as_deref() == Some("true")
}

fn block_name(host: &dyn LevelHost, state: mod_api::BlockState) -> String {
    host.state_block(state).unwrap_or("").to_owned()
}

fn analog_strength(host: &dyn LevelHost, state: mod_api::BlockState) -> i32 {
    property(host, state, "strength")
        .and_then(|value| value.parse::<i32>().ok())
        .unwrap_or(0)
        .clamp(0, 15)
}

fn block_name_server<H: HostBlockStates + ?Sized>(host: &H, state: mod_api::BlockState) -> String {
    host.block_states().name(state.block()).unwrap_or("").to_owned()
}

fn analog_strength_server<H: HostBlockStates + ?Sized>(host: &H, state: mod_api::BlockState) -> i32 {
    state
        .property(&host.block_states(), "strength")
        .ok()
        .flatten()
        .and_then(|value| value.parse::<i32>().ok())
        .unwrap_or(0)
        .clamp(0, 15)
}

fn powered_server<H: HostBlockStates + ?Sized>(
    host: &H,
    state: mod_api::BlockState,
    key: &str,
) -> bool {
    state
        .property(&host.block_states(), key)
        .ok()
        .flatten()
        == Some("true")
}

fn signal_for(host: &dyn LevelHost, event: &BlockSignalEvent) -> Option<i32> {
    let block = block_name(host, event.state);
    let facing = facing(host, event.state);
    match block.as_str() {
        ANALOG_LEVER => {
            let mount = property(host, event.state, "face").unwrap_or_else(|| "floor".into());
            let output_face = match mount.as_str() {
                "floor" => "up",
                "ceiling" => "down",
                _ => facing,
            };
            if event.direct && event.face != signal_face(output_face) {
                Some(0)
            } else {
                Some(analog_strength(host, event.state))
            }
        }
        REDSTONE_CONTACT if powered(host, event.state, "powered") => {
            Some(if !event.direct && event.face != direction(facing) {
                15
            } else {
                0
            })
        }
        ELEVATOR_CONTACT if powered(host, event.state, "powered") => {
            Some(if event.direct { 0 } else { 15 })
        }
        DESK_BELL if powered(host, event.state, "powered") => {
            let output = signal_face(facing);
            Some(if !event.direct || event.face == output { 15 } else { 0 })
        }
        ROSE_LAMP => Some(if !event.direct && powered(host, event.state, "powering") { 15 } else { 0 }),
        "create:powered_latch" | "create:powered_toggle_latch"
        | "create:pulse_repeater" | "create:pulse_extender" | "create:pulse_timer" => {
            let on = powered(host, event.state, "powering") ^ powered(host, event.state, "inverted");
            let output_face = direction(facing).opposite();
            Some(if on && event.face == output_face { 15 } else { 0 })
        }
        _ => None,
    }
}

fn relative(pos: [i32; 3], side: mod_api::Direction) -> [i32; 3] {
    let [x, y, z] = side.normal();
    [pos[0] + x, pos[1] + y, pos[2] + z]
}

fn input_power(level: &dyn LevelTicksHost, pos: [i32; 3], side: mod_api::Direction) -> bool {
    let source = relative(pos, side);
    let toward_receiver = side.opposite();
    level.signal(source, toward_receiver) > 0
}

fn powered_input(level: &dyn LevelTicksHost, pos: [i32; 3], facing: &str) -> bool {
    input_power(level, pos, direction(facing).opposite())
}

fn side_input(level: &dyn LevelTicksHost, pos: [i32; 3], facing: &str) -> bool {
    let back = direction(facing);
    let sides = match back {
        mod_api::Direction::North | mod_api::Direction::South => [
            mod_api::Direction::East,
            mod_api::Direction::West,
        ],
        _ => [mod_api::Direction::North, mod_api::Direction::South],
    };
    sides.into_iter().any(|side| input_power(level, pos, side))
}

fn set_property(level: &mut dyn LevelWriteHost, pos: [i32; 3], name: &str, value: bool) -> bool {
    level.set_block_property(
        pos,
        name,
        if value { "true" } else { "false" },
        (BlockUpdateFlags::CLIENTS | BlockUpdateFlags::NEIGHBORS).bits(),
    )
}

impl RedstoneControls {
    fn interact(
        &self,
        host: &mut dyn ServerHost,
        state: mod_api::BlockState,
        click: &BlockClick<'_>,
    ) -> Option<InteractionResult> {
        let block = block_name_server(host, state);
        if !matches!(block.as_str(), ANALOG_LEVER | DESK_BELL) && !DIODE_BLOCKS.contains(&block.as_str()) {
            return None;
        }
        let pos = click.pos;
        let level = host.level(click.dimension.key().id())?;
        let entity = host.block_entity_identity(level, pos)?;
        let mut nbt = entity.data(host)?;
        if block == ANALOG_LEVER {
            let old = analog_strength_server(host, state);
            let player = host.player(click.player)?;
            let change = if player.entity().is_shift_key_down(host).unwrap_or(false) {
                -1
            } else {
                1
            };
            let next = (old + change).clamp(0, 15);
            if next == old {
                return Some(InteractionResult::SuccessServer);
            }
            nbt.insert("State".into(), Tag::Int(next));
            nbt.insert("ChangeTimer".into(), Tag::Int(15));
            if !entity.merge_data(host, nbt).unwrap_or(false) {
                return Some(InteractionResult::Fail);
            }
        } else if block == DESK_BELL {
            nbt.insert("DingTimer".into(), Tag::Int(20));
            if !entity.merge_data(host, nbt).unwrap_or(false) {
                return Some(InteractionResult::Fail);
            }
            let _ = host.set_block_property_with(
                pos,
                "powered",
                "true",
                (BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS).bits(),
            );
        } else {
            let toggle = block == "create:powered_toggle_latch";
            let value = if toggle {
                !powered_server(host, state, "powering")
            } else {
                true
            };
            let _ = host.set_block_property_with(
                pos,
                "powering",
                if value { "true" } else { "false" },
                (BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS).bits(),
            );
        }
        host.block_entity_sync(pos);
        Some(InteractionResult::SuccessServer)
    }
}

#[mod_api::horizon_part]
impl BlockPart for RedstoneControls {
    fn use_item_on(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseItemOnEvent<'_>,
    ) -> Option<InteractionResult> {
        self.interact(host, event.state, event.click)
    }

    fn use_without_item(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseWithoutItemEvent<'_>,
    ) -> Option<InteractionResult> {
        self.interact(host, event.state, event.click)
    }

    fn block_signal(&self, host: &dyn LevelHost, event: &mut BlockSignalEvent) {
        if let Some(signal) = signal_for(host, event) {
            event.signal = signal;
        }
    }

    fn tick_block(&self, level: &mut dyn LevelWriteHost, event: &mut mod_api::TickBlockEvent) -> mod_api::Flow {
        let pos = [event.pos.x, event.pos.y, event.pos.z];
        let block = level.state_block(event.state).unwrap_or("").to_owned();
        if block == ROSE_LAMP {
            let should_power = level.has_neighbor_signal(pos);
            if should_power != powered(level, event.state, "powered") {
                let _ = set_property(level, pos, "powered", should_power);
            }
            return mod_api::Flow::Cancel;
        }
        if !DIODE_BLOCKS.contains(&block.as_str()) {
            return mod_api::Flow::Continue;
        }
        let facing = facing(level, event.state);
        let input = powered_input(level, pos, facing);
        let was_powered = powered(level, event.state, "powered");
        let was_side = powered(level, event.state, "powered_side");
        let mut output = powered(level, event.state, "powering");
        if block.starts_with("create:pulse_") {
            if input != was_powered {
                let _ = set_property(level, pos, "powered", input);
                if input {
                    output = true;
                    let _ = set_property(level, pos, "powering", true);
                    let delay = if block == "create:pulse_timer" { 20 } else { 2 };
                    let _ = level.set_block_property(
                        pos,
                        "activate",
                        "true",
                        BlockUpdateFlags::CLIENTS.bits(),
                    );
                    let _ = level.schedule_block_tick(pos, event.state.block(), delay);
                }
            } else if powered(level, event.state, "activate") {
                let _ = set_property(level, pos, "powering", false);
                let _ = level.set_block_property(
                    pos,
                    "activate",
                    "false",
                    BlockUpdateFlags::CLIENTS.bits(),
                );
            }
            let _ = output;
            return mod_api::Flow::Cancel;
        }

        let toggle = block == "create:powered_toggle_latch";
        if toggle {
            if input && !was_powered {
                output = !output;
            }
            if input != was_powered {
                let _ = set_property(level, pos, "powered", input);
            }
            if output != powered(level, event.state, "powering") {
                let _ = set_property(level, pos, "powering", output);
            }
        } else {
            let side = side_input(level, pos, facing);
            let mut next_output = output;
            if input != was_powered {
                let _ = set_property(level, pos, "powered", input);
                if input || was_side {
                    next_output = input;
                }
            }
            if side != was_side {
                let _ = set_property(level, pos, "powered_side", side);
                if side || was_powered {
                    next_output = !side;
                }
            }
            if next_output != output {
                let _ = set_property(level, pos, "powering", next_output);
            }
        }
        mod_api::Flow::Cancel
    }

    fn is_signal_source(&self, host: &dyn LevelHost, event: &mut IsSignalSourceEvent) {
        let block = block_name(host, event.state);
        event.source |= matches!(
            block.as_str(),
            ANALOG_LEVER | REDSTONE_CONTACT | ELEVATOR_CONTACT | DESK_BELL | ROSE_LAMP
                | "create:powered_latch" | "create:powered_toggle_latch"
                | "create:pulse_repeater" | "create:pulse_extender" | "create:pulse_timer"
        );
    }

    fn neighbor_changed(&self, level: &mut dyn LevelTicksHost, event: &mut mod_api::NeighborChangedEvent) {
        let block = block_name(level, event.state);
        if block != ROSE_LAMP && !DIODE_BLOCKS.contains(&block.as_str()) {
            return;
        }
        let pos = [event.pos.x, event.pos.y, event.pos.z];
        if block == ROSE_LAMP {
            let was = powered(level, event.state, "powered");
            if level.has_neighbor_signal(pos) == was {
                return;
            }
        } else if DIODE_BLOCKS.contains(&block.as_str()) {
            let input = powered_input(level, pos, &facing(level, event.state));
            let was = powered(level, event.state, "powered");
            if input == was {
                return;
            }
        }
        let _ = level.schedule_block_tick(pos, event.state.block(), 1);
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for RedstoneControls {
    fn block_entity(&self, _: mod_api::LevelSide, event: &mut mod_api::BlockEntityEvent<'_>) -> Option<Compound> {
        match event.block {
            ANALOG_LEVER => Some(Compound::from([
                ("State".into(), Tag::Int(0)),
                ("ChangeTimer".into(), Tag::Int(0)),
            ])),
            DESK_BELL => Some(Compound::from([("DingTimer".into(), Tag::Int(0))])),
            _ => None,
        }
    }

    fn block_entity_ticks(&self, _: &dyn mod_api::Host, event: &mut BlockEntityTicksEvent<'_>) {
        if matches!(event.block, ANALOG_LEVER | DESK_BELL) {
            event.ticks = true;
        }
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let block = event.entity.id().to_owned();
        let pos = event.pos;
        let nbt = &mut event.entity.nbt;
        if block == ANALOG_LEVER {
            let timer = match nbt.get(&"ChangeTimer".into()) {
                Some(Tag::Int(value)) => *value,
                _ => 0,
            };
            if timer <= 0 {
                *event.reply = mod_api::BlockEntityTickReply::Unchanged;
                return;
            }
            nbt.insert("ChangeTimer".into(), Tag::Int(timer - 1));
            if timer == 1 {
                let _ = host.set_block_property_with(
                    pos,
                    "strength",
                    &match nbt.get(&"State".into()) {
                        Some(Tag::Int(value)) => (*value).clamp(0, 15).to_string(),
                        _ => "0".into(),
                    },
                    (BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS).bits(),
                );
            }
        } else if block == DESK_BELL {
            let timer = match nbt.get(&"DingTimer".into()) {
                Some(Tag::Int(value)) => *value,
                _ => 0,
            };
            if timer <= 0 {
                *event.reply = mod_api::BlockEntityTickReply::Unchanged;
                return;
            }
            nbt.insert("DingTimer".into(), Tag::Int(timer - 1));
            if timer == 1 {
                let _ = host.set_block_property_with(
                    pos,
                    "powered",
                    "false",
                    (BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS).bits(),
                );
            }
        } else {
            *event.reply = mod_api::BlockEntityTickReply::Unchanged;
        }
    }
}
