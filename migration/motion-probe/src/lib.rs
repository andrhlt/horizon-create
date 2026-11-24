use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent,
    BlockPart, BlockState, BlockUpdateFlags, ClientHost, Compound, HostSide, ServerHost, Tag,
};

const BEARING: &str = "create:mechanical_bearing";

#[derive(Clone, Copy)]
struct MovingPart;

#[derive(Clone, Copy)]
struct GlueBox {
    low: [f64; 3],
    high: [f64; 3],
}

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
    fn glue_vector(tag: Option<&Tag>) -> Option<[f64; 3]> {
        let Some(Tag::List(values)) = tag else {
            return None;
        };
        let [Tag::Double(x), Tag::Double(y), Tag::Double(z)] = values.as_slice() else {
            return None;
        };
        Some([f64::from_bits(*x), f64::from_bits(*y), f64::from_bits(*z)])
    }

    fn glue_boxes(
        host: &mut dyn ServerHost,
        level: mod_api::LevelRef,
        anchor: [i32; 3],
    ) -> Vec<GlueBox> {
        let Some(entities) = level.special_entities_in(
            host,
            [
                f64::from(anchor[0] - 4),
                f64::from(anchor[1] - 4),
                f64::from(anchor[2] - 4),
            ],
            [
                f64::from(anchor[0] + 5),
                f64::from(anchor[1] + 5),
                f64::from(anchor[2] + 5),
            ],
        ) else {
            return Vec::new();
        };
        entities
            .into_iter()
            .filter_map(|entity| {
                let kind = entity.kind(host).map(|kind| kind.id(host));
                let data = entity.nbt(host)?;
                let is_marker = data.get(&"CreateSuperGlue".into()) == Some(&Tag::Byte(1));
                if kind.as_deref() != Some("create:super_glue") && !is_marker {
                    return None;
                }
                let from = Self::glue_vector(data.get(&"From".into()))?;
                let to = Self::glue_vector(data.get(&"To".into()))?;
                let position = entity.position(host)?;
                Some(GlueBox {
                    low: std::array::from_fn(|axis| position[axis] + from[axis].min(to[axis])),
                    high: std::array::from_fn(|axis| position[axis] + from[axis].max(to[axis])),
                })
            })
            .collect()
    }

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
        dismount_at: Option<[f64; 3]>,
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
        let Some(target) = dismount_at.or_else(|| {
            (delta != [0.0; 3]).then_some([px + delta[0], py + delta[1], pz + delta[2]])
        }) else {
            // Angular motion can round to the same block for several ticks. It
            // is still moving continuously, so a zero block delta is not a
            // dismount request and must leave the rider in place.
            return;
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
            if dismount_at.is_some() {
                entity.insert("RiderSafeDismount".into(), Tag::Byte(1));
            }
        }
    }

    fn payload_snapshots(entity: &Compound) -> Option<Vec<Compound>> {
        let Some(Tag::List(blocks)) = entity.get(&"PayloadBlocks".into()) else {
            return None;
        };
        Some(
            blocks
                .iter()
                .filter_map(|block| match block {
                    Tag::Compound(block) => Some(block.clone()),
                    _ => None,
                })
                .collect(),
        )
    }

    fn payload_positions(entity: &Compound) -> Option<Vec<[i32; 3]>> {
        let Some(Tag::List(positions)) = entity.get(&"PayloadPositions".into()) else {
            return None;
        };
        Some(
            positions
                .iter()
                .filter_map(|position| match position {
                    Tag::IntArray(position) if position.len() == 3 => {
                        Some([position[0], position[1], position[2]])
                    }
                    _ => None,
                })
                .collect(),
        )
    }

    fn snapshot_relative(snapshot: &Compound) -> Option<[i32; 3]> {
        match snapshot.get(&"Pos".into()) {
            Some(Tag::IntArray(pos)) if pos.len() == 3 => Some([pos[0], pos[1], pos[2]]),
            _ => None,
        }
    }

    fn snapshot_state(host: &dyn ServerHost, snapshot: &Compound) -> Option<BlockState> {
        let Some(Tag::String(state)) = snapshot.get(&"State".into()) else {
            return None;
        };
        host.block_state_id(&state.to_string_lossy())
    }

    fn snapshot_entity(snapshot: &Compound) -> Option<Compound> {
        match snapshot.get(&"Entity".into()) {
            Some(Tag::Compound(entity)) => Some(entity.clone()),
            _ => None,
        }
    }

    fn snapshot_block(
        host: &dyn ServerHost,
        level: mod_api::LevelRef,
        position: [i32; 3],
        anchor: [i32; 3],
    ) -> Option<Compound> {
        let state = level.block_state(host, position)?;
        let state = host.block_state_string(state)?;
        let mut snapshot = Compound::from([
            (
                "Pos".into(),
                Tag::IntArray(
                    position
                        .into_iter()
                        .zip(anchor)
                        .map(|(value, origin)| value - origin)
                        .collect(),
                ),
            ),
            ("State".into(), Tag::String(state.as_str().into())),
        ]);
        if let Some(block_entity) = host.block_entity_identity(level, position)
            && let Some(data) = block_entity.data(host)
        {
            snapshot.insert("Entity".into(), Tag::Compound(data));
        }
        Some(snapshot)
    }

    fn ensure_payload(
        &self,
        host: &mut dyn ServerHost,
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
        if entity.contains_key(&"PayloadPositions".into()) {
            return;
        }
        let Some(air) = host.block_key("minecraft:air") else {
            return;
        };
        let candidates = [
            [pos[0], pos[1] + 1, pos[2]],
            [pos[0] + 1, pos[1] + 1, pos[2]],
            [pos[0] - 1, pos[1] + 1, pos[2]],
            [pos[0], pos[1] + 1, pos[2] + 1],
            [pos[0], pos[1] + 1, pos[2] - 1],
        ];
        let glue = Self::glue_boxes(host, level, pos);
        let mut snapshots = Vec::new();
        let mut positions = Vec::new();
        for candidate in candidates {
            let Some(block) = level.block(host, candidate) else {
                continue;
            };
            if block == air {
                continue;
            }
            if let Some(snapshot) = Self::snapshot_block(host, level, candidate, pos) {
                positions.push(candidate);
                snapshots.push(snapshot);
            }
        }
        let mut index = 0;
        while index < positions.len() {
            let current = positions[index];
            for neighbor in [
                [current[0] + 1, current[1], current[2]],
                [current[0] - 1, current[1], current[2]],
                [current[0], current[1] + 1, current[2]],
                [current[0], current[1] - 1, current[2]],
                [current[0], current[1], current[2] + 1],
                [current[0], current[1], current[2] - 1],
            ] {
                if positions.contains(&neighbor)
                    || !glue.iter().any(|area| {
                        let contains = |position: [i32; 3]| {
                            (0..3).all(|axis| {
                                let center = f64::from(position[axis]) + 0.5;
                                center >= area.low[axis] && center < area.high[axis]
                            })
                        };
                        contains(current) && contains(neighbor)
                    })
                {
                    continue;
                }
                let Some(block) = level.block(host, neighbor) else {
                    continue;
                };
                if block == air {
                    continue;
                }
                let Some(snapshot) = Self::snapshot_block(host, level, neighbor, pos) else {
                    continue;
                };
                positions.push(neighbor);
                snapshots.push(snapshot);
            }
            index += 1;
        }
        let Some(first) = positions.first().copied() else {
            return;
        };
        entity.insert(
            "PayloadBlocks".into(),
            Tag::List(snapshots.into_iter().map(Tag::Compound).collect()),
        );
        entity.insert(
            "PayloadPositions".into(),
            Tag::List(
                positions
                    .iter()
                    .map(|position| Tag::IntArray(position.to_vec()))
                    .collect(),
            ),
        );
        entity.insert("PayloadPos".into(), Tag::IntArray(first.to_vec()));
        entity.insert("PayloadOrigin".into(), Tag::IntArray(first.to_vec()));
        entity.insert("PayloadAnchor".into(), Tag::IntArray(pos.to_vec()));
        entity.insert("PayloadSource".into(), Tag::String("world_blocks".into()));
        if let Some(dimension) = level.dimension().id(host) {
            entity.insert(
                "PayloadDimension".into(),
                Tag::String(dimension.as_str().into()),
            );
        }
        for position in positions {
            self.capture_standing_rider(host, level, position, entity);
        }
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
        let snapshots = Self::payload_snapshots(&data).unwrap_or_default();
        let positions = Self::payload_positions(&data).unwrap_or_else(|| {
            match data.get(&"PayloadPos".into()) {
                Some(Tag::IntArray(pos)) if pos.len() == 3 => vec![[pos[0], pos[1], pos[2]]],
                _ => vec![[event.pos[0], event.pos[1] + 1, event.pos[2]]],
            }
        });
        if snapshots.is_empty() || snapshots.len() != positions.len() {
            return;
        }
        let payload_pos = positions[0];
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
        let anchor = match data.get(&"PayloadAnchor".into()) {
            Some(Tag::IntArray(pos)) if pos.len() == 3 => [pos[0], pos[1], pos[2]],
            _ => event.pos,
        };
        let next_positions: Vec<_> = snapshots
            .iter()
            .zip(&positions)
            .filter_map(|(snapshot, current)| {
                let relative = Self::snapshot_relative(snapshot)?;
                Some(if powered {
                    Self::rotate_position(
                        [
                            anchor[0] + relative[0],
                            anchor[1] + relative[1],
                            anchor[2] + relative[2],
                        ],
                        anchor,
                        next_angle.to_radians(),
                    )
                } else {
                    [current[0], current[1] + 1, current[2]]
                })
            })
            .collect();
        if next_positions.len() != snapshots.len() {
            return;
        }
        let duplicate_target = next_positions
            .iter()
            .enumerate()
            .any(|(index, target)| next_positions[..index].contains(target));
        let blocked = duplicate_target
            || next_positions.iter().any(|next_pos| {
                !positions.contains(next_pos)
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
                        .unwrap_or(false)
            });
        data.insert("CollisionBlocked".into(), Tag::Byte(blocked as i8));
        let moving = scroll.is_some_and(|value| value != 0) || (!powered && offset < 8);
        if !blocked && moving {
            let Some(states) = snapshots
                .iter()
                .map(|snapshot| Self::snapshot_state(host, snapshot))
                .collect::<Option<Vec<_>>>()
            else {
                return;
            };
            for position in &positions {
                if !level.remove_block(host, *position, true) {
                    return;
                }
            }
            for (index, (next_pos, state)) in next_positions.iter().zip(&states).enumerate() {
                if !level
                    .set_block(
                        host,
                        *next_pos,
                        *state,
                        BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
                    )
                    .is_ok_and(|changed| changed)
                {
                    for position in &next_positions[..index] {
                        let _ = level.remove_block(host, *position, true);
                    }
                    for (old_pos, old_state) in positions.iter().zip(&states) {
                        let _ = level.set_block(
                            host,
                            *old_pos,
                            *old_state,
                            BlockUpdateFlags::NEIGHBORS | BlockUpdateFlags::CLIENTS,
                        );
                    }
                    return;
                }
                if let Some(next_entity) = host.block_entity_identity(level, *next_pos)
                    && let Some(entity_data) = Self::snapshot_entity(&snapshots[index])
                {
                    let _ = next_entity.merge_data(host, entity_data);
                }
            }
            data.insert(
                "PayloadPositions".into(),
                Tag::List(
                    next_positions
                        .iter()
                        .map(|position| Tag::IntArray(position.to_vec()))
                        .collect(),
                ),
            );
            data.insert(
                "PayloadPos".into(),
                Tag::IntArray(next_positions[0].to_vec()),
            );
            data.insert("MotionOffset".into(), Tag::Int(offset + 1));
            if powered {
                data.insert("Angle".into(), Tag::Float((next_angle as f32).to_bits()));
            }
            self.move_rider(
                host,
                &mut data,
                [
                    f64::from(next_positions[0][0] - payload_pos[0]),
                    f64::from(next_positions[0][1] - payload_pos[1]),
                    f64::from(next_positions[0][2] - payload_pos[2]),
                ],
                None,
            );
        } else {
            data.insert("Moving".into(), Tag::Byte(0));
            data.insert("Disassembled".into(), Tag::Byte(1));
            self.move_rider(
                host,
                &mut data,
                [0.0; 3],
                Some([
                    f64::from(payload_pos[0]) + 0.5,
                    f64::from(payload_pos[1] + 1),
                    f64::from(payload_pos[2]) + 0.5,
                ]),
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
