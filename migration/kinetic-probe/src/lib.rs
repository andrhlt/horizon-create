#[path = "../../../native/kinetic_slice.rs"]
pub(crate) mod kinetic_slice;
#[path = "../../../native/kinetic_adapter.rs"]
pub(crate) mod kinetic_adapter;
pub(crate) mod motor_board;


#[derive(Default)]
struct Mod;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Mod {
    fn register(&self, registrar: &mut dyn mod_api::Registrar, _: &mod_api::RegistrationContext) {
        kinetic_adapter::register(registrar);
        motor_board::register(registrar);
    }

}

