import json
import os
import time
from playwright.sync_api import sync_playwright
import requests

URL = "https://store.eternalhero.rivvy.games/"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
ACCOUNTS = json.loads(os.environ.get("ACCOUNTS", "[]"))


def send_discord(total, success, fail, items):
  """디스코드 웹훅으로 수령 결과 보고"""
  if not DISCORD_WEBHOOK:
    print("DISCORD_WEBHOOK 환경변수가 비어 있습니다.")
    return

  message = (
      f"**[Eternal Hero 보상 수령 보고]**\n"
      f"• 현황: 등록 인원 {total}명 / 완료 {success}명 (실패 {fail}명)\n"
      f"• 신규 수령: 총 {items}개 수령 완료"
  )
  resp = requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=15)
  print(f"디스코드 전송 상태코드: {resp.status_code}")


def hide_overlays(page, hide_user_modal=True):
  """모달 및 GDPR 창이 클릭을 방해하지 않도록 숨김 처리"""
  try:
    page.evaluate(
        """(hideModal) => {
                const selectors = ['#gdpr-consent-form', '.gdpr-container'];
                if (hideModal) {
                    selectors.push('[data-id="user-id-modal"]', '.user-id-modal', '.ui-site-modal-window');
                }
                selectors.forEach((sel) => {
                    document.querySelectorAll(sel).forEach((el) => {
                        el.style.setProperty('display', 'none', 'important');
                        el.style.setProperty('visibility', 'hidden', 'important');
                        el.style.setProperty('pointer-events', 'none', 'important');
                    });
                });
            }""",
        hide_user_modal,
    )
  except Exception:
    pass


def click_element_smart(page, selectors, timeout_sec=10):
  """여러 선택자 중 보이는 요소를 찾아 일반 click() -> JS click() 순으로 클릭"""
  deadline = time.time() + timeout_sec
  while time.time() < deadline:
    for sel in selectors:
      loc = page.locator(sel)
      count = loc.count()
      for i in range(count):
        el = loc.nth(i)
        try:
          if el.is_visible():
            el.scroll_into_view_if_needed(timeout=2500)
            try:
              el.click(timeout=2500)
              return True
            except Exception:
              el.evaluate("node => node.click()")
              return True
        except Exception:
          continue
    time.sleep(0.35)
  return False


