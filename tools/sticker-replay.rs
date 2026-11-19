#[path="../native/sticker_animation.rs"] mod sticker_animation;
use sticker_animation::Animation;
fn main() {
    let times: [&[usize];3] = [&[1,8],&[1,2,4,5,6,7],&[1,2,5,6,10]];
    let targets: [&[bool];3] = [&[true,false],&[true,false,true,false,true,false],&[true,true,false,false,true]];
    let mut scenario=0;
    for initial in [false,true] { for attached in [false,true] { for schedule in 0..3 {
        let mut animation=Animation::new(initial);let mut extended=initial;
        for tick in 0..16 {
            if tick==0 { animation.receive(); }
            for (index,&at) in times[schedule].iter().enumerate() { if at==tick { extended=targets[schedule][index];animation.receive(); } }
            let events=animation.tick(extended,attached);
            let frames=[0.0,0.25,0.5,0.75,1.0].map(|p|animation.head_offset(p).to_bits().to_string()).join(",");
            println!("{{\"kind\":\"animation\",\"case\":{scenario},\"tick\":{tick},\"previous\":{},\"value\":{},\"target\":{},\"events\":{events},\"frames\":[{frames}]}}",animation.previous.to_bits(),animation.value.to_bits(),animation.target.to_bits());
        }
        scenario+=1;
    } } }
}
