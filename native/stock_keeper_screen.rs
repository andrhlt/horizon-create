use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_client::{hud::HudBatch, mod_api::NativeScreenView, ui::EditBox};
use horizon_world::nbt::{self, Tag};

use super::{
    Game, ItemStack,
    commands::Target,
    create_burner, create_elevator_seats, create_item_filters,
    create_machines::{mod_entity, same_stack},
    create_package_filter_editor::{contains, edit_address_key},
    create_packager,
    create_stock_network::{self, Request, Summary},
    create_stock_ticker::TICKER,
};

const SCREEN: &str = "create:stock_keeper";
const SPRITE: &str = "create:gui/stock_keeper";
const WIDTH: f32 = 226.0;
const TOP: f32 = 36.0;
const BOTTOM: f32 = 80.0;
const STEP: f32 = 20.0;
const COLUMNS: usize = 9;
const GRID: [f32; 2] = [24.0, 37.0];
const SEARCH: [f32; 4] = [71.0, 22.0, 100.0, 9.0];
const LIMITS: nbt::Limits = nbt::Limits {
    max_bytes: 29_000,
    max_nodes: 16_384,
    max_depth: 30,
};
const SIDES: [(i32, i32); 4] = [(0, -1), (1, 0), (0, 1), (-1, 0)];

#[derive(Clone)]
struct Session {
    token: u64,
    conn: u32,
    pos: [i32; 3],
    dimension: String,
    frequency: [i32; 4],
}

struct KeeperScreen {
    token: u64,
    summary: Summary,
    groups: Vec<Group>,
    search: EditBox,
    address: EditBox,
    order: Vec<ItemStack>,
    sent_limit: Vec<ItemStack>,
    pending: Option<Tag>,
    first_row: usize,
    refresh: u8,
}

thread_local! {
    static SERIAL: Cell<u64> = const { Cell::new(0) };
    static SESSIONS: RefCell<HashMap<u128, Session>> = RefCell::new(HashMap::new());
    static VIEW: RefCell<Option<KeeperScreen>> = const { RefCell::new(None) };
}

pub(super) fn clear_server() {
    SESSIONS.with_borrow_mut(HashMap::clear);
    create_stock_network::clear_summaries();
}

fn frequency(game: &Game<'_>, pos: [i32; 3]) -> Option<[i32; 4]> {
    let entity = mod_entity(game, pos).filter(|entity| entity.id == TICKER)?;
    let Tag::IntArray(freq) = entity.nbt.get(&"Freq".into())? else {
        return None;
    };
    freq.as_slice().try_into().ok()
}

struct Group {
    label: Option<String>,
    indices: Vec<usize>,
}

impl Group {
    fn to_tag(&self) -> Tag {
        let indices = self.indices.iter().map(|&index| index as i32).collect();
        let mut row =
            horizon_world::nbt::Compound::from([("Items".into(), Tag::IntArray(indices))]);
        if let Some(label) = &self.label {
            row.insert("Label".into(), Tag::String(label.as_str().into()));
        }
        Tag::Compound(row)
    }

    fn from_tag(tag: &Tag) -> Option<Self> {
        let Tag::IntArray(items) = tag.get("Items")? else {
            return None;
        };
        Some(Self {
            label: crate::save::text(tag.get("Label")),
            indices: items
                .iter()
                .filter_map(|&index| usize::try_from(index).ok())
                .collect(),
        })
    }
}

