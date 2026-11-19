use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_client::first_person::Hand;
use horizon_client::hud::HudBatch;
use horizon_client::mod_api::NativeScreenView;
use horizon_world::nbt::Tag;
use serde::{Deserialize, Serialize};

use super::{
    Game,
    commands::Target,
    create_worldshaper::{Brush, PATTERNS, TOOLS},
};
use crate::items::ItemStack;

const ITEM: &str = "create:handheld_worldshaper";
const CHANNEL: &str = "create:worldshaper_screen";
const BACKGROUND: &str = "create:gui/curiosities";
const WIDGETS: &str = "create:gui/widgets";
const ICONS: &str = "create:gui/icons";
const WIDTH: f32 = 234.0;
const HEIGHT: f32 = 103.0;
const PLACEMENTS: [&str; 3] = ["merged", "attached", "inserted"];

#[derive(Clone, Deserialize, Serialize)]
struct Settings {
    token: u64,
    brush: u8,
    pattern: u8,
    dimensions: [i32; 3],
    placement: u8,
    tool: u8,
}

struct Session {
    token: u64,
    slot: usize,
    main_hand: bool,
    held: ItemStack,
}

struct Editor {
    settings: Settings,
    closing: bool,
}

thread_local! {
    static SESSIONS: RefCell<HashMap<u128, Session>> = RefCell::new(HashMap::new());
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn open(game: &mut Game<'_>, stack: &ItemStack) -> bool {
    if stack.item.as_ref() != ITEM || !game.native_sneaking() {
        return false;
    }
    let Some(player) = game.native_acting_player() else {
        return false;
    };
    let slot = game.held_slot();
    let main_hand = game.hand == Hand::Main;
    // On-block and item use can arrive together for the same click.
    if SESSIONS.with_borrow(|sessions| {
        sessions.get(&player.uuid).is_some_and(|session| {
            session.slot == slot && session.main_hand == main_hand && &session.held == stack
        })
    }) {
        return true;
    }
    let pattern = match game.native_component(stack, "create:placement_pattern") {
        Ok(Some(Tag::String(value))) => PATTERNS
            .iter()
            .position(|name| *name == value.to_string_lossy())
            .unwrap_or(0) as u8,
        _ => 0,
    };
    let brush = match game.native_component(stack, "create:shaper_brush") {
        Ok(Some(Tag::String(value))) => Brush::ALL
            .into_iter()
            .find(|brush| brush.name() == value.to_string_lossy())
            .unwrap_or_default(),
        _ => Brush::default(),
    };
    let dimensions = match game.native_component(stack, "create:shaper_brush_params") {
        Ok(Some(Tag::IntArray(values))) => <[i32; 3]>::try_from(values.as_slice())
            .ok()
            .map(|values| brush.clamp(values))
            .unwrap_or([1, 1, 1]),
        _ => [1, 1, 1],
    };
    let placement = match game.native_component(stack, "create:shaper_placement_options") {
        Ok(Some(Tag::String(value))) => PLACEMENTS
            .iter()
            .position(|name| *name == value.to_string_lossy())
            .unwrap_or(0) as u8,
        _ => 0,
    };
    let tool = match game.native_component(stack, "create:shaper_tool") {
        Ok(Some(Tag::String(value))) => TOOLS
            .iter()
            .position(|name| *name == value.to_string_lossy())
            .unwrap_or(0) as u8,
        _ => 0,
    };
    let tool = if brush.tools().contains(&usize::from(tool)) {
        tool
    } else {
        brush.tools()[0] as u8
    };
    let token = SERIAL.with(|serial| {
        let next = serial.get().wrapping_add(1);
        serial.set(next);
        next
    });
    let settings = Settings {
        token,
        brush: brush.index(),
        pattern,
        dimensions,
        placement,
        tool,
    };
    let Ok(data) = serde_json::to_vec(&settings) else {
        return false;
    };
    if game
        .native_net_send_to_player(player.uuid, CHANNEL, &data)
        .is_err()
    {
        return false;
    }
    SESSIONS.with_borrow_mut(|sessions| {
        sessions.insert(
            player.uuid,
            Session {
                token,
                slot,
                main_hand,
                held: stack.clone(),
            },
        )
    });
    true
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 256 || game.native_mod_screen() == Some(CHANNEL) {
        return;
    }
    let Ok(settings) = serde_json::from_slice::<Settings>(data) else {
        return;
    };
    if valid(&settings) && game.native_mod_screen_open(CHANNEL) {
        EDITOR.with_borrow_mut(|editor| {
            *editor = Some(Editor {
                settings,
                closing: false,
            })
        });
    }
}

fn valid(settings: &Settings) -> bool {
    usize::from(settings.placement) < PLACEMENTS.len()
        && usize::from(settings.tool) < TOOLS.len()
        && usize::from(settings.pattern) < PATTERNS.len()
        && Brush::ALL
            .get(usize::from(settings.brush))
            .is_some_and(|brush| {
                brush.tools().contains(&usize::from(settings.tool))
                    && brush.clamp(settings.dimensions) == settings.dimensions
            })
}

pub(super) fn save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 256 {
        return;
    }
    let Ok(settings) = serde_json::from_slice::<Settings>(data) else {
        return;
    };
    if !valid(&settings) {
        return;
    }
    let session = SESSIONS.with_borrow_mut(|sessions| {
        if sessions.get(&player)?.token != settings.token {
            return None;
        }
        sessions.remove(&player)
    });
    let Some(session) = session else { return };
    let Some(conn) = game.native_conn(player) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        if (session.main_hand && actor.selected != session.slot)
            || actor.stack_in(session.slot) != Some(&session.held)
        {
            return;
        }
        let mut held = session.held;
        for (key, value) in [
            (
                "create:placement_pattern",
                Tag::String(PATTERNS[usize::from(settings.pattern)].into()),
            ),
            (
                "create:shaper_brush",
                Tag::String(Brush::ALL[usize::from(settings.brush)].name().into()),
            ),
            (
                "create:shaper_brush_params",
                Tag::IntArray(settings.dimensions.to_vec()),
            ),
            (
                "create:shaper_tool",
                Tag::String(TOOLS[usize::from(settings.tool)].into()),
            ),
            (
                "create:shaper_placement_options",
                Tag::String(PLACEMENTS[settings.placement as usize].into()),
            ),
        ] {
            if actor.native_set_component(&mut held, key, value).is_err() {
                return;
            }
        }
        *actor.stack_in_mut(session.slot) = Some(held);
    });
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [
        x + ((w - WIDTH) / 2.0).floor() - 10.0,
        y + ((h - HEIGHT) / 2.0).floor(),
    ]
}

