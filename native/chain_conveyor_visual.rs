use horizon_client::block_entity_render::vertex_light;
use horizon_core::geometry::trig::{RAD_TO_DEG, atan2};
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::Game;
use super::create_chain_conveyor::{Span, loop_position};
use super::create_chain_conveyor_box_visual;
use super::create_chain_conveyor_connect::links;
use super::create_depot::compound;
use super::create_machines::{CONVEYOR, FROGPORT, float, int, mod_entity, offset, saved_speed};
use super::native_block_entity_draw::BlockEntityDraw;

const WHEEL: &str = "create:block/chain_conveyor/wheel";
const SHAFT: &str = "create:block/chain_conveyor/shaft";
const GUARD: &str = "create:block/chain_conveyor/guard";
const BODY: &str = "create:block/package_frogport/body";
const HEAD: &str = "create:block/package_frogport/head";
const GOGGLES: &str = "create:block/package_frogport/head_goggles";
const TONGUE: &str = "create:block/package_frogport/tongue";
const CHAIN_SPRITE: &str = "block/iron_chain";
const CHAIN_MIP_DISTANCE: f64 = 48.0;
// Entity vertex flag consumed by horizon-chain-span-light.patch.
const SPAN_LIGHT_BLEND: u32 = 1 << 24;
pub(super) const VIEW_DISTANCE: f64 = 256.0;
const CENTER: [f32; 3] = [0.5; 3];
const Y: [f32; 3] = [0.0, 1.0, 0.0];
const X: [f32; 3] = [1.0, 0.0, 0.0];
const PIVOT: [f32; 3] = [0.5, 10.0 / 16.0, 11.0 / 16.0];
const WHITE: u32 = 0xFFFFFF;
const RIGGINGS: [&str; 4] = [
    "create:item/package/rigging_12x12",
    "create:item/package/rigging_10x12",
    "create:item/package/rigging_10x8",
    "create:item/package/rigging_12x10",
];

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(
        [WHEEL, SHAFT, GUARD, BODY, HEAD, GOGGLES, TONGUE]
            .into_iter()
            .chain(RIGGINGS)
            .map(str::to_owned),
    );
}

pub(super) fn update_tag(entity: &ModBlockEntity, update: &mut Option<Compound>) {
    use super::create_chain_conveyor_packages::{
        BLOCKED_EXPORT, CARGO_SAMPLE_TIME, CARGO_VISUALS, cargo_update,
    };
    let keys: &[&str] = match entity.id.as_str() {
        CONVEYOR => &[
            "Speed",
            "Network",
            "Connections",
            "Reversed",
            CARGO_SAMPLE_TIME,
        ],
        FROGPORT => &[
            "Target",
            "PassiveYaw",
            "ReceivingPackage",
            "SendingPackage",
            "CurrentlyDepositing",
            "AnimationStartedAt",
            "AnimationProgress",
            "Goggles",
            BLOCKED_EXPORT,
        ],
        _ => return,
    };
    let update = update.get_or_insert_with(Compound::new);
    for &key in keys {
        if let Some(value) = entity.nbt.get(&key.into()) {
            update.insert(key.into(), value.clone());
        }
    }
    if entity.id == CONVEYOR {
        update.insert(CARGO_VISUALS.into(), cargo_update(&entity.nbt));
        update
            .entry("Connections".into())
            .or_insert_with(|| Tag::List(Vec::new()));
    } else {
        super::create_frogport_open::data_tag(entity, update);
        update.extend(entity.take_client_update_fields());
        update.entry(BLOCKED_EXPORT.into()).or_insert(Tag::Byte(0));
        update
            .entry("ReceivingPackage".into())
            .or_insert_with(|| Tag::Compound(Compound::new()));
        update
            .entry("CurrentlyDepositing".into())
            .or_insert(Tag::Byte(0));
        if !entity.nbt.contains_key(&"AnimationStartedAt".into()) {
            update.insert("AnimationStartedAt".into(), Tag::Long(-1));
            update.insert("SendingPackage".into(), Tag::Compound(Compound::new()));
        }
    }
}

