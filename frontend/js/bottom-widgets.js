// gaemiGTP bottom widgets module
// 하단 개미 투표 기능을 app.js에서 분리하기 위한 전용 파일.
// 기존 HTML onclick 호환을 위해 전역 함수 이름 castVote를 그대로 유지한다.

let voted = false;

function castVote(type) {
  if (voted) return alert('이미 투표하셨습니다!');
  voted = true;
  const bar = document.getElementById('voteProgressBar');
  const upLbl = document.getElementById('voteUpLabel');
  const downLbl = document.getElementById('voteDownLabel');
  if (type === 'up') {
    bar.style.width = '74%';
    upLbl.innerText = '상승 74%';
    downLbl.innerText = '하락 26%';
  } else {
    bar.style.width = '61%';
    upLbl.innerText = '상승 61%';
    downLbl.innerText = '하락 39%';
  }
}