def dump_visible_buttons(page):
  """3단계 실패 시 현재 화면의 버튼 텍스트/testid 일부 출력"""
  try:
    info = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button'))
                .filter(b => b.offsetParent !== null)
                .slice(0, 20)
                .map(b => ({
                    text: (b.innerText || '').trim().replace(/\\s+/g, ' '),
                    testid: b.getAttribute('data-testid') || '',
                    aria: b.getAttribute('aria-label') || ''
                }));
        }""")
    print(f"    [3단계 디버그 버튼] {info}")
  except Exception:
    pass


def run_one_account(page, player_id):
  """1개 Player ID 작업: 로그인 -> 하단 무료 아이템 담기 -> 장바구니 열기 및 확인"""
  player_id = str(player_id).strip()
  step = "페이지 접속"
  try:
    page.goto(URL, wait_until="domcontentloaded", timeout=25000)
    time.sleep(1.5)
    hide_overlays(page, hide_user_modal=False)

    # 1단계: Player ID 입력
    step = "1단계(Player ID 입력)"
    id_input = page.locator(
        'input[placeholder*="플레이어 ID"],'
        ' input[placeholder*="Player ID" i], input.fast-login__input,'
        ' input[type="password"]'
    ).first
    id_input.wait_for(state="visible", timeout=10000)
    id_input.evaluate("node => node.focus()")
    id_input.fill(player_id)
    time.sleep(0.5)

    # 1단계: 화살표 버튼 또는 Enter로 로그인 제출
    step = "1단계(로그인 제출)"
    clicked_login = click_element_smart(
        page,
        [
            'button:has(svg.fast-login__input-container-button-icon)',
            '[class*="fast-login"] button',
            'svg.fast-login__input-container-button-icon',
        ],
        timeout_sec=5,
    )
    if not clicked_login:
      page.keyboard.press("Enter")
    time.sleep(3)

    hide_overlays(page, hide_user_modal=True)

    # 2단계: 화면 하단으로 스크롤 후 무료 아이템 담기 버튼 클릭
    step = "2단계(무료 아이템 담기)"
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1.5)
    hide_overlays(page, hide_user_modal=True)

    free_btns = page.locator(
        'button[data-testid^="add-to-cart-store-button-free"],'
        ' button[data-sku^="free"], button[data-testid="free-button"]'
    )
    free_count = free_btns.count()
    print(f"    발견된 무료 버튼 수: {free_count}")

    claimed = 0
    for i in range(min(free_count, 3)):
      hide_overlays(page, hide_user_modal=True)
      btn = free_btns.nth(i)
      try:
        btn.scroll_into_view_if_needed(timeout=3000)
        try:
          btn.click(timeout=2500)
        except Exception:
          btn.evaluate("node => node.click()")
        claimed += 1
        time.sleep(0.9)
      except Exception as e:
        print(f"    무료 버튼 {i+1}번째 클릭 스킵: {e}")

    if claimed == 0:
      raise RuntimeError("클릭 가능한 무료 버튼이 없거나 담기에 실패했습니다.")

    # 3단계: 헤더 장바구니 열기 및 최종 확인 클릭
    step = "3단계(장바구니 열기 및 확인)"
    hide_overlays(page, hide_user_modal=True)

    checkout_selectors = [
        'button[data-testid="cart-checkout-button"]',
        "button.cart__checkout-button",
        'button:has-text("확인해 보세요")',
        'button:has-text("확인")',
        'button:has-text("Checkout")',
    ]

    opened_cart = False
    for attempt in range(2):
      clicked_cart = click_element_smart(
          page,
          [
              'button[data-testid="header-cart-button"]',
              'button[aria-label="헤더 장바구니 버튼"]',
              "button.cart-button",
          ],
          timeout_sec=8,
      )
      if not clicked_cart:
        break

      # 장바구니 패널/모달이 열릴 때까지 대기
      deadline = time.time() + 5
      while time.time() < deadline:
        for csel in checkout_selectors:
          if page.locator(csel).first.is_visible():
            opened_cart = True
            break
        if opened_cart:
          break
        time.sleep(0.3)

      if opened_cart:
        break
      time.sleep(0.6)

    if not opened_cart:
      dump_visible_buttons(page)
      raise RuntimeError("장바구니가 열리지 않았거나 확인 버튼을 찾지 못했습니다.")

    checked_out = click_element_smart(
        page,
        checkout_selectors,
        timeout_sec=10,
    )
    if not checked_out:
      dump_visible_buttons(page)
      raise RuntimeError("장바구니 확인/결제 버튼을 찾지 못했습니다.")
    time.sleep(2)

    return claimed

  except Exception as e:
    short_msg = str(e).splitlines()[0] if str(e) else "알 수 없는 오류"
    raise RuntimeError(f"[{step}] {short_msg}") from e


def main():
  total = len(ACCOUNTS)
  success = 0
  fail = 0
  total_items = 0

  if total == 0:
    print("ACCOUNTS 목록이 비어 있습니다.")
    return

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for idx, acc in enumerate(ACCOUNTS, start=1):
      pid = (acc.get("player_id") or acc.get("id") or "").strip()
      if not pid:
        fail += 1
        print(f"[{idx}/{total}] 빈 Player ID 건너뜀")
        continue

      context = browser.new_context(viewport={"width": 1440, "height": 900})
      page = context.new_page()
      try:
        items = run_one_account(page, pid)
        success += 1
        total_items += items
        print(f"[{idx}/{total}] [{pid}] 성공 ({items}개)")
      except Exception as e:
        fail += 1
        print(f"[{idx}/{total}] [{pid}] 실패: {e}")
      finally:
        context.close()

    browser.close()

  send_discord(total, success, fail, total_items)


if __name__ == "__main__":
  main()