pub(super) fn directed_span(
    game: &Game<'_>,
    at: [i32; 3],
    entity: &ModBlockEntity,
    edge: [i32; 3],
) -> Option<Span> {
    let other = mod_entity(game, offset(at, edge)).filter(|other| other.id == CONVEYOR)?;
    links(&other.nbt)
        .any(|back| back == edge.map(|axis| -axis))
        .then(|| Span::new(at, edge, int(&entity.nbt, "Reversed").unwrap_or(0) != 0))
}

fn chain_geometry(
    game: &Game<'_>,
    draw: &mut BlockEntityDraw,
    length: f32,
    phase: f32,
    far: bool,
    light: u32,
) -> usize {
    let mut top = length;
    let mut v = if far { 0.0 } else { phase.rem_euclid(1.0) };
    let radius = if far { 1.0 / 16.0 } else { 1.5 / 16.0 };
    let mut quads = 0;
    while top > 1e-6 {
        let strip = if far { top } else { (1.0 - v).min(top) };
        let bottom = top - strip;
        let end_v = if far { 1.0 } else { (v + strip) * 16.0 };
        for (p, q, u) in [
            ([0.0, radius], [0.0, -radius], 0.0),
            ([radius, 0.0], [-radius, 0.0], 3.0),
        ] {
            let (u_start, u_end) = if far { (4.0, 3.0) } else { (u + 3.0, u) };
            for (p, q) in [(p, q), (q, p)] {
                let begin = draw.vertices_mut().len();
                if !game.native_draw_quad(
                    draw,
                    CHAIN_SPRITE,
                    [
                        [p[0], top, p[1]],
                        [p[0], bottom, p[1]],
                        [q[0], bottom, q[1]],
                        [q[0], top, q[1]],
                    ],
                    [u_start, v * 16.0, u_end, end_v],
                    WHITE,
                ) {
                    continue;
                }
                quads += 1;
                for (vertex, along) in draw.vertices_mut()[begin..]
                    .iter_mut()
                    .zip([top, bottom, bottom, top])
                {
                    vertex.light = light;
                    vertex.layer |= SPAN_LIGHT_BLEND;
                    vertex.glint_uv[0] = along / length;
                }
            }
        }
        top = bottom;
        v = 0.0;
    }
    quads
}

fn trace_span_lights(
    draw: &mut BlockEntityDraw,
    start: usize,
    at: [i32; 3],
    far: bool,
    length: f32,
) {
    let pose = draw.pose();
    let origin = pose.transform_point3(glam::Vec3::ZERO);
    let axis = pose.transform_vector3(glam::Vec3::Y).normalize();
    let mut endpoints = [0; 2];
    let mut middle = 0;
    let mut error = 0.0_f32;
    let vertices = &draw.vertices_mut()[start..];
    let Some(first) = vertices.first() else {
        return;
    };
    let [light_a, light_b] = [first.light & 0xffff, first.light >> 16];
    let valid = vertices
        .iter()
        .all(|vertex| vertex.light == first.light && vertex.layer & SPAN_LIGHT_BLEND != 0);
    for vertex in vertices {
        let fraction = vertex.glint_uv[0];
        let actual = (glam::Vec3::from_array(vertex.pos) - origin).dot(axis) / length;
        error = error.max((fraction - actual).abs());
        if fraction == 0.0 {
            endpoints[0] += 1;
        } else if fraction == 1.0 {
            endpoints[1] += 1;
        } else {
            middle += 1;
        }
    }
    println!(
        "CREATE_CHAIN_SPAN_LIGHT {at:?},{far},{light_a},{light_b},{},{},{middle},{error:.9},{valid}",
        endpoints[0], endpoints[1],
    );
}

