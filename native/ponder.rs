use std::cell::{Cell, RefCell};
use std::io::Read;

use glam::{Mat4, Vec3};
use horizon_client::{hud::HudBatch, keybinds, mod_api::{NativeMod, NativeScreenView}, text::Text};
use horizon_world::nbt::{self, Tag};

use super::{Game, Screen};
use super::native_block_entity_draw::BlockEntityDraw;

const SCREEN: &str = "create:ponder_shaft";
const SHAFT: &str = "create:shaft";
const COGWHEEL: &str = "create:cogwheel";
const LARGE_COGWHEEL: &str = "create:large_cogwheel";
const ENCASED: [&str; 2] = ["create:andesite_encased_shaft", "create:brass_encased_shaft"];

#[derive(Clone, Copy, PartialEq, Eq)]
enum Story { Relay, Encasing, CogRelay, LargeCogRelay, Gearshift }

impl Story {
    fn path(self) -> &'static str { match self { Self::Relay => "shaft/relay", Self::Encasing => "shaft/encasing", Self::CogRelay => "cog/small", Self::LargeCogRelay => "cog/large", Self::Gearshift => "cog/speedup" } }
    fn end(self) -> u32 { match self { Self::Relay => 65, Self::Encasing => 124, Self::CogRelay => 205, Self::LargeCogRelay => 190, Self::Gearshift => 390 } }
}

#[derive(Clone)]
struct Block {
    pos: [i32; 3],
    name: String,
    properties: Vec<(String, String)>,
}

struct Scene {
    story: Story,
    subject: u8,
    blocks: Vec<Block>,
    tick: u32,
    animation: u32,
    paused: bool,
}

thread_local! {
    static HOVER: Cell<u8> = const { Cell::new(0) };
    static HOLD_ITEM: Cell<u8> = const { Cell::new(0) };
    static HOLD: Cell<u8> = const { Cell::new(0) };
    static RENDERED: Cell<bool> = const { Cell::new(false) };
    static CLOSE: Cell<bool> = const { Cell::new(false) };
    static BACK: Cell<bool> = const { Cell::new(false) };
    static PREVIOUS: Cell<u8> = const { Cell::new(0) };
    static SCENE: RefCell<Option<Scene>> = const { RefCell::new(None) };
}

pub(super) fn mods(mods: &mut Vec<NativeMod>) {
    let key = ["ponder".to_owned(), "Ponder".to_owned(), "key.keyboard.w".to_owned()];
    if let Some(existing) = mods.iter_mut().find(|entry| entry.id == "create") {
        existing.keys.push(key);
    } else {
        mods.push(NativeMod { id: "create".into(), title: "Create".into(), description: String::new(), keys: vec![key] });
    }
}

pub(super) fn tooltip(game: &Game<'_>, stack: &crate::items::ItemStack, lines: &mut Vec<(Text, u32)>) {
    if (stack.item.as_ref() == SHAFT || stack.item.as_ref() == COGWHEEL || stack.item.as_ref() == LARGE_COGWHEEL) || ENCASED.contains(&stack.item.as_ref()) {
        let key = game.native_mod_key("create", "ponder", "key.keyboard.w");
        let label = keybinds::display_name(&key).plain();
        lines.push((Text::literal(&format!("Hold [{label}] to Ponder")), 0xffaaaaaa));
    }
}

pub(super) fn hovered(stack: &crate::items::ItemStack) {
    match stack.item.as_ref() {
        SHAFT => HOVER.set(1),
        COGWHEEL => HOVER.set(3),
        LARGE_COGWHEEL => HOVER.set(4),
        item if ENCASED.contains(&item) => HOVER.set(2),
        _ => {}
    }
}

fn integer(tag: &Tag) -> Option<i32> {
    match tag { Tag::Int(value) => Some(*value), _ => None }
}

