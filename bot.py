Python
import json
import os
import time
from playwright.sync_api import sync_playwright
import requests

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

URL = "https://store.eternalhero.rivvy.games/"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
MAX_CLAIMS_PER_ACCOUNT = 10

SELECTORS = {
    "logged_in_badge": (
        '[data-testid="user-account"]:visible, [data-testid="header-logout-button"]:visible'
    ),
    "open_login_trigger": (
        'button:has-text("Log in"):visible, button:has-text("Login"):visible, '
        'button:has-text("로그인"):visible, [data-testid*="login" i]:visible'
    ),
    "player_id_input": (
        'input[name*="player" i], input[placeholder*="player" i], '
        'input[placeholder*="id" i], input[type="text"]'
    ),
    "login_submit": (
        'button:has-text("Log in"):visible, button:has-text("Login"):visible, '
        'button:has-text("Continue"):visible, button:has-text("Confirm"):visible, '
        'button:has-text("로그인"):visible, button:has-text("확인"):visible, button[type="submit"]:visible'
    ),
    "free_button": (
        '[data-testid="free-button"]:visible, '
        ':is(button, a, div[role="button"]):has-text("Get free"):visible, '
        ':is(button, a, div[role="button"]):has-text("무료로 받으세요"):visible, '
        ':is(button, a, div[role="button"]):has-text("무료"):visible'
    ),
    "cart_button": (
        '[data-testid="header-cart-button"]:visible, [aria-label*="cart" i]:visible, .cart-button:visible'
    ),
    "checkout_button": (
        '[data-testid="cart-checkout-button"]:visible, .cart__checkout-button:visible, '
        'button:has-text("Checkout"):visible, button:has-text("Confirm"):visible, '
        'button:has-text("확인"):visible, button:has-text("결제"):visible'
    ),
}


def get_accounts():
  if FIXED_ACCOUNTS:
    return FIXED_ACCOUNTS
  return json.loads(os.environ.get("ACCOUNTS", "[]"))


def send_discord(total, success, fail, items):
  if not DISCORD_WEBHOOK:
    return
  message = (
      f"**[Eternal Hero 보상 수령 보고]**\n"
      f"• 현황: 등록 인원 {total}명 / 완료 {success}명 (실패 {fail}명)\n"
      f"• 신규 수령: 총 {items}개 수령 완료"
  )
  requests.post(DISCORD_WEBHOOK, json={"content": message})


def is_logged_in(page):
  return page.locator(SELECTORS["logged_in_badge"]).count() > 0


def apply_player_id(page, player_id):
  if is_logged_in(page):
    return "이미로그인"

  # 로그인 창/모달을 여는 버튼이 먼저 필요한 경우 시도
  inputs = page.locator(SELECTORS["player_id_input"])
  has_visible_input = any(
      inputs.nth(i).is_visible() and inputs.nth(i).is_editable()
      for i in range(inputs.count())
  )
  if not has_visible_input:
    triggers = page.locator(SELECTORS["open_login_trigger"])
    for t in range(triggers.count()):
      tbtn = triggers.nth(t)
      if tbtn.is_visible() and tbtn.is_enabled():
        try:
          tbtn.click(timeout=2500)
          time.sleep(1.0)
          break
        except Exception:
          continue

  inputs = page.locator(SELECTORS["player_id_input"])
  for i in range(inputs.count()):
    inp = inputs.nth(i)
    if inp.is_visible() and inp.is_editable():
      inp.click()
      inp.fill(player_id)
      inp.press("Enter")
      time.sleep(1.2)
      break

  submit_btns = page.locator(SELECTORS["login_submit"])
  for j in range(submit_btns.count()):
    btn = submit_btns.nth(j)
    if btn.is_visible() and btn.is_enabled():
      try:
        btn.click(timeout=2500)
        time.sleep(1.5)
        break
      except Exception:
        continue

  return "로그인확인" if is_logged_in(page) else "미로그인상태"


def debug_page_hints(page):
  """담기:0일 때 화면에 어떤 버튼/테스트ID가 있는지 짧게 출력"""
  info = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, [role="button"], a')).slice(0, 12);
        return btns.map(el => ({
            text: (el.innerText || '').trim().slice(0, 20),
            testid: el.getAttribute('data-testid') || ''
        }));
    }""")
  return str(info)


def collect_free_items(page):
  claimed = 0
  seen_clicks = 0

  while claimed < MAX_CLAIMS_PER_ACCOUNT and seen_clicks < 25:
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(0.8)

    free_btns = page.locator(SELECTORS["free_button"])
    count = free_btns.count()
    if count == 0:
      break

    clicked_in_pass = False
    for idx in range(count):
      btn = free_btns.nth(idx)
      if not btn.is_visible() or not btn.is_enabled():
        continue
      txt = (btn.inner_text() or "").strip().lower()
      if any(k in txt for k in ("owned", "claimed", "수령 완료", "완료")):
        continue

      seen_clicks += 1
      try:
        btn.scroll_into_view_if_needed(timeout=3000)
        btn.click(timeout=3000)
        claimed += 1
        clicked_in_pass = True
        time.sleep(1.0)
        break
      except Exception:
        continue

    if not clicked_in_pass:
      break

  return claimed


def checkout_if_not_empty(page, claimed_count):
  if claimed_count == 0:
    return 0, "결제버튼없음"

  cart_btns = page.locator(SELECTORS["cart_button"])
  if cart_btns.count() == 0:
    return 0, "장바구니버튼없음"

  try:
    cbtn = cart_btns.first
    cbtn.scroll_into_view_if_needed(timeout=3000)
    cbtn.click(timeout=3000)
    time.sleep(1.5)
  except Exception:
    return 0, "장바구니클릭실패"

  checkout_btns = page.locator(SELECTORS["checkout_button"])
  for j in range(checkout_btns.count()):
    kbtn = checkout_btns.nth(j)
    if kbtn.is_visible() and kbtn.is_enabled():
      try:
        kbtn.click(timeout=3000)
        time.sleep(2.0)
        return claimed_count, "결제완료"
      except Exception:
        continue

  return 0, "결제버튼없음"


def run_one_account(page, player_id):
  page.goto(URL, wait_until="domcontentloaded", timeout=30000)
  page.wait_for_load_state("networkidle", timeout=15000)
  time.sleep(2)

  login_state = apply_player_id(page, player_id)
  claimed = collect_free_items(page)
  final_claimed, status_note = checkout_if_not_empty(page, claimed)
  extra = ""
  if claimed == 0:
    extra = f" | {login_state} | 힌트: {debug_page_hints(page)}"
  return final_claimed, f"담기:{claimed}, {status_note}{extra}"


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
      context = browser.new_context(viewport={"width": 1440, "height": 900})
      page = context.new_page()
      try:
        items, detail = run_one_account(page, pid)
        success += 1
        total_items += items
        print(f"{pid} 성공 ({items}개) [{detail}]")
      except Exception as e:
        fail += 1
        print(f"{pid} 실패: {e}")
      finally:
        context.close()
    browser.close()

  send_discord(total, success, fail, total_items)


if __name__ == "__main__":
  main()
