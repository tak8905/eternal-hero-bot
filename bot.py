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
    {"player_id": "Q6Sm1JxFUvTBse6EAsJr9wvdYeE2"},
    
]

# =====================================================================
# [상단 고정 영역 2] 기본 URL, 웹훅 및 웹샵 버튼 선택자
# (웹샵 버튼이 바뀌거나 추가되면 아래 선택자만 수정)
# =====================================================================
URL = "https://store.eternalhero.rivvy.games/"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
MAX_CLAIMS_PER_ACCOUNT = 6

SELECTORS = {
    "center_id_input": (
        'input[placeholder*="Enter your player id" i],'
        ' input[placeholder*="Enter Player ID" i],'
        ' input[placeholder*="플레이어 ID" i], input.fast-login__input'
    ),
    "modal_id_input": (
        'input[placeholder*="Enter Player ID Here" i],'
        ' .user-id-modal input, [data-id="user-id-modal"] input,'
        ' .user-id-modal input[type="password"]'
    ),
    "top_login_button": (
        'header button:has-text("Log in"), header button:has-text("로그인"),'
        ' button:has-text("Log in")'
    ),
    "login_submit": (
        'button:has-text("Log in"):visible, button:has-text("로그인"):visible,'
        ' button[type="submit"]:visible'
    ),
    "user_account": (
        '[data-testid="user-account"], [data-testid*="user" i],'
        ' [data-testid*="account" i], [data-testid*="logout" i],'
        ' button:has-text("Log out"), button:has-text("로그아웃")'
    ),
    "free_cart_button": (
        'button[data-testid^="add-to-cart-store-button-free"]:visible,'
        ' button[data-sku^="free"][aria-label*="cart" i]:visible'
    ),
    "free_button": (
        'button[data-testid="free-button"]:visible,'
        ' button:has-text("Get free"):visible'
    ),
    "cart_button": (
        '[data-testid="header-cart-button"], button[aria-label="Header cart'
        ' button"], button[aria-label="헤더 장바구니 버튼"], .cart-button'
    ),
    "checkout_button": (
        '[data-testid="cart-checkout-button"], .cart__checkout-button'
    ),
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
  resp = requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=15)
  print(f"디스코드 전송 상태코드: {resp.status_code}")


