// StickerBlockEntity.tick + Catnip LerpedFloat.LINEAR, with Java float storage.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Animation {
    pub previous: f32,
    pub value: f32,
    pub target: f32,
    pub chasing: bool,
    pub update: bool,
}
impl Animation {
    pub(crate) fn new(extended: bool) -> Self {
        let value = if extended { 1.0 } else { 0.0 };
        Self { previous: value, value, target: value, chasing: false, update: false }
    }
    pub(crate) fn receive(&mut self) { self.update = true; }
    // Bits preserve Java's event order: attachment, detachment, visual update.
    pub(crate) fn tick(&mut self, extended: bool, attached: bool) -> u8 {
        self.previous = self.value;
        if self.chasing {
            let delta = f64::from(self.target) - f64::from(self.value);
            self.value = if delta.abs() < 1e-5 { self.target } else {
                (f64::from(self.value) + delta.clamp(-f64::from(0.4_f32), f64::from(0.4_f32))) as f32
            };
        }
        let mut events = u8::from(attached && self.previous != self.value && self.value == 1.0);
        if !self.update { return events; }
        self.update = false;
        let target = if extended { 1.0 } else { 0.0 };
        if attached && target == 0.0 && self.target == 1.0 { events |= 2; }
        self.target = target;
        self.chasing = true;
        events | 4
    }
    pub(crate) fn value_at(&self, partial: f32) -> f32 {
        (f64::from(self.previous) + f64::from(partial) * (f64::from(self.value) - f64::from(self.previous))) as f32
    }
    pub(crate) fn head_offset(&self, partial: f32) -> f32 {
        let offset = self.value_at(partial);
        offset * offset * 4.0 / 16.0
    }
}
pub(crate) fn neighbor(was_powered: bool, extended: bool, powered: bool) -> (bool, bool) {
    (powered, if powered != was_powered && powered { !extended } else { extended })
}
