fn elevator_sound_playback(
    sound: &crate::sound_engine::SoundPlayback<'_>,
    volume: f32,
    pitch: f32,
) {
    use std::sync::OnceLock;
    static TRACE: OnceLock<bool> = OnceLock::new();
    let elevator_trace =
        *TRACE.get_or_init(|| std::env::var_os("HORIZON_CREATE_ELEVATOR_TRACE").is_some());
    if std::env::var_os("HORIZON_CREATE_WHISTLE_TRACE").is_some()
        && matches!(
            sound.identifier,
            "create:whistle" | "create:whistle_high" | "create:whistle_low" | "create:chiff"
        )
    {
        let [x, y, z] = sound.position;
        eprintln!(
            "CREATE_WHISTLE_PLAYBACK {},{},{x},{y},{z},{volume},{pitch},{}",
            sound.identifier, sound.source, sound.starting
        );
    }
    if elevator_trace
        && sound.starting
        && matches!(
            sound.identifier,
            "create:scroll_value"
                | "create:controller_click"
                | "create:depot_plop"
                | "create:cardboard_bonk"
                | "create:desk_bell"
                | "create:package_pop"
                | "minecraft:entity.snowball.throw"
                | "minecraft:entity.item_frame.add_item"
                | "create:package_pop_compounded_1"
                | "create:depot_slide"
                | "create:funnel_flap"
                | "create:funnel_flap_compounded_1"
                | "create:mechanical_press_activation"
                | "create:mechanical_press_activation_compounded_1"
                | "create:mechanical_press_activation_belt"
                | "create:mechanical_press_activation_belt_compounded_1"
                | "create:contraption_assemble"
                | "create:contraption_assemble_compounded_1"
                | "create:contraption_disassemble"
                | "minecraft:block.iron_door.open"
                | "minecraft:block.iron_door.close"
                | "minecraft:block.wooden_trapdoor.open"
                | "minecraft:block.wooden_trapdoor.close"
                | "minecraft:block.chest.open"
                | "minecraft:block.wooden_button.click_off"
        )
    {
        let [x, y, z] = sound.position;
        eprintln!(
            "CREATE_ELEVATOR_PLAYBACK {},{},{x},{y},{z},{volume},{pitch}",
            sound.identifier, sound.source,
        );
    }
}
