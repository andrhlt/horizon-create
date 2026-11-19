// Java LinearActuatorBlockEntity.tryDisassemble: mode 0 always places,
// mode 1 places only at the assembly offset, mode 2 never places.
pub(crate) fn should_place(mode: i32, initial: i32, offset: f32) -> bool {
    mode != 2 && (mode != 1 || (offset + 0.5) as i32 == initial)
}