fn structure(game: &Game<'_>, story: Story) -> Option<Vec<Block>> {
    let path = game.options.resources.join(format!("assets/create/ponder/{}.nbt", story.path()));
    let bytes = std::fs::read(path).ok()?;
    let mut raw = Vec::new();
    flate2::read::GzDecoder::new(bytes.as_slice()).read_to_end(&mut raw).ok()?;
    let (root, _) = nbt::read_named(&raw, nbt::Limits::templates()).ok()?;
    let Tag::List(palette) = root.tag.get("palette")? else { return None; };
    let states: Vec<_> = palette.iter().map(|entry| {
        let Tag::String(name) = entry.get("Name")? else { return None; };
        let properties = match entry.get("Properties") {
            Some(Tag::Compound(values)) => values.iter().filter_map(|(key, value)| {
                let Tag::String(value) = value else { return None; };
                Some((key.to_string_lossy(), value.to_string_lossy()))
            }).collect(),
            _ => Vec::new(),
        };
        Some((name.to_string_lossy(), properties))
    }).collect::<Option<_>>()?;
    let Tag::List(entries) = root.tag.get("blocks")? else { return None; };
    let mut blocks = Vec::new();
    for entry in entries {
        let Tag::List(position) = entry.get("pos")? else { return None; };
        let [x, y, z] = position.as_slice() else { return None; };
        let state = usize::try_from(integer(entry.get("state")?)?).ok()?;
        let (name, properties) = states.get(state)?.clone();
        blocks.push(Block { pos: [integer(x)?, integer(y)?, integer(z)?], name, properties });
    }
    Some(blocks)
}

fn trace(event: &str) {
    if std::env::var_os("CREATE_PONDER_TRACE").is_some() { eprintln!("CREATE_PONDER {event}"); }
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.native_mod_screen() == Some(SCREEN) {
        if BACK.replace(false) {
            let previous = PREVIOUS.replace(0);
            game.native_mod_screen_close(SCREEN);
            SCENE.set(None);
            game.screen = if previous == 2 && game.creative { Screen::Creative } else { Screen::Inventory };
            game.capture(false);
            trace("back to inventory");
            return;
        }
        if CLOSE.replace(false) { game.native_mod_screen_close(SCREEN); SCENE.set(None); return; }
        SCENE.with_borrow_mut(|scene| if let Some(scene) = scene {
            if !scene.paused {
                scene.animation = scene.animation.saturating_add(1);
                if scene.tick < scene.story.end() {
                    scene.tick += 1;
                    match scene.story {
                        Story::Relay if matches!(scene.tick, 5 | 20 | 25 | 30 | 35 | 45 | 65) => trace(&format!("tick {}", scene.tick)),
                        Story::Encasing if matches!(scene.tick, 20 | 27 | 37 | 44 | 54 | 124) => trace(&format!("encasing tick {}", scene.tick)),
                        Story::CogRelay if matches!(scene.tick, 5 | 20 | 25 | 30 | 35 | 45 | 105 | 115 | 135 | 205) => trace(&format!("cog tick {}", scene.tick)),
                        Story::LargeCogRelay if matches!(scene.tick, 5 | 10 | 15 | 20 | 25 | 95 | 110 | 115 | 120 | 125 | 130 | 190) => trace(&format!("large cog tick {}", scene.tick)),
                        Story::Gearshift if matches!(scene.tick, 5 | 15 | 95 | 125 | 185 | 190 | 235 | 240 | 250 | 255 | 265 | 345 | 350 | 390) => trace(&format!("gearshift tick {}", scene.tick)),
                        _ => {}
                    }
                }
            }
        });
        HOVER.set(0);
        return;
    }
    SCENE.set(None);
    let hovered = HOVER.replace(0);
    let key = game.native_mod_key("create", "ponder", "key.keyboard.w");
    let down = keybinds::key_code(&key).is_some_and(|key| game.native_is_key_down(key));
    if hovered == 0 || !down || !matches!(game.screen, Screen::Inventory | Screen::Creative) {
        HOLD.set(0);
        HOLD_ITEM.set(0);
        return;
    }
    if HOLD_ITEM.replace(hovered) != hovered { HOLD.set(0); }
    let ticks = HOLD.get().saturating_add(1);
    HOLD.set(ticks);
    if ticks < 12 { return; }
    let story = match hovered { 2 => Story::Encasing, 3 => Story::CogRelay, 4 => Story::Gearshift, _ => Story::Relay };
    let Some(blocks) = structure(game, story) else { HOLD.set(0); trace("missing structure"); return; };
    let previous = if game.screen == Screen::Creative { 2 } else if game.container.is_none()
        && game.craft_table.is_none() && game.station.is_none() && game.open_container_slots.is_none()
        && game.remote.as_ref().is_none_or(|remote| remote.menu.is_none()) { 1 } else { 0 };
    game.close_container();
    game.screen = Screen::Playing;
    if game.native_mod_screen_open(SCREEN) {
        CLOSE.set(false);
        BACK.set(false);
        PREVIOUS.set(previous);
        if story == Story::Gearshift { trace(&format!("gearshift open blocks {}", blocks.len())); }
        else if story == Story::CogRelay { trace(&format!("cog open blocks {}", blocks.len())); }
        else if story == Story::LargeCogRelay { trace(&format!("large cog open blocks {}", blocks.len())); }
        else { trace(&format!("open tick 0 blocks {}", blocks.len())); }
        SCENE.set(Some(Scene { story, subject: hovered, blocks, tick: 0, animation: 0, paused: false }));
        RENDERED.set(false);
    }
    HOLD.set(0);
}

