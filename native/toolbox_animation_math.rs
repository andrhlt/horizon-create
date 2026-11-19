const SPEED: f64 = 0.2_f32 as f64;
const EPSILON: f64 = 1e-5;

#[derive(Clone, Copy, Default)]
struct Chase {
    previous: f32,
    current: f32,
}

impl Chase {
    fn tick(&mut self, opening: bool, exponential: bool) {
        self.previous = self.current;
        let target = u8::from(opening) as f64;
        let current = f64::from(self.current);
        let delta = target - current;
        self.current = if delta.abs() < EPSILON {
            target as f32
        } else {
            let advance = if exponential {
                delta * SPEED
            } else {
                delta.clamp(-SPEED, SPEED)
            };
            (current + advance) as f32
        };
    }

    fn settled(self, opening: bool) -> bool {
        let target = u8::from(opening) as f64;
        (f64::from(self.previous) - f64::from(self.current)).abs() < EPSILON
            && (f64::from(self.current) - target).abs() < EPSILON
    }

    fn at(self, partial: f32) -> f32 {
        let previous = f64::from(self.previous);
        (previous + (f64::from(self.current) - previous) * f64::from(partial)) as f32
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Cue {
    Open,
    ChestClose,
    IronClose,
}

#[derive(Default)]
pub(super) struct Motion {
    target_open: bool,
    lid: Chase,
    drawers: Chase,
}

impl Motion {
    pub(super) fn tick(&mut self, open: bool) -> Option<Cue> {
        let cue = if self.lid.settled(self.target_open) {
            match (self.target_open, open) {
                (false, true) => Some(Cue::Open),
                (true, false) => Some(Cue::ChestClose),
                _ => None,
            }
        } else if !open
            && !self.target_open
            && self.lid.previous > 1.0 / 16.0
            && self.lid.current < 1.0 / 16.0
        {
            Some(Cue::IronClose)
        } else {
            None
        };
        self.target_open = open;
        self.lid.tick(open, false);
        self.drawers.tick(open, true);
        cue
    }

    pub(super) fn at(&self, partial: f32) -> [f32; 2] {
        [self.lid.at(partial), self.drawers.at(partial)]
    }

    pub(super) fn closed(&self) -> bool {
        self.lid.previous == 0.0
            && self.lid.current == 0.0
            && self.drawers.previous == 0.0
            && self.drawers.current == 0.0
    }
}