fn groups(game: &Game<'_>, pos: [i32; 3], summary: &Summary) -> Vec<Group> {
    let Some(Tag::List(categories)) =
        mod_entity(game, pos).and_then(|entity| entity.nbt.get(&"Categories".into()))
    else {
        return Vec::new();
    };
    let mut unclaimed: Vec<_> = (0..summary.items.len()).collect();
    let mut groups = Vec::new();
    for category in categories {
        let Tag::Compound(filter) = category else {
            continue;
        };
        let Some(stack) = ItemStack::from_nbt(filter) else {
            continue;
        };
        if !matches!(
            stack.item.as_ref(),
            "create:filter" | "create:attribute_filter" | "create:package_filter"
        ) {
            continue;
        }
        let mut indices = Vec::new();
        unclaimed.retain(|&index| {
            if create_item_filters::matches(game.items(), filter, &summary.items[index], false) {
                indices.push(index);
                false
            } else {
                true
            }
        });
        let label = stack
            .data()
            .and_then(|data| data.custom_name.as_ref())
            .map(horizon_client::component::name_text)
            .map(|name| name.plain().to_string())
            .unwrap_or_else(|| {
                game.stack_display_name(&stack)
                    .plain()
                    .trim_start_matches('[')
                    .trim_end_matches(']')
                    .to_string()
            });
        groups.push(Group {
            label: Some(label),
            indices,
        });
    }
    groups.push(Group {
        label: None,
        indices: unclaimed,
    });
    groups
}

fn trace_groups(game: &Game<'_>, summary: &Summary, groups: &[Group]) {
    if std::env::var_os("CREATE_STOCK_CATEGORY_TRACE").is_none() {
        return;
    }
    let trace = groups
        .iter()
        .map(|group| {
            group
                .indices
                .iter()
                .map(|&index| {
                    let item = &summary.items[index];
                    let id = item.item.rsplit(':').next().unwrap_or(&item.item);
                    format!("{id}:{}", item.count)
                })
                .collect::<Vec<_>>()
                .join("+")
        })
        .collect::<Vec<_>>()
        .join("|");
    eprintln!(
        "CREATE_STOCK_CATEGORY {},{},{}",
        game.world.game_time,
        groups.len().saturating_sub(1),
        trace
    );
}

fn send_summary(game: &mut Game<'_>, player: u128, session: &Session, opening: bool) -> bool {
    let summary = create_stock_network::summary(game, session.frequency, false);
    let groups = groups(game, session.pos, &summary);
    trace_groups(game, &summary, &groups);
    let mut tag = summary.to_tag();
    if !groups.is_empty()
        && let Tag::Compound(ref mut view) = tag
    {
        view.insert(
            "Groups".into(),
            Tag::List(groups.iter().map(Group::to_tag).collect()),
        );
    }
    if opening && let Tag::Compound(ref mut view) = tag {
        let address = mod_entity(game, session.pos)
            .and_then(|entity| entity.nbt.get(&"PreviousAddress".into()))
            .cloned();
        if let Some(address) = address {
            view.insert("Address".into(), address);
        }
    }
    let Some(payload) = nbt::write_network(&tag, LIMITS).ok() else {
        return false;
    };
    let mut packet = session.token.to_be_bytes().to_vec();
    packet.push(u8::from(opening));
    packet.extend(payload);
    if std::env::var_os("CREATE_STOCK_SUMMARY_TRACE").is_some() {
        let accurate = create_stock_network::summary(game, session.frequency, true);
        let iron = |summary: &Summary| {
            summary
                .items
                .iter()
                .find(|item| item.item.as_ref() == "minecraft:iron_ingot")
                .map_or(0, |item| item.count)
        };
        eprintln!(
            "CREATE_STOCK_SUMMARY {},{},{},{},{}",
            game.world.game_time,
            iron(&summary),
            summary.links,
            iron(&accurate),
            accurate.links
        );
    }
    game.native_net_send_to_player(player, SCREEN, &packet)
        .is_ok()
}

fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    let Some(actor) = game
        .native_acting_player()
        .filter(|player| player.game_mode != 3)
    else {
        return false;
    };
    let Some(frequency) = frequency(game, pos) else {
        return false;
    };
    let Some(conn) = game.lan_acting.or_else(|| game.native_conn(actor.uuid)) else {
        return false;
    };
    if SESSIONS.with_borrow(|sessions| {
        sessions.get(&actor.uuid).is_some_and(|session| {
            session.conn == conn
                && session.pos == pos
                && session.dimension == actor.dimension
                && session.frequency == frequency
        })
    }) {
        return true;
    }
    let session = Session {
        conn,
        token: SERIAL.with(|serial| {
            let next = serial.get().wrapping_add(1);
            serial.set(next);
            next
        }),
        pos,
        dimension: actor.dimension,
        frequency,
    };
    if !send_summary(game, actor.uuid, &session, true) {
        return false;
    }
    SESSIONS.with_borrow_mut(|sessions| sessions.insert(actor.uuid, session));
    true
}

pub(super) fn use_burner(game: &mut Game<'_>, [x, y, z]: [i32; 3]) -> bool {
    let burner = [x, y, z];
    if game.hand != horizon_client::first_person::Hand::Main
        || game.native_block(burner) != create_burner::BURNER
        || game
            .held()
            .is_some_and(|stack| stack.item.as_ref() == "create:goggles")
        || !mod_entity(game, burner).is_some_and(|entity| entity.id == create_burner::HEATER)
        || game.native_block_property(burner, "blaze").as_deref() == Some("none")
    {
        return false;
    }
    SIDES
        .into_iter()
        .map(|(dx, dz)| [x + dx, y, z + dz])
        .find(|&pos| game.native_block(pos) == TICKER)
        .is_some_and(|pos| open(game, pos))
}

pub(super) fn use_mob(game: &mut Game<'_>, index: usize) -> bool {
    let mob = &game.mobs[index];
    let Some([x, y, z]) = mob
        .extra
        .mount
        .and_then(|id| create_elevator_seats::static_vehicle_position(game, id))
        .filter(|_| mob.alive() && !mob.removed)
    else {
        return false;
    };
    let mut stations = SIDES
        .into_iter()
        .flat_map(|(dx, dz)| [[x + dx, y, z + dz], [x + dx, y + 1, z + dz]])
        .filter(|&pos| game.native_block(pos) == TICKER);
    match (stations.next(), stations.next()) {
        (Some(pos), None) => open(game, pos),
        _ => false,
    }
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, packet: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let Some(token) = packet
        .get(..8)
        .and_then(|bytes| bytes.try_into().ok())
        .map(u64::from_be_bytes)
    else {
        return;
    };
    if packet.get(8) == Some(&2) {
        if VIEW.with_borrow(|view| view.as_ref().is_some_and(|view| view.token == token)) {
            game.native_mod_screen_close(SCREEN);
        }
        return;
    }
    let Some(bytes) = packet.get(9..) else { return };
    let Ok((tag, used)) = nbt::read_network(bytes, LIMITS) else {
        return;
    };
    if used != bytes.len() {
        return;
    }
    let summary = Summary::from_tag(&tag);
    let groups = match tag.get("Groups") {
        Some(Tag::List(rows)) => rows.iter().filter_map(Group::from_tag).collect(),
        _ => Vec::new(),
    };
    match packet[8] {
        1 if game.native_mod_screen_open(SCREEN) => {
            let mut search = EditBox::new(SEARCH[0], SEARCH[1], SEARCH[2], SEARCH[3]);
            search.bordered = false;
            search.max_length = 50;
            search.text_color = 0xff4a2d31;
            let mut address = EditBox::new(27.0, 0.0, 92.0, 10.0);
            address.bordered = false;
            address.max_length = 25;
            address.text_color = 0xff714a40;
            address.set_value(&crate::save::text(tag.get("Address")).unwrap_or_default());
            VIEW.replace(Some(KeeperScreen {
                token,
                summary,
                groups,
                search,
                address,
                order: Vec::new(),
                sent_limit: Vec::new(),
                pending: None,
                first_row: 0,
                refresh: 0,
            }));
        }
        1 => send(game, token, 1, None),
        0 if game.native_mod_screen() == Some(SCREEN) => {
            VIEW.with_borrow_mut(|view| {
                if let Some(view) = view.as_mut().filter(|view| view.token == token) {
                    view.sent_limit
                        .retain(|entry| amount(&summary.items, entry) > entry.count);
                    view.summary = summary;
                    view.groups = groups;
                    view.revalidate();
                }
            });
        }
        _ => {}
    }
}