fn visible(block: &Block, story: Story, tick: u32) -> bool {
    if story == Story::Encasing { return block.pos[1] == 0 || (block.pos[1] == 1 && block.pos[2] == 2); }
    if story == Story::Gearshift {
        return match block.pos {
            [_, 0, _] => true,
            [4..=5, 1, 2] => tick >= 5,
            [3, 1, 2] | [3, 2, 3] => tick >= 15,
            [0..=2, 1..=2, 2..=3] => tick >= 95,
            _ => false,
        };
    }
    if story == Story::LargeCogRelay {
        return match block.pos {
            [_, 0, _] => true,
            [_, 1, _] => tick >= 5,
            [3, 2, 4] => (10..95).contains(&tick),
            [3, 2, 5] => (15..95).contains(&tick),
            [3, 2, z @ 1..=3] => (10 + (4 - z as u32) * 5..95).contains(&tick) || (z == 3 && tick >= 115),
            [4, 2, 3] => tick >= 110,
            [5, 2, 3] => tick >= 115,
            [x @ 1..=2, 2, 3] => tick >= 130 - x as u32 * 5,
            _ => false,
        };
    }
    if story == Story::CogRelay {
        return match block.pos {
            [_, 0, _] | [4, 1, 1] => true,
            [1, 1, 3..=5] => tick >= 5,
            [0, 1, 2] => tick >= 25,
            [x @ 1..=4, 1, 2] => tick >= 15 + x as u32 * 5,
            [1..=2, 1, 1] => tick >= 105,
            _ => false,
        };
    }
    match block.pos {
        [_, 0, _] | [0, 1, 2] => true,
        [5, 1, 2] => tick >= 5,
        [4, 1, 2] => tick >= 20,
        [3, 1, 2] => tick >= 25,
        [2, 1, 2] => tick >= 30,
        [1, 1, 2] => tick >= 35,
        _ => false,
    }
}

