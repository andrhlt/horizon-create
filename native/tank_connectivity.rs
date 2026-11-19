use std::collections::{BTreeMap, BTreeSet, VecDeque};

const PER_PART: i32 = 8000;

pub(crate) type Pos = [i32; 3];

pub(crate) trait Fluid: Clone {
    fn amount(&self) -> i32;
    fn set_amount(&mut self, amount: i32);
    fn same_variant(&self, other: &Self) -> bool;
}

#[derive(Clone)]
pub(crate) struct Part<F> {
    pub(crate) controller: Pos,
    pub(crate) width: i32,
    pub(crate) height: i32,
    pub(crate) fluid: Option<F>,
    pub(crate) dirty: bool,
    pub(crate) touched: bool,
}

fn cells(origin: Pos, width: i32, height: i32) -> Vec<Pos> {
    let mut result = Vec::new();
    for y in 0..height {
        for x in 0..width {
            for z in 0..width {
                result.push([origin[0] + x, origin[1] + y, origin[2] + z]);
            }
        }
    }
    result
}

// The controller's fluid is authoritative even when a candidate includes a
// noncontroller part of an existing group.
fn candidate<F: Fluid>(parts: &BTreeMap<Pos, Part<F>>, origin: Pos, width: i32) -> i32 {
    let Some(root) = parts.get(&origin) else { return 0 };
    if root.controller != origin { return 0; }
    let initial = root.fluid.as_ref();
    let mut height = 0;
    'layers: for y in 0..32 {
        for pos in cells([origin[0], origin[1] + y, origin[2]], width, 1) {
            let Some(part) = parts.get(&pos) else { break 'layers };
            let Some(controller) = parts.get(&part.controller) else { break 'layers };
            let c = part.controller;
            if controller.width > width
                || c[0] < origin[0] || c[2] < origin[2]
                || c[0] + controller.width > origin[0] + width
                || c[2] + controller.width > origin[2] + width
                || initial.zip(controller.fluid.as_ref()).is_some_and(|(a, b)| !a.same_variant(b))
            {
                break 'layers;
            }
        }
        height += 1;
    }
    width * width * height
}

fn best<F: Fluid>(parts: &BTreeMap<Pos, Part<F>>, origin: Pos) -> (i32, i32) {
    let (mut width, mut amount) = (1, 0);
    for w in 1..=3 {
        let score = candidate(parts, origin, w);
        if score >= amount {
            width = w;
            amount = score;
        }
    }
    (width, amount)
}

// ConnectivityHandler.splitMultiAndInvalidate, for a live controller: the
// controller keeps one part's capacity, then the remainder is distributed in
// y,x,z order to its former parts.
fn split<F: Fluid>(parts: &mut BTreeMap<Pos, Part<F>>, controller: Pos, creative: bool) {
    let Some(group) = parts.get(&controller).cloned() else { return };
    if group.width == 1 && group.height == 1 { return; }
    let mut remaining = group.fluid.clone();
    if let Some(fluid) = remaining.as_mut() {
        fluid.set_amount((fluid.amount() - PER_PART).max(0));
    }
    for pos in cells(controller, group.width, group.height) {
        let Some(part) = parts.get_mut(&pos) else { continue };
        if part.controller != controller { continue; }
        part.controller = pos;
        part.width = 1;
        part.height = 1;
        part.dirty = true;
        part.touched = true;
        if creative {
            part.fluid = if pos == controller { group.fluid.clone() } else {
                remaining.as_ref().filter(|f| f.amount() > 0).cloned().map(|mut f| { f.set_amount(PER_PART); f })
            };
        } else if pos == controller {
            part.fluid = group.fluid.clone().and_then(|mut fluid| {
                fluid.set_amount(fluid.amount().min(PER_PART));
                (fluid.amount() > 0).then_some(fluid)
            });
        } else {
            part.fluid = remaining.as_mut().and_then(|fluid| {
                let amount = fluid.amount().min(PER_PART);
                fluid.set_amount(fluid.amount() - amount);
                (amount > 0).then(|| {
                    let mut share = fluid.clone();
                    share.set_amount(amount);
                    share
                })
            });
        }
    }
}

fn form<F: Fluid>(parts: &mut BTreeMap<Pos, Part<F>>, origin: Pos, creative: bool) {
    let (width, amount) = best(parts, origin);
    if amount <= 1 { return; }
    let height = amount / width / width;
    let Some(root) = parts.get(&origin) else { return };
    if root.controller != origin || (root.width == width && root.height == height) { return; }
    split(parts, origin, creative);
    let capacity = amount * PER_PART;
    let creative_empty = creative && parts.get(&origin).is_some_and(|root| root.fluid.is_none());
    for pos in cells(origin, width, height) {
        if pos == origin { continue; }
        let Some(part) = parts.get(&pos).cloned() else { continue };
        // Java attempts the local tank transfer before splitting the old
        // controller. A noncontroller's local tank is normally empty.
        if let Some(mut incoming) = part.fluid.clone() {
            let root = parts.get_mut(&origin).unwrap();
            root.touched = true;
            if creative {
                if creative_empty {
                    incoming.set_amount(capacity);
                    root.fluid = Some(incoming);
                }
            } else if root.fluid.as_ref().is_none_or(|fluid| fluid.same_variant(&incoming)) {
                let current = root.fluid.as_ref().map_or(0, |fluid| fluid.amount());
                incoming.set_amount(incoming.amount().min((capacity - current).max(0)));
                if incoming.amount() > 0 {
                    if let Some(fluid) = root.fluid.as_mut() { fluid.set_amount(fluid.amount() + incoming.amount()); }
                    else { root.fluid = Some(incoming); }
                }
            }
        }
        if let Some(part) = parts.get_mut(&pos) {
            part.fluid = None;
            part.touched = true;
        }
        split(parts, part.controller, creative);
        if let Some(part) = parts.get_mut(&pos) {
            part.controller = origin;
            part.dirty = false;
        }
    }
    if let Some(root) = parts.get_mut(&origin) {
        root.width = width;
        root.height = height;
        root.dirty = false;
        root.touched = true;
    }
}

fn queue_push(queue: &mut Vec<(i32, Pos)>, item: (i32, Pos)) {
    queue.push(item);
    let mut index = queue.len() - 1;
    while index > 0 {
        let parent = (index - 1) / 2;
        if queue[parent].0 >= item.0 { break; }
        queue[index] = queue[parent];
        index = parent;
    }
    queue[index] = item;
}

fn queue_pop(queue: &mut Vec<(i32, Pos)>) -> Option<(i32, Pos)> {
    let last = queue.pop()?;
    if queue.is_empty() { return Some(last); }
    let result = queue[0];
    let mut index = 0;
    while index * 2 + 1 < queue.len() {
        let left = index * 2 + 1;
        let right = left + 1;
        let child = if right < queue.len() && queue[right].0 > queue[left].0 { right } else { left };
        if last.0 >= queue[child].0 { break; }
        queue[index] = queue[child];
        index = child;
    }
    queue[index] = last;
    Some(result)
}

pub(crate) fn reconnect<F: Fluid>(parts: &mut BTreeMap<Pos, Part<F>>, start: Pos, creative: bool) {
    let Some(part) = parts.get_mut(&start) else { return };
    if !part.dirty { return; }
    part.dirty = false;
    if part.controller != start { return; }
    let mut frontier = VecDeque::from([start]);
    let mut visited = BTreeSet::new();
    let mut candidates = Vec::new();
    while let Some(pos) = frontier.pop_front() {
        if !visited.insert(pos) { continue; }
        let (_, amount) = best(parts, pos);
        if amount > 1 { queue_push(&mut candidates, (amount, pos)); }
        for next in [[pos[0] - 1, pos[1], pos[2]], [pos[0], pos[1] - 1, pos[2]], [pos[0], pos[1], pos[2] - 1]] {
            if next[0] > start[0] - 3 && next[2] > start[2] - 3 && parts.contains_key(&next) {
                frontier.push_back(next);
            }
        }
    }
    while let Some((_, origin)) = queue_pop(&mut candidates) { form(parts, origin, creative); }
}

// Split a tank into the surviving singleton block entities.
pub(crate) fn split_removed<F: Fluid>(
    root: Pos, width: i32, height: i32, removed: Pos,
    mut remaining: Option<F>, present: &BTreeSet<Pos>, creative: bool,
) -> BTreeMap<Pos, Part<F>> {
    let take_share = |remaining: &mut Option<F>| {
        remaining.as_mut().and_then(|fluid| {
            let amount = fluid.amount().min(PER_PART);
            fluid.set_amount(fluid.amount() - amount);
            (amount > 0).then(|| {
                let mut share = fluid.clone();
                share.set_amount(amount);
                share
            })
        })
    };
    if creative {
        let original = remaining.clone();
        let distribute = remaining.as_mut().and_then(|fluid| {
            if removed != root { fluid.set_amount((fluid.amount() - PER_PART).max(0)); }
            (fluid.amount() > 0).then(|| { let mut copy = fluid.clone(); copy.set_amount(PER_PART); copy })
        });
        return cells(root, width, height).into_iter().filter(|at| *at != removed && present.contains(at))
            .map(|at| (at, Part { controller: at, width: 1, height: 1,
                fluid: if at == root { original.clone() } else { distribute.clone() }, dirty: true, touched: true })).collect();
    }
    let retained = if removed != root { take_share(&mut remaining) } else { None };
    let mut result = BTreeMap::new();
    for at in cells(root, width, height) {
        if at == removed || !present.contains(&at) { continue; }
        let fluid = if at == root { retained.clone() } else { take_share(&mut remaining) };
        result.insert(at, Part { controller: at, width: 1, height: 1, fluid, dirty: true, touched: true });
    }
    result
}
