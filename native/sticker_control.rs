fn sticker_control(game: &mut crate::game::Game<'_>, line: &str) -> std::ops::ControlFlow<Result<Option<Value>>> {
    if std::env::var_os("CREATE_STICKER_TEST").is_none() { return std::ops::ControlFlow::Continue(()); }
    let Some(payload)=line.strip_prefix("create-test-sticker ") else { return std::ops::ControlFlow::Continue(()); };
    fn apply(game: &mut crate::game::Game<'_>, request: &Value) -> std::result::Result<Value,String> {
        let pos: [i32;3]=serde_json::from_value(request["pos"].clone()).map_err(|e|e.to_string())?;
        if request["op"]=="defaults" {
            let state=game.world.block(pos[0],pos[1],pos[2]);let facts=game.res.facts().get(state);
            let coeff=game.res.core.motion.blocks.get(state).map_err(|e|e.to_string())?.coefficients;
            let boxes=game.native_block_collision(pos);
            return Ok(serde_json::json!({"facing":game.native_block_state_property(state,"facing"),"powered":game.native_block_state_property(state,"powered")==Some("true"),"extended":game.native_block_state_property(state,"extended")==Some("true"),"hardness":facts.hardness,"explosion_resistance":facts.explosion_resistance,"friction":coeff.friction,"speed_factor":coeff.speed_factor,"jump_factor":coeff.jump_factor,"occludes":facts.can_occlude,"collision_full_cube":boxes==vec![[0.0,0.0,0.0,1.0,1.0,1.0]],"collision_boxes":boxes}));
        }
        if request["op"]=="interactions" {
            let mut rows=Vec::new();
            for row in request["cases"].as_array().ok_or("missing cases")? {
                let mut state=game.pack.assets.registry.state(game.pack.assets.registry.default_state("create:sticker").ok_or("missing Sticker")?).ok_or("missing state")?.clone();
                for (key,value) in [("facing",row["facing"].as_str().unwrap_or("up")),("extended","true"),("powered","true")] {state.properties.insert(key.into(),value.into());}
                let state=game.pack.assets.registry.id(&state).ok_or("missing Sticker state")?;
                game.world.set(pos[0],pos[1],pos[2],state).map_err(|e|e.to_string())?;
                if row["kind"]=="wrench" {
                    let target=horizon_core::geometry::Direction::ALL.into_iter().find(|&d|crate::game::create_fluids::name(d)==row["target"].as_str().unwrap_or("")).ok_or("invalid target")?;
                    crate::game::create_wrench::change_pose(game,pos,target,"create:sticker");
                    let state=game.world.block(pos[0],pos[1],pos[2]);
                    rows.push(serde_json::json!({"kind":"wrench","facing":row["facing"],"target":row["target"],"result":game.native_block_state_property(state,"facing"),"extended":game.native_block_state_property(state,"extended")==Some("true"),"powered":game.native_block_state_property(state,"powered")==Some("true")}));
                } else {
                    let weak=game.with_level(|_,level,_| {let mut options=(true,false);level.native_override_signal_options(state,&mut options);options.0});
                    rows.push(serde_json::json!({"kind":"weak_power","direction":row["direction"],"check":weak}));
                }
            }
            return Ok(serde_json::json!({"rows":rows}));
        }
        if request["op"]=="faces" {
            let mut rows=Vec::new();
            for row in request["cases"].as_array().ok_or("missing cases")? {
                let text=row["state"].as_str().ok_or("missing state")?;
                let (name,props)=text.split_once('[').unwrap_or((text,""));
                let id=game.pack.assets.registry.default_state(name).ok_or_else(||format!("unknown block {name}"))?;
                let mut state=game.pack.assets.registry.state(id).ok_or("missing default state")?.clone();
                for prop in props.trim_end_matches(']').split(',').filter(|s|!s.is_empty()) {
                    let (key,value)=prop.split_once('=').ok_or("invalid property")?;
                    state.properties.insert(key.into(),value.into());
                }
                let id=game.pack.assets.registry.id(&state).ok_or_else(||format!("unknown state {text}"))?;
                game.world.set(pos[0],pos[1],pos[2],id).map_err(|e|e.to_string())?;
                let side=horizon_core::geometry::Direction::ALL.into_iter().find(|&d|crate::game::create_fluids::name(d)==row["direction"].as_str().unwrap_or("")).ok_or("bad direction")?;
                let (attached,necessary,not_supportive,valid)=crate::game::create_sticker::face_checks(game,pos,side);
                rows.push(serde_json::json!({"kind":"face","state":text,"direction":row["direction"],"attached":attached,"necessary":necessary,"not_supportive":not_supportive,"valid":valid}));
            }
            return Ok(serde_json::json!({"rows":rows}));
        }
        if request["op"]=="callbacks" {
            let mut rows=Vec::new();
            let pig=game.mobs.iter().find(|m|m.kind.id=="minecraft:pig").cloned();
            for case in request["cases"].as_array().ok_or("missing cases")? {
                let mut row=case.clone();
                let upright=case["facing"]=="up";let careful=case["careful"].as_bool().unwrap_or(false);
                if case["kind"]=="physics" {
                    let velocity=[0.5,case["vy"].as_f64().ok_or("missing vy")?,0.25];
                    for (key,value) in [("bounce",horizon_world::create_sticker::bounce(velocity,upright,case["living"].as_bool().unwrap_or(false),careful)),("step",horizon_world::create_sticker::step(velocity,upright,careful))] {
                        row[key]=serde_json::json!(value.map(|v|v.to_bits().to_string()));
                    }
                } else if case["kind"]=="fall" {
                    let mut mob=pig.clone().ok_or("summon a fresh pig before fall probes")?;
                    mob.legacy_fall_damage_until_landing=true;
                    let count=horizon_world::create_sticker::fall_calls(upright,careful);
                    let mut events=Vec::new();
                    for _ in 0..count {mob.cause_fall_damage_from(case["distance"].as_f64().ok_or("missing distance")?,1.0,&mut events);}
                    row["health"]=serde_json::json!(mob.health);row["alive"]=serde_json::json!(mob.alive());row["damage_calls"]=serde_json::json!(count);
                }
                rows.push(row);
            }
            return Ok(serde_json::json!({"rows":rows}));
        }
        if request["op"]=="capture" {
            let controller:[i32;3]=serde_json::from_value(request["controller"].clone()).map_err(|e|e.to_string())?;
            let blocks=crate::game::create_bearing::capture_from(game,controller,pos,[pos]);
            let mut positions:Vec<_>=blocks.iter().map(crate::game::create_bearing::relative).collect();positions.sort();
            return Ok(serde_json::json!({"positions":positions}));
        }
        let state=game.world.block(pos[0],pos[1],pos[2]);
        Ok(serde_json::json!({"powered":game.native_block_state_property(state,"powered")==Some("true"),
            "extended":game.native_block_state_property(state,"extended")==Some("true"),
            "attached":crate::game::create_sticker::attached(game,pos)}))
    }
    let mut run=||->Result<Option<Value>> {
        game.require_world()?;
        let request:Value=serde_json::from_str(payload)?;
        let result=if let Some(server)=&game.integrated {server.call(move |g|g.in_owner_level(|g|apply(g,&request))).ok_or(super::integrated::NO_ANSWER)??}
            else {apply(game,&request)?};
        Ok(Some(result))
    };
    std::ops::ControlFlow::Break(run())
}
