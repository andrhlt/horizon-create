fn legacy_material_float(game: &mut crate::game::Game<'_>) {
    use std::sync::{Mutex, OnceLock};

    use crate::game::ItemStack;
    use horizon_core::{
        geometry::Vec3,
        random::{LegacyRandom, RandomSource},
    };
    use horizon_world::level::flags;
    use horizon_world::nbt::{Compound, Tag};

    if !game.native_authoritative() {
        return;
    }
    const COMPOUND: &str = "create:chromatic_compound";
    const SHADOW: &str = "create:shadow_steel";
    const RADIANCE: &str = "create:refined_radiance";
    const COLLECTED_LIGHT: &str = "create:chromatic_compound_collecting_light";
    const LIGHT_THRESHOLD: i32 = 10;
    let min_y = f64::from(game.level_min_y());
    let ticking = game.entity_ticking_area();
    let through = game.ticked_entities_through;
    let mut consumed = Vec::new();
    for index in 0..game.dropped.len() {
        let item = &game.dropped[index];
        let id = item.stack.item.as_ref();
        if !matches!(id, COMPOUND | SHADOW | RADIANCE)
            || item.stack.count == 0
            || item.id > through
            || game.contact_drops.contains(&item.id)
            || !ticking(
                item.position.x.floor() as i32,
                item.position.z.floor() as i32,
            )
        {
            continue;
        }
        let compound = id == COMPOUND;
        let radiance = id == RADIANCE;
        let conversion = if compound {
            let at = item.position;
            let y = at.y;
            let charge = match item
                .stack
                .data()
                .and_then(|data| data.other(COLLECTED_LIGHT))
            {
                Some(Tag::Int(charge)) => *charge,
                _ => 0,
            };
            if y < min_y && y - item.velocity.y < min_y - 10.0 {
                Some(SHADOW)
            } else if charge >= LIGHT_THRESHOLD {
                let motion = item.velocity;
                let item = &mut game.dropped[index];
                item.stack.count -= 1;
                if item.stack.count == 0 {
                    consumed.push(index);
                } else {
                    item.stack.data_mut().set_other(COLLECTED_LIGHT, None);
                    item.needs_sync = true;
                }
                let before = game.next_entity;
                game.spawn_item(
                    ItemStack::new(RADIANCE, 1),
                    [at.x, at.y, at.z],
                    [motion.x, motion.y, motion.z],
                    0,
                );
                if game.next_entity != before && game.just_spawned_item().is_some() {
                    let data = Compound::from([("JustCreated".into(), Tag::Byte(1))]);
                    game.persist.raw.insert(
                        game.next_entity,
                        Tag::Compound(Compound::from([(
                            "NeoForgeData".into(),
                            Tag::Compound(data),
                        )])),
                    );
                }
                continue;
            } else if in_beacon_beam(game, at) {
                Some(RADIANCE)
            } else {
                if collect_sampled_light(game, at) {
                    let item = &mut game.dropped[index];
                    let mut charged = item.stack.clone();
                    charged.count = 1;
                    charged
                        .data_mut()
                        .set_other(COLLECTED_LIGHT, Some(Tag::Int(charge + 1)));
                    item.stack.count -= 1;
                    if item.stack.count == 0 {
                        consumed.push(index);
                    } else {
                        item.needs_sync = true;
                    }
                    let motion = item.velocity;
                    game.spawn_item(
                        charged,
                        [at.x, at.y, at.z],
                        [motion.x, motion.y, motion.z],
                        10,
                    );
                }
                continue;
            }
        } else {
            None
        };
        let item = &mut game.dropped[index];
        let raw = game
            .persist
            .raw
            .entry(item.id)
            .or_insert_with(|| Tag::Compound(Compound::new()));
        let Tag::Compound(data) = raw else {
            continue;
        };
        if let Some(output) = conversion {
            let data = data
                .entry("NeoForgeData".into())
                .or_insert_with(|| Tag::Compound(Compound::new()));
            if let Tag::Compound(data) = data {
                data.insert("JustCreated".into(), Tag::Byte(1));
                item.stack = ItemStack::new(output, item.stack.count);
                item.needs_sync = true;
            }
            continue;
        }

        item.no_gravity = true;
        data.insert("NoGravity".into(), Tag::Byte(1));
        let just_created = match data.get_mut(&"NeoForgeData".into()) {
            Some(Tag::Compound(forge)) => forge.remove(&"JustCreated".into()).is_some(),
            _ => false,
        };
        if just_created {
            if radiance {
                item.velocity.y += 0.25;
            } else {
                item.velocity = Vec3::new(
                    0.0,
                    f64::from((item.fall_distance as f32 + 3.0) / 50.0),
                    0.0,
                );
            }
            item.needs_sync = true;
            data.insert("Silent".into(), Tag::Byte(1));
        }
    }

    for index in consumed.into_iter().rev() {
        game.remove_dropped(index);
    }

    fn collect_sampled_light(game: &mut crate::game::Game<'_>, at: Vec3) -> bool {
        fn sampled_block(random: &mut impl RandomSource, at: Vec3) -> Option<[i32; 3]> {
            if random.next_float() > 0.5 {
                return None;
            }
            Some([at.x, at.y, at.z].map(|position| {
                let offset = (random.next_float() - 0.5) * 6.0;
                (position + f64::from(offset)).floor() as i32
            }))
        }

        static FIXTURE: OnceLock<Option<Mutex<LegacyRandom>>> = OnceLock::new();
        let fixture = FIXTURE.get_or_init(|| {
            let seed = std::env::var("CREATE_RADIANCE_TRACE_SEED")
                .ok()?
                .parse()
                .ok()?;
            Some(Mutex::new(LegacyRandom::new(seed)))
        });
        let sample = match fixture {
            Some(random) => sampled_block(&mut *random.lock().expect("radiance fixture RNG"), at),
            None => sampled_block(&mut game.world.random, at),
        };
        let Some([x, y, z]) = sample else {
            return false;
        };
        if game.native_block([x, y, z]) == crate::game::create_depot::DEPOT {
            return collect_light_from_transport(game, at, [x, y, z]);
        }
        collect_placed_light_at(game, at, [x, y, z])
    }

    fn collect_placed_light_at(game: &mut crate::game::Game<'_>, at: Vec3, pos: [i32; 3]) -> bool {
        let [x, y, z] = pos;
        let state = game.res.facts().get(game.world.block(x, y, z));
        if state.emission == 0
            || state.hardness == -1.0
            || state.name.as_ref() == "minecraft:beacon"
        {
            return false;
        }
        let eye = Vec3::new(at.x, at.y + 0.5, at.z);
        let target = Vec3::new(f64::from(x) + 0.5, f64::from(y) + 0.5, f64::from(z) + 0.5);
        if game.mob_world_base(&[]).clip_block_at(eye, target) != Some(pos) {
            return false;
        }
        let Some(air) = game.pack.assets.registry.default_state("minecraft:air") else {
            return false;
        };
        game.native_set_block(game.native_dimension(), pos, air, flags::UPDATE_ALL)
    }

    fn collect_light_from_transport(
        game: &mut crate::game::Game<'_>,
        at: Vec3,
        pos: [i32; 3],
    ) -> bool {
        let Some(light) = crate::game::create_machines::mod_entity(game, pos)
            .and_then(|entity| entity.items.first().and_then(Option::as_ref))
            .filter(|stack| stack.count > 0)
            .cloned()
        else {
            return false;
        };
        let Some(state) = game.native_default_state(&light.item) else {
            return false;
        };
        let facts = game.res.facts().get(state);
        if facts.emission == 0 || facts.hardness == -1.0 {
            return false;
        }
        let eye = Vec3::new(at.x, at.y + 0.5, at.z);
        let target = Vec3::new(
            f64::from(pos[0]) + 0.5,
            f64::from(pos[1]) + 0.5,
            f64::from(pos[2]) + 0.5,
        );
        if game.mob_world_base(&[]).clip_block_at(eye, target) != Some(pos) {
            return false;
        }

        let consumed = game.native_with_mod_block_entity(pos, |depot| {
            let Some(Some(stack)) = depot.items.first_mut() else {
                return false;
            };
            if stack.item != light.item || stack.count == 0 {
                return false;
            }
            stack.count -= 1;
            if stack.count == 0 {
                depot.items[0] = None;
            }
            true
        }) == Some(true);
        if !consumed {
            return false;
        }
        game.native_block_entity_sync(pos);
        true
    }

    fn in_beacon_beam(game: &crate::game::Game<'_>, at: horizon_core::geometry::Vec3) -> bool {
        use horizon_client::containers::BlockEntity;

        let x = at.x.floor() as i32;
        let z = at.z.floor() as i32;
        let top = (at.y.floor() as i32).min(game.world_surface(x, z));
        for y in (game.level_min_y()..top).rev() {
            let state = game.res.facts().get(game.world.block(x, y, z));
            if state.dampening >= 15 && state.name.as_ref() != "minecraft:bedrock" {
                return false;
            }
            if state.name.as_ref() == "minecraft:beacon" {
                return matches!(game.world.block_entities.get(&(x, y, z)),
                Some(BlockEntity::Beacon(beacon)) if !beacon.sections.is_empty());
            }
        }
        false
    }
}
