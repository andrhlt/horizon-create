use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent,
    BlockPart, BlockState, BlockUpdateFlags, ClientHost, Compound, HostBlockStates, HostSide,
    ServerHost, Tag,
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
    fn rotate_position(origin: [i32; 3], anchor: [i32; 3], angle: f64) -> [i32; 3] {
        let dx = f64::from(origin[0] - anchor[0]);
        let dz = f64::from(origin[2] - anchor[2]);
        let (sin, cos) = angle.sin_cos();
        [
            (f64::from(anchor[0]) + dx * cos + dz * sin).round() as i32,
            origin[1],
            (f64::from(anchor[2]) - dx * sin + dz * cos).round() as i32,
        ]
    }

    fn motor_scroll(
        &self,
        host: &dyn ServerHost,
        level: mod_api::LevelRef,
        bearing: [i32; 3],
    ) -> Option<i32> {
        let motor = [bearing[0], bearing[1] - 1, bearing[2]];
        let motor_key = host.block_key("create:creative_motor")?;
        if level.block(host, motor) != Some(motor_key) {
            return None;
        }
        let motor_entity = host.block_entity_identity(level, motor)?;
        match motor_entity.data(host)?.get(&"ScrollValue".into()) {
            Some(Tag::Int(value)) => Some(*value),
            _ => Some(0),
        }
    }

    fn angle(data: &Compound) -> f64 {
        match data.get(&"Angle".into()) {
            Some(Tag::Float(bits)) => f64::from(f32::from_bits(*bits)),
            Some(Tag::Double(bits)) => f64::from_bits(*bits),
            _ => 0.0,
        }
    }

    fn render_angle(data: &Compound, partial: f32) -> f32 {
        let angle = Self::angle(data) as f32;
        let rpm = match data.get(&"BearingRPM".into()) {
            Some(Tag::Float(bits)) => f32::from_bits(*bits),
            _ => 0.0,
        };
        angle + rpm * 0.3 * partial
    }

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
            // A standing player can be 1/8 block below the integer payload
            // surface because a chest's collision top is 7/8 high.
            if px >= x && px < x + 1.0 && pz >= z && pz < z + 1.0 && py >= y - 0.25 && py < y + 0.25
            {
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
        delta: [f64; 3],
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
        let target = if delta == [0.0; 3] {
            dismount_at
        } else {
            [px + delta[0], py + delta[1], pz + delta[2]]
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
            if delta == [0.0; 3] {
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
        let candidates = [
            [pos[0], pos[1] + 1, pos[2]],
            [pos[0] + 1, pos[1] + 1, pos[2]],
            [pos[0] - 1, pos[1] + 1, pos[2]],
            [pos[0], pos[1] + 1, pos[2] + 1],
            [pos[0], pos[1] + 1, pos[2] - 1],
        ];
        let Some(attached) = candidates
            .into_iter()
            .find(|candidate| level.block(host, *candidate) == Some(chest))
        else {
            return;
        };
        let Some(block_entity) = host.block_entity_identity(level, attached) else {
            return;
        };
        let Some(chest_data) = block_entity.data(host) else {
            return;
        };
        entity.insert("PayloadPos".into(), Tag::IntArray(attached.to_vec()));
        entity.insert("PayloadOrigin".into(), Tag::IntArray(attached.to_vec()));
        entity.insert("PayloadAnchor".into(), Tag::IntArray(pos.to_vec()));
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

    fn block_entity_submit(
        &self,
        host: &dyn ClientHost,
        event: &mut mod_api::BlockEntitySubmitEvent<'_>,
    ) {
        if event.block != BEARING {
            return;
        }
        let Some(chest) = host.block_key("minecraft:chest") else {
            return;
        };
        let Some(Tag::IntArray(origin)) = event.entity.nbt.get(&"PayloadOrigin".into()) else {
            return;
        };
        if origin.len() != 3 {
            return;
        }
        let relative = [
            (origin[0] - event.pos[0]) as f32,
            (origin[1] - event.pos[1]) as f32,
            (origin[2] - event.pos[2]) as f32,
        ];
        event.draw.push();
        event.draw.rotate_about(
            [0.0, 1.0, 0.0],
            Self::render_angle(&event.entity.nbt, event.draw.partial()),
            [0.5; 3],
        );
        event.draw.translate(relative);
        let _ = event.draw.block(chest, &[]);
        event.draw.pop();
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
        let scroll = self.motor_scroll(host, level, event.pos);
        let powered = scroll.is_some();
        data.insert(
            "BearingRPM".into(),
            Tag::Float((scroll.unwrap_or(0) as f32).to_bits()),
        );
        let angle = Self::angle(&data);
        let next_angle = match scroll {
            Some(value) if value != 0 => angle + f64::from(value) * 360.0 / 60.0 / 20.0,
            Some(_) => angle,
            None => angle,
        };
        let next_pos = if powered {
            let origin = match data.get(&"PayloadOrigin".into()) {
                Some(Tag::IntArray(pos)) if pos.len() == 3 => [pos[0], pos[1], pos[2]],
                _ => payload_pos,
            };
            let anchor = match data.get(&"PayloadAnchor".into()) {
                Some(Tag::IntArray(pos)) if pos.len() == 3 => [pos[0], pos[1], pos[2]],
                _ => event.pos,
            };
            Self::rotate_position(origin, anchor, next_angle.to_radians())
        } else {
            [payload_pos[0], payload_pos[1] + 1, payload_pos[2]]
        };
        let blocked = next_pos != payload_pos
            && level
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
        let moving = scroll.is_some_and(|value| value != 0) || (!powered && offset < 8);
        if !blocked && moving && data.contains_key(&"PayloadPos".into()) {
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
            if powered {
                data.insert("Angle".into(), Tag::Float((next_angle as f32).to_bits()));
            }
            self.move_rider(
                host,
                &mut data,
                [
                    f64::from(next_pos[0] - payload_pos[0]),
                    f64::from(next_pos[1] - payload_pos[1]),
                    f64::from(next_pos[2] - payload_pos[2]),
                ],
                [0.0, 0.0, 0.0],
            );
        } else {
            data.insert("Moving".into(), Tag::Byte(0));
            data.insert("Disassembled".into(), Tag::Byte(1));
            self.move_rider(
                host,
                &mut data,
                [0.0; 3],
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
