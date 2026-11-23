import json
import os
import time
from playwright.sync_api import sync_playwright
import requests

# =====================================================================
# [상단 고정 영역 1] 유저 목록 (새 유저가 생기면 여기에 한 줄씩 추가)
# =====================================================================
FIXED_ACCOUNTS = [
    {"player_id": "PusOwtcLJcV03wn8RjtoECrhB1CA"},
    {"player_id": "Ehqg9VFIColuEZ0YriFCndrkjqxC"},
    {"player_id": "etltqmR2t7nHhsA4Zlj69eIBMgHw"},
    {"player_id": "Cpt2bVRCBN8sPB0X4kanLhbmUQnB"},
    {"player_id": "mKmcEKX8iEn3uyL7ay9QBupYfGVw"},
    {"player_id": "0MnF3UKYBXPloeubzu5wqFbNircx"},
    {"player_id": "SCk8Uc6IpSZPRH8a1fgfDe97fvD2"},
    {"player_id": "7khxgIvJmnNZHSAitTS1fORtb5Au"},
    {"player_id": "3e8KsPLnWGbBMdvywp6sPlfZ3iwr"},
    {"player_id": "PMJDQNNjcUGwB1zFa7gmOccepBDq"},
    {"player_id": "jX6vzhEGdaVhgYsrtpX3AgAQxOOW"},
    {"player_id": "ONSm7j4CrpFGUKjWUvxpmvAPvt55"},
    {"player_id": "LNmItELQHMJkpwagKNa6ev44UmLd"},
    {"player_id": "lDQjbL4M6f47NtjWsM1clWtlH0dQ"},
    {"player_id": "YAfE5fsF4tEeTxiqD7syZxIv3G2x"},
    {"player_id": "BJw4fxytlnQTCxquBX5psPIfMt3K"},
    {"player_id": "IcYEucZP6I5xDDD7Jffp0QrWtIaO"},
]

# =====================================================================
# [상단 고정 영역 2] 기본 URL, 웹훅 및 웹샵 버튼 선택자
# =====================================================================
URL = "https://store.eternalhero.rivvy.games/"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
MAX_CLAIMS_PER_ACCOUNT = 10  # 무료 보상 개수가 늘어나도 넉넉히 대응

SELECTORS = {
    "player_id_input": 'input[name*="player" i], input[placeholder*="ID" i], input[type="text"]',
    "free_button": 'button:has-text("Get free"):visible, button:has-text("무료로 받으세요"):visible, button:has-text("무료"):visible',
    "cart_button": '[data-testid="header-cart-button"], [aria-label="Cart"], .cart-button',
    "checkout_button": '[data-testid="cart-checkout-button"], .cart__checkout-button, button:has-text("Checkout"):visible, button:has-text("Confirm"):visible, button:has-text("확인"):visible, button:has-text("결제"):visible',
}


# =====================================================================
# [하단 실행 영역] 수령 로직
# =====================================================================
def get_accounts():
  if FIXED_ACCOUNTS:
    return FIXED_ACCOUNTS
  return json.loads(os.environ.get("ACCOUNTS", "[]"))


def send_discord(total, success, fail, items):
  if not DISCORD_WEBHOOK:
    print("디스코드 웹훅 URL이 설정되지 않았습니다.")
    return

  message = (
      f"**[Eternal Hero 보상 수령 보고]**\n"
      f"• 현황: 등록 인원 {total}명 / 완료 {success}명 (실패 {fail}명)\n"
      f"• 신규 수령: 총 {items}개 수령 완료"
  )
  requests.post(DISCORD_WEBHOOK, json={"content": message})


def apply_player_id(page, player_id):
  """페이지 내 Player ID 입력칸이 있으면 계정별로 입력"""
  inputs = page.locator(SELECTORS["player_id_input"])
  for i in range(inputs.count()):
    inp = inputs.nth(i)
    if inp.is_visible() and inp.is_editable():
      inp.fill(player_id)
      inp.press("Enter")
      time.sleep(1.5)
      break


def collect_free_items(page):
  """화면 하단까지 내리며 보이는 무료 아이템을 가능한 만큼 장바구니에 담기"""
  claimed = 0
  seen_clicks = 0

  while claimed < MAX_CLAIMS_PER_ACCOUNT and seen_clicks < 25:
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(0.7)

    free_btns = page.locator(SELECTORS["free_button"])
    count = free_btns.count()
    if count == 0:
      break

    clicked_in_pass = False
    for idx in range(count):
      btn = free_btns.nth(idx)
      if not btn.is_visible() or not btn.is_enabled():
        continue
      seen_clicks += 1
      try:
        btn.scroll_into_view_if_needed(timeout=3000)
        btn.click(timeout=3000)
        claimed += 1
        clicked_in_pass = True
        time.sleep(1)
        break
      except Exception:
        continue

    if not clicked_in_pass:
      break

  return claimed


def checkout_if_not_empty(page, claimed_count):
  """장바구니에 담긴 항목이 있을 때만 장바구니를 열고 결제/확인 진행"""
  cart_btn = page.locator(SELECTORS["cart_button"]).first
  if cart_btn.count() == 0:
    return 0

  cart_btn.click()
  time.sleep(1.2)

  # 장바구니가 비어 있음을 나타내는 문구가 보이면 결제 없이 종료
  empty_signals = page.locator(
      ':text("empty"), :text("Empty"), :text("비어"), :text("0 items"), :text("0개")'
  )
  if claimed_count == 0 and empty_signals.count() > 0:
    return 0

  checkout_btn = page.locator(SELECTORS["checkout_button"]).first
  if checkout_btn.count() == 0 or not checkout_btn.is_visible():
    return 0

  checkout_btn.click()
  time.sleep(2)
  return claimed_count


def run_one_account(page, player_id):
  page.goto(URL, wait_until="networkidle")
  time.sleep(2)

  apply_player_id(page, player_id)
  claimed = collect_free_items(page)
  final_claimed = checkout_if_not_empty(page, claimed)
  return final_claimed


def main():
  accounts = get_accounts()
  total = len(accounts)
  success = 0
  fail = 0
  total_items = 0

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for acc in accounts:
      pid = (acc.get("player_id") or acc.get("id") or "").strip()
      if not pid:
        continue
      context = browser.new_context()
      page = context.new_page()
      try:
        items = run_one_account(page, pid)
        success += 1
        total_items += items
        print(f"{pid} 성공 ({items}개)")
      except Exception as e:
        fail += 1
        print(f"{pid} 실패: {e}")
      finally:
        context.close()
    browser.close()

  send_discord(total, success, fail, total_items)


if __name__ == "__main__":
  main()
