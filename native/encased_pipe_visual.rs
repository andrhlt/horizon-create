use std::sync::OnceLock;

use horizon_core::geometry::Direction;

use super::Game;
use super::create_fluid_tank::{CREATIVE, TANK};
use super::create_fluids::{BASIN, name, open_to};
use super::create_item_drain::DRAIN;
use super::create_machines::{mod_entity, offset};
use super::create_portable_interface::FLUID as PORTABLE_INTERFACE;
use super::create_spout::SPOUT;
use super::native_block_entity_draw::BlockEntityDraw;

const PARTS: [&str; 2] = ["rim_connector", "drain"];
static TRACE: OnceLock<bool> = OnceLock::new();

fn model(part: &str, face: Direction) -> String {
    format!("create:block/fluid_pipe/{part}/{}", name(face))
}

pub(super) fn models(models: &mut Vec<String>) {
    for face in Direction::ALL {
        models.extend(PARTS.map(|part| model(part, face)));
    }
}

fn has_draining_neighbor(game: &Game<'_>, pos: [i32; 3], face: Direction) -> bool {
    let neighbor = offset(pos, face.normal());
    let exposed_side = face.opposite();
    // Java's encased transport keeps only the DRAIN attachment. Hose pulleys
    // and other pipes never qualify, even when their adjacent port is open.
    let has_fluid_handler = match game.native_block(neighbor).as_str() {
        TANK | CREATIVE | BASIN | PORTABLE_INTERFACE => true,
        DRAIN => exposed_side != Direction::Up,
        SPOUT => exposed_side != Direction::Down,
        _ => false,
    };
    has_fluid_handler && mod_entity(game, neighbor).is_some()
}

pub(super) fn submit(game: &Game<'_>, pos: [i32; 3], draw: &mut BlockEntityDraw) {
    let mut flags = 0u8;
    let mut drawn = 0u8;
    for (index, face) in Direction::ALL.into_iter().enumerate() {
        if open_to(game, pos, face) && has_draining_neighbor(game, pos, face) {
            flags |= 1 << index;
            for part in PARTS {
                drawn += u8::from(game.native_draw_model(draw, &model(part, face), 0xFFFFFF));
            }
        }
    }

    if *TRACE.get_or_init(|| std::env::var_os("CREATE_ENCASED_PIPE_DRAIN_TRACE").is_some()) {
        let [x, y, z] = pos;
        let faces = Direction::ALL
            .into_iter()
            .enumerate()
            .filter_map(|(index, face)| (flags & (1 << index) != 0).then_some(name(face)))
            .collect::<Vec<_>>()
            .join("|");
        eprintln!("CREATE_ENCASED_PIPE_DRAIN {x},{y},{z},{faces},{drawn}");
    }
}
