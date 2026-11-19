//! Replays tank scripts through the same connectivity module used by Horizon.
#[path = "../native/tank_connectivity.rs"]
mod create_tank_connectivity;
#[path = "../native/tank_storage.rs"]
mod tank_storage;

use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::io::{self, Write};
use std::time::Instant;
use serde_json::{Value, json};
use create_tank_connectivity::{Part, Pos};

#[derive(Clone)]
struct FixtureFluid { id: String, amount: i32, components: Option<Value> }
impl create_tank_connectivity::Fluid for FixtureFluid {
    fn amount(&self) -> i32 { self.amount }
    fn set_amount(&mut self, amount: i32) { self.amount = amount; }
    fn same_variant(&self, other: &Self) -> bool { self.id == other.id && self.components == other.components }
}
fn pos(v: &Value) -> Result<Pos, Box<dyn Error>> { Ok(serde_json::from_value(v.clone())?) }
fn integer(v: &Value) -> Result<i32, Box<dyn Error>> { Ok(serde_json::from_value(v.clone())?) }

fn fluid(action: &Value) -> Result<FixtureFluid, Box<dyn Error>> {
    let id = action["fluid"].as_str().ok_or("missing fluid")?;
    let amount = integer(&action["amount"])?;
    if amount < 0 { return Err("negative amount".into()); }
    let components = match &action["components"] {
        Value::Null => None,
        Value::Object(map) if map.is_empty() => None,
        Value::Object(_) => Some(action["components"].clone()),
        _ => return Err("components must be an object".into()),
    };
    Ok(FixtureFluid { id: id.into(), amount, components })
}

fn reconnect_kind(parts: &mut BTreeMap<Pos, Part<FixtureFluid>>, creative: &BTreeSet<Pos>, at: Pos) {
    let kind = creative.contains(&at);
    let mut group: BTreeMap<_, _> = parts.iter()
        .filter(|(pos, _)| creative.contains(*pos) == kind)
        .map(|(&pos, part)| (pos, part.clone())).collect();
    create_tank_connectivity::reconnect(&mut group, at, kind);
    parts.extend(group);
}