fn geometry(game: &Game<'_>, scene: &Scene, partial: f32) -> Vec<horizon_client::mesher::Vertex> {
    let mut draw = BlockEntityDraw::posed(partial, i64::from(scene.animation), 240 | 240 << 8,
        [0; 3], Mat4::IDENTITY, (Vec3::Y, Vec3::Y), Vec::new());
    for block in scene.blocks.iter().filter(|block| visible(block, scene.story, scene.tick)) {
        draw.push();
        let start = if scene.story == Story::Encasing { 0 } else if scene.story == Story::Gearshift { match block.pos {
            [_, 0, _] => 0, [4..=5, 1, 2] => 5, [3, 1, 2] | [3, 2, 3] => 15, _ => 95,
        }} else if scene.story == Story::LargeCogRelay { match block.pos {
            [_, 0, _] => 0, [_, 1, _] => 5, [3, 2, 4] => 10, [3, 2, 5] => 15,
            [3, 2, 3] if scene.tick >= 115 => 115, [3, 2, z @ 1..=3] => 10 + (4 - z as u32) * 5,
            [4, 2, 3] => 110, [5, 2, 3] => 115, [x @ 1..=2, 2, 3] => 130 - x as u32 * 5, _ => 0,
        }} else if scene.story == Story::CogRelay { match block.pos {
            [_, 0, _] | [4, 1, 1] => 0, [1, 1, 3..=5] => 5, [0, 1, 2] => 25,
            [x @ 1..=4, 1, 2] => 15 + x as u32 * 5, [1..=2, 1, 1] => 105, _ => 0,
        }} else { match block.pos {
            [_, 0, _] | [0, 1, 2] => 0,
            [5, 1, 2] => 5, [4, 1, 2] => 20, [3, 1, 2] => 25,
            [2, 1, 2] => 30, [1, 1, 2] => 35, _ => 0,
        }};
        let progress = ((scene.tick.saturating_sub(start) as f32 + partial) / 10.0).clamp(0.0, 1.0);
        let offset = (1.0 - progress) * if block.pos[1] == 0 { -1.0 } else { 1.0 };
        let [x, y, z] = block.pos;
        if scene.story == Story::Gearshift && matches!(block.pos, [3, 1, 2] | [3, 2, 3]) {
            let t = scene.tick as f32 + partial;
            let lift = if (235.0..240.0).contains(&t) { (t - 235.0) / 5.0 }
                else if (240.0..250.0).contains(&t) { 1.0 }
                else if (250.0..255.0).contains(&t) { (255.0 - t) / 5.0 } else { 0.0 };
            let turn = if (240.0..250.0).contains(&t) { (t - 240.0) * 18.0 } else { 0.0 };
            draw.translate([0.0, lift, 0.0]);
            draw.rotate_about([1.0, 0.0, 0.0], turn, [3.5, 2.0, 3.0]);
        }
        draw.translate([x as f32, y as f32 + offset, z as f32]);
        let rpm = match (scene.story, block.name.as_str()) {
            (Story::Relay, "create:large_cogwheel") => -32.0,
            (Story::Relay, _) => 64.0,
            (Story::Encasing, "create:large_cogwheel") => -16.0,
            (Story::Encasing, _) => 32.0,
            (Story::CogRelay, _) => if block.pos[0] % 2 == 0 { -64.0 } else { 64.0 },
            (Story::LargeCogRelay, _) => if block.pos[1] == 1 { 16.0 } else { -16.0 },
            (Story::Gearshift, _) => if (235..255).contains(&scene.tick) { 0.0 }
                else if block.pos[1] == 2 { if scene.tick < 255 { -64.0 } else { -16.0 } } else { 32.0 },
        };
        let axis = if scene.story == Story::CogRelay { 2 } else if scene.story == Story::LargeCogRelay {
            if block.pos == [3, 2, 3] && scene.tick >= 115 { 0 }
            else { match block.properties.iter().find(|(key, _)| key == "axis").map(|(_, value)| value.as_str()) {
                Some("y") => 1, Some("z") => 2, _ => 0,
            }}
        } else { 0 };
        let angle = super::create_visuals::wheel_angle(i64::from(scene.animation), partial, rpm, 0.0);
        match block.name.as_str() {
            "create:shaft" if scene.story == Story::Gearshift && matches!(block.pos, [3, 1, 2] | [3, 2, 3]) => {
                let large = (block.pos[1] == 1) == (scene.tick < 250);
                if large {
                    super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/large_cogwheel_shaftless");
                    super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/cogwheel_shaft");
                } else {
                    super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/cogwheel");
                }
            }
            "create:shaft" if scene.story == Story::LargeCogRelay && block.pos == [4, 2, 3] => {
                super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/large_cogwheel_shaftless");
                super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/cogwheel_shaft");
            }
            "create:shaft" => {
                if scene.story == Story::Encasing && block.pos == [3, 1, 2] && scene.tick >= 27 {
                    game.native_draw_block(&mut draw, ENCASED[0], &[("axis", "x")]);
                } else if scene.story == Story::Encasing && block.pos == [1, 1, 2] && scene.tick >= 44 {
                    game.native_draw_block(&mut draw, ENCASED[1], &[("axis", "x")]);
                }
                super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/shaft");
            }
            "create:cogwheel" => super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/cogwheel"),
            "create:large_cogwheel" => {
                super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/large_cogwheel_shaftless");
                super::create_visuals::draw_rotating(game, &mut draw, axis, angle, "create:block/cogwheel_shaft");
            }
            _ => {
                let props: Vec<_> = block.properties.iter().map(|(key, value)| (key.as_str(), value.as_str())).collect();
                game.native_draw_block(&mut draw, &block.name, &props);
                if block.name == "create:speedometer" {
                    let (start_tick, first_rpm) = if scene.story == Story::Gearshift {
                        (95.0, if block.pos[1] == 2 { 64.0 } else { 32.0 })
                    } else { (35.0, 64.0) };
                    let elapsed = (scene.animation as f32 + partial - start_tick).max(0.0);
                    let initial = super::create_visuals::speed_target(first_rpm) * (1.0 - 0.875_f32.powf(elapsed));
                    let reading = if scene.story == Story::Gearshift && block.pos[1] == 2 && scene.animation >= 255 {
                        let target = super::create_visuals::speed_target(16.0);
                        target + (initial - target) * 0.875_f32.powf(scene.animation as f32 + partial - 255.0)
                    } else { initial };
                    for yaw in if scene.story == Story::CogRelay { [0.0, 180.0] } else { [90.0, -90.0] } {
                        draw.push();
                        draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
                        game.native_draw_model(&mut draw, "create:block/gauge/speedometer/head", 0xffffff);
                        draw.rotate_about([1.0, 0.0, 0.0], -90.0 * reading, [0.0, 5.75 / 16.0, 5.75 / 16.0]);
                        game.native_draw_model(&mut draw, "create:block/gauge/dial", 0xffffff);
                        draw.pop();
                    }
                }
            }
        }
        draw.pop();
    }
    draw.into_vertices()
}

pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch, screen: &NativeScreenView<'_>) {
    if game.native_mod_screen() != Some(SCREEN) { return; }
    SCENE.with_borrow(|scene| {
        let Some(scene) = scene else { return; };
        let (width, height) = game.gui_size();
        game.native_fill(batch, [0.0, 0.0, width, height], 0xff182025);
        let title = match scene.story {
            Story::Relay => game.translate("create.ponder.shaft.header", "Relaying rotational force using Shafts"),
            Story::Encasing => game.translate("create.ponder.shaft_casing.header", "Encasing Shafts"),
            Story::CogRelay => game.translate("create.ponder.cogwheel.header", "Relaying rotational force using Cogwheels"),
            Story::Gearshift => game.translate("create.ponder.cog_speedup.header", "Gearshifting with Cogs"),
            Story::LargeCogRelay => game.translate("create.ponder.large_cogwheel.header", "Relaying rotational force using Large Cogwheels"),
        };
        game.native_text(batch, &title, [20.0, 16.0], 0xffffff, true);
        let scale = (width / 10.0).min((height - 90.0) / 6.0).max(8.0);
        let rotation = if scene.story == Story::Relay {
            ((scene.tick.saturating_sub(25) as f32 + screen.partial_tick) / 10.0).clamp(0.0, 1.0) * 70.0
        } else { 0.0 };
        let camera = Mat4::from_rotation_x(0.55) * Mat4::from_rotation_y((35.0_f32 + rotation).to_radians());
        let vertices = geometry(game, scene, screen.partial_tick);
        if !RENDERED.replace(true) { trace(&format!("render vertices {}", vertices.len())); }
        let start = batch.vertices.len();
        for quad in vertices.chunks_exact(4) {
            let points = std::array::from_fn(|i| {
                let p = camera.transform_point3(Vec3::from_array(quad[i].pos) - Vec3::new(2.5, 0.7, 2.5));
                [width * 0.5 + p.x * scale, height * 0.53 - p.y * scale, p.z]
            });
            batch.quad_3d(points, std::array::from_fn(|i| quad[i].uv), quad[0].color);
        }
        batch.depth_since(start, [0.0, 30.0, width, height - 40.0]);
        if matches!(scene.story, Story::Relay | Story::CogRelay) && (35..45).contains(&scene.tick) {
            let target = if scene.story == Story::CogRelay { Vec3::new(2.0, 0.8, -1.0) } else { Vec3::new(-2.0, 0.8, 0.0) };
            let p = camera.transform_point3(target);
            let x = width * 0.5 + p.x * scale;
            let y = height * 0.53 - p.y * scale;
            game.native_fill(batch, [x - 6.0, y - 1.0, 12.0, 2.0], 0xffffdd55);
            game.native_fill(batch, [x - 1.0, y - 6.0, 2.0, 12.0], 0xffffdd55);
        }
        if scene.story == Story::CogRelay && (115..135).contains(&scene.tick) {
            for (x, symbol) in [(1.0, "↻"), (2.0, "↺")] {
                let p = camera.transform_point3(Vec3::new(x + 0.5, 1.8, 1.5) - Vec3::new(2.5, 0.7, 2.5));
                game.native_text(batch, symbol, [width * 0.5 + p.x * scale, height * 0.53 - p.y * scale], 0xffff55, true);
            }
        }
        let caption = match scene.story {
            Story::Relay if scene.tick >= 45 => Some(game.translate("create.ponder.shaft.text_1", "Shafts will relay rotation in a straight line.")),
            Story::Encasing if (54..154).contains(&scene.animation) => Some(game.translate("create.ponder.shaft_casing.text_1", "Brass or Andesite Casing can be used to decorate Shafts")),
            Story::CogRelay if (45..105).contains(&scene.animation) => Some(game.translate("create.ponder.cogwheel.text_1", "Cogwheels will relay rotation to other adjacent cogwheels")),
            Story::CogRelay if (135..235).contains(&scene.animation) => Some(game.translate("create.ponder.cogwheel.text_2", "Neighbouring shafts connected like this will rotate in opposite directions")),
            Story::Gearshift if (15..75).contains(&scene.animation) => Some(game.translate("create.ponder.cog_speedup.text_1", "Large and Small cogs can be connected diagonally")),
            Story::Gearshift if (95..175).contains(&scene.animation) => Some(game.translate("create.ponder.cog_speedup.text_2", "Shifting from large to small cogs, the conveyed speed will be doubled")),
            Story::Gearshift if (255..335).contains(&scene.animation) => Some(game.translate("create.ponder.cog_speedup.text_3", "Shifting the opposite way, the conveyed speed will be halved")),
            Story::LargeCogRelay if (25..95).contains(&scene.animation) => Some(game.translate("create.ponder.large_cogwheel.text_1", "Large cogwheels can connect to each other at right angles")),
            Story::LargeCogRelay if (130..220).contains(&scene.animation) => Some(game.translate("create.ponder.large_cogwheel.text_2", "It will help relaying conveyed speed to other axes of rotation")),
            _ => None,
        };
        if let Some(text) = caption { game.native_text(batch, &text, [20.0, height - 62.0], 0xffffff, true); }
        if scene.story == Story::Encasing {
            for (start, end, x, item) in [
                (20, 80, 3.0, "create:andesite_casing"),
                (37, 97, 1.0, "create:brass_casing"),
            ] {
                if (start..end).contains(&scene.tick) {
                    let p = camera.transform_point3(Vec3::new(x + 0.5, 1.5, 2.5) - Vec3::new(2.5, 0.7, 2.5));
                    let at = [width * 0.5 + p.x * scale, height * 0.53 - p.y * scale - 28.0];
                    game.native_fill(batch, [at[0] - 5.0, at[1] - 5.0, 82.0, 26.0], 0xd0202020);
                    game.native_item(batch, item, at, 16.0);
                    game.native_text(batch, "Right-click", [at[0] + 20.0, at[1] + 4.0], 0xffffff, true);
                }
            }
        }
        if scene.story == Story::Gearshift {
            for (start, end, x, key, fallback) in [
                (185, 215, 25.0, "create.ponder.shared.rpm32", "32 RPM"),
                (190, 220, 110.0, "create.ponder.shared.rpm16", "16 RPM"),
                (345, 405, 25.0, "create.ponder.shared.rpm8", "8 RPM"),
                (350, 410, 110.0, "create.ponder.shared.rpm16", "16 RPM"),
            ] {
                if (start..end).contains(&scene.animation) {
                    game.native_text(batch, &game.translate(key, fallback), [x, height - 48.0], 0xffffff, true);
                }
            }
        }
        if PREVIOUS.get() != 0 { game.native_text(batch, "Backspace: Back", [20.0, 31.0], 0xffffff, true); }
        game.native_text(batch, if scene.paused { "Space: Play" } else { "Space: Pause" }, [20.0, height - 27.0], 0xffffff, true);
        game.native_text(batch, "R: Replay", [115.0, height - 27.0], 0xffffff, true);
        game.native_text(batch, "Esc: Close", [190.0, height - 27.0], 0xffffff, true);
        if scene.subject == 1 || scene.subject == 4 || scene.subject == 3 {
            game.native_text(batch, if matches!(scene.story, Story::Relay | Story::CogRelay) || (scene.story == Story::Gearshift && scene.subject == 4) { "Right: Next" } else { "Left: Previous" }, [280.0, height - 27.0], 0xffffff, true);
        }
    });
}

