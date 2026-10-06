(function () {
  'use strict';

  function buildDailyFortune() {
    // 한국 날짜를 seed로 사용해 같은 날에는 몇 번 눌러도 같은 운세가 나온다.
    const dateKey = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(new Date());

    let seed = 0;
    for (let i = 0; i < dateKey.length; i += 1) {
      seed = ((seed * 31) + dateKey.charCodeAt(i)) >>> 0;
    }
    const pick = (items, salt = 0) => items[(seed + salt) % items.length];

    const temperatures = [58, 61, 64, 67, 69, 72, 74, 77, 79, 82, 84, 87, 89, 92];
    const tagSets = [
      ['#관망의미학', '#숨참고러브다이브', '#줍줍각'],
      ['#존버의미학', '#분할접근', '#촉은살아있다'],
      ['#눈치게임', '#한템포쉬기', '#개미촉ON'],
      ['#천천히줍줍', '#추격금지', '#기다림승부'],
      ['#돈신내림', '#분할매수', '#오늘은신중'],
      ['#촉주의보', '#뉴스체크', '#무지성금지'],
      ['#개미레이더', '#숨고르기', '#타이밍대기']
    ];
    const messages = [
      ['오늘은 무지성 추격보다,', '한 템포 쉬어가는 개미가', '결국 웃게 될 운명 ✨'],
      ['급할수록 계좌만 숨차다.', '오늘은 천천히 보는 개미에게', '떡상 기운이 슬쩍 붙는 날 🔮'],
      ['촉은 왔지만 손은 잠깐 주머니에.', '한 번 더 보고 움직이는 개미가', '마음 편하게 웃는 날 🐜'],
      ['오늘은 앞자리보다 뒷자리가 명당.', '남들 뛸 때 숨 한번 고르고', '내 타이밍을 기다려보자 ✨'],
      ['떡상 기운은 있는데 성급함은 금지.', '조금씩 나눠 보는 개미에게', '운빨이 은근히 붙는 날 📈'],
      ['차트보다 내 손가락이 더 위험한 날.', '뉴스 한 번 더 보고 천천히.', '오늘의 행운은 참을성에 있다 🤫'],
      ['개미 레이더는 켜두고 손은 가볍게.', '기회는 도망가지 않으니', '오늘은 타이밍과 눈치 싸움 👀']
    ];

    const temperature = pick(temperatures, 3);
    const seoulDay = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Seoul',
      weekday: 'short'
    }).format(new Date());
    const isWeekend = seoulDay === 'Sat' || seoulDay === 'Sun';

    const weekendTagSets = [
      ['#주말존버', '#월요일대기', '#개미충전중'],
      ['#장도휴식중', '#손가락휴무', '#떡상기운저장'],
      ['#주말눈치게임', '#월요일준비', '#개미휴게소'],
      ['#오늘은관망', '#차트도쉰다', '#충전완료대기']
    ];
    const weekendMessages = [
      ['떡상 기운은 충만한데', '오늘은 장이 쉬는 날 🐜', '손가락도 같이 쉬어가자 ✨'],
      ['계좌 온도는 뜨겁지만', '오늘 거래소는 휴무 중.', '떡상 기운은 월요일까지 저장 🔋'],
      ['촉은 벌써 출근했는데', '장은 아직 주말 모드다.', '오늘은 개미도 충전하는 날 🐜'],
      ['오늘의 운빨은 아껴두자.', '차트도 쉬고 개미도 쉬고,', '월요일에 다시 레이더 ON 📡']
    ];

    const tags = isWeekend ? pick(weekendTagSets, 11) : pick(tagSets, 11);
    const message = isWeekend ? pick(weekendMessages, 19) : pick(messages, 19);
    return [
      '🔮 오늘의 떡상 기운',
      '',
      `오늘의 계좌 온도: ${temperature}°C 📈`,
      '',
      tags.join(' '),
      '',
      ...message,
      '',
      '※ 100% 재미용! 챗봇 탓 금지 🤫'
    ].join('\n');
  }

  window.GaemiGTPDailyFortune = {
    buildDailyFortune
  };
})();