pub(super) fn handle(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != SCREEN {
        return;
    }
    let Some(token) = data
        .get(..8)
        .and_then(|bytes| <[u8; 8]>::try_from(bytes).ok())
    else {
        return;
    };
    let token = u64::from_be_bytes(token);
    let Some(session) = SESSIONS.with_borrow(|sessions| {
        sessions
            .get(&player)
            .filter(|session| session.token == token)
            .cloned()
    }) else {
        return;
    };
    if game.native_conn(player) != Some(session.conn) {
        return;
    }
    let action = data.get(8).copied().unwrap_or(0);
    if action == 1 {
        SESSIONS.with_borrow_mut(|sessions| sessions.remove(&player));
    }
    let conn = session.conn;
    let available = game.for_player(Target::Guest(conn), |actor| {
        if actor.native_dimension() != session.dimension
            || frequency(actor, session.pos) != Some(session.frequency)
        {
            return false;
        }
        if action == 1 {
            if let Some(tag) = read_body(data) {
                save_address(actor, session.pos, &tag);
            }
            return true;
        }
        if !super::create_stock_ticker::keeper_present(actor, session.pos) {
            return false;
        }
        match action {
            0 if data.len() == 8 => send_summary(actor, player, &session, false),
            2 => {
                if let Some(tag) = read_body(data) {
                    submit_order(actor, &session, &tag);
                }
                true
            }
            _ => true,
        }
    });
    if action != 1 && available != Some(true) {
        SESSIONS.with_borrow_mut(|sessions| sessions.remove(&player));
        let mut close = token.to_be_bytes().to_vec();
        close.push(2);
        let _ = game.native_net_send_to_player(player, SCREEN, &close);
    }
}

fn read_body(data: &[u8]) -> Option<Tag> {
    let payload = data.get(9..)?;
    let (tag, used) = nbt::read_network(payload, LIMITS).ok()?;
    (used == payload.len()).then_some(tag)
}

fn save_address(game: &mut Game<'_>, pos: [i32; 3], data: &Tag) -> Option<String> {
    let address = crate::save::text(data.get("Address"))?;
    if address.encode_utf16().count() > 25 || address.chars().any(char::is_control) {
        return None;
    }
    game.native_with_mod_block_entity(pos, |entity| {
        entity.nbt.insert(
            "PreviousAddress".into(),
            Tag::String(address.as_str().into()),
        );
    });
    game.native_block_entity_sync(pos);
    Some(address)
}

fn submit_order(game: &mut Game<'_>, session: &Session, data: &Tag) {
    let Some(order) = data.get("Order") else {
        return;
    };
    let items = create_stock_network::order_stacks(order);
    if items.is_empty() || items.len() > COLUMNS {
        return;
    }
    if items
        .iter()
        .any(|item| items.iter().filter(|other| same_stack(other, item)).count() != 1)
    {
        return;
    }
    let Some(address) = save_address(game, session.pos, data) else {
        return;
    };
    let order = create_stock_network::encode_order(items.into_iter());
    game.with_level(|_, level, ticks| {
        create_stock_network::request(
            level,
            ticks,
            &session.frequency,
            &order,
            &address,
            Request::Player,
        );
    });
}