pub(super) fn key(game: &Game<'_>, key: &str, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) { return; }
    SCENE.with_borrow_mut(|scene| if let Some(scene) = scene {
        match key {
            "key.keyboard.backspace" if PREVIOUS.get() != 0 => { BACK.set(true); *canceled = true; }
            "key.keyboard.r" => { scene.tick = 0; scene.animation = 0; scene.paused = false; trace("replay tick 0"); *canceled = true; }
            "key.keyboard.space" => { scene.paused = !scene.paused; *canceled = true; }
            "key.keyboard.right" if scene.story == Story::Gearshift && scene.subject == 4 => {
                if let Some(blocks) = structure(game, Story::LargeCogRelay) {
                    *scene = Scene { story: Story::LargeCogRelay, subject: 4, blocks, tick: 0, animation: 0, paused: false };
                    RENDERED.set(false); trace(&format!("large cog open blocks {}", scene.blocks.len()));
                }
                *canceled = true;
            }
            "key.keyboard.right" if scene.story == Story::CogRelay && scene.subject == 3 => {
                if let Some(blocks) = structure(game, Story::Gearshift) {
                    *scene = Scene { story: Story::Gearshift, subject: 3, blocks, tick: 0, animation: 0, paused: false };
                    RENDERED.set(false); trace(&format!("gearshift open blocks {}", scene.blocks.len()));
                }
                *canceled = true;
            }
            "key.keyboard.left" if scene.story == Story::LargeCogRelay && scene.subject == 4 => {
                if let Some(blocks) = structure(game, Story::Gearshift) {
                    *scene = Scene { story: Story::Gearshift, subject: 4, blocks, tick: 0, animation: 0, paused: false };
                    RENDERED.set(false); trace(&format!("gearshift open blocks {}", scene.blocks.len()));
                }
                *canceled = true;
            }
            "key.keyboard.left" if scene.story == Story::Gearshift && scene.subject == 3 => {
                if let Some(blocks) = structure(game, Story::CogRelay) {
                    *scene = Scene { story: Story::CogRelay, subject: 3, blocks, tick: 0, animation: 0, paused: false };
                    RENDERED.set(false); trace(&format!("cog open blocks {}", scene.blocks.len()));
                }
                *canceled = true;
            }
            "key.keyboard.right" if scene.story == Story::Relay => {
                if let Some(blocks) = structure(game, Story::Encasing) {
                    *scene = Scene { story: Story::Encasing, subject: 1, blocks, tick: 0, animation: 0, paused: false };
                    RENDERED.set(false); trace(&format!("encasing open blocks {}", scene.blocks.len()));
                }
                *canceled = true;
            }
            "key.keyboard.left" if scene.story == Story::Encasing && scene.subject == 1 => {
                if let Some(blocks) = structure(game, Story::Relay) {
                    *scene = Scene { story: Story::Relay, subject: 1, blocks, tick: 0, animation: 0, paused: false };
                    RENDERED.set(false); trace(&format!("relay open blocks {}", scene.blocks.len()));
                }
                *canceled = true;
            }
            _ => {}
        }
    });
}

