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


def click_login_arrow(page):
  """Player ID 입력창 옆 화살표(제출) 버튼 클릭"""
  # 1순위: 화살표 아이콘을 감싼 버튼
  arrow_parent_btn = page.locator(
      'button:has(svg.fast-login__input-container-button-icon), [class*="fast-login"] button'
  )
  if arrow_parent_btn.count() > 0 and arrow_parent_btn.first.is_visible():
    arrow_parent_btn.first.click(timeout=8000)
    return

  # 2순위: svg 아이콘 자체 또는 Enter 키
  arrow_svg = page.locator("svg.fast-login__input-container-button-icon")
  if arrow_svg.count() > 0:
    arrow_svg.first.click(timeout=8000, force=True)
    return

  page.keyboard.press("Enter")


def run_one_account(page, player_id):
  """1개 Player ID 작업: 로그인 -> 하단 무료 아이템 담기 -> 장바구니 확인"""
  player_id = str(player_id).strip()
  step = "페이지 접속"
  try:
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)

    # 1단계: Player ID 입력창(type="password", placeholder="플레이어 ID를 입력하세요...") 찾기
    step = "1단계(Player ID 입력)"
    id_input = page.locator(
        'input[placeholder*="플레이어 ID"],'
        ' input[placeholder*="Player ID" i], input.fast-login__input,'
        ' input[type="password"]'
    ).first
    id_input.wait_for(state="visible", timeout=10000)
    id_input.click(timeout=8000)
    id_input.fill(player_id)
    time.sleep(0.5)

    step = "1단계(화살표 로그인 클릭)"
    click_login_arrow(page)
    time.sleep(3)

    # 2단계: 화면 최하단으로 스크롤 후 무료('무료로 받으세요' / free-button) 아이템 최대 3개 클릭
    step = "2단계(무료 아이템 담기)"
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    free_btns = page.locator(
        '[data-testid="free-button"], [data-button-type="free"],'
        ' button:has-text("무료로 받으세요"), button:has-text("무료")'
    )
    free_count = free_btns.count()
    print(f"  - 발견된 무료 버튼 수: {free_count}")

    claimed = 0
    for i in range(min(free_count, 3)):
      btn = free_btns.nth(i)
      btn.scroll_into_view_if_needed(timeout=8000)
      btn.click(timeout=8000)
      claimed += 1
      time.sleep(1)

    # 3단계: 장바구니 열기 및 최종 확인 클릭
    step = "3단계(장바구니 열기 및 확인)"
    cart_btn = page.locator(
        '[aria-label*="Cart" i], [aria-label*="장바구니" i], .cart-button,'
        ' button:has-text("Cart"), button:has-text("장바구니")'
    ).first
    cart_btn.click(timeout=8000)
    time.sleep(1.5)

    confirm_btn = page.locator(
        'button:has-text("Confirm"), button:has-text("Checkout"),'
        ' button:has-text("Claim"), button:has-text("확인"),'
        ' button:has-text("받기"), button:has-text("구매")'
    ).first
    confirm_btn.click(timeout=8000)
    time.sleep(2)

    return claimed

  except Exception as e:
    raise RuntimeError(f"[{step}] {e}") from e


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