fn replay(script: &Value) -> Result<Vec<Value>, Box<dyn Error>> {
    let mut parts = BTreeMap::<Pos, Part<FixtureFluid>>::new();
    let mut order = Vec::new();
    let mut creative = BTreeSet::new();
    let include_components = script["include_components"].as_bool().unwrap_or(false);
    let mut tick = 0;
    let mut output = Vec::new();
    for action in script["actions"].as_array().ok_or("missing actions")? {
        match action["op"].as_str().ok_or("missing op")? {
            "place" => {
                let at = pos(&action["pos"])?;
                if parts.contains_key(&at) { continue; }
                parts.insert(at, Part { controller: at, width: 1, height: 1, fluid: None, dirty: true, touched: true });
                if action["block"].as_str() == Some("creative") { creative.insert(at); }
                order.push(at);
                reconnect_kind(&mut parts, &creative, at);
            }
            "fill" | "drain" | "configure" => {
                let op = action["op"].as_str().unwrap();
                let at = pos(&action["pos"])?;
                let root = parts.get(&at).ok_or("missing tank")?.controller;
                let part = parts.get_mut(&root).ok_or("missing controller")?;
                let capacity = part.width * part.width * part.height * 8000;
                let is_creative = creative.contains(&root);
                let execute = !action["simulate"].as_bool().unwrap_or(false);
                match op {
                    "fill" => {
                        let incoming = fluid(action)?;
                        let accepted = tank_storage::fill(&mut part.fluid, capacity, is_creative, &incoming, execute);
                        output.push(json!({"type":"fill", "tick":tick, "pos":at, "accepted":accepted}));
                    }
                    "drain" => {
                        let amount = integer(&action["amount"])?;
                        if amount < 0 { return Err("negative amount".into()); }
                        let requested = if action["fluid"].is_null() { None } else { Some(fluid(action)?) };
                        let drained = tank_storage::drain(&mut part.fluid, is_creative, amount, requested.as_ref(), execute);
                        let (id, amount) = drained.as_ref().map_or(("minecraft:empty", 0), |f| (f.id.as_str(), f.amount));
                        let mut row = json!({"type":"drain", "tick":tick, "pos":at, "fluid":id, "amount":amount});
                        if include_components { row["components"] = drained.and_then(|f| f.components).unwrap_or(Value::Null); }
                        output.push(row);
                    }
                    _ => {
                        if !is_creative { return Err("configure requires a creative tank".into()); }
                        let incoming = fluid(action)?;
                        let configured = (incoming.id != "minecraft:empty" && incoming.amount > 0).then_some(incoming);
                        tank_storage::configure(&mut part.fluid, capacity, configured);
                        output.push(json!({"type":"configure", "tick":tick, "pos":at}));
                    }
                }
            }
            "remove" => {
                let at = pos(&action["pos"])?;
                if let Some(root) = parts.get(&at).map(|p| p.controller) {
                    let controller = parts.get(&root).ok_or("missing controller")?;
                    let present: BTreeSet<_> = parts.keys().copied().collect();
                    let released = create_tank_connectivity::split_removed(root, controller.width, controller.height, at, controller.fluid.clone(), &present, creative.contains(&root));
                    parts.remove(&at);
                    creative.remove(&at);
                    parts.extend(released);
                    order.retain(|p| *p != at);
                }
            }
            "tick" => {
                let count = integer(&action["count"])?;
                if count < 0 { return Err("negative tick count".into()); }
                for _ in 0..count {
                    for &at in &order { reconnect_kind(&mut parts, &creative, at); }
                    tick += 1;
                }
            }
            "probe" => {
                let label = action["label"].as_str().ok_or("missing label")?;
                for value in action["positions"].as_array().ok_or("missing positions")? {
                    let at = pos(value)?;
                    let (block, root, capacity, fluid, amount) = match parts.get(&at) {
                        Some(part) => {
                            let controller = parts.get(&part.controller).ok_or("missing controller")?;
                            let (id, amount) = controller.fluid.as_ref().map_or(("minecraft:empty",0), |f| (f.id.as_str(), f.amount));
                            (if creative.contains(&at) { "create:creative_fluid_tank" } else { "create:fluid_tank" }, Some(part.controller), controller.width * controller.width * controller.height * 8000, id, amount)
                        }
                        None => ("minecraft:air", None, 0, "minecraft:empty", 0),
                    };
                    let mut row = json!({"type":"probe","label":label,"tick":tick,"pos":at,
                        "block":block,"controller":root,"capacity":capacity,"fluid":fluid,"amount":amount});
                    if include_components {
                        row["components"] = root.and_then(|r| parts.get(&r)).and_then(|p| p.fluid.as_ref())
                            .and_then(|f| f.components.clone()).unwrap_or(Value::Null);
                    }
                    output.push(row);
                }
            }
            op => return Err(format!("unsupported tank script operation {op}").into()),
        }
    }
    Ok(output)
}
fn main() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args().skip(1);
    let path = args.next().ok_or("usage: create-tank-replay SCRIPT [--repeat N]")?;
    let repetitions: usize = match args.next().as_deref() {
        None => 1,
        Some("--repeat") => args.next().ok_or("missing repeat count")?.parse()?,
        Some(_) => return Err("unknown argument".into()),
    };
    if repetitions == 0 || args.next().is_some() { return Err("invalid arguments".into()); }
    let script: Value = serde_json::from_slice(&std::fs::read(&path)?)?;
    let started = Instant::now();
    let first = replay(&script)?;
    for _ in 1..repetitions { std::hint::black_box(replay(&script)?); }
    eprintln!("{}", json!({"backend":"core","repetitions":repetitions,"elapsed_seconds":started.elapsed().as_secs_f64(),"records":first.len()}));
    let mut stdout = io::BufWriter::new(io::stdout().lock());
    for record in first { serde_json::to_writer(&mut stdout, &record)?; writeln!(stdout)?; }
    Ok(())
}