pub(super) fn mouse(game: &Game<'_>, screen: &NativeScreenView<'_>, button: i32, canceled: &mut bool) {
    if *canceled || button != 0 || game.native_mod_screen() != Some(SCREEN) { return; }
    let [x, y] = screen.mouse;
    let (_, height) = game.gui_size();
    if PREVIOUS.get() != 0 && (20.0..120.0).contains(&x) && (27.0..45.0).contains(&y) {
        BACK.set(true);
        *canceled = true;
        return;
    }
    if !(height - 32.0..height - 12.0).contains(&y) { return; }
    if (20.0..105.0).contains(&x) { key(game, "key.keyboard.space", canceled); }
    else if (115.0..185.0).contains(&x) { key(game, "key.keyboard.r", canceled); }
    else if (190.0..270.0).contains(&x) { CLOSE.set(true); *canceled = true; }
    else if (280.0..width_limit(game)).contains(&x) {
        let story = SCENE.with_borrow(|scene| scene.as_ref().map(|scene| scene.story));
        match story {
            Some(Story::Relay) => key(game, "key.keyboard.right", canceled),
            Some(Story::Encasing) => key(game, "key.keyboard.left", canceled),
            Some(Story::CogRelay) => key(game, "key.keyboard.right", canceled),
            Some(Story::Gearshift) => {
                let subject = SCENE.with_borrow(|scene| scene.as_ref().map(|scene| scene.subject));
                key(game, if subject == Some(4) { "key.keyboard.right" } else { "key.keyboard.left" }, canceled);
            },
            Some(Story::LargeCogRelay) => key(game, "key.keyboard.left", canceled),
            None => {}
        }
    }
}

fn width_limit(game: &Game<'_>) -> f32 {
    game.gui_size().0.min(385.0)
}