fn contains([x, y, w, h]: [f32; 4], [mx, my]: [f32; 2]) -> bool {
    mx >= x && mx < x + w && my >= y && my < y + h
}

fn brush_selector([x, y]: [f32; 2]) -> [f32; 4] {
    [x + 56.0, y + 20.0, 77.0, 18.0]
}

fn dimension([x, y]: [f32; 2], index: usize) -> [f32; 4] {
    [x + 56.0 + index as f32 * 20.0, y + 40.0, 18.0, 18.0]
}

fn pattern_button([x, y]: [f32; 2], index: usize) -> [f32; 4] {
    [
        x + 158.0 + (index % 3) as f32 * 18.0,
        y + 21.0 + (index / 3) as f32 * 18.0,
        18.0,
        18.0,
    ]
}

fn tool_button([x, y]: [f32; 2], index: usize) -> [f32; 4] {
    [x + 7.0 + index as f32 * 18.0, y + 79.0, 18.0, 18.0]
}

fn connectivity([x, y]: [f32; 2], index: usize) -> [f32; 4] {
    [x + 79.0 + index as f32 * 18.0, y + 79.0, 18.0, 18.0]
}

fn placement([x, y]: [f32; 2], index: usize) -> [f32; 4] {
    [x + 136.0 + index as f32 * 18.0, y + 79.0, 18.0, 18.0]
}

fn confirm([x, y]: [f32; 2]) -> [f32; 4] {
    [x + WIDTH - 33.0, y + HEIGHT - 24.0, 18.0, 18.0]
}

