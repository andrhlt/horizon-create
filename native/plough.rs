use horizon_core::geometry::Direction;
use horizon_world::level::flags;

use super::Game;

pub(super) const PLOUGH: &str = "create:mechanical_plough";

pub(super) fn visit(
    game: &mut Game<'_>,
    local: [i32; 3],
    face: Direction,
    previous: [f64; 3],
    current: [f64; 3],
    motion: [f64; 3],
) {
    let normal = face.normal();
    let dot = normal
        .into_iter()
        .zip(motion)
        .map(|(facing, speed)| f64::from(facing) * speed)
        .sum::<f64>();
    if dot <= 0.0 {
        return;
    }
    let cell = |origin: [f64; 3]| {
        std::array::from_fn::<_, 3, _>(|i| {
            (origin[i] + f64::from(local[i]) + 0.5 + f64::from(normal[i]) * 0.45).floor() as i32
        })
    };
    let at = cell(current);
    if at != cell(previous) {
        till(game, at);
    }
}

pub(super) fn till(game: &mut Game<'_>, at: [i32; 3]) {
    if game.native_block(at) != "minecraft:air" {
        return;
    }
    let soil = [at[0], at[1] - 1, at[2]];
    let tilled = match game.native_block(soil).as_str() {
        "minecraft:grass_block" | "minecraft:dirt" | "minecraft:dirt_path" => "minecraft:farmland",
        "minecraft:coarse_dirt" | "minecraft:rooted_dirt" => "minecraft:dirt",
        _ => return,
    };
    if let Some(state) = game.native_default_state(tilled) {
        game.native_set_block(game.native_dimension(), soil, state, flags::UPDATE_ALL);
    }
}
