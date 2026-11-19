#[derive(Default)]
pub(super) struct Motion {
    previous: f32,
    current: f32,
}

impl Motion {
    pub(super) fn tick(&mut self, viewers: i32) -> bool {
        self.previous = self.current;
        self.current = if viewers > 0 {
            (self.current + 0.35).min(1.0)
        } else {
            (self.current - 0.35).max(0.0)
        };
        self.previous > 0.0 && self.current == 0.0
    }

    pub(super) fn value(&self, partial: f32) -> f32 {
        self.previous + (self.current - self.previous) * partial
    }

    pub(super) fn closed(&self) -> bool {
        self.previous == 0.0 && self.current == 0.0
    }
}
