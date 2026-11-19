// Opt-in fixture control through the same storage operations used by gameplay.
fn tank_script_control(
    game: &mut crate::game::Game<'_>,
    line: &str,
) -> std::ops::ControlFlow<Result<Option<Value>>> {
    if std::env::var_os("CREATE_TANK_SCRIPT_CONTROL").is_none() {
        return std::ops::ControlFlow::Continue(());
    }
    let Some(payload) = line.strip_prefix("create-test-tank-script ") else {
        return std::ops::ControlFlow::Continue(());
    };
    fn apply(
        game: &mut crate::game::Game<'_>,
        action: &Value,
    ) -> std::result::Result<Value, String> {
        use crate::game::create_fluids::Fluid;
        use horizon_world::nbt::{Compound, Tag};
        fn position(value: &Value) -> std::result::Result<[i32; 3], String> {
            serde_json::from_value(value.clone()).map_err(|e| e.to_string())
        }
        fn tag(value: &Value) -> std::result::Result<Tag, String> {
            Ok(match value {
                Value::Bool(v) => Tag::Byte(i8::from(*v)),
                Value::Number(v) if v.is_i64() => {
                    let n = v.as_i64().ok_or("invalid integer")?;
                    if let Ok(n) = i32::try_from(n) {
                        Tag::Int(n)
                    } else {
                        Tag::Long(n)
                    }
                }
                Value::Number(v) => Tag::Double(v.as_f64().ok_or("invalid number")?.to_bits()),
                Value::String(v) => Tag::String(v.as_str().into()),
                Value::Array(v) => {
                    Tag::List(v.iter().map(tag).collect::<std::result::Result<_, _>>()?)
                }
                Value::Object(v) => Tag::Compound(
                    v.iter()
                        .map(|(k, v)| Ok((k.as_str().into(), tag(v)?)))
                        .collect::<std::result::Result<Compound, String>>()?,
                ),
                Value::Null => return Err("null is not an NBT component value".into()),
            })
        }
        fn json_tag(value: &Tag) -> Value {
            match value {
                Tag::Byte(v) => serde_json::json!(*v),
                Tag::Short(v) => serde_json::json!(*v),
                Tag::Int(v) => serde_json::json!(*v),
                Tag::Long(v) => serde_json::json!(*v),
                Tag::Float(v) => serde_json::json!(f32::from_bits(*v)),
                Tag::Double(v) => serde_json::json!(f64::from_bits(*v)),
                Tag::String(v) => serde_json::json!(v.to_string_lossy()),
                Tag::List(v) => Value::Array(v.iter().map(json_tag).collect()),
                Tag::Compound(v) => Value::Object(
                    v.iter()
                        .map(|(k, v)| (k.to_string_lossy(), json_tag(v)))
                        .collect(),
                ),
                Tag::ByteArray(v) => serde_json::json!(v),
                Tag::IntArray(v) => serde_json::json!(v),
                Tag::LongArray(v) => serde_json::json!(v),
                Tag::End => Value::Null,
            }
        }
        fn components(value: &Value) -> std::result::Result<Option<Compound>, String> {
            if value.is_null() {
                return Ok(None);
            }
            match tag(value)? {
                Tag::Compound(v) if v.is_empty() => Ok(None),
                Tag::Compound(v) => Ok(Some(v)),
                _ => Err("components must be an object".into()),
            }
        }
        fn fluid(action: &Value) -> std::result::Result<Fluid, String> {
            let id = action["fluid"].as_str().ok_or("missing fluid")?;
            let amount: i32 =
                serde_json::from_value(action["amount"].clone()).map_err(|e| e.to_string())?;
            if amount < 0 {
                return Err("negative amount".into());
            }
            Ok(Fluid {
                id: id.into(),
                amount,
                components: components(&action["components"])?,
            })
        }
        let include_components = action["include_components"].as_bool().unwrap_or(false);
        match action["op"].as_str() {
            Some("inventory") => {
                let item = |stack: &crate::items::ItemStack| {
                    let mut value = json_tag(&crate::game::create_depot::encode(stack));
                    if let Some(map) = value.as_object_mut() { map.remove("Slot"); }
                    value
                };
                let held = game.held().map_or(Value::Null, &item);
                let inventory: Vec<_> = game.inventory.iter().enumerate()
                    .filter(|(slot, _)| *slot != game.selected)
                    .filter_map(|(slot, stack)| stack.as_ref().map(|stack| serde_json::json!({"slot": slot, "item": item(stack)})))
                    .collect();
                Ok(serde_json::json!({"ok":true, "held":held, "inventory":inventory}))
            }
            Some("world_light") => {
                let pos = position(&action["pos"])?;
                let (block, sky) = game.native_light(pos);
                Ok(serde_json::json!({"ok": true, "block": block, "sky": sky}))
            }
            Some("probe") => {
                let positions = action["positions"].as_array().ok_or("missing positions")?;
                let mut rows = Vec::new();
                for value in positions {
                    let pos = position(value)?;
                    let block = game.native_block(pos);
                    let storage = crate::game::create_fluid_tank::storage(game, pos);
                    let (controller, capacity, stored) = match storage {
                        Some((_root, capacity, fluid)) => (crate::game::create_fluid_tank::controller(game, pos), capacity, fluid),
                        None => (None, 0, None),
                    };
                    let (capacity, stored) = if controller.is_some_and(|root| crate::game::create_steam::accepts_water(game, root)) {
                        (10000, None)
                    } else { (capacity, stored) };
                    let (id, amount) = stored
                        .as_ref()
                        .map_or(("minecraft:empty", 0), |f| (f.id.as_str(), f.amount));
                    let mut row = serde_json::json!({"pos": pos, "block": block,
                        "controller": controller, "capacity": capacity, "fluid": id, "amount": amount});
                    if action["include_shape"].as_bool().unwrap_or(false) {
                        row["shape"] = game.native_block_property(pos, "shape").map_or(Value::Null, Value::String);
                    }
                    if action["include_block_light"].as_bool().unwrap_or(false) {
                        row["block_light"] = serde_json::json!(game.native_light(pos).0);
                    }
                    if action["include_signals"].as_bool().unwrap_or(false) {
                        let light = game.native_dynamic_emission(pos).unwrap_or(0);
                        let comparator = game.with_level(|_, level, _| {
                            let state = level.world.block(pos[0], pos[1], pos[2]);
                            let mut output = 0;
                            level.native_analog_output(level.dimension,
                                horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]), state,
                                horizon_core::geometry::Direction::North, &mut output);
                            output.clamp(0, 15)
                        });
                        row["light"] = serde_json::json!(light);
                        row["comparator"] = serde_json::json!(comparator);
                    }
                    if include_components {
                        row["components"] = stored
                            .as_ref()
                            .and_then(|f| f.components.as_ref())
                            .map_or(Value::Null, |c| json_tag(&Tag::Compound(c.clone())));
                    }
                    rows.push(row);
                }
                Ok(serde_json::json!({"ok": true, "rows": rows}))
            }
            Some(op @ ("fill" | "drain" | "configure")) => {
                let pos = position(&action["pos"])?;
                let (root, capacity, mut stored) =
                    crate::game::create_fluid_tank::storage(game, pos).ok_or("missing tank")?;
                let creative = game.native_block(root) == crate::game::create_fluid_tank::CREATIVE;
                let boiler = crate::game::create_steam::accepts_water(game, root);
                let execute = !action["simulate"].as_bool().unwrap_or(false);
                let mut changed = false;
                let result = match op {
                    "fill" => {
                        let incoming = fluid(action)?;
                        let accepted = if boiler {
                            crate::game::create_steam::boiler_fill(game, root, &incoming.id, incoming.amount, execute)
                        } else {
                            crate::game::create_tank_storage::fill(&mut stored, capacity, creative, &incoming, execute)
                        };
                        changed = execute && !creative && !boiler && accepted > 0;
                        serde_json::json!({"ok": true, "accepted": accepted})
                    }
                    "drain" => {
                        let amount: i32 = serde_json::from_value(action["amount"].clone())
                            .map_err(|e| e.to_string())?;
                        if amount < 0 {
                            return Err("negative amount".into());
                        }
                        let requested = if action["fluid"].is_null() {
                            None
                        } else {
                            Some(fluid(action)?)
                        };
                        let drained = if boiler { None } else {
                            crate::game::create_tank_storage::drain(&mut stored, creative, amount, requested.as_ref(), execute)
                        };
                        changed = execute && !creative && drained.is_some();
                        let (id, amount) = drained
                            .as_ref()
                            .map_or(("minecraft:empty", 0), |f| (f.id.as_str(), f.amount));
                        let mut row =
                            serde_json::json!({"ok": true, "fluid": id, "amount": amount});
                        if include_components {
                            row["components"] = drained
                                .as_ref()
                                .and_then(|f| f.components.as_ref())
                                .map_or(Value::Null, |c| json_tag(&Tag::Compound(c.clone())));
                        }
                        row
                    }
                    _ => {
                        if !creative {
                            return Err("configure requires a creative tank".into());
                        }
                        let incoming = fluid(action)?;
                        let configured = (incoming.id != "minecraft:empty" && incoming.amount > 0)
                            .then_some(incoming);
                        crate::game::create_tank_storage::configure(
                            &mut stored,
                            capacity,
                            configured,
                        );
                        changed = true;
                        serde_json::json!({"ok": true})
                    }
                };
                if changed {
                    let written = stored.unwrap_or(Fluid {
                        id: "minecraft:empty".into(),
                        amount: 0,
                        components: None,
                    });
                    crate::game::create_fluid_tank::write(game, root, written);
                }
                Ok(result)
            }
            _ => Err("unsupported tank fixture control operation".into()),
        }
    }
    let mut run = || -> Result<Option<Value>> {
        game.require_world()?;
        let action: Value = serde_json::from_str(payload)?;
        let value = if action["op"].as_str() == Some("inventory") {
            apply(game, &action)?
        } else if let Some(server) = &game.integrated {
            server
                .call(move |g| g.in_owner_level(|g| apply(g, &action)))
                .ok_or(super::integrated::NO_ANSWER)??
        } else {
            apply(game, &action)?
        };
        Ok(Some(value))
    };
    std::ops::ControlFlow::Break(run())
}
