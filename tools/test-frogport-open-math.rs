#[path = "../native/frogport_open_math.rs"]
mod frogport_open_math;

#[test]
fn opening_and_reversing_match_java() {
    let mut motion = frogport_open_math::Motion::default();
    let mut last_tick = -1;
    let mut closed = false;
    let mut count = 0;
    for row in include_str!("../fixtures/frogport-manual-open-java.csv")
        .lines()
        .skip(1)
    {
        let fields: Vec<_> = row.split(',').collect();
        let tick: i32 = fields[0].parse().unwrap();
        if tick != last_tick {
            closed = motion.tick(fields[1].parse().unwrap());
            last_tick = tick;
        }
        let value = motion.value(fields[2].parse().unwrap());
        for (actual, expected) in [value, value * 60.0, value * 0.25]
            .into_iter()
            .zip(&fields[3..6])
        {
            assert!(
                (actual - expected.parse::<f32>().unwrap()).abs() < 0.000005,
                "{row}: {actual}"
            );
        }
        assert_eq!(closed, fields[6].parse::<bool>().unwrap(), "{row}");
        count += 1;
    }
    assert_eq!(count, 48);
    assert!(motion.closed());
}