fn button(
    game: &Game<'_>,
    out: &mut HudBatch,
    screen: &NativeScreenView<'_>,
    rect: [f32; 4],
    icon: [f32; 2],
    selected: bool,
) {
    let u = if contains(rect, screen.mouse) {
        18.0
    } else if selected {
        72.0
    } else {
        0.0
    };
    game.native_sprite(out, WIDGETS, [u, 0.0, 18.0, 18.0], rect);
    game.native_sprite(
        out,
        ICONS,
        [icon[0], icon[1], 16.0, 16.0],
        [rect[0] + 1.0, rect[1] + 1.0, 16.0, 16.0],
    );
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, out: &mut HudBatch) {
    if game.native_mod_screen() != Some(CHANNEL) {
        return;
    }
    EDITOR.with_borrow(|editor| {
        let Some(editor) = editor else { return };
        let [x, y] = origin(screen.rect);
        game.native_sprite(
            out,
            BACKGROUND,
            [0.0, 0.0, WIDTH, HEIGHT],
            [x, y, WIDTH, HEIGHT],
        );
        let title = game.translate("item.create.handheld_worldshaper", "Creative Worldshaper");
        game.native_text(
            out,
            &title,
            [x + (WIDTH - game.native_text_width(&title)) / 2.0, y + 4.0],
            0x54214f,
            false,
        );
        let brush = Brush::ALL[usize::from(editor.settings.brush)];
        let brush_label = ["Cuboid", "Sphere", "Cylinder", "Surface", "Cluster"]
            [usize::from(editor.settings.brush)];
        game.native_text(out, brush_label, [x + 61.0, y + 25.0], 0xffffff, true);
        horizon_client::widgets::record(
            &format!("Brush: {brush_label}"),
            brush_selector([x, y]),
            true,
        );
        let first_label = match brush {
            Brush::Cuboid => "Width",
            Brush::Sphere | Brush::Cylinder => "Radius",
            _ => "Range",
        };
        for (i, label) in [first_label, "Height", "Length"]
            .into_iter()
            .take(brush.count())
            .enumerate()
        {
            let area = dimension([x, y], i);
            let value = editor.settings.dimensions[i].to_string();
            game.native_text(
                out,
                &value,
                [
                    area[0] + 9.0 - game.native_text_width(&value) / 2.0,
                    y + 45.0,
                ],
                0xffffff,
                true,
            );
            horizon_client::widgets::record(&format!("{label}: {value}"), area, true);
        }
        for i in brush.count()..3 {
            game.native_sprite(
                out,
                BACKGROUND,
                [238.0, 0.0, 18.0, 18.0],
                dimension([x, y], i),
            );
        }
        game.native_text(out, "Tool", [x + 7.0, y + 69.0], 0x767676, false);
        if !brush.connected() {
            game.native_text(out, "Placement", [x + 136.0, y + 69.0], 0x767676, false);
        }
        for (i, label) in [
            "Solid",
            "Checkerboard",
            "Inverted Checkerboard",
            "25% Roll",
            "50% Roll",
            "75% Roll",
        ]
        .into_iter()
        .enumerate()
        {
            let area = pattern_button([x, y], i);
            button(
                game,
                out,
                screen,
                area,
                [(i % 4) as f32 * 16.0, 96.0 + (i / 4) as f32 * 16.0],
                i == usize::from(editor.settings.pattern),
            );
            let label = game.translate(
                &format!("create.gui.terrainzapper.pattern.{}", PATTERNS[i]),
                label,
            );
            horizon_client::widgets::record(&label, area, true);
        }
        for (i, &tool) in brush.tools().iter().enumerate() {
            let label = ["Fill", "Place", "Replace", "Clear", "Overlay", "Flatten"][tool];
            let area = tool_button([x, y], i);
            button(
                game,
                out,
                screen,
                area,
                [112.0 + tool as f32 * 16.0, 32.0],
                tool == usize::from(editor.settings.tool),
            );
            horizon_client::widgets::record(label, area, true);
        }
        if brush.connected() {
            for (i, label) in ["Follow Diagonals", "Across Materials"]
                .into_iter()
                .enumerate()
            {
                let area = connectivity([x, y], i);
                let active = editor.settings.dimensions[i + 1] == 0;
                button(
                    game,
                    out,
                    screen,
                    area,
                    [32.0 + i as f32 * 16.0, 112.0],
                    active,
                );
                horizon_client::widgets::record(
                    &format!("{label}: {}", if active { "On" } else { "Off" }),
                    area,
                    true,
                );
            }
        } else {
            for (i, label) in ["Merged", "Attached", "Inserted"].into_iter().enumerate() {
                let area = placement([x, y], i);
                button(
                    game,
                    out,
                    screen,
                    area,
                    [64.0 + i as f32 * 16.0, 32.0],
                    i == editor.settings.placement as usize,
                );
                horizon_client::widgets::record(label, area, true);
            }
        }
        let area = confirm([x, y]);
        button(game, out, screen, area, [0.0, 16.0], false);
        horizon_client::widgets::record("Confirm", area, true);
        game.native_item(out, ITEM, [x + WIDTH, y + HEIGHT - 48.0], 64.0);
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(CHANNEL) || button != 0 {
        return;
    }
    let origin = origin(screen.rect);
    EDITOR.with_borrow_mut(|editor| {
        let Some(editor) = editor else { return };
        let brush = Brush::ALL[usize::from(editor.settings.brush)];
        if contains(confirm(origin), screen.mouse) {
            editor.closing = true;
            *canceled = true;
        } else if let Some(i) =
            (0..PATTERNS.len()).find(|&i| contains(pattern_button(origin, i), screen.mouse))
        {
            editor.settings.pattern = i as u8;
            *canceled = true;
        } else if let Some(i) =
            (0..brush.tools().len()).find(|&i| contains(tool_button(origin, i), screen.mouse))
        {
            editor.settings.tool = brush.tools()[i] as u8;
            *canceled = true;
        } else if brush.connected() {
            if let Some(i) = (0..2).find(|&i| contains(connectivity(origin, i), screen.mouse)) {
                editor.settings.dimensions[i + 1] = 1 - editor.settings.dimensions[i + 1];
                *canceled = true;
            }
        } else {
            for i in 0..3 {
                if contains(placement(origin, i), screen.mouse) {
                    editor.settings.placement = i as u8;
                    *canceled = true;
                    break;
                }
            }
        }
    });
}

pub(super) fn scroll(
    game: &Game<'_>,
    mouse: [f32; 2],
    scroll: [f64; 2],
    modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(CHANNEL) || scroll[1] == 0.0 {
        return;
    }
    let Some(renderer) = game.renderer.as_ref() else {
        return;
    };
    let batch = HudBatch::new([renderer.config.width, renderer.config.height]);
    let origin = origin([0.0, 0.0, batch.width, batch.height]);
    EDITOR.with_borrow_mut(|editor| {
        let Some(editor) = editor else { return };
        let direction = scroll[1].signum() as i32;
        if contains(brush_selector(origin), mouse) {
            editor.settings.brush = (i32::from(editor.settings.brush) + direction)
                .clamp(0, Brush::ALL.len() as i32 - 1) as u8;
            let brush = Brush::ALL[usize::from(editor.settings.brush)];
            editor.settings.dimensions = brush.clamp(editor.settings.dimensions);
            if !brush.tools().contains(&usize::from(editor.settings.tool)) {
                editor.settings.tool = brush.tools()[0] as u8;
            }
            *canceled = true;
            return;
        }
        let brush = Brush::ALL[usize::from(editor.settings.brush)];
        for i in 0..brush.count() {
            if contains(dimension(origin, i), mouse) {
                let step = if modifiers & 1 != 0 { 5 } else { 1 };
                let (min, max) = brush.bounds(i);
                editor.settings.dimensions[i] =
                    (editor.settings.dimensions[i] + direction * step).clamp(min, max);
                *canceled = true;
                break;
            }
        }
    });
}

pub(super) fn tick(game: &mut Game<'_>) {
    let closed = EDITOR.with_borrow_mut(|editor| {
        if game.native_mod_screen() != Some(CHANNEL)
            || editor.as_ref().is_some_and(|editor| editor.closing)
        {
            editor.take()
        } else {
            None
        }
    });
    if let Some(editor) = closed {
        if let Ok(data) = serde_json::to_vec(&editor.settings) {
            let _ = game.native_net_send_to_server(CHANNEL, &data);
        }
        game.native_mod_screen_close(CHANNEL);
    }
}