fn send(game: &mut Game<'_>, token: u64, action: u8, tag: Option<&Tag>) {
    let mut packet = token.to_be_bytes().to_vec();
    packet.push(action);
    if let Some(tag) = tag {
        let Ok(body) = nbt::write_network(tag, LIMITS) else {
            return;
        };
        packet.extend(body);
    }
    let _ = game.native_net_send_to_server(SCREEN, &packet);
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.native_mod_screen() != Some(SCREEN) {
        if let Some(view) = VIEW.take() {
            if let Some(order) = &view.pending {
                send(game, view.token, 2, Some(order));
            }
            let close = view.settings(None);
            send(game, view.token, 1, Some(&close));
        }
        return;
    }
    let pending = VIEW.with_borrow_mut(|view| {
        let view = view.as_mut()?;
        view.pending.take().map(|order| (view.token, order))
    });
    if let Some((token, order)) = pending {
        send(game, token, 2, Some(&order));
    }
    let token = VIEW.with_borrow_mut(|view| {
        let view = view.as_mut()?;
        view.refresh += 1;
        if view.refresh != 16 {
            return None;
        }
        view.refresh = 0;
        Some(view.token)
    });
    if let Some(token) = token {
        let _ = game.native_net_send_to_server(SCREEN, &token.to_be_bytes());
    }
}

fn amount(items: &[ItemStack], stack: &ItemStack) -> u32 {
    items
        .iter()
        .find(|item| same_stack(item, stack))
        .map_or(0, |item| item.count)
}

fn item_index(point: [f32; 2], x: f32, y: f32, rows: usize) -> Option<usize> {
    let [px, py] = point;
    let col = (px - x) / STEP;
    let row = (py - y) / STEP;
    ((0.0..COLUMNS as f32).contains(&col) && (0.0..rows as f32).contains(&row))
        .then_some(row as usize * COLUMNS + col as usize)
}

impl KeeperScreen {
    fn displayed(&self, stack: &ItemStack) -> u32 {
        self.sent_limit
            .iter()
            .find(|item| same_stack(item, stack))
            .map_or(stack.count, |item| item.count.min(stack.count))
    }

    fn revalidate(&mut self) {
        let listed = &self.summary.items;
        self.order.retain_mut(|item| {
            item.count = item.count.min(amount(listed, item));
            item.count != 0
        });
    }

    fn settings(&self, order: Option<Tag>) -> Tag {
        let mut data = horizon_world::nbt::Compound::new();
        data.insert(
            "Address".into(),
            Tag::String(self.address.value.as_str().into()),
        );
        if let Some(order) = order {
            data.insert("Order".into(), order);
        }
        Tag::Compound(data)
    }

    fn submit(&mut self) {
        if self.pending.is_some() {
            return;
        }
        self.revalidate();
        if self.order.is_empty() {
            return;
        }
        self.sent_limit = self
            .order
            .iter()
            .map(|item| {
                let mut limit = item.clone();
                limit.count = amount(&self.summary.items, item).saturating_sub(item.count);
                limit
            })
            .collect();
        let order = create_stock_network::encode_order(self.order.drain(..));
        self.pending = Some(self.settings(Some(order)));
        self.refresh = 10;
    }

    fn adjust(&mut self, item: &ItemStack, delta: i64) {
        let current = amount(&self.order, item);
        let max = amount(&self.summary.items, item);
        let next = (i64::from(current) + delta).clamp(0, i64::from(max)) as u32;
        if let Some(at) = self.order.iter().position(|entry| same_stack(entry, item)) {
            if next == 0 {
                self.order.remove(at);
            } else {
                self.order[at].count = next;
            }
        } else if next > 0 && self.order.len() < COLUMNS {
            let mut selection = item.clone();
            selection.count = next;
            self.order.push(selection);
        }
    }
}

fn geometry([x, y, width, height]: [f32; 4]) -> (f32, f32, f32, usize) {
    let rows = (((height - 10.0 - TOP - BOTTOM) / STEP).floor() as usize).clamp(1, 17);
    let panel = TOP + rows as f32 * STEP + BOTTOM;
    (
        x + ((width - WIDTH) / 2.0).floor(),
        y + ((height - panel) / 2.0).floor(),
        panel,
        rows,
    )
}

enum StockRow<'a> {
    Heading(Option<&'a str>),
    Items(Vec<&'a ItemStack>),
}

impl<'a> StockRow<'a> {
    fn item(&self, index: usize) -> Option<&'a ItemStack> {
        match self {
            Self::Items(items) => items.get(index).copied(),
            Self::Heading(_) => None,
        }
    }
}

