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


def run_one_account(page, player_id):
    """1개 Player ID 작업: 로그인 -> 하단 무료 3개 담기 -> 장바구니 확인"""
    player_id = str(player_id).strip()
    step = "페이지 접속"
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)

    # 1단계: 로그인 열기 버튼(있을 경우) 및 Player ID 입력/제출
    step = "1단계(Player ID 입력 및 로그인)"
    open_login_btn = page.locator(
        'button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")'
    )
    id_box = page.locator(
        'input[placeholder*="Player ID" i], input[placeholder*="ID" i], input[type="text"], input'
    )
    if open_login_btn.count() > 0 and (id_box.count() == 0 or not id_box.first.is_visible()):
        open_login_btn.first.click(timeout=8000)
        time.sleep(1)

    id_input = id_box.first
    id_input.wait_for(state="visible", timeout=8000)
    id_input.click(timeout=8000)
    id_input.fill(player_id)
    time.sleep(0.5)

    submit_btn = page.locator(
        'button[type="submit"], button:has-text("Log in"), button:has-text("Login"), button:has-text("Confirm"), button:has-text("Continue")'
    ).first
    submit_btn.click(timeout=8000)
    time.sleep(2.5)

    # 2단계: 화면 최하단 스크롤 후 무료 아이템 최대 3개 클릭
    step = "2단계(무료 아이템 클릭)"
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1.5)

    free_btns = page.locator(
        'button:has-text("Get free"), button:has-text("Free"), button:has-text("무료")'
    )
    free_count = free_btns.count()
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
        '[aria-label*="Cart" i], .cart-button, button:has-text("Cart")'
    ).first
    cart_btn.click(timeout=8000)
    time.sleep(1)

    confirm_btn = page.locator(
        'button:has-text("Confirm"), button:has-text("Checkout"), button:has-text("Claim"), button:has-text("확인")'
    ).first
    confirm_btn.click(timeout=8000)
    time.sleep(1.5)

    return claimed


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
