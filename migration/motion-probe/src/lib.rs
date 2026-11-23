use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent,
    BlockState, BlockUpdateFlags, Compound, HostBlockStates, HostSide, ServerHost, Tag,
};

const BEARING: &str = "create:mechanical_bearing";

#[derive(Clone, Copy)]
struct MovingPart;

fn payload() -> Compound {
    Compound::from([
        (
            "PayloadBlocks".into(),
            Tag::List(vec![Tag::Compound(Compound::from([
                ("Name".into(), Tag::String("minecraft:chest".into())),
                ("Pos".into(), Tag::IntArray(vec![0, 0, 0])),
            ]))]),
        ),
        (
            "PayloadItems".into(),
            Tag::List(vec![Tag::Compound(Compound::from([
                ("Item".into(), Tag::String("minecraft:iron_ingot".into())),
                ("Count".into(), Tag::Int(7)),
            ]))]),
        ),
        ("Rider".into(), Tag::IntArray(vec![1, 2, 3, 4])),
        ("MotionOffset".into(), Tag::Int(0)),
        ("Moving".into(), Tag::Byte(1)),
    ])
}

impl MovingPart {
    fn ensure_payload(
        &self,
        host: &dyn mod_api::Host,
        level: mod_api::LevelRef,
        pos: [i32; 3],
        entity: &mut Compound,
    ) {
        if !entity.contains_key(&"PayloadBlocks".into()) {
            let initial = payload();
            for (key, value) in initial {
                entity.insert(key, value);
            }
        }
        if entity.contains_key(&"PayloadPos".into()) {
            return;
        }
        let Some(chest) = host.block_key("minecraft:chest") else {
            return;
        };
        let attached = [pos[0], pos[1] + 1, pos[2]];
        if level.block(host, attached) != Some(chest) {
            return;
        }
        let Some(block_entity) = host.block_entity_identity(level, attached) else {
            return;
        };
        let Some(chest_data) = block_entity.data(host) else {
            return;
        };
        entity.insert("PayloadPos".into(), Tag::IntArray(attached.to_vec()));
        entity.insert("PayloadEntity".into(), Tag::Compound(chest_data));
        entity.insert("PayloadSource".into(), Tag::String("world_chest".into()));
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for MovingPart {
    fn block_entity_update_tag(
        &self,
        event: &mut mod_api::BlockEntityUpdateTagEvent<'_>,
    ) -> Option<Compound> {
        Some(event.entity.nbt.clone())
    }

    fn block_entity_on_load(&self, side: HostSide<'_>, event: &mut BlockEntityOnLoadEvent) {
        let HostSide::Server(host) = side else { return };
        let mut data = event.entity.nbt.clone();
        let Some(level) = event.entity.level(host) else {
            return;
        };
        let Some(pos) = event.entity.position(host) else {
            return;
        };
        self.ensure_payload(host, level, pos, &mut data);
        event.entity.nbt = data.clone();
        let _ = event.entity.merge_data(host, data);
    }

    fn block_entity_ticks(&self, _: &dyn mod_api::Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let Some(level) = event.entity.level(host) else {
            return;
        };
        let mut data = event.entity.nbt.clone();
        self.ensure_payload(host, level, event.pos, &mut data);
        let offset = match data.get(&"MotionOffset".into()) {
            Some(Tag::Int(value)) => *value,
            _ => 0,
        };
        let payload_pos = match data.get(&"PayloadPos".into()) {
            Some(Tag::IntArray(pos)) if pos.len() == 3 => [pos[0], pos[1], pos[2]],
            _ => [event.pos[0], event.pos[1] + 1, event.pos[2]],
        };
        let next_pos = [payload_pos[0], payload_pos[1] + 1, payload_pos[2]];
        let blocked = host
            .level_has_collisions(
                level,
                [
                    f64::from(next_pos[0]),
                    f64::from(next_pos[1]),
                    f64::from(next_pos[2]),
                    f64::from(next_pos[0] + 1),
                    f64::from(next_pos[1] + 1),
                    f64::from(next_pos[2] + 1),
                ],
            )
            .unwrap_or(false);
        data.insert("CollisionBlocked".into(), Tag::Byte(blocked as i8));
        if !blocked && offset < 8 && data.contains_key(&"PayloadPos".into()) {
            let Some(chest) = host.block_key("minecraft:chest") else {
                return;
            };
            let Ok(chest_state) = BlockState::of(&host.block_states(), chest, &[]) else {
                return;
            };
            let Some(Tag::Compound(chest_data)) = data.get(&"PayloadEntity".into()) else {
                return;
            };
            if !host.level_remove_block(level, payload_pos, true) {
                return;
            }
            if !host
                .level_set_block(
                    level,
                    next_pos,
                    chest_state,
                    BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
                )
                .is_ok_and(|changed| changed)
            {
                let _ = host.level_set_block(
                    level,
                    payload_pos,
                    chest_state,
                    BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
                );
                return;
            }
            if let Some(next_entity) = host.block_entity_identity(level, next_pos) {
                let _ = next_entity.merge_data(host, chest_data.clone());
            }
            data.insert("PayloadPos".into(), Tag::IntArray(next_pos.to_vec()));
            data.insert("MotionOffset".into(), Tag::Int(offset + 1));
        } else {
            data.insert("Moving".into(), Tag::Byte(0));
            data.insert("Disassembled".into(), Tag::Byte(1));
            data.insert("RiderSafeDismount".into(), Tag::Byte(1));
        }
        event.entity.nbt = data;
    }
}

#[derive(Default)]
struct Mod;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Mod {
    fn register(&self, registrar: &mut dyn mod_api::Registrar, _: &mod_api::RegistrationContext) {
        let kind = registrar
            .block_entity_type("create:mechanical_bearing")
            .blocks(&[BEARING])
            .build();
        registrar.block_entity_part(&kind, MovingPart).unwrap();
    }
}