fn stock_rows<'a>(game: &Game<'_>, view: &'a KeeperScreen) -> Vec<StockRow<'a>> {
    let query = view.search.value.to_lowercase();
    let matches = |item: &&ItemStack| {
        query.is_empty()
            || game
                .stack_display_name(item)
                .plain()
                .to_lowercase()
                .contains(&query)
    };
    let groups: Vec<_> = view
        .groups
        .iter()
        .map(|group| {
            let items: Vec<_> = group
                .indices
                .iter()
                .filter_map(|&index| view.summary.items.get(index))
                .filter(matches)
                .collect();
            (group.label.as_deref(), items)
        })
        .collect();

    let mut rows = Vec::new();
    if groups
        .iter()
        .any(|(label, items)| label.is_some() && !items.is_empty())
    {
        for (label, items) in groups {
            if items.is_empty() {
                continue;
            }
            rows.push(StockRow::Heading(label));
            rows.extend(
                items
                    .chunks(COLUMNS)
                    .map(|items| StockRow::Items(items.to_vec())),
            );
        }
    } else {
        let items: Vec<_> = view.summary.items.iter().filter(matches).collect();
        rows.extend(
            items
                .chunks(COLUMNS)
                .map(|items| StockRow::Items(items.to_vec())),
        );
    }
    rows
}

fn sprite(game: &Game<'_>, batch: &mut HudBatch, at: [f32; 2], source: [f32; 4]) {
    game.native_sprite(batch, SPRITE, source, [at[0], at[1], source[2], source[3]]);
}

fn centered(game: &Game<'_>, batch: &mut HudBatch, text: &str, x: f32, y: f32, color: u32) {
    game.native_text(
        batch,
        text,
        [x - game.native_text_width(text) / 2.0, y],
        color,
        false,
    );
}

fn count(game: &Game<'_>, batch: &mut HudBatch, value: u32, [x, y]: [f32; 2]) {
    if value < 2 {
        return;
    }
    let label = match value {
        1_000_000.. => format!("{}m", value / 1_000_000),
        10_000.. => format!("{}k", value / 1_000),
        1_000.. => format!("{:.1}k", (value / 100) as f32 / 10.0),
        100.. => value.to_string(),
        _ => format!(" {value}"),
    };
    let mut u = x + 14.0 - (label.len() as f32 * 2.5).ceil();
    for digit in label.bytes() {
        let (offset, width) = match digit {
            b' ' => {
                u += 4.0;
                continue;
            }
            b'.' => (60.0, 3.0),
            b'k' => (64.0, 5.0),
            b'm' => (70.0, 7.0),
            n => (f32::from(n - b'0') * 6.0, 5.0),
        };
        sprite(
            game,
            batch,
            [u, y + 10.0],
            [48.0 + offset, 176.0, width, 8.0],
        );
        u += width - 1.0;
    }
}

