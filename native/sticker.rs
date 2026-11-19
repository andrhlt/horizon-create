use horizon_core::position::BlockPos;
use horizon_world::{level::{PlacementContext, Ticks, flags}, registry::BlockStateId};
use super::{GameLevel, create_fluids::name as direction_name};

pub(super) const STICKER: &str = "create:sticker";

pub(super) fn placement(level: &GameLevel<'_>, state: BlockStateId, context: &PlacementContext) -> Option<BlockStateId> {
    if level.native_state_block(state) != Some(STICKER) { return None; }
    let look = context.nearest_looking_direction();
    let facing = if context.sneaking { look } else { look.opposite() };
    level.native_state_with_property(state, "facing", direction_name(facing))
}

pub(super) fn neighbor(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos, state: BlockStateId) {
    if level.client_side { return; }
    let Some(info) = level.registry.state(state) else { return; };
    let was_powered = info.properties.get("powered").is_some_and(|p| p == "true");
    let extended = info.properties.get("extended").is_some_and(|p| p == "true");
    let blocks = level.behaviours;
    let powered = blocks.has_neighbor_signal(level, ticks, pos);
    if powered == was_powered { return; }
    let Some(mut next) = level.native_state_with_property(state, "powered", if powered { "true" } else { "false" }) else { return; };
    let (_, extended) = super::create_sticker_animation::neighbor(was_powered, extended, powered);
    let Some(toggled) = level.native_state_with_property(next, "extended", if extended { "true" } else { "false" }) else { return; };
    next = toggled;
    blocks.set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
}

pub(super) fn placed(level: &mut GameLevel<'_>, ticks: &mut Ticks, pos: BlockPos, state: BlockStateId) {
    let blocks = level.behaviours;
    let powered = blocks.has_neighbor_signal(level, ticks, pos);
    if powered && let Some(next) = level.native_state_with_property(state, "powered", "true") {
        blocks.set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    }
}

// Unsaved client state: Java saves no piston animation in the block entity.
use horizon_world::nbt::{Compound, Tag};
use crate::containers::{BlockEntity, ModBlockEntity};
use super::{Game, create_sticker_animation::Animation};
use super::native_block_entity_draw::BlockEntityDraw;
const HEAD: &str = "create:block/sticker/head";
const ANIMATION: &str = "CreateStickerAnimation";

fn float(tag: &Compound, name: &str) -> Option<f32> {
    if let Some(Tag::Float(value)) = tag.get(&name.into()) { Some(f32::from_bits(*value)) } else { None }
}
fn animation(entity: &ModBlockEntity, extended: bool) -> Animation {
    let Some(Tag::Compound(tag)) = entity.runtime.get(&ANIMATION.into()) else { return Animation::new(extended) };
    Animation { previous: float(tag, "Previous").unwrap_or(0.0), value: float(tag, "Value").unwrap_or(0.0),
        target: float(tag, "Target").unwrap_or(0.0), chasing: tag.get(&"Chasing".into()) == Some(&Tag::Byte(1)),
        update: tag.get(&"Update".into()) == Some(&Tag::Byte(1)) }
}
fn save_animation(entity: &mut ModBlockEntity, animation: Animation, state: BlockStateId) {
    let mut tag = Compound::new();
    for (name, value) in [("Previous", animation.previous), ("Value", animation.value), ("Target", animation.target)] {
        tag.insert(name.into(), Tag::Float(value.to_bits()));
    }
    tag.insert("Chasing".into(), Tag::Byte(i8::from(animation.chasing)));
    tag.insert("Update".into(), Tag::Byte(i8::from(animation.update)));
    tag.insert("State".into(), Tag::Int(state.0 as i32));
    entity.runtime.insert(ANIMATION.into(), Tag::Compound(tag));
}

