// Fluid capability operations shared by tank interactions and fixtures.
use super::create_tank_connectivity::Fluid;

pub(crate) fn fill<F: Fluid>(
    stored: &mut Option<F>,
    capacity: i32,
    creative: bool,
    incoming: &F,
    execute: bool,
) -> i32 {
    let amount = incoming.amount().max(0);
    if creative {
        return amount;
    }
    if stored
        .as_ref()
        .is_some_and(|fluid| !fluid.same_variant(incoming))
    {
        return 0;
    }
    let current = stored.as_ref().map_or(0, Fluid::amount);
    let accepted = amount.min((capacity - current).max(0));
    if execute && accepted > 0 {
        let mut result = incoming.clone();
        result.set_amount(current + accepted);
        *stored = Some(result);
    }
    accepted
}

pub(crate) fn drain<F: Fluid>(
    stored: &mut Option<F>,
    creative: bool,
    amount: i32,
    requested: Option<&F>,
    execute: bool,
) -> Option<F> {
    let fluid = stored.as_ref()?;
    if requested.is_some_and(|requested| !fluid.same_variant(requested)) {
        return None;
    }
    let drained = amount.max(0).min(fluid.amount());
    if drained <= 0 {
        return None;
    }
    let mut result = fluid.clone();
    result.set_amount(drained);
    if execute && !creative {
        let remaining = fluid.amount() - drained;
        if remaining == 0 {
            *stored = None;
        } else {
            stored.as_mut().unwrap().set_amount(remaining);
        }
    }
    Some(result)
}

pub(crate) fn configure<F: Fluid>(stored: &mut Option<F>, capacity: i32, fluid: Option<F>) {
    *stored = fluid.filter(|fluid| fluid.amount() > 0).map(|mut fluid| {
        fluid.set_amount(capacity);
        fluid
    });
}
