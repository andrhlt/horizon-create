use std::cell::Cell;

use horizon_client::{
    hud::HudBatch,
    menu::{Env, Input, Menu},
    text::Text,
};
use horizon_world::nbt::{Compound, Tag};

use crate::{containers::ModBlockEntity, items::ItemStack, save::item_to_nbt};

use super::{
    Game,
    create_machines::mod_entity,
    create_packager::max_stack,
    create_toolbox::{self, COMPARTMENTS, FILTERS, SLOTS, STACKS_PER_COMPARTMENT},
};

const POSITIONS: [[f32; 2]; COMPARTMENTS] = [
    [79.0, 37.0],
    [112.0, 31.0],
    [145.0, 37.0],
    [151.0, 70.0],
    [145.0, 103.0],
    [112.0, 109.0],
    [79.0, 103.0],
    [73.0, 70.0],
];

const DEPOSIT: i32 = 0;
const DEPOSIT_RECT: [f32; 4] = [111.0, 69.0, 18.0, 18.0];

const CONFIRM_RECT: [f32; 4] = [185.0, 147.0, 18.0, 18.0];

thread_local! {
    static CONFIRM: Cell<bool> = const { Cell::new(false) };
}

fn inside([x, y]: [f32; 2], [left, top, width, height]: [f32; 4]) -> bool {
    (left..left + width).contains(&x) && (top..top + height).contains(&y)
}

pub(super) fn confirm_click(
    game: &Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if *canceled || button != 0 || screen.menu != Some(create_toolbox::ENTITY) {
        return;
    }
    let [left, top, _, _] = screen.rect;
    let [x, y] = screen.mouse;
    if inside([x - left, y - top], CONFIRM_RECT) {
        CONFIRM.set(true);
        *canceled = true;
    }
}

pub(super) fn client_tick(game: &mut Game<'_>) {
    if CONFIRM.replace(false) && game.remote_menu_type() == Some(create_toolbox::ENTITY) {
        game.close_container();
        game.screen = super::Screen::Playing;
        game.capture(true);
    }
}

fn deposit_label() -> String {
    Text::translate("create.toolbox.depositBox", &[]).plain()
}

fn over_deposit([x, y]: [f32; 2]) -> bool {
    inside([x, y], DEPOSIT_RECT)
}

pub(super) fn screen_click(at: [f32; 2]) -> Option<i32> {
    over_deposit(at).then_some(DEPOSIT)
}

pub(super) fn tooltip(at: [f32; 2], output: &mut Vec<String>) {
    if over_deposit(at) {
        output.push(deposit_label());
    }
}

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.hand != horizon_client::first_person::Hand::Main
        || game.native_sneaking()
        || !create_toolbox::block(&game.native_block(pos))
    {
        return false;
    }
    game.open_menu(pos);
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    let mut slots = vec![None; SLOTS];
    for (group, position) in POSITIONS.into_iter().enumerate() {
        slots[group * STACKS_PER_COMPARTMENT] = Some(position);
    }
    crate::mod_api::NativeScreen {
        width: 240.0,
        height: 255.0,
        slots,
        inventory_x: 8.0,
        inventory_y: 165.0,
        own_labels: true,
        own_background: true,
    }
}

fn shown_items<'a>(game: &'a Game<'_>) -> &'a [Option<ItemStack>] {
    game.container
        .and_then(|key| game.world.block_entities.get(&key))
        .map_or(&[], crate::containers::BlockEntity::slots)
}

pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch, [x, y]: [f32; 2]) {
    game.native_sprite(
        batch,
        "create:gui/toolbox",
        [0.0, 0.0, 188.0, 171.0],
        [x + 30.0, y, 188.0, 171.0],
    );
    game.native_sprite(
        batch,
        "create:gui/player_inventory",
        [0.0, 0.0, 176.0, 108.0],
        [x, y + 147.0, 176.0, 108.0],
    );
    if let Some(title) = game.native_screen_title() {
        game.native_text(batch, &title, [x + 45.0, y + 4.0], 0x592424, false);
    }
    let [left, top, width, height] = DEPOSIT_RECT;
    let bounds = [x + left, y + top, width, height];
    let [cursor_x, cursor_y] = game.native_cursor();
    let hover = over_deposit([cursor_x - x, cursor_y - y]);
    horizon_client::widgets::record(&deposit_label(), bounds, true);
    game.native_sprite(
        batch,
        "create:gui/widgets",
        [if hover { 18.0 } else { 0.0 }, 0.0, 18.0, 18.0],
        bounds,
    );
    game.native_sprite(
        batch,
        "create:gui/icons",
        [176.0, 48.0, 16.0, 16.0],
        [bounds[0] + 1.0, bounds[1] + 1.0, 16.0, 16.0],
    );
    let [left, top, width, height] = CONFIRM_RECT;
    let bounds = [x + left, y + top, width, height];
    let hover = inside([cursor_x - x, cursor_y - y], CONFIRM_RECT);
    horizon_client::widgets::record("Confirm", bounds, true);
    game.native_sprite(
        batch,
        "create:gui/widgets",
        [if hover { 18.0 } else { 0.0 }, 0.0, 18.0, 18.0],
        bounds,
    );
    game.native_sprite(
        batch,
        "create:gui/icons",
        [0.0, 16.0, 16.0, 16.0],
        [bounds[0] + 1.0, bounds[1] + 1.0, 16.0, 16.0],
    );
    if let Some(pos) = game.native_screen_pos()
        && let Some(entity) = mod_entity(game, pos)
    {
        for (group, [cx, cy]) in POSITIONS.into_iter().enumerate() {
            let start = group * STACKS_PER_COMPARTMENT;
            if shown_items(game).get(start).is_none_or(Option::is_none)
                && let Some(filter) = create_toolbox::saved_filter(&entity.nbt, group)
            {
                game.native_item_stack(batch, &filter, [x + cx, y + cy], 16.0);
                let left = x + cx + 15.0 - game.native_text_width("0");
                game.native_text(batch, "0", [left, y + cy + 9.0], 0xffffff, true);
            }
        }
    }
}

pub(super) fn draw_compartment_item(
    game: &Game<'_>,
    batch: &mut HudBatch,
    slot: usize,
    stack: &Option<ItemStack>,
    x: f32,
    y: f32,
) -> bool {
    let Some(index) = slot
        .checked_sub(300)
        .filter(|&index| index < SLOTS && index % STACKS_PER_COMPARTMENT == 0)
    else {
        return false;
    };
    if game.remote_menu_type() != Some(create_toolbox::ENTITY) {
        return false;
    }
    let Some(stack) = stack else {
        return false;
    };
    let total: u32 = shown_items(game)
        .iter()
        .skip(index)
        .take(STACKS_PER_COMPARTMENT)
        .flatten()
        .map(|stack| stack.count)
        .sum();
    let total = total.max(stack.count);
    game.draw_item_model(batch, stack, x, y);
    game.draw_item_decorations(batch, stack, x, y, Some(total.to_string()));
    true
}

pub(super) fn menu_button(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    id: i32,
) {
    if id != DEPOSIT {
        return;
    }
    super::create_toolbox_links::before_deposit(game, pos);
    entity.items.resize(SLOTS, None);
    let mut changed = false;
    for slot in 0..36 {
        let Some(mut stack) = game.stack_in(slot).cloned() else {
            continue;
        };
        let count = stack.count;
        deposit(game.items(), entity, &mut stack);
        if stack.count != count {
            *game.stack_in_mut(slot) = (stack.count > 0).then_some(stack);
            changed = true;
        }
    }
    if changed && game.lan_acting.is_some() {
        game.guest_inventory_resend = true;
    }
}

