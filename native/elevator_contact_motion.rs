const BOUNDS_INFLATION: f64 = 1.0e-7;
const SEPARATION: f64 = 1.0e-4;

pub(super) const FOOT_CLEARANCE: f64 = BOUNDS_INFLATION + SEPARATION;

pub(super) struct Contact {
    pub feet_y: f64,
    pub velocity_y: f64,
}

fn direction(value: f64) -> i8 {
    i8::from(value > 0.0) - i8::from(value < 0.0)
}

// ContraptionCollider.saveClientPlayerFromClipping uses the tracked offset to
// raycast against the deck when it moves out from under the player.
fn ray_corrected_feet(
    feet_y: f64,
    velocity_y: f64,
    deck_y: f64,
    cabin_motion_y: f64,
    previous_deck_offset: Option<f64>,
) -> f64 {
    let Some(offset) = previous_deck_offset else {
        return feet_y;
    };
    let trend = direction(feet_y - deck_y - offset);
    let relative_speed = cabin_motion_y - velocity_y;
    let speed_squared = cabin_motion_y * cabin_motion_y;
    let threshold = if trend > 0 { 0.1 } else { 0.05 };
    if trend != 0 && trend != direction(relative_speed) && speed_squared >= threshold {
        deck_y
    } else {
        feet_y
    }
}

// Resolve the vertical pass of Create's flat deck collision after vanilla
// travel. The caller selects the supporting top face using the rider's bounds.
pub(super) fn resolve(
    feet_y: f64,
    velocity_y: f64,
    deck_y: f64,
    cabin_motion_y: f64,
    previous_deck_offset: Option<f64>,
) -> Option<Contact> {
    let feet_y = ray_corrected_feet(
        feet_y,
        velocity_y,
        deck_y,
        cabin_motion_y,
        previous_deck_offset,
    );
    let gap = feet_y - deck_y;
    let hard = gap <= BOUNDS_INFLATION;
    // ContinuousOBBCollider repeats the sweep after resolving overlap.
    let sweep = if hard {
        SEPARATION
    } else {
        gap - BOUNDS_INFLATION
    };
    let temporal = sweep > 0.0 && sweep < cabin_motion_y - velocity_y;
    if !hard && !temporal {
        return None;
    }

    let velocity_y = if temporal {
        cabin_motion_y - sweep
    } else {
        velocity_y
    };
    Some(Contact {
        feet_y: if hard {
            deck_y + FOOT_CLEARANCE
        } else {
            feet_y
        },
        velocity_y: if hard && velocity_y < 0.0 {
            cabin_motion_y
        } else {
            velocity_y
        },
    })
}
