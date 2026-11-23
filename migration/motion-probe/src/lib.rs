use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent,
    BlockPart, BlockState, BlockUpdateFlags, Compound, HostBlockStates, HostSide, ServerHost, Tag,
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
    fn uuid_tag(uuid: u128) -> Tag {
        Tag::IntArray(
            [
                (uuid >> 96) as i32,
                (uuid >> 64) as i32,
                (uuid >> 32) as i32,
                uuid as i32,
            ]
            .to_vec(),
        )
    }

    fn rider_uuid(entity: &Compound) -> Option<u128> {
        let Some(Tag::IntArray(uuid)) = entity.get(&"RiderUuid".into()) else {
            return None;
        };
        (uuid.len() == 4).then(|| {
            (u128::from(uuid[0] as u32) << 96)
                | (u128::from(uuid[1] as u32) << 64)
                | (u128::from(uuid[2] as u32) << 32)
                | u128::from(uuid[3] as u32)
        })
    }

    fn capture_standing_rider(
        &self,
        host: &dyn ServerHost,
        level: mod_api::LevelRef,
        payload_pos: [i32; 3],
        entity: &mut Compound,
    ) {
        if entity.contains_key(&"RiderUuid".into()) {
            return;
        }
        let Some(players) = level.online_players(host) else {
            return;
        };
        let x = f64::from(payload_pos[0]);
        let y = f64::from(payload_pos[1] + 1);
        let z = f64::from(payload_pos[2]);
        for player in players {
            let Some([px, py, pz]) = player.entity().position(host) else {
                continue;
            };
            if px >= x && px < x + 1.0 && pz >= z && pz < z + 1.0 && py >= y && py < y + 1.25 {
                entity.insert("RiderUuid".into(), Self::uuid_tag(player.uuid()));
                entity.insert("RiderCaptured".into(), Tag::Byte(1));
                return;
            }
        }
    }

    fn move_rider(
        &self,
        host: &mut dyn ServerHost,
        entity: &mut Compound,
        delta_y: f64,
        dismount_at: [f64; 3],
    ) {
        let Some(uuid) = Self::rider_uuid(entity) else {
            return;
        };
        let Some(player) = host.player(uuid) else {
            return;
        };
        let player_entity = player.entity();
        let Some([px, py, pz]) = player_entity.position(host) else {
            return;
        };
        let target = if delta_y == 0.0 {
            dismount_at
        } else {
            [px, py + delta_y, pz]
        };
        if player_entity.teleport_to(host, target, None) {
            entity.insert(
                "RiderLastPosition".into(),
                Tag::List(
                    target
                        .into_iter()
                        .map(|value| Tag::Double(value.to_bits()))
                        .collect(),
                ),
            );
            if delta_y == 0.0 {
                entity.insert("RiderSafeDismount".into(), Tag::Byte(1));
            }
        }
    }

    fn ensure_payload(
        &self,
        host: &dyn ServerHost,
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
        if let Some(dimension) = level.dimension().id(host) {
            entity.insert(
                "PayloadDimension".into(),
                Tag::String(dimension.as_str().into()),
            );
        }
        self.capture_standing_rider(host, level, attached, entity);
    }
}

#[mod_api::horizon_part]
impl BlockPart for MovingPart {}

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
        let mut data = event.entity.data(host).unwrap_or_default();
        let Some(level) = event.entity.level(host) else {
            return;
        };
        let Some(pos) = event.entity.position(host) else {
            return;
        };
        self.ensure_payload(host, level, pos, &mut data);
        if !data.contains_key(&"PayloadDimension".into()) {
            if let Some(dimension) = level.dimension().id(host) {
                data.insert(
                    "PayloadDimension".into(),
                    Tag::String(dimension.as_str().into()),
                );
            }
        }
        let _ = event.entity.merge_data(host, data);
    }

    fn block_entity_ticks(&self, _: &dyn mod_api::Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let dimension = match event.entity.nbt.get(&"PayloadDimension".into()) {
            Some(Tag::String(value)) => value.to_string_lossy(),
            _ => String::new(),
        };
        let level = host.level(&dimension).or_else(|| {
            host.levels()
                .list_levels()
                .into_iter()
                .find(|level| level.block(host, event.pos) == host.block_key(BEARING))
        });
        let Some(level) = level else { return };
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
        self.capture_standing_rider(host, level, payload_pos, &mut data);
        let next_pos = [payload_pos[0], payload_pos[1] + 1, payload_pos[2]];
        let blocked = level
            .has_collisions(
                host,
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
            let chest_data = match data.get(&"PayloadEntity".into()) {
                Some(Tag::Compound(chest_data)) => chest_data.clone(),
                _ => return,
            };
            if !level.remove_block(host, payload_pos, true) {
                return;
            }
            if !level
                .set_block(
                    host,
                    next_pos,
                    chest_state,
                    BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
                )
                .is_ok_and(|changed| changed)
            {
                let _ = level.set_block(
                    host,
                    payload_pos,
                    chest_state,
                    BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
                );
                return;
            }
            if let Some(next_entity) = host.block_entity_identity(level, next_pos) {
                let _ = next_entity.merge_data(host, chest_data);
            }
            data.insert("PayloadPos".into(), Tag::IntArray(next_pos.to_vec()));
            data.insert("MotionOffset".into(), Tag::Int(offset + 1));
            self.move_rider(host, &mut data, 1.0, [0.0, 0.0, 0.0]);
        } else {
            data.insert("Moving".into(), Tag::Byte(0));
            data.insert("Disassembled".into(), Tag::Byte(1));
            self.move_rider(
                host,
                &mut data,
                0.0,
                [
                    f64::from(payload_pos[0]) + 0.5,
                    f64::from(payload_pos[1] + 1),
                    f64::from(payload_pos[2]) + 0.5,
                ],
            );
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