pub(super) fn deposit(
    items: &crate::items::Items,
    entity: &mut ModBlockEntity,
    stack: &mut ItemStack,
) {
    let limit = max_stack(items, stack);
    let mut eligible = [false; COMPARTMENTS];
    for (group, accepts) in eligible.iter_mut().enumerate() {
        *accepts = create_toolbox::saved_filter(&entity.nbt, group)
            .is_some_and(|filter| create_toolbox::compatible(items, &filter, stack));
    }
    if !eligible.iter().any(|value| *value)
        || !horizon_client::bundle::fits_inside_container_items(items, stack)
    {
        return;
    }
    for (index, held) in entity.items.iter_mut().enumerate() {
        if stack.count == 0 {
            return;
        }
        if eligible[index / STACKS_PER_COMPARTMENT]
            && let Some(existing) = held
            && existing.same_item_same_components(stack)
        {
            let inserted = stack.count.min(limit.saturating_sub(existing.count));
            existing.count += inserted;
            stack.count -= inserted;
        }
    }
    for (group, slots) in entity
        .items
        .chunks_exact_mut(STACKS_PER_COMPARTMENT)
        .enumerate()
    {
        if stack.count == 0 {
            return;
        }
        if !eligible[group] {
            continue;
        }
        for slot in slots.iter_mut().filter(|slot| slot.is_none()) {
            if stack.count == 0 {
                break;
            }
            let inserted = stack.count.min(limit);
            *slot = Some(ItemStack {
                count: inserted,
                ..stack.clone()
            });
            stack.count -= inserted;
        }
        create_toolbox::settle(items, slots);
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity, update: &mut Option<Compound>) {
    if entity.id != create_toolbox::ENTITY {
        return;
    }
    let update = update.get_or_insert_with(Default::default);
    super::create_toolbox_animation::update_tag(entity, update);
    if let Some(filters) = entity.nbt.get(&FILTERS.into()) {
        update.insert(FILTERS.into(), filters.clone());
    }
}

fn store_filter(state: &mut Compound, group: usize, filter: Option<&ItemStack>) {
    let slot = filter.map_or_else(empty_filter, |stack| {
        item_to_nbt(&ItemStack {
            count: 1,
            ..stack.clone()
        })
    });
    let list = state
        .entry(FILTERS.into())
        .or_insert_with(|| Tag::List((0..COMPARTMENTS).map(|_| empty_filter()).collect()));
    let Tag::List(filters) = list else {
        return;
    };
    filters.resize_with(COMPARTMENTS, empty_filter);
    filters[group] = slot;
}

fn empty_filter() -> Tag {
    Tag::Compound(Compound::new())
}

fn group_filter(state: &Compound, menu: &Menu, group: usize) -> Option<ItemStack> {
    create_toolbox::saved_filter(state, group).or_else(|| {
        let start = group * STACKS_PER_COMPARTMENT;
        (start..start + STACKS_PER_COMPARTMENT)
            .find_map(|slot| menu.slot(slot))
            .cloned()
    })
}

fn can_place(env: &Env<'_>, state: &Compound, menu: &Menu, slot: usize, stack: &ItemStack) -> bool {
    horizon_client::bundle::fits_inside_container_items(env.items, stack)
        && group_filter(state, menu, slot / STACKS_PER_COMPARTMENT)
            .is_none_or(|filter| create_toolbox::compatible(env.items, &filter, stack))
}

fn settle(env: &Env<'_>, state: &mut Compound, menu: &mut Menu, group: usize) {
    let first = group * STACKS_PER_COMPARTMENT;
    let mut slots =
        std::array::from_fn::<_, STACKS_PER_COMPARTMENT, _>(|i| menu.slot(first + i).cloned());
    if create_toolbox::saved_filter(state, group).is_none()
        && let Some(stack) = slots.iter().flatten().next()
    {
        store_filter(state, group, Some(stack));
    }
    create_toolbox::settle(env.items, &mut slots);
    for (offset, stack) in slots.into_iter().enumerate() {
        if stack.as_ref() != menu.slot(first + offset) {
            menu.set_slot(env, first + offset, stack);
        }
    }
}

fn shift_in(env: &Env<'_>, state: &mut Compound, menu: &mut Menu, source: usize) {
    let Some(mut stack) = menu.slot(source).cloned() else {
        return;
    };
    let limit = max_stack(env.items, &stack);
    for slot in 0..SLOTS {
        if stack.count == 0 {
            break;
        }
        if let Some(mut held) = menu.slot(slot).cloned()
            && held.same_item_same_components(&stack)
            && can_place(env, state, menu, slot, &stack)
        {
            let inserted = stack.count.min(limit.saturating_sub(held.count));
            held.count += inserted;
            stack.count -= inserted;
            menu.set_slot(env, slot, Some(held));
        }
    }
    if stack.count > 0
        && let Some(slot) = (0..SLOTS)
            .find(|&slot| menu.slot(slot).is_none() && can_place(env, state, menu, slot, &stack))
    {
        let inserted = stack.count.min(limit);
        menu.set_slot(
            env,
            slot,
            Some(ItemStack {
                count: inserted,
                ..stack.clone()
            }),
        );
        stack.count -= inserted;
    }
    menu.set_slot(env, source, (stack.count > 0).then_some(stack));
    for group in 0..COMPARTMENTS {
        settle(env, state, menu, group);
    }
}

pub(super) fn click(
    menu: &mut Menu,
    env: &Env<'_>,
    state: &mut Compound,
    slot: i32,
    button: i32,
    input: Input,
    handled: &mut bool,
) {
    if menu.quick_crafting() && input != Input::QuickCraft {
        return;
    }
    let Ok(slot) = usize::try_from(slot) else {
        return;
    };
    if slot >= menu.slot_count() {
        return;
    }
    if input == Input::QuickCraft && button & 3 == 1 && slot <= SLOTS {
        *handled = true;
        return;
    }
    if slot >= SLOTS {
        if input == Input::QuickMove && (0..=1).contains(&button) {
            shift_in(env, state, menu, slot);
            *handled = true;
        }
        return;
    }
    if slot % STACKS_PER_COMPARTMENT != 0 {
        return;
    }
    let group = slot / STACKS_PER_COMPARTMENT;
    if input == Input::Pickup && (0..=1).contains(&button) {
        *handled = true;
        if let Some(cursor) = menu.carried.as_ref() {
            if !can_place(env, state, menu, slot, cursor) {
                return;
            }
            if menu
                .slot(slot)
                .is_some_and(|current| create_toolbox::compatible(env.items, current, cursor))
            {
                menu.click_hidden_mod_slot(env, slot + STACKS_PER_COMPARTMENT - 1, button);
                settle(env, state, menu, group);
                return;
            }
        } else if menu.slot(slot).is_none() {
            store_filter(state, group, None);
            return;
        }
        let _ = menu.click(env, slot as i32, button, input);
        settle(env, state, menu, group);
    } else if input == Input::QuickMove && (0..=1).contains(&button) {
        *handled = true;
        while let Some(before) = menu.slot(slot).cloned() {
            let _ = menu.click(env, slot as i32, button, input);
            if menu.slot(slot) == Some(&before) {
                break;
            }
            settle(env, state, menu, group);
        }
    } else if input == Input::Swap || input == Input::Throw || input == Input::PickupAll {
        *handled = true;
        if input == Input::Swap
            && let Ok(source) = usize::try_from(button)
            && let Some(stack) = (source < 9 || source == 40)
                .then(|| menu.player_item(source))
                .flatten()
            && !can_place(env, state, menu, slot, stack)
        {
            return;
        }
        let _ = menu.click(env, slot as i32, button, input);
        settle(env, state, menu, group);
    }
}