// These are BlockMovementChecks' state-only exceptions used by SuperGlue's
// face query. Attachment itself does not require that a block be movable.
fn not_supportive(game: &Game<'_>, pos: [i32; 3], side: horizon_core::geometry::Direction) -> bool {
    use horizon_core::geometry::Direction;
    let block = game.native_block(pos);
    let face = game.native_block_property(pos, "facing");
    let is_face = face.as_deref() == Some(direction_name(side));
    if matches!(block.as_str(), "create:mechanical_drill" | "create:mechanical_saw" | "create:mechanical_bearing"
        | "create:portable_storage_interface") { return is_face; }
    if matches!(block.as_str(), "create:cart_assembler" | "create:rope_pulley") { return side == Direction::Down; }
    if matches!(block.as_str(), "create:mechanical_harvester" | "create:mechanical_plough") { return is_face; }
    if super::create_sail::is_sail(&block) {
        return face.as_deref().and_then(super::create_machines::facing_axis) == super::create_machines::facing_axis(direction_name(side));
    }
    if matches!(block.as_str(), "create:piston_extension_pole" | "create:mechanical_piston_head") {
        return face.as_deref().and_then(super::create_machines::facing_axis) != super::create_machines::facing_axis(direction_name(side));
    }
    if block == STICKER { return game.native_block_property(pos, "extended").as_deref() != Some("true") && is_face; }
    if game.block_in_tag("minecraft:wool_carpets", &block) { return side == Direction::Up; }
    if block.ends_with("_door") && block.starts_with("create:") {return false;}
    brittle(game,pos)
}
fn brittle(game: &Game<'_>, pos: [i32;3]) -> bool {
    let block=game.native_block(pos);
    if block=="create:cart_assembler" {return false;}
    if game.block_in_tag("minecraft:wool_carpets",&block) {return true;}
    let hanging=game.native_block_property(pos,"hanging").is_some();
    let face_attached=game.native_block_property(pos,"face").is_some()
        && !matches!(block.as_str(),"minecraft:grindstone"|"create:stock_link");
    hanging || face_attached || block == "minecraft:ladder" || block.ends_with("torch")
        || block.ends_with("_sign") || block.ends_with("_pressure_plate")
        || block.ends_with("_rail") || matches!(block.as_str(),"minecraft:rail"|"minecraft:redstone_wire"|"minecraft:repeater"|"minecraft:comparator"
            |"create:pulse_repeater"|"create:pulse_extender"|"create:pulse_timer"|"create:powered_latch"|"create:powered_toggle_latch"
            |"create:steam_whistle"|"create:steam_whistle_extension"|"create:andesite_belt_funnel"|"create:brass_belt_funnel")
        || game.block_in_tag("create:brittle",&block)

}
fn block_attached(game: &Game<'_>, pos: [i32; 3], side: horizon_core::geometry::Direction) -> bool {
    use horizon_core::geometry::Direction;
    let block = game.native_block(pos);
    let face = game.native_block_property(pos, "facing");
    if block=="create:sticker" && game.native_block_property(pos,"extended").as_deref()==Some("true") && face.as_deref()==Some(direction_name(side)) {
        return !not_supportive(game,super::create_machines::offset(pos,side.normal()),side.opposite());
    }
    let adjacent=super::create_machines::offset(pos,side.normal());
    if matches!(block.as_str(),"create:fluid_tank"|"create:creative_fluid_tank") && game.native_block(adjacent)==block {
        return super::create_fluid_tank::parts(game,pos).is_some_and(|(_,parts)|parts.contains(&adjacent));
    }
    if block=="create:item_vault" && game.native_block(adjacent)==block {
        return super::create_vault::parts(&game.world,&game.pack.assets.registry,pos).is_some_and(|(_,parts)|parts.contains(&adjacent));
    }
    if block.ends_with("_bogey") {
        return game.native_block_property(pos,"axis").as_deref().is_some_and(|axis|match axis {"x"=>side.normal()[0]!=0,"z"=>side.normal()[2]!=0,_=>false});
    }
    let attached = if block.ends_with("_door") && !block.ends_with("_trapdoor") {
        side == Direction::Down || (game.native_block_property(pos,"half").as_deref()==Some("lower") && side==Direction::Up)
    } else if block.ends_with("_bed") {
        let target=if game.native_block_property(pos,"part").as_deref()==Some("head") { side.opposite() } else { side };
        face.as_deref()==Some(direction_name(target))
    } else if block=="create:redstone_link" || matches!(block.as_str(),"create:mechanical_harvester"|"create:mechanical_plough"|"create:mechanical_roller"|"create:hand_crank"|"create:nozzle") || block.ends_with("_valve_handle") {
        face.as_deref()==Some(direction_name(side.opposite()))
    } else if super::create_sail::is_sail(&block) {
        face.as_deref().and_then(super::create_machines::facing_axis)!=super::create_machines::facing_axis(direction_name(side))
    } else if block=="create:steam_whistle" {
        if game.native_block_property(pos,"wall").as_deref()==Some("true") { face.as_deref()==Some(direction_name(side)) } else { side==Direction::Down }
    } else if block=="minecraft:bell" {
        match game.native_block_property(pos,"attachment").as_deref() {Some("floor")=>side==Direction::Down,Some("ceiling")=>side==Direction::Up,_=>face.as_deref()==Some(direction_name(side))}
    } else if block=="minecraft:flower_pot" || block.starts_with("minecraft:potted_") || block=="create:steam_whistle_extension" { side==Direction::Down
    } else if block.ends_with("_wall_sign") || (block.ends_with("_wall_torch") || block=="minecraft:wall_torch") || block == "minecraft:ladder" {
        face.as_deref() == Some(direction_name(side.opposite()))
    } else if (block.ends_with("_sign") && !block.ends_with("_hanging_sign")) || block.ends_with("_pressure_plate") || game.block_in_tag("minecraft:wool_carpets", &block)
        || block.ends_with("_rail") || matches!(block.as_str(), "create:cart_assembler" | "create:pulse_repeater" | "create:pulse_extender" | "create:pulse_timer" | "create:powered_latch" | "create:powered_toggle_latch" | "minecraft:rail" | "minecraft:redstone_wire" | "minecraft:repeater" | "minecraft:comparator" | "minecraft:torch" | "minecraft:redstone_torch" | "minecraft:soul_torch") {
        side == Direction::Down
    } else if let Some(attach) = game.native_block_property(pos, "face") {
        match attach.as_str() { "floor" => side == Direction::Down, "ceiling" => side == Direction::Up,
            "wall" => face.as_deref() == Some(direction_name(side.opposite())), _ => false }
    } else if let Some(hanging) = game.native_block_property(pos, "hanging") {
        side == if hanging == "true" { Direction::Up } else { Direction::Down }
    } else { false };
    attached
}
pub(super) fn necessary(game: &Game<'_>, pos: [i32;3]) -> bool {
    let block=game.native_block(pos);
    block=="create:cart_assembler" || brittle(game,pos) || game.block_in_tag("create:movable_empty_collider",&block)
        || (!game.native_block_collision(pos).is_empty() && !game.res.behaviours().is_replaceable(game.world.block(pos[0],pos[1],pos[2])))
}
pub(super) fn face_checks(game: &Game<'_>,pos: [i32;3],side: horizon_core::geometry::Direction) -> (bool,bool,bool,bool) {
    let attached=block_attached(game,pos,side);let needed=necessary(game,pos);let unsupported=not_supportive(game,pos,side);
    (attached,needed,unsupported,attached || (needed && !unsupported))
}
pub(super) fn attached(game: &Game<'_>, pos: [i32; 3]) -> bool {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(face) = super::create_fan::facing(game, state) else { return false };
    face_checks(game, super::create_machines::offset(pos, face.normal()), face.opposite()).3
}
pub(super) fn collect(game: &Game<'_>, pos: [i32; 3], next: &mut std::collections::VecDeque<[i32; 3]>) {
    if game.native_block(pos) != STICKER || game.native_block_property(pos, "extended").as_deref() != Some("true") { return; }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(face) = super::create_fan::facing(game, state) else { return };
    let target = super::create_machines::offset(pos, face.normal());
    if !not_supportive(game, target, face.opposite()) { next.push_back(target); }
}
pub(super) fn loaded(game: &mut Game<'_>, pos: [i32; 3]) {
    if game.native_block(pos) != STICKER { return; }
    let extended = game.native_block_property(pos, "extended").as_deref() == Some("true");
    let state = game.world.block(pos[0], pos[1], pos[2]);
    game.native_with_mod_block_entity(pos, |entity| {
        let mut animation = animation(entity, extended);
        animation.receive();
        save_animation(entity, animation, state);
    });
}
pub(super) fn client_tick(game: &mut Game<'_>) {
    if game.player.is_none() { return; }
    let positions: Vec<_> = game.world.block_entities.iter().filter_map(|(&(x,y,z), entity)|
        matches!(entity, BlockEntity::Mod(entity) if entity.id == STICKER).then_some([x,y,z])).collect();
    for pos in positions {
        let state = game.world.block(pos[0],pos[1],pos[2]);
        let extended = game.native_block_property(pos, "extended").as_deref() == Some("true");
        let Some(entity) = super::create_machines::mod_entity(game, pos) else { continue };
        let mut value = animation(entity, extended);
        if let Some(Tag::Compound(tag)) = entity.runtime.get(&ANIMATION.into()) {
            if tag.get(&"State".into()) != Some(&Tag::Int(state.0 as i32)) { value.receive(); }
        }
        let connected = attached(game, pos);
        let events = value.tick(extended, connected);
        if let Some(BlockEntity::Mod(entity))=game.world.block_entities.get_mut(&(pos[0],pos[1],pos[2])) {save_animation(entity,value,state);}
        if events & 1 != 0 { attachment_particles(game,pos,state); }
        for (flag,pitch) in [(1,0.75),(2,0.2)] {
            if events & flag != 0 { game.native_play_local_sound("create:slime_added", pos.map(|v| f64::from(v)+0.5), 0.35, pitch, 0); }
        }
        if std::env::var_os("CREATE_STICKER_TRACE").is_some() {
            eprintln!("CREATE_STICKER_TICK {} {:?} {} {} {} {} {} {}", game.world.game_time,pos,
                value.previous.to_bits(),value.value.to_bits(),value.target.to_bits(),events,extended,connected);
        }
    }
}
pub(super) fn models(models: &mut Vec<String>) { models.push(HEAD.into()); }
pub(super) fn render(game: &Game<'_>, pos: [i32;3], state: BlockStateId, entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    use horizon_core::geometry::Direction;
    let Some(face) = super::create_fan::facing(game,state) else { return };
    let extended = game.native_block_state_property(state,"extended") == Some("true");
    let live=game.world.block(pos[0],pos[1],pos[2])==state && super::create_machines::mod_entity(game,pos).is_some_and(|world|std::ptr::eq(world,entity));
    let animation = if live {animation(entity,extended)} else {Animation::new(extended)};
    let offset = animation.head_offset(draw.partial);
    let yaw = match face { Direction::West=>90.0,Direction::North=>180.0,Direction::East=>270.0,_=>0.0 };
    let pitch = match face { Direction::Up=>0.0,Direction::Down=>180.0,_=>90.0 };
    let start = draw.vertices_mut().len();
    draw.push(); draw.rotate_about([0.0,1.0,0.0],yaw,[0.5;3]);
    draw.rotate_about([1.0,0.0,0.0],pitch,[0.5;3]); draw.translate([0.0,offset,0.0]);
    game.native_draw_model(draw,HEAD,0xffffff); draw.pop();
    if std::env::var_os("CREATE_STICKER_TRACE").is_some() {
        let count = draw.vertices_mut().len()-start;
        eprintln!("CREATE_STICKER_FRAME {} {:?} {} {} {} {}",draw.game_time,pos,draw.partial,offset,count,super::create_fluids::name(face));
        let inverse=draw.pose().inverse();let mut bounds=[f32::INFINITY;6];bounds[3..].fill(f32::NEG_INFINITY);
        for vertex in &draw.vertices_mut()[start..] {
            let v=inverse.transform_point3(glam::Vec3::from_array(vertex.pos)).to_array();
            for axis in 0..3 {bounds[axis]=bounds[axis].min(v[axis]);bounds[axis+3]=bounds[axis+3].max(v[axis]);}
        }
        eprintln!("CREATE_STICKER_GEOMETRY {:?} {} {} {:?}",pos,super::create_fluids::name(face),offset,bounds);
    }
}

