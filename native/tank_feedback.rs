use horizon_core::random::RandomSource;
use super::Game;
use super::create_fluids::Fluid;

// FluidTankBlock selects the sound from the fluid visible at the exchange
// point, then computes pitch from the handler's current amount.
pub(super) fn exchange(game: &mut Game<'_>, pos: [i32; 3], into_tank: bool, sound_fluid: Option<&Fluid>, amount: i32) {
    let lava = sound_fluid.is_some_and(|fluid| matches!(fluid.id.as_str(), "minecraft:lava" | "minecraft:flowing_lava"));
    let sound = match (into_tank, lava) {
        (true, true) => "minecraft:item.bucket.empty_lava",
        (true, false) => "minecraft:item.bucket.empty",
        (false, true) => "minecraft:item.bucket.fill_lava",
        (false, false) => "minecraft:item.bucket.fill",
    };
    let pitch = (1.0 - amount as f32 / (8000.0 * 16.0)).clamp(0.0, 1.0) / 1.5 + 0.5
        + (game.world.random.next_float() - 0.5) / 4.0;
    game.native_play_sound_in_place(sound, pos.map(|v| f64::from(v) + 0.5), 4, 0.5, pitch);
}
