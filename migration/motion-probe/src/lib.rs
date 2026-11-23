use mod_api::{
    BlockEntityOnLoadEvent, BlockEntityPart, BlockEntityTickEvent, BlockEntityTicksEvent, Compound,
    HostSide, ServerHost, Tag,
};

const BEARING: &str = "create:mechanical_bearing";

#[derive(Clone, Copy)]
struct MovingPart;

fn payload() -> Compound {
    Compound::from([
        (
            "PayloadBlocks".into(),
            Tag::List(vec![Tag::Compound(Compound::from([
                ("Name".into(), Tag::String("minecraft:chest".into())),
                ("Pos".into(), Tag::IntArray(vec![0, 0, 0])),
            ]))]),
        ),
        (
            "PayloadItems".into(),
            Tag::List(vec![Tag::Compound(Compound::from([
                ("Item".into(), Tag::String("minecraft:iron_ingot".into())),
                ("Count".into(), Tag::Int(7)),
            ]))]),
        ),
        ("Rider".into(), Tag::IntArray(vec![1, 2, 3, 4])),
        ("MotionOffset".into(), Tag::Int(0)),
        ("Moving".into(), Tag::Byte(1)),
    ])
}

impl MovingPart {
    fn ensure_payload(&self, entity: &mut Compound) {
        if !entity.contains_key(&"PayloadBlocks".into()) {
            let initial = payload();
            for (key, value) in initial {
                entity.insert(key, value);
            }
        }
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for MovingPart {
    fn block_entity_update_tag(
        &self,
        event: &mut mod_api::BlockEntityUpdateTagEvent<'_>,
    ) -> Option<Compound> {
        Some(event.entity.nbt.clone())
    }

    fn block_entity_on_load(&self, side: HostSide<'_>, event: &mut BlockEntityOnLoadEvent) {
        let HostSide::Server(host) = side else { return };
        let mut data = event.entity.nbt.clone();
        self.ensure_payload(&mut data);
        event.entity.nbt = data.clone();
        let _ = event.entity.merge_data(host, data);
    }

    fn block_entity_ticks(&self, _: &dyn mod_api::Host, event: &mut BlockEntityTicksEvent<'_>) {
        event.ticks = true;
    }

    fn block_entity_tick(&self, host: &mut dyn ServerHost, event: &mut BlockEntityTickEvent<'_>) {
        let Some(level) = event.entity.level(host) else {
            return;
        };
        let mut data = event.entity.nbt.clone();
        self.ensure_payload(&mut data);
        let offset = match data.get(&"MotionOffset".into()) {
            Some(Tag::Int(value)) => *value,
            _ => 0,
        };
        let blocked = host
            .level_has_collisions(
                level,
                [
                    f64::from(event.pos[0]) + 0.1,
                    f64::from(event.pos[1]) + f64::from(offset) * 0.05,
                    f64::from(event.pos[2]) + 0.1,
                    f64::from(event.pos[0]) + 1.9,
                    f64::from(event.pos[1]) + 1.9 + f64::from(offset) * 0.05,
                    f64::from(event.pos[2]) + 1.9,
                ],
            )
            .unwrap_or(false);
        data.insert("CollisionBlocked".into(), Tag::Byte(blocked as i8));
        if !blocked && offset < 8 {
            data.insert("MotionOffset".into(), Tag::Int(offset + 1));
        } else {
            data.insert("Moving".into(), Tag::Byte(0));
            data.insert("Disassembled".into(), Tag::Byte(1));
            data.insert("RiderSafeDismount".into(), Tag::Byte(1));
        }
        event.entity.nbt = data;
    }
}

#[derive(Default)]
struct Mod;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Mod {
    fn register(&self, registrar: &mut dyn mod_api::Registrar, _: &mod_api::RegistrationContext) {
        let kind = registrar
            .block_entity_type("create:mechanical_bearing")
            .blocks(&[BEARING])
            .build();
        registrar.block_entity_part(&kind, MovingPart).unwrap();
    }
}