// SuperGlueItem.spawnParticles(fullBlock=true): forty outward slime fragments.
fn attachment_particles(game: &mut Game<'_>, pos: [i32;3], state: BlockStateId) {
    use horizon_core::random::RandomSource;
    use horizon_client::particles::{ParticleOptions,ParticleType};
    let Some(face)=super::create_fan::facing(game,state) else { return };
    let normal=face.normal(); let axis=normal.iter().position(|&v|v!=0).unwrap();
    let center=std::array::from_fn::<_,3,_>(|i|f64::from(pos[i])+0.5+f64::from(normal[i])*0.5);
    let plane=normal.map(|v|1.0-f64::from(v.abs()));
    let mut options=ParticleOptions::simple(ParticleType::Item);
    options.item=Some(vec!["minecraft:item/slime_ball".into()]);
    options.source=Some("minecraft:slime_ball".into());
    let table=horizon_core::geometry::trig::sine_table();
    for _ in 0..40 {
        let degrees=360.0_f32*game.world.random.next_float();
        let angle=(f64::from(degrees)/180.0*std::f64::consts::PI) as f32;
        let phase=angle*10430.378_f32;
        let sin=f64::from(table[((phase as i32)&65535) as usize]);
        let cos=f64::from(table[(((phase+16384.0) as i32)&65535) as usize]);
        let [x,y,z]=plane;
        let offset=match axis { 0=>[x,y*cos-z*sin,z*cos+y*sin],1=>[x*cos+z*sin,y,z*cos-x*sin],_=>[x*cos-y*sin,y*cos+x*sin,z] };
        let length=(offset[0]*offset[0]+offset[1]*offset[1]+offset[2]*offset[2]).sqrt();
        let motion=offset.map(|v|v/length/16.0);
        let at=std::array::from_fn(|i|center[i]+offset[i].clamp(-0.5,0.5));
        game.native_add_particle(&options,at,motion);
    }
}
