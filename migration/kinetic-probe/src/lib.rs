pub(crate) mod kinetic_slice;
pub(crate) mod kinetic_adapter;

#[derive(Default)]
struct Mod;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Mod {
    fn register(&self, registrar: &mut dyn mod_api::Registrar, _: &mod_api::RegistrationContext) {
        kinetic_adapter::register(registrar);
    }
}
