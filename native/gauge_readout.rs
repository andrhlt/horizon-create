use mod_api::{ClientHost, CrosshairTarget, GuiRenderPostEvent, Host, Tag};
use std::sync::OnceLock;

static KEYS: OnceLock<(mod_api::BlockKey, mod_api::BlockKey)> = OnceLock::new();

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let _ = KEYS.set((
        registrar.block_key("create:speedometer"),
        registrar.block_key("create:stressometer"),
    ));
}

pub fn draw(host: &dyn ClientHost, event: &mut GuiRenderPostEvent<'_>) {
    if event.gui_hidden || !event.focused {
        return;
    }
    let Some((speedometer, stressometer)) = KEYS.get() else {
        return;
    };
    let Some(camera) = host.camera() else { return };
    let Some(CrosshairTarget::Block { pos, .. }) = host.crosshair_target() else {
        return;
    };
    let at = [pos.x, pos.y, pos.z];
    let Some(level) = host.level(&camera.dimension) else {
        return;
    };
    let Some(block) = level.block(host, at) else {
        return;
    };
    let label = if block == *speedometer {
        "Speed"
    } else if block == *stressometer {
        "Stress"
    } else {
        return;
    };
    let Some(data) = host
        .block_entity(level, at)
        .and_then(|entity| entity.data(host))
    else {
        return;
    };
    let value = |compound: &mod_api::Compound, key: &str| match compound.get(&key.into()) {
        Some(Tag::Float(bits)) => f32::from_bits(*bits),
        _ => 0.0,
    };
    let rpm = value(&data, "Speed");
    let network = match data.get(&"Network".into()) {
        Some(Tag::Compound(network)) => network,
        _ => return,
    };
    let capacity = value(network, "Capacity");
    let stress = value(network, "Stress");
    let line = if label == "Speed" {
        let effective = super::kinetic_slice::effective_speed(rpm, capacity, stress);
        format!("Speed: {effective:.1} RPM")
    } else {
        format!("Stress: {stress:.1} / {capacity:.1}")
    };
    let [width, height] = event.batch.size();
    let x = width * 0.5 + 10.0;
    let y = height * 0.5 + 10.0;
    let text_width = event.batch.text_width(&line);
    event
        .batch
        .fill([x - 3.0, y - 3.0, text_width + 6.0, 14.0], 0x90000000);
    event.batch.text(&line, [x, y], 0xffeeeeee, true);
}
