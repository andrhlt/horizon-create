pub const BLOCK: &str = "create:creative_motor";

pub fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 334.0,
        height: 166.0,
        slots: vec![Some([8.0, 84.0])],
        inventory_x: 8.0,
        inventory_y: 80.0,
        own_labels: true,
        own_background: true,
    }
}

pub fn draw_screen(
    game: &crate::game::Game<'_>,
    draw: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    const ROWS: [&str; 2] = ["Counterclockwise RPM", "Clockwise RPM"];
    for (row, label) in ROWS.into_iter().enumerate() {
        let rect = [x + 25.0, y + 19.0 + row as f32 * 11.0, 294.0, 11.0];
        horizon_client::widgets::record(label, rect, true);
        game.native_text(draw, label, [x + 5.0, rect[1] + 1.0], 0x442000, false);
    }
}

pub fn screen_click(at: [f32; 2], right: bool, button: &mut Option<i32>) {
    if right {
        return;
    }
    let [x, y] = at;
    let Some(row) = (0..2).find(|row| {
        let top = 19.0 + *row as f32 * 11.0;
        (top..top + 11.0).contains(&y) && (25.0..319.0).contains(&x)
    }) else {
        return;
    };
    let value = (0..=256)
        .min_by_key(|value| {
            let milestone = (*value).saturating_sub(1) / 32 * 4;
            let marker = 25
                + milestone
                + *value
                + 1
                + i32::from(*value % 32 == 0) * 2
                + i32::from(*value > 0) * 4;
            (marker as f32 - x).abs().to_bits()
        })
        .unwrap_or(0);
    *button = Some(if row == 0 { 256 - value } else { 256 + value });
}
