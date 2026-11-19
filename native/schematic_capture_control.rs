// Fixture-only bridge: enabled only when a test supplies an output path.
fn schematic_capture_control(
    game: &mut crate::game::Game<'_>,
    line: &str,
) -> std::ops::ControlFlow<Result<Option<Value>>> {
    let Some(path) = std::env::var_os("CREATE_TEST_SCHEMATIC_CAPTURE") else {
        return std::ops::ControlFlow::Continue(());
    };
    let mut words = line.split_whitespace();
    if words.next() != Some("create-test-schematic-capture") {
        return std::ops::ControlFlow::Continue(());
    }
    let mut run = || -> Result<Option<Value>> {
        let values: Vec<i32> = words
            .map(str::parse)
            .collect::<std::result::Result<_, _>>()?;
        if values.len() != 6 {
            return Err("expected six corner coordinates".into());
        }
        game.require_world()?;
        let first = [values[0], values[1], values[2]];
        let second = [values[3], values[4], values[5]];
        let path = std::path::PathBuf::from(path);
        if let Some(server) = &game.integrated {
            server
                .call(move |g| {
                    g.in_owner_level(|g| {
                        g.capture_schematic(first, second, &path)
                            .map_err(|e| e.to_string())
                    })
                })
                .ok_or(super::integrated::NO_ANSWER)??;
        } else {
            game.capture_schematic(first, second, &path)?;
        }
        Ok(Some(serde_json::json!({"ok": true})))
    };
    std::ops::ControlFlow::Break(run())
}
