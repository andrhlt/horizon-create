use horizon_core::geometry::Direction;
use horizon_world::{nbt::{Compound, Tag}, registry::BlockStateId};

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_belt_funnel::{ANDESITE, BRASS, FUNNEL};
use super::create_fan::facing;
use super::native_block_entity_draw::BlockEntityDraw;

const BELT_FLAP: &str = "create:block/belt_funnel/flap";
const FLAP: &str = "create:block/funnel/flap";
const CUE: &str = "create:funnel_flap";
const SECOND_CUE: &str = "create:funnel_flap_compounded_1";
const FLAP_AT: &str = "FlapAt";
const FLAP_DIRECTION: &str = "FlapDirection";
const PIVOT: [f32; 3] = [0.0, 10.0 / 16.0, 9.5 / 16.0];

fn set_motion(entity: &mut ModBlockEntity, now: i64, direction: i8) {
    entity.set_client_update_fields(Compound::from([
        (FLAP_AT.into(), Tag::Long(now)),
        (FLAP_DIRECTION.into(), Tag::Byte(direction)),
    ]));
}

fn play(game: &mut Game<'_>, pos: [i32; 3]) {
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    game.native_play_sound_in_place(CUE, at, 4, 0.125, 1.5);
    game.native_play_sound_in_place(SECOND_CUE, at, 4, 0.0425, 0.75);
}

fn start_inward(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let now = game.world.game_time;
    if game.native_with_mod_block_entity(pos, |entity| set_motion(entity, now, -1)).is_none() {
        return false;
    }
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn pulled(game: &mut Game<'_>, pos: [i32; 3]) {
    if start_inward(game, pos) {
        // Java's funnel insertion and its direct belt caller each trigger the flap.
        play(game, pos);
        play(game, pos);
    }
}

pub(super) fn received(game: &mut Game<'_>, pos: [i32; 3]) {
    if start_inward(game, pos) {
        play(game, pos);
    }
}

pub(super) fn pushed(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    set_motion(entity, game.world.game_time, 1);
    game.native_block_entity_sync(pos);
    play(game, pos);
}

pub(super) fn update_tag(entity: &ModBlockEntity, tag: &mut Option<Compound>) {
    if entity.id == FUNNEL {
        let fields = entity.take_client_update_fields();
        if !fields.is_empty() {
            tag.get_or_insert_with(Default::default).extend(fields);
        }
    }
}

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([BELT_FLAP.into(), FLAP.into()]);
}

fn flap_value(age: i64, direction: i8) -> f32 {
    if age > 220 {
        return 0.0;
    }
    let mut value = f32::from(direction);
    for _ in 0..age {
        value += -value * 0.05;
    }
    value
}

fn segment_angle(flap: f32, segment: usize) -> f32 {
    let intensity = [1.0, 2.0, 3.0, 1.5][segment];
    let radians = (f64::from(1.0 - flap.abs()) * std::f64::consts::PI * intensity) as f32;
    let table_index = (radians * 10_430.378_f32) as i32 & 65_535;
    let sine = (f64::from(table_index) * std::f64::consts::TAU / 65_536.0).sin() as f32;
    sine * 30.0 * flap * if flap < 0.0 { 0.5 } else { 1.0 }
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    block: &str,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    if entity.id != FUNNEL {
        return;
    }
    let yaw = match facing(game, state).map(Direction::opposite) {
        Some(Direction::North) => 180.0,
        Some(Direction::East) => -270.0,
        Some(Direction::West) => -90.0,
        Some(Direction::South) => 0.0,
        _ => return,
    };
    let (model, offset) = if matches!(block, ANDESITE | BRASS) {
        (BELT_FLAP, match game.native_block_state_property(state, "shape") {
            Some("extended") => -8.0 / 16.0,
            Some("pulling" | "pushing") => 2.0 / 16.0,
            _ => 0.0,
        })
    } else {
        (FLAP, 1.0 / 16.0)
    };
    let mut sample = None;
    let flap = match entity.nbt.get(&FLAP_AT.into()) {
        Some(Tag::Long(start)) => {
            let age = draw.game_time.saturating_sub(*start).saturating_sub(1).max(0);
            let direction = match entity.nbt.get(&FLAP_DIRECTION.into()) {
                Some(Tag::Byte(direction)) => *direction,
                _ => -1,
            };
            let previous = flap_value(age, direction);
            let current = previous + -previous * 0.05;
            sample = Some((age, previous, current));
            previous + (current - previous) * draw.partial
        }
        _ => 0.0,
    };
    let trace = std::env::var_os("CREATE_FUNNEL_FLAP_RENDER").is_some();
    let start = draw.vertices_mut().len();
    let mut angles = [0.0; 4];
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
    draw.translate([0.075 / 16.0, 0.0, offset]);
    for (segment, angle) in angles.iter_mut().enumerate() {
        *angle = segment_angle(flap, segment);
        draw.push();
        draw.rotate_about([1.0, 0.0, 0.0], *angle, PIVOT);
        game.native_draw_model(draw, model, 0xffffff);
        draw.pop();
        draw.translate([-3.05 / 16.0, 0.0, 0.0]);
    }
    draw.pop();
    if trace && let Some((age, previous, current)) = sample {
        let [x, y, z] = pos;
        let vertices = draw.vertices_mut().len() - start;
        eprintln!(
            "CREATE_FUNNEL_FLAP_RENDER {x},{y},{z},{},{age},{},{previous:.9},{current:.9},{flap:.9},{vertices},{angles:?}",
            draw.game_time, draw.partial
        );
    }
}
