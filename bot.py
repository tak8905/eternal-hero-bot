import json
import os
import time
from playwright.sync_api import sync_playwright
import requests

# =====================================================================
# [상단 고정 영역 1] 유저 목록 (총 17명 / 새 유저가 생기면 여기에 한 줄씩 추가)
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
# (웹샵 버튼이 바뀌거나 추가되면 아래 선택자만 수정)
# =====================================================================
URL = "https://store.eternalhero.rivvy.games/"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
MAX_CLAIMS_PER_ACCOUNT = 6

SELECTORS = {
    "free_button": 'button:has-text("Get free"):visible',
    "cart_button": '[data-testid="header-cart-button"], [aria-label="Cart"], .cart-button',
    "checkout_button": '[data-testid="cart-checkout-button"], .cart__checkout-button',
}


# =====================================================================
# [하단 실행 영역] 실제 수령 로직 (웹샵 구조 변경 시 이 아래는 가급적 유지)
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


def run_one_account(page, player_id):
  page.goto(URL, wait_until="networkidle")
  time.sleep(2)

  # 무료 버튼 클릭 (옆에 새 박스가 생겨도 항상 첫 번째 활성 버튼 기준)
  claimed = 0
  while claimed < MAX_CLAIMS_PER_ACCOUNT:
    free_btns = page.locator(SELECTORS["free_button"])
    if free_btns.count() == 0:
      break
    free_btns.first.click()
    claimed += 1
    time.sleep(1)

  if claimed > 0:
    page.locator(SELECTORS["cart_button"]).first.click()
    time.sleep(1)
    page.locator(SELECTORS["checkout_button"]).first.click()
    time.sleep(2)

  return claimed


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