pub(super) fn draw(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let (x, y, height, slices) = geometry(screen.rect);
    sprite(game, batch, [x - 15.0, y], [0.0, 0.0, 256.0, TOP]);
    for slice in 0..slices {
        sprite(
            game,
            batch,
            [x - 15.0, y + TOP + slice as f32 * STEP],
            [0.0, 48.0, 256.0, STEP],
        );
    }
    sprite(
        game,
        batch,
        [x - 15.0, y + height - BOTTOM],
        [0.0, 80.0, 256.0, BOTTOM],
    );
    sprite(game, batch, [x + 42.0, y + 17.0], [57.0, 17.0, 142.0, 18.0]);
    let title = game.translate("create.gui.stock_keeper.title", "Stock Keeper");
    centered(game, batch, &title, x + WIDTH / 2.0, y + 4.0, 0x714a40);
    VIEW.with_borrow_mut(|view| {
        let Some(view) = view.as_mut() else { return };
        view.search.x = x + SEARCH[0];
        view.search.y = y + SEARCH[1];
        view.search.draw(batch, &game.gui.atlas, None);
        if view.search.value.is_empty() && !view.search.focused {
            let search = game.translate("create.gui.stock_keeper.search_items", "Search Items");
            centered(
                game,
                batch,
                &search,
                x + WIDTH / 2.0,
                y + SEARCH[1],
                0x4a2d31,
            );
        }
        let footer = y + height;
        view.address.x = x + 27.0;
        view.address.y = footer - 36.0;
        view.address.draw(batch, &game.gui.atlas, None);
        if view.address.value.is_empty() && !view.address.focused {
            let hint = game.translate("create.gui.stock_keeper.package_address", "Package Address");
            game.native_text(batch, &hint, [x + 27.0, footer - 36.0], 0xcdbca8, false);
        }
        let button = [x + 143.0, footer - 39.0, 78.0, 18.0];
        if contains(button, screen.mouse) {
            sprite(
                game,
                batch,
                [x + WIDTH - 81.0, footer - 41.0],
                [55.0, 200.0, 80.0, 20.0],
            );
        }
        let send = game.translate("create.gui.stock_keeper.send", "Send");
        centered(
            game,
            batch,
            &send,
            x + WIDTH - 42.0,
            footer - 35.0,
            0x252525,
        );
        for (i, item) in view.order.iter().enumerate() {
            let at = [x + GRID[0] + i as f32 * STEP, footer - 72.0];
            game.native_gui_draw_item_with(batch, item, [at[0] + 1.0, at[1] + 1.0], Some(""));
            count(game, batch, item.count, at);
        }
        let rows = stock_rows(game, view);
        let first_row = view.first_row.min(rows.len().saturating_sub(slices));
        if rows.is_empty() {
            let (key, fallback) = if view.summary.links == 0 {
                ("no_packagers_linked", "No Packagers Linked")
            } else if view.summary.items.is_empty() {
                ("inventories_empty", "Linked Inventories are Empty")
            } else {
                ("no_search_results", "No matching items found")
            };
            let message = game.translate(&format!("create.gui.stock_keeper.{key}"), fallback);
            centered(game, batch, &message, x + WIDTH / 2.0, y + 53.0, 0xf8f8ec);
        }
        for (row, entry) in rows.into_iter().skip(first_row).take(slices).enumerate() {
            let top = y + GRID[1] + row as f32 * STEP;
            match entry {
                StockRow::Heading(label) => {
                    let default =
                        game.translate("create.gui.stock_keeper.unsorted_category", "Unsorted");
                    let label = label.unwrap_or(&default);
                    let left = x + GRID[0];
                    sprite(game, batch, [left, top + 2.0], [151.0, 176.0, 8.0, 8.0]);
                    game.native_text(batch, label, [left + 10.0, top + 4.0], 0x4a2d31, false);
                    game.native_text(batch, label, [left + 9.0, top + 3.0], 0xf8f8ec, false);
                }
                StockRow::Items(items) => {
                    for (column, item) in items.into_iter().enumerate() {
                        let left = x + GRID[0] + column as f32 * STEP;
                        sprite(game, batch, [left, top], [32.0, 200.0, 18.0, 18.0]);
                        let available = view
                            .displayed(item)
                            .saturating_sub(amount(&view.order, item));
                        if available > 0 {
                            game.native_gui_draw_item_with(
                                batch,
                                item,
                                [left + 1.0, top + 1.0],
                                Some(""),
                            );
                            count(game, batch, available, [left, top]);
                        }
                    }
                }
            }
        }
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let (x, y, height, slices) = geometry(screen.rect);
    VIEW.with_borrow_mut(|view| {
        if let Some(view) = view.as_mut() {
            let inside = contains(
                [
                    x + SEARCH[0] - 4.0,
                    y + SEARCH[1] - 4.0,
                    SEARCH[2] + 8.0,
                    SEARCH[3] + 8.0,
                ],
                screen.mouse,
            );
            view.search.focused = inside;
            if inside && button == 1 {
                view.search.set_value("");
                view.first_row = 0;
            }
            let in_address = contains([x + 25.0, y + height - 39.0, 96.0, 16.0], screen.mouse);
            view.address.focused = in_address;
            if in_address {
                if button == 1 {
                    view.address.set_value("");
                } else if button == 0 {
                    view.address
                        .click(&game.gui.atlas, screen.mouse[0], modifiers & 1 != 0, false);
                }
            }
            if !inside && !in_address && matches!(button, 0 | 1) {
                if button == 0 && contains([x + 143.0, y + height - 39.0, 78.0, 18.0], screen.mouse)
                {
                    view.submit();
                } else {
                    let order_index = item_index(screen.mouse, x + GRID[0], y + height - 72.0, 1);
                    let stock_index = item_index(screen.mouse, x + GRID[0], y + GRID[1], slices);
                    let rows = stock_rows(game, view);
                    let first_row = view.first_row.min(rows.len().saturating_sub(slices));
                    let item = order_index
                        .and_then(|index| view.order.get(index))
                        .or_else(|| {
                            let index = stock_index?;
                            rows.get(first_row + index / COLUMNS)?.item(index % COLUMNS)
                        })
                        .cloned();
                    if let Some(item) = item {
                        let transfer = if modifiers & 1 != 0 {
                            create_packager::max_stack(game.items(), &item)
                        } else if modifiers & 10 != 0 {
                            10
                        } else {
                            1
                        };
                        let delta = i64::from(transfer)
                            * if button == 1 || order_index.is_some() {
                                -1
                            } else {
                                1
                            };
                        view.adjust(&item, delta);
                    }
                }
            }
            *canceled = true;
        }
    });
}

pub(super) fn scroll(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    delta: f64,
    canceled: &mut bool,
) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    let (x, y, height, slices) = geometry(screen.rect);
    VIEW.with_borrow_mut(|view| {
        if let Some(view) = view.as_mut() {
            let rows = stock_rows(game, view);
            let max = rows.len().saturating_sub(slices);
            let first_row = view.first_row.min(max);
            let order = item_index(screen.mouse, x + GRID[0], y + height - 72.0, 1)
                .and_then(|index| view.order.get(index));
            let stock = item_index(screen.mouse, x + GRID[0], y + GRID[1], slices)
                .and_then(|index| rows.get(first_row + index / COLUMNS)?.item(index % COLUMNS));
            let transfer = delta.abs().ceil().copysign(delta) as i64;
            let item = order
                .or_else(|| stock.filter(|_| max == 0 || game.native_has_shift_down()))
                .cloned();
            if let Some(item) = item {
                view.adjust(
                    &item,
                    transfer
                        * if game.native_has_control_down() {
                            10
                        } else {
                            1
                        },
                );
            } else {
                view.first_row = view
                    .first_row
                    .saturating_add_signed(-transfer as isize)
                    .min(max);
            }
            *canceled = true;
        }
    });
}

pub(super) fn key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    VIEW.with_borrow_mut(|view| {
        if let Some(view) = view.as_mut() {
            if view.address.focused {
                *canceled = edit_address_key(&mut view.address, key, modifiers);
            } else if view.search.focused {
                *canceled = edit_address_key(&mut view.search, key, modifiers);
                if *canceled {
                    view.first_row = 0;
                }
            }
        }
    });
}

pub(super) fn character(game: &Game<'_>, c: char, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(SCREEN) {
        return;
    }
    VIEW.with_borrow_mut(|view| {
        if let Some(view) = view.as_mut() {
            if view.address.focused {
                view.address.insert_text(&c.to_string());
                *canceled = true;
            } else if view.search.focused {
                view.search.insert_text(&c.to_string());
                view.first_row = 0;
                *canceled = true;
            }
        }
    });
}
