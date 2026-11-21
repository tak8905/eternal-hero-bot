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


def clear_blockers(page, hide_user_modal=False):
  """GDPR 동의 배너와 모달 창이 클릭을 가로막지 않도록 정리"""
  # 1) GDPR 쿠키 동의/수락 버튼 클릭 시도
  gdpr_selectors = [
      '#gdpr-consent-form button:has-text("Accept")',
      '#gdpr-consent-form button:has-text("Agree")',
      '#gdpr-consent-form button:has-text("Allow")',
      '#gdpr-consent-form button:has-text("동의")',
      '#gdpr-consent-form button:has-text("수락")',
      '#gdpr-consent-form button:has-text("확인")',
      ".gdpr-container button",
  ]
  for sel in gdpr_selectors:
    loc = page.locator(sel)
    if loc.count() > 0:
      for i in range(loc.count()):
        btn = loc.nth(i)
        if btn.is_visible():
          try:
            btn.click(timeout=2000)
            time.sleep(0.4)
            break
          except Exception:
            pass

  # 2) 열린 모달 닫기 버튼 클릭 시도
  if hide_user_modal:
    close_selectors = [
        '.user-id-modal button[aria-label*="close" i]',
        '.user-id-modal button[aria-label*="닫기" i]',
        '.user-id-modal button:has-text("×")',
        '.user-id-modal button:has-text("✕")',
        '.user-id-modal [class*="close"]',
    ]
    for sel in close_selectors:
      loc = page.locator(sel)
      if loc.count() > 0 and loc.first.is_visible():
        try:
          loc.first.click(timeout=2000)
          time.sleep(0.4)
          break
        except Exception:
          pass

  # 3) 여전히 화면을 가리고 클릭을 가로채는 GDPR / 모달 오버레이 처리
  try:
    page.evaluate(
        """(hideModal) => {
            const gdpr = document.querySelector('#gdpr-consent-form, .gdpr-container');
            if (gdpr) {
                gdpr.style.setProperty('display', 'none', 'important');
                gdpr.style.setProperty('pointer-events', 'none', 'important');
            }
            if (hideModal) {
                const modals = document.querySelectorAll('[data-id="user-id-modal"], .user-id-modal');
                modals.forEach((m) => {
                    m.style.setProperty('display', 'none', 'important');
                    m.style.setProperty('pointer-events', 'none', 'important');
                });
            }
        }""",
        hide_user_modal,
    )
  except Exception:
    pass


def click_login_arrow(page):
  """Player ID 입력창 옆 화살표(제출) 버튼 클릭"""
  arrow_parent_btn = page.locator(
      'button:has(svg.fast-login__input-container-button-icon), [class*="fast-login"] button'
  )
  if arrow_parent_btn.count() > 0 and arrow_parent_btn.first.is_visible():
    arrow_parent_btn.first.click(timeout=10000)
    return

  arrow_svg = page.locator("svg.fast-login__input-container-button-icon")
  if arrow_svg.count() > 0:
    arrow_svg.first.click(timeout=10000, force=True)
    return

  page.keyboard.press("Enter")


def run_one_account(page, player_id):
  """1개 Player ID 작업: 로그인 -> 하단 무료 3개 장바구니 담기 -> 카트 열기 -> 확인해 보세요 클릭"""
  player_id = str(player_id).strip()
  step = "페이지 접속"
  try:
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    # 로그인 입력창이 모달 안에 있을 수 있으므로 로그인 전에는 user-id-modal을 숨기지 않고 GDPR만 정리
    clear_blockers(page, hide_user_modal=False)

    # 1단계: Player ID 입력 및 로그인 제출
    step = "1단계(Player ID 입력)"
    id_input = page.locator(
        'input[placeholder*="플레이어 ID"],'
        ' input[placeholder*="Player ID" i], input.fast-login__input,'
        ' input[type="password"]'
    ).first
    id_input.wait_for(state="visible", timeout=10000)
    id_input.click(timeout=10000)
    id_input.fill(player_id)
    time.sleep(0.5)

    step = "1단계(화살표 로그인 클릭)"
    click_login_arrow(page)
    time.sleep(3)
    # 로그인 후에는 user-id-modal과 GDPR이 상품 버튼 클릭을 막지 않도록 정리
    clear_blockers(page, hide_user_modal=True)

    # 2단계: 화면 최하단으로 스크롤 후 무료 상품 장바구니 담기 버튼 클릭
    step = "2단계(무료 아이템 장바구니 담기)"
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    clear_blockers(page, hide_user_modal=True)

    free_cart_btns = page.locator(
        'button[data-testid^="add-to-cart-store-button-free"],'
        ' button[data-sku^="free"]'
    )
    free_count = free_cart_btns.count()
    print(f"    발견된 무료 장바구니 버튼 수: {free_count}")

    claimed = 0
    for i in range(min(free_count, 3)):
      clear_blockers(page, hide_user_modal=True)
      btn = free_cart_btns.nth(i)
      btn.scroll_into_view_if_needed(timeout=10000)
      btn.click(timeout=10000)
      claimed += 1
      time.sleep(1)

    # 3단계: 헤더 장바구니('카트') 버튼 클릭 후 장바구니 내 '확인해 보세요' 버튼 클릭
    step = "3단계(헤더 장바구니 열기)"
    clear_blockers(page, hide_user_modal=True)
    header_cart_btn = page.locator(
        'button[data-testid="header-cart-button"],'
        ' button[aria-label="헤더 장바구니 버튼"], button.cart-button'
    ).first
    header_cart_btn.scroll_into_view_if_needed(timeout=10000)
    header_cart_btn.click(timeout=10000)
    time.sleep(1.5)

    step = "3단계(확인해 보세요 클릭)"
    checkout_btn = page.locator(
        'button[data-testid="cart-checkout-button"], button.cart__checkout-button'
    ).first
    checkout_btn.wait_for(state="visible", timeout=10000)
    checkout_btn.click(timeout=10000)
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

      context = browser.new_context()
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