fn conveyor(game: &Game<'_>, at: [i32; 3], entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    let rpm = saved_speed(&entity.nbt);
    let time = draw.game_time as f32 + draw.partial;
    let phase = if (at[0] + at[2]) % 2 == 0 { 22.5 } else { 0.0 };
    let shaft_angle = (time * rpm * 3.0 / 10.0 + phase) % 360.0;
    let chain_phase = (time / (360.0 / rpm.abs())).rem_euclid(1.0) - 0.5;
    let begin = draw.vertices_mut().len();
    game.native_draw_model(draw, WHEEL, WHITE);
    let wheel_vertices = draw.vertices_mut().len() - begin;
    let before_shaft = draw.vertices_mut().len();
    super::create_visuals::draw_rotating(game, draw, 1, shaft_angle, SHAFT);
    let shaft_vertices = draw.vertices_mut().len() - before_shaft;
    let trace = std::env::var_os("CREATE_CHAIN_RENDER").is_some();
    if trace {
        let [x, y, z] = at;
        let facts = game.res.facts().get(game.world.block(x, y, z));
        let sky = |dy| game.world.light(x, y + dy, z) >> 4;
        println!(
            "CREATE_CHAIN_WHEEL_SKY {at:?},{},{},{},{},{},{}",
            facts.dampening,
            facts.skylight_down,
            facts.can_occlude,
            sky(1),
            sky(0),
            sky(-1)
        );
        println!(
            "CREATE_CHAIN_WHEEL {at:?},{},{:.9},{rpm:.6},{shaft_angle:.9},{wheel_vertices},{shaft_vertices}",
            draw.game_time, draw.partial
        );
    }

    for edge in links(&entity.nbt) {
        let Some(span) = directed_span(game, at, entity, edge) else {
            continue;
        };
        let [x, y, z]: [f64; 3] = std::array::from_fn(|axis| span.end[axis] - span.start[axis]);
        let yaw = (f64::from(RAD_TO_DEG) * atan2(x, z)) as f32;
        let pitch = (f64::from(RAD_TO_DEG) * atan2(y, (x * x + z * z).sqrt())) as f32;
        draw.push();
        draw.rotate_about(Y, yaw, CENTER);
        game.native_draw_model(draw, GUARD, WHITE);
        draw.pop();

        draw.push();
        draw.translate(std::array::from_fn(|axis| {
            (span.start[axis] - f64::from(at[axis])) as f32
        }));
        draw.rotate_about(Y, yaw, [0.0; 3]);
        draw.rotate_about(X, 90.0 - pitch, [0.0; 3]);
        draw.rotate_about(Y, 45.0, [0.0; 3]);
        let midpoint = glam::DVec3::from_array(std::array::from_fn(|axis| {
            f64::from(at[axis]) + 0.5 + f64::from(edge[axis]) * 0.5
        }));
        let distance_squared = game.locator_camera.map_or(0.0, |(camera, ..)| {
            glam::DVec3::from_array(camera).distance_squared(midpoint)
        });
        let far = distance_squared >= CHAIN_MIP_DISTANCE * CHAIN_MIP_DISTANCE;
        let chain_start = draw.vertices_mut().len();
        let [other_x, other_y, other_z] = offset(at, edge);
        let light = draw.light | (vertex_light(game.world.light(other_x, other_y, other_z)) << 16);
        let quads = chain_geometry(game, draw, span.length, chain_phase, far, light);
        if trace {
            trace_span_lights(draw, chain_start, at, far, span.length);
        }
        draw.pop();
        if trace {
            if let Some(sprite) = game.gui.atlas.sprites.get(CHAIN_SPRITE) {
                let vertices = &draw.vertices_mut()[chain_start..];
                if let [first, _, _, last, ..] = vertices {
                    let width = glam::Vec3::from_array(first.pos)
                        .distance(glam::Vec3::from_array(last.pos));
                    let [min_u, max_u, min_v, max_v] = vertices.iter().fold(
                        [
                            f32::INFINITY,
                            f32::NEG_INFINITY,
                            f32::INFINITY,
                            f32::NEG_INFINITY,
                        ],
                        |[min_u, max_u, min_v, max_v], vertex| {
                            let u = (vertex.uv[0] - sprite.u0) / (sprite.u1 - sprite.u0);
                            let v = (vertex.uv[1] - sprite.v0) / (sprite.v1 - sprite.v0);
                            [min_u.min(u), max_u.max(u), min_v.min(v), max_v.max(v)]
                        },
                    );
                    let distance = distance_squared.sqrt();
                    println!(
                        "CREATE_CHAIN_MIP {at:?},{distance:.9},{far},{width:.9},{min_u:.9},{max_u:.9},{min_v:.9},{max_v:.9}"
                    );
                }
            }
            println!(
                "CREATE_CHAIN_SPAN {at:?},{edge:?},{},{:.9},{yaw:.9},{pitch:.9},{chain_phase:.9},{:.9},{quads}",
                draw.game_time, draw.partial, span.length
            );
        }
    }
    create_chain_conveyor_box_visual::draw(game, at, entity, draw, trace);
}

