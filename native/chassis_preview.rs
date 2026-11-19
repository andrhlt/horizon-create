use std::cell::{Cell, RefCell};
use std::collections::BTreeSet;
use std::sync::OnceLock;

use horizon_core::geometry::Direction;
use winit::keyboard::KeyCode;

use crate::world_primitives::WorldPrimitives;

use super::Game;
use super::create_chassis_range;
use super::create_linear_chassis;
use super::create_machines::offset;
use super::native_world_draw::NativeWorldDraw;

const ACTIVE_TICKS: i16 = 200;
const STOWED_TICKS: i16 = 20;
const FADE_TICKS: i16 = 8;
const FACE_INSET: f32 = 1.0 / 128.0;
const HALF_LINE: f64 = 1.0 / 32.0;
const SPRITE: &str = "create:gui/chassis_preview";
const SCREEN: &str = "create:chassis_range";

struct Preview {
    origin: [i32; 3],
    group: bool,
    members: Vec<[i32; 3]>,
    board_range: Option<i32>,
    selected: i32,
    range_ticks: i16,
    fade: i16,
    blocks: BTreeSet<[i32; 3]>,
    faces: Vec<([i32; 3], Direction)>,
    edges: BTreeSet<([i32; 3], usize)>,
}

thread_local! {
    static PREVIEW: RefCell<Option<Preview>> = const { RefCell::new(None) };
    static LAST_FRAME: Cell<Option<u64>> = const { Cell::new(None) };
}

fn trace_enabled() -> bool {
    static TRACE: OnceLock<bool> = OnceLock::new();
    *TRACE.get_or_init(|| std::env::var_os("CREATE_CHASSIS_PREVIEW_TRACE").is_some())
}

pub(super) fn clear() {
    PREVIEW.with_borrow_mut(|preview| *preview = None);
    LAST_FRAME.with(|last| last.set(None));
}

fn grouping(game: &Game<'_>) -> bool {
    game.physical_keys.contains(&KeyCode::ControlLeft)
        || game.physical_keys.contains(&KeyCode::ControlRight)
}

fn show(game: &Game<'_>, origin: [i32; 3], range: Option<i32>) {
    let group = grouping(game);
    PREVIEW.with_borrow_mut(|current| {
        if let Some(preview) = current
            && preview.range_ticks > 0
            && preview.group == group
            && preview.members.contains(&origin)
            && (range.is_none() || preview.board_range == range)
        {
            preview.range_ticks = ACTIVE_TICKS;
            return;
        }
        let members = if group {
            create_linear_chassis::group(game, origin)
        } else {
            vec![origin]
        };
        let blocks = members
            .iter()
            .flat_map(|&member| {
                let reach = range.unwrap_or_else(|| create_chassis_range::value(game, member));
                create_linear_chassis::preview(game, member, reach)
            })
            .collect();
        let (faces, edges) = boundary(&blocks);
        *current = Some(Preview {
            origin,
            group,
            members,
            board_range: range,
            selected: range.unwrap_or_else(|| create_chassis_range::value(game, origin)),
            range_ticks: ACTIVE_TICKS,
            fade: 0,
            blocks,
            faces,
            edges,
        });
    });
}

pub(super) fn hover(game: &Game<'_>, origin: [i32; 3], range: i32) {
    if create_linear_chassis::is_chassis(&game.native_block(origin)) {
        show(game, origin, Some(range));
    }
}

pub(super) fn tick(game: &Game<'_>) {
    if !game.native_window() {
        return;
    }
    let has_wrench = game
        .stack_in(game.selected)
        .is_some_and(|stack| stack.item.as_ref() == "create:wrench");
    PREVIEW.with_borrow_mut(|current| {
        let Some(preview) = current else { return };
        let [x, _, z] = preview.origin;
        if !game.world.loaded(x, z)
            || !create_linear_chassis::is_chassis(&game.native_block(preview.origin))
        {
            *current = None;
            return;
        }
        if preview.range_ticks == 0 {
            preview.fade -= 1;
            return;
        }
        if has_wrench && game.native_mod_screen() == Some(SCREEN) {
            return;
        }
        if !has_wrench && preview.range_ticks > STOWED_TICKS {
            preview.range_ticks = STOWED_TICKS;
        } else {
            preview.range_ticks -= 1;
        }
    });
    if has_wrench
        && game.native_mod_screen() != Some(SCREEN)
        && let Some(hit) = game.pick()
        && create_linear_chassis::is_chassis(&game.native_block(hit.pos))
    {
        show(game, hit.pos, None);
    }
    if trace_enabled() {
        PREVIEW.with_borrow(|preview| {
            let Some(preview) = preview else { return };
            let mut selected: Vec<_> = preview
                .blocks
                .iter()
                .map(|block| {
                    let [x, y, z] =
                        std::array::from_fn::<_, 3, _>(|i| block[i] - preview.origin[i]);
                    format!("{x}:{y}:{z}")
                })
                .collect();
            selected.sort_unstable();
            let vanished = preview.fade < -FADE_TICKS;
            eprintln!(
                "CREATE_CHASSIS_PREVIEW_HORIZON {},{},{},{},{},{},{},{},{}",
                game.ticks,
                if preview.range_ticks > 0 {
                    preview.range_ticks
                } else {
                    -1
                },
                if vanished { -99 } else { preview.fade },
                if vanished { 0 } else { preview.faces.len() },
                if vanished { 0 } else { preview.edges.len() },
                create_chassis_range::value(game, preview.origin),
                preview.selected,
                preview.group,
                selected.join("|"),
            );
        });
    }
    PREVIEW.with_borrow_mut(|current| {
        if current
            .as_ref()
            .is_some_and(|preview| preview.fade < -FADE_TICKS)
        {
            *current = None;
        }
    });
}

