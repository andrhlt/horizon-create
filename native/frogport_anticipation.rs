#[derive(Default)]
pub(super) struct Anticipation {
    request: Option<i64>,
    previous: f32,
    current: f32,
    active: bool,
}

impl Anticipation {
    pub(super) fn tick(&mut self, request: Option<i64>) {
        if request.is_some() && request != self.request {
            self.request = request;
            self.active = true;
        }
        if self.current == 1.0 {
            self.reset();
        }
        self.previous = self.current;
        if self.active {
            self.current = (self.current + 0.1).min(1.0);
        }
    }

    pub(super) fn reset(&mut self) {
        self.previous = 0.0;
        self.current = 0.0;
        self.active = false;
    }

    pub(super) fn value(&self, partial: f32) -> f32 {
        self.previous + (self.current - self.previous) * partial
    }
}

pub(super) fn head_factor(phase: f32) -> f32 {
    if phase > 0.0 {
        (1.0 - (f64::from(phase) * 1.25 * 2.0 - 1.0).powi(4)).max(0.0) as f32
    } else {
        0.0
    }
}
