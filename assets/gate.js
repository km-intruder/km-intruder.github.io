/* 간단한 접근 코드 화면 (사이트 전체)
   - 코드는 저장하지 않고 SHA-256 해시만 둔다. 변경: python scripts/set_access_code.py <새 코드>
   - 입력 상태는 sessionStorage 에만 둔다: 브라우저(탭)를 닫으면 다시 묻는다
   - 공개 저장소의 파일 자체를 숨기지는 않는다. 우연한 방문·검색 노출을 막는 용도 */
(function () {
  var HASH = '56bb10679132bfba0133eb050cb5bb48a0ea50efe91ad934ff4bf6f6df63ac1a'; // set_access_code.py 가 갱신
  var SALT = 'km-intruder:';
  var KEY = 'km-access';

  function saved() { try { return sessionStorage.getItem(KEY); } catch (e) { return null; } }

  // 로그아웃(잠그기) 버튼: 화면 왼쪽 아래 작게, 인쇄 시 숨김
  function addLock() {
    if (document.getElementById('gate-lock')) return;
    var btn = document.createElement('button');
    btn.id = 'gate-lock';
    btn.type = 'button';
    btn.textContent = '잠그기';
    btn.title = '접근 코드를 지우고 다시 잠급니다';
    btn.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:900;padding:4px 10px;font-size:12px;' +
      'font-family:Pretendard,-apple-system,"Malgun Gothic",sans-serif;background:#fff;color:#4a525c;' +
      'border:1px solid #d7dbe0;border-radius:0;cursor:pointer;opacity:.85';
    btn.addEventListener('click', function () {
      try { sessionStorage.removeItem(KEY); } catch (e) {}
      location.reload();
    });
    var css = document.createElement('style');
    css.textContent = '@media print{#gate-lock{display:none!important}}';
    document.head.appendChild(css);
    document.body.appendChild(btn);
  }
  function whenBody(fn) { if (document.body) fn(); else document.addEventListener('DOMContentLoaded', fn); }

  if (saved() === HASH) { whenBody(addLock); return; }

  var hide = document.createElement('style');
  hide.id = 'gate-hide';
  hide.textContent = 'html{visibility:hidden!important;background:#fff}';
  document.head.appendChild(hide);

  async function sha256(text) {
    var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
  }

  function show() {
    var box = document.createElement('div');
    box.id = 'gate';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-label', '접근 코드 입력');
    box.style.cssText = 'visibility:visible;position:fixed;inset:0;z-index:2147483647;background:#fff;display:flex;align-items:center;justify-content:center;font-family:Pretendard,-apple-system,"Malgun Gothic",sans-serif;color:#16191d';
    box.innerHTML =
      '<form style="width:min(320px,calc(100vw - 32px));border-top:3px solid #16191d;padding-top:16px">' +
      '<div style="font-size:13px;color:#7b838d">김광섭 교수 교육 서비스</div>' +
      '<div style="font-size:20px;font-weight:700;margin:4px 0 14px">접근 코드</div>' +
      '<input type="password" autocomplete="current-password" aria-label="접근 코드" required ' +
      'style="width:100%;box-sizing:border-box;border:1px solid #16191d;padding:10px;font-size:16px;border-radius:0">' +
      '<button type="submit" style="margin-top:8px;width:100%;padding:10px;border:0;background:#16191d;color:#fff;font-size:15px;cursor:pointer;border-radius:0">들어가기</button>' +
      '<div class="gate-msg" style="min-height:20px;margin-top:8px;font-size:13px;color:#c4161c"></div></form>';
    document.body.appendChild(box);
    var form = box.querySelector('form'), input = box.querySelector('input'), msg = box.querySelector('.gate-msg');
    input.focus();
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!window.crypto || !crypto.subtle) { msg.textContent = 'https 주소로 접속해 주세요.'; return; }
      if (await sha256(SALT + input.value) === HASH) {
        try { sessionStorage.setItem(KEY, HASH); } catch (err) {}
        box.remove();
        hide.remove();
        addLock();
      } else {
        msg.textContent = '코드가 맞지 않습니다.';
        input.select();
      }
    });
  }

  whenBody(show);
})();