def clear_blockers(page, hide_user_modal=True):
  """GDPR 팝업 및 불필요한 모달이 포인터 이벤트를 가로막지 않도록 정리"""
  try:
    page.evaluate(
        """(hideModal) => {
            const gdpr = document.querySelectorAll('#gdpr-consent-form, .gdpr-container');
            gdpr.forEach((el) => {
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('pointer-events', 'none', 'important');
            });
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


def click_fast(locator, timeout=7000):
  locator.scroll_into_view_if_needed(timeout=timeout)
  try:
    locator.click(timeout=timeout)
  except Exception:
    locator.evaluate("el => el.click()")


def is_logged_in(page):
  """로그인 계정 요소 노출 여부 또는 상단 Log in 버튼 소멸 여부로 확인"""
  acc_loc = page.locator(SELECTORS["user_account"])
  if acc_loc.count() > 0:
    for i in range(acc_loc.count()):
      if acc_loc.nth(i).is_visible():
        return True

  # 상단 헤더에 Log in 버튼이 사라졌고 ID 입력창도 안 보이면 로그인 상태로 간주
  header_login = page.locator('header button:has-text("Log in")')
  center_input = page.locator(SELECTORS["center_id_input"]).first
  header_login_hidden = header_login.count() == 0 or not header_login.first.is_visible()
  center_input_hidden = center_input.count() == 0 or not center_input.is_visible()
  return header_login_hidden and center_input_hidden


def login_with_both_paths(page, player_id):
  """1순위: 가운데 입력창 로그인 -> 실패/미표시 시 2순위: 오른쪽 상단 Log in 모달 로그인"""
  clear_blockers(page, hide_user_modal=False)

  # [경로 1] 화면 가운데 "Enter your player id..." 박스 시도
  center_input = page.locator(SELECTORS["center_id_input"]).first
  if center_input.count() > 0 and center_input.is_visible():
    center_input.fill(player_id)
    time.sleep(0.3)
    center_submit = page.locator(SELECTORS["login_submit"]).last
    click_fast(center_submit, timeout=6000)
    time.sleep(2)
    if is_logged_in(page):
      return

  # [경로 2] 오른쪽 상단 "Log in" 클릭 -> "Enter Player ID Here" 모달 시도
  clear_blockers(page, hide_user_modal=False)
  modal_input = page.locator(SELECTORS["modal_id_input"]).first
  if modal_input.count() == 0 or not modal_input.is_visible():
    top_btn = page.locator(SELECTORS["top_login_button"]).first
    if top_btn.count() > 0 and top_btn.is_visible():
      click_fast(top_btn, timeout=6000)
      time.sleep(1)

  modal_input = page.locator(SELECTORS["modal_id_input"]).first
  if modal_input.count() > 0 and modal_input.is_visible():
    modal_input.fill(player_id)
    time.sleep(0.3)
    modal_submit = page.locator(
        '.user-id-modal button:has-text("Log in"),'
        ' [data-id="user-id-modal"] button:has-text("Log in"),'
        ' button:has-text("Log in"):visible'
    ).first
    click_fast(modal_submit, timeout=6000)
    time.sleep(2)

  if not is_logged_in(page):
    raise RuntimeError("로그인 실패(Player ID 반영 안 됨)")


def run_one_account(page, player_id):
  page.set_default_timeout(8000)
  page.goto(URL, wait_until="domcontentloaded", timeout=25000)
  time.sleep(1.5)

  # 1단계: 두 가지 로그인 경로로 Player ID 로그인
  login_with_both_paths(page, player_id)
  clear_blockers(page, hide_user_modal=True)

  # 2단계: 화면 하단 무료 상품 영역으로 스크롤 후 수령/담기
  page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
  time.sleep(1.5)
  clear_blockers(page, hide_user_modal=True)

  claimed = 0
  while claimed < MAX_CLAIMS_PER_ACCOUNT:
    clear_blockers(page, hide_user_modal=True)
    cart_add_btns = page.locator(SELECTORS["free_cart_button"])
    if cart_add_btns.count() > 0:
      click_fast(cart_add_btns.first, timeout=7000)
      claimed += 1
      time.sleep(0.8)
      continue

    free_btns = page.locator(SELECTORS["free_button"])
    if free_btns.count() > 0:
      click_fast(free_btns.first, timeout=7000)
      claimed += 1
      time.sleep(0.8)
      continue

    break

  # 3단계: 장바구니 열기 및 확인 버튼 클릭
  if claimed > 0:
    clear_blockers(page, hide_user_modal=True)
    cart_loc = page.locator(SELECTORS["cart_button"]).first
    if cart_loc.count() > 0 and cart_loc.is_visible():
      click_fast(cart_loc, timeout=7000)
      time.sleep(1)

    checkout_loc = page.locator(SELECTORS["checkout_button"]).first
    if checkout_loc.count() > 0 and checkout_loc.is_visible():
      click_fast(checkout_loc, timeout=7000)
      time.sleep(1.5)

  return claimed


def main():
  accounts = get_accounts()
  total = len(accounts)
  success = 0
  fail = 0
  total_items = 0

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for idx, acc in enumerate(accounts, start=1):
      pid = (acc.get("player_id") or acc.get("id") or "").strip()
      if not pid:
        continue
      context = browser.new_context(viewport={"width": 1440, "height": 900})
      page = context.new_page()
      try:
        items = run_one_account(page, pid)
        success += 1
        total_items += items
        print(f"[{idx}/{total}] {pid} 성공 ({items}개)")
      except Exception as e:
        fail += 1
        short_err = str(e).splitlines()[0] if str(e) else "오류"
        print(f"[{idx}/{total}] {pid} 실패: {short_err}")
      finally:
        context.close()
    browser.close()

  send_discord(total, success, fail, total_items)


if __name__ == "__main__":
  main()
