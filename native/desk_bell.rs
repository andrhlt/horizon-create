use horizon_core::{geometry::Direction, random::RandomSource};
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::{PlacementContext, flags},
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use crate::containers::ModBlockEntity;

use super::{
    Game, GameLevel, Hand, create_contact::face_name, native_block_entity_draw::BlockEntityDraw,
};

pub(super) const BELL: &str = "create:desk_bell";
const PLUNGER: &str = "create:block/desk_bell/plunger";
const BODY: &str = "create:block/desk_bell/bell";

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([PLUNGER.to_owned(), BODY.to_owned()]);
}

pub(super) fn is_bell(level: &GameLevel<'_>, state: BlockStateId) -> bool {
    level.native_state_block(state) == Some(BELL)
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<Option<BlockStateId>> {
    if !is_bell(level, state) {
        return None;
    }
    Some((|| {
        let state = level.native_state_with_property(state, "facing", face_name(context.face))?;
        level.native_state_with_property(
            state,
            "waterlogged",
            if fluid.kind() == FluidKind::Water && fluid.is_source() {
                "true"
            } else {
                "false"
            },
        )
    })())
}

pub(super) fn signal(
    level: &GameLevel<'_>,
    state: BlockStateId,
    face: Direction,
    direct: bool,
    out: &mut i32,
) {
    let Some(data) = level.registry.state(state).filter(|data| data.name == BELL) else {
        return;
    };
    if data
        .properties
        .get("powered")
        .is_some_and(|value| value == "true")
        && (!direct
            || data
                .properties
                .get("facing")
                .is_some_and(|side| side == face_name(face.opposite())))
    {
        *out = 15;
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    if *canceled
        || !game.native_authoritative()
        || game.hand != Hand::Main
        || game.native_block(pos) != BELL
        || game
            .held()
            .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
    {
        return;
    }

    let now = game.world.game_time;
    let phase = game.world.random.next_float() * std::f32::consts::TAU;
    if game
        .native_with_mod_block_entity(pos, |entity| {
            entity.data = vec![20];
            entity.set_client_update_fields(Compound::from([
                ("DingAt".into(), Tag::Long(now)),
                ("DingPhase".into(), Tag::Float(phase.to_bits())),
            ]));
        })
        .is_none()
    {
        return;
    }

    game.native_set_block_property_with(pos, "powered", "true", flags::UPDATE_ALL);
    game.native_update_signal_neighbors(game.native_dimension(), pos);
    game.native_block_entity_sync(pos);
    game.native_play_sound_in_place(BELL, pos.map(|v| f64::from(v) + 0.5), 4, 1.0, 1.0);
    game.swing_arm();
    *canceled = true;
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let Some(timer) = entity.data.first_mut() else {
        return;
    };
    *timer -= 1;
    if *timer <= 0 {
        entity.data.clear();
        game.native_set_block_property_with(pos, "powered", "false", flags::UPDATE_ALL);
        game.native_update_signal_neighbors(game.native_dimension(), pos);
    }
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(data) = game.pack.assets.registry.state(state) else {
        return;
    };
    if !data
        .properties
        .get("powered")
        .is_some_and(|value| value == "true")
    {
        return;
    }
    let (pitch, yaw) = match data.properties.get("facing").map(String::as_str) {
        Some("down") => (180.0, 0.0),
        Some("north") => (90.0, 180.0),
        Some("south") => (90.0, 0.0),
        Some("east") => (90.0, 90.0),
        Some("west") => (90.0, 270.0),
        _ => (0.0, 0.0),
    };
    let progress = match entity.nbt.get(&"DingAt".into()) {
        Some(Tag::Long(start)) => {
            let elapsed = draw.game_time.saturating_sub(*start).clamp(0, 21) as f32;
            (1.0 - (elapsed + draw.partial - 1.0).max(0.0) * 0.05).max(0.0)
        }
        _ => 0.0,
    };
    let phase = match entity.nbt.get(&"DingPhase".into()) {
        Some(Tag::Float(value)) => f32::from_bits(*value),
        _ => 0.0,
    };
    let pivot = [0.5; 3];
    let x = [1.0, 0.0, 0.0];
    let y = [0.0, 1.0, 0.0];
    let z = [0.0, 0.0, 1.0];
    let dip = 1.0 - 4.0 * ((progress - 0.5).max(0.0) - 0.5).powi(2);
    let swing = progress.powf(1.25) * 8.0;
    let angle = progress * std::f32::consts::PI * 4.0 + phase;

    draw.push();
    draw.rotate_about(y, yaw, pivot);
    draw.rotate_about(x, pitch, pivot);
    draw.push();
    draw.translate([0.0, dip * -0.75 / 16.0, 0.0]);
    game.native_draw_model(draw, PLUNGER, 0xffffff);
    draw.pop();
    draw.rotate_about(x, swing * angle.sin(), pivot);
    draw.rotate_about(z, swing * angle.cos(), pivot);
    draw.translate(pivot);
    draw.scale([0.995; 3]);
    draw.translate([-0.5; 3]);
    game.native_draw_model(draw, BODY, 0xffffff);
    draw.pop();
}
