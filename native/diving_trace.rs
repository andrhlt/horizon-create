fn diving_trace(game: &crate::game::Game<'_>, target: Target) {
    use std::io::Write;
    use std::sync::OnceLock;

    static TRACE: OnceLock<Option<std::path::PathBuf>> = OnceLock::new();
    let Some(path) = TRACE.get_or_init(|| std::env::var_os("CREATE_TRACE_DIVING").map(Into::into))
    else {
        return;
    };
    let Target::Mob(id) = target else { return };
    let Some(mob) = game.mobs.iter().find(|mob| mob.id == id && !mob.removed) else {
        return;
    };
    if let Ok(mut log) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    {
        let _ = writeln!(
            log,
            "{},{},{}",
            game.world.game_time,
            mob.fluids.in_lava,
            mob.fire_immune()
        );
    }
}