type Face = ([i32; 3], Direction);
type Edge = ([i32; 3], usize);

fn boundary(blocks: &BTreeSet<[i32; 3]>) -> (Vec<Face>, BTreeSet<Edge>) {
    let mut faces = Vec::new();
    let mut edges = BTreeSet::new();
    for &block in blocks {
        for side in Direction::ALL {
            if !blocks.contains(&offset(block, side.normal())) {
                faces.push((block, side));
            }
        }
        // Exactly the cuboid edges with odd incidence stay in the outline.
        for axis in 0..3 {
            let a = (axis + 1) % 3;
            let b = (axis + 2) % 3;
            for i in 0..2 {
                for j in 0..2 {
                    let mut corner = block;
                    corner[a] += i;
                    corner[b] += j;
                    let edge = (corner, axis);
                    if !edges.remove(&edge) {
                        edges.insert(edge);
                    }
                }
            }
        }
    }
    (faces, edges)
}

fn opacity(preview: &Preview, partial: f32) -> Option<f32> {
    let elapsed = (f32::from(-preview.fade - 1) + partial).max(0.0);
    let fade = (1.0 - elapsed / f32::from(FADE_TICKS)).max(0.0).powi(3);
    (fade >= 0.125).then_some(fade)
}

fn quad(side: Direction) -> [[f32; 3]; 4] {
    let points = match side {
        Direction::Down => [[0., 0., 1.], [0., 0., 0.], [1., 0., 0.], [1., 0., 1.]],
        Direction::Up => [[0., 1., 0.], [0., 1., 1.], [1., 1., 1.], [1., 1., 0.]],
        Direction::North => [[1., 1., 0.], [1., 0., 0.], [0., 0., 0.], [0., 1., 0.]],
        Direction::South => [[0., 1., 1.], [0., 0., 1.], [1., 0., 1.], [1., 1., 1.]],
        Direction::West => [[0., 1., 0.], [0., 0., 0.], [0., 0., 1.], [0., 1., 1.]],
        Direction::East => [[1., 1., 1.], [1., 0., 1.], [1., 0., 0.], [1., 1., 0.]],
    };
    let normal = side.normal().map(|v| v as f32 * FACE_INSET);
    points.map(|p| std::array::from_fn(|i| p[i] + normal[i]))
}

pub(super) fn render_faces(game: &Game<'_>, draw: &mut NativeWorldDraw) {
    PREVIEW.with_borrow(|current| {
        let Some(preview) = current else { return };
        let Some(fade) = opacity(preview, draw.partial) else {
            return;
        };
        let alpha = (fade * 255.0).round() as u8;
        let mut submitted = 0;
        for &(block, side) in &preview.faces {
            draw.push();
            draw.translate_world(block.map(f64::from));
            let drawn = game.native_world_quad(
                draw,
                SPRITE,
                quad(side),
                [0., 0., 16., 16.],
                [255, 255, 255, alpha],
            );
            submitted += usize::from(drawn);
            draw.pop();
        }
        if trace_enabled() {
            LAST_FRAME.with(|last| {
                if last.replace(Some(game.ticks)) != Some(game.ticks) {
                    eprintln!(
                        "CREATE_CHASSIS_PREVIEW_DRAW {},{},{}",
                        game.ticks,
                        submitted,
                        preview.edges.len()
                    );
                }
            });
        }
    });
}

pub(super) fn render_edges(partial: f32, primitives: &mut WorldPrimitives) {
    PREVIEW.with_borrow(|current| {
        let Some(preview) = current else { return };
        let Some(fade) = opacity(preview, partial) else {
            return;
        };
        let color = ((fade * 255.0).round() as u32) << 24 | 0xFFFFFF;
        let thickness = HALF_LINE * f64::from(fade);
        for &(corner, axis) in &preview.edges {
            let min = corner.map(|n| f64::from(n) - thickness);
            let mut max = corner.map(|n| f64::from(n) + thickness);
            max[axis] += 1.0;
            primitives.filled_box(min, max, color);
        }
    });
}