fn vector(tag: &Compound, key: &str) -> Option<[i32; 3]> {
    let Tag::IntArray(value) = tag.get(&key.into())? else {
        return None;
    };
    value.as_slice().try_into().ok()
}

pub(super) fn frog_anchor(
    game: &Game<'_>,
    at: [i32; 3],
    entity: &ModBlockEntity,
) -> Option<[f64; 3]> {
    let target = compound(&entity.nbt, "Target")?;
    let anchor = offset(at, vector(target, "RelativePos")?);
    let position = float(target, "ChainPosition")?;
    let conveyor = mod_entity(game, anchor).filter(|entity| entity.id == CONVEYOR)?;
    if let Some(edge) = vector(target, "Connection") {
        Some(directed_span(game, anchor, conveyor, edge)?.position(position))
    } else {
        Some(loop_position(anchor, position))
    }
}

fn frogport(game: &Game<'_>, at: [i32; 3], entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    let target = frog_anchor(game, at, entity);
    let diff: [f64; 3] = target.map_or([0.0; 3], |target| {
        std::array::from_fn(|axis| target[axis] - f64::from(at[axis]) - 0.5)
    });
    let passive = float(&entity.nbt, "PassiveYaw").unwrap_or(0.0);
    let yaw = target.map_or(passive, |_| {
        (atan2(diff[0], diff[2]) * f64::from(RAD_TO_DEG)) as f32 + 180.0
    });

    let start = match entity.nbt.get(&"AnimationStartedAt".into()) {
        Some(Tag::Long(start)) if *start >= 0 => Some(*start),
        _ => None,
    };
    let depositing = start.is_some() && int(&entity.nbt, "CurrentlyDepositing") == Some(1);
    let [x, y, z] = [
        diff[0],
        diff[1] - if depositing { 0.0 } else { 0.75 },
        diff[2],
    ];
    let base_pitch = atan2(y, (x * x + z * z).sqrt() + 3.0 / 16.0) as f32 * RAD_TO_DEG;
    let head_pitch = if target.is_some() {
        (base_pitch * 2.0).clamp(60.0, 100.0)
    } else {
        80.0
    };
    let progress = start.map_or(0.0, |start| {
        let ticks = (draw.game_time - start).clamp(0, 10);
        let previous = (0..ticks).fold(0.0_f32, |phase, _| phase + 0.1);
        previous + ((previous + 0.1).min(1.0) - previous) * draw.partial
    });
    let field = if depositing {
        "SendingPackage"
    } else {
        "ReceivingPackage"
    };
    let package = start
        .and_then(|_| compound(&entity.nbt, field))
        .and_then(ItemStack::from_nbt);
    let length = ((x * x + y * y + z * z).sqrt() as f32).max(1.0);
    let (head, tongue, scale, distance) = if depositing {
        let phase = f64::from(progress);
        let extension = (1.0 - ((phase - 0.25) * 4.0 - 1.0).powi(4)).max(0.0);
        let distance = f64::from(length) * ((phase - 0.25) * 3.0).min(1.0).max(extension);
        let tongue = (1.0 - ((phase * 1.25 - 0.25) * 4.0 - 1.0).powi(4)).max(0.0);
        let head = (1.0 - ((phase * 1.25) * 2.0 - 1.0).powi(4)).max(0.0) as f32;
        (
            head_pitch * head,
            (f64::from(length) * tongue) as f32,
            0.25 + progress * 3.0 / 4.0,
            distance as f32,
        )
    } else if package.is_some() {
        let head = head_pitch * (1.0 - (((progress * 1.5).powi(2) - 0.5) * 2.0).clamp(0.0, 1.0));
        let tongue = length * (1.0 - progress * 1.25).max(0.0).powi(5);
        (head, tongue, (1.0 - progress * 1.25).max(0.5), tongue)
    } else {
        let phase = super::create_frogport_open::anticipates(at, draw.partial);
        let head = head_pitch * super::create_frogport_anticipation::head_factor(phase);
        if phase > 0.0 && std::env::var_os("CREATE_FROGPORT_ANTICIPATION").is_some() {
            println!(
                "CREATE_FROGPORT_ANTICIPATE_MODEL {at:?},{},{:.9},{head:.9},{head_pitch:.9}",
                draw.game_time, phase
            );
        }
        (head, 0.0, 1.0, 0.0)
    };

    let manual = super::create_frogport_open::progress(at, draw.partial);
    let head = head.max(manual * 60.0);
    let tongue = tongue.max(manual * 0.25);
    let base_pitch = if target.is_none() { 0.0 } else { base_pitch };
    let before = draw.vertices_mut().len();
    let visible = !depositing || start.is_some_and(|start| draw.game_time - start < 6);
    if let Some(stack) = package.filter(|_| scale >= 0.45 && visible) {
        let length = (x * x + y * y + z * z).sqrt();
        let direction = if length > 0.0 {
            [x / length, y / length, z / length]
        } else {
            [0.0; 3]
        };
        let [dx, dy, dz] = direction.map(|axis| (axis * f64::from(distance)) as f32);
        draw.push();
        draw.translate([
            dx,
            dy + 3.0 / 16.0 - if depositing { 0.75 } else { 0.0 },
            dz,
        ]);
        draw.translate(CENTER);
        draw.scale([scale; 3]);
        draw.translate(CENTER.map(|axis| -axis));
        let model = format!(
            "create:item/{}",
            stack.item.strip_prefix("create:").unwrap_or("")
        );
        game.native_draw_model(draw, &model, WHITE);
        if depositing
            && let Some((width, height)) = super::create_package_style::dimensions(&stack.item)
        {
            let width = (width * 16.0).round() as i32;
            let height = (height * 16.0).round() as i32;
            let rig = format!("create:item/package/rigging_{width}x{height}");
            game.native_draw_model(draw, &rig, WHITE);
        }
        draw.pop();
    }

    draw.push();
    draw.rotate_about(Y, yaw, CENTER);
    game.native_draw_model(draw, BODY, WHITE);
    let head_model = if int(&entity.nbt, "Goggles") == Some(1) {
        GOGGLES
    } else {
        HEAD
    };
    draw.push();
    draw.rotate_about(X, head, PIVOT);
    let head_start = draw.vertices_mut().len();
    game.native_draw_model(draw, head_model, WHITE);
    if head_model == GOGGLES
        && draw.vertices_mut().len() > head_start
        && std::env::var_os("CREATE_CHAIN_RENDER").is_some()
    {
        println!("CREATE_FROGPORT_GOGGLES_MODEL {at:?}");
    }
    draw.pop();
    if tongue > 0.0 {
        draw.translate(PIVOT);
        draw.rotate_about(X, base_pitch, [0.0; 3]);
        draw.scale([1.0, 1.0, tongue / (7.0 / 16.0)]);
        draw.translate(PIVOT.map(|axis| -axis));
        game.native_draw_model(draw, TONGUE, WHITE);
    }
    draw.pop();

    if std::env::var_os("CREATE_CHAIN_RENDER").is_some() {
        let vertices = draw.vertices_mut().len() - before;
        let label = if depositing {
            "CREATE_FROGPORT_SEND_MODEL"
        } else {
            "CREATE_FROGPORT_MODEL"
        };
        println!(
            "{label} {at:?},{},{:.9},{yaw:.9},{progress:.9},{head:.9},{base_pitch:.9},{tongue:.9},{scale:.9},{vertices}",
            draw.game_time, draw.partial
        );
    }
}

pub(super) fn render(
    game: &Game<'_>,
    at: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) -> bool {
    match entity.id.as_str() {
        CONVEYOR => conveyor(game, at, entity, draw),
        FROGPORT => frogport(game, at, entity, draw),
        _ => return false,
    }
    true
}
