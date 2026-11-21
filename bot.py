import json
import os
import time
from playwright.sync_api import sync_playwright
import requests

URL = "https://store.eternalhero.rivvy.games/"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
ACCOUNTS = json.loads(os.environ.get("ACCOUNTS", "[]"))


def send_discord(total, success, fail, items):
    """디스코드 웹훅으로 수령 결과 보고"""
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
    """1개 Player ID 작업: Player ID 로그인 -> 하단 무료 아이템 담기 -> 장바구니 확인"""
    page.goto(URL, wait_until="networkidle")
    time.sleep(2)

    # 1. Player ID 입력 및 로그인 버튼 클릭 (실제 입력창/버튼에 맞게 미세 조정 가능)
    id_input = page.locator('input[placeholder*="Player ID" i], input[type="text"], input').first
    id_input.fill(player_id)
    page.get_by_role("button", name="Log in").click()
    time.sleep(3)

    # 2. 화면 최하단 스크롤 후 무료 아이템(예: Get free / Free) 클릭
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    free_btns = page.locator('button:has-text("Get free"), button:has-text("Free"), button:has-text("무료")')
    claimed = 0
    for i in range(min(free_btns.count(), 3)):
        free_btns.nth(i).click()
        claimed += 1
        time.sleep(1)

    # 3. 장바구니 열기 및 최종 확인 클릭
    page.locator('[aria-label="Cart"], .cart-button, button:has-text("Cart")').first.click()
    time.sleep(1)
    page.get_by_role("button", name="Confirm").click()
    time.sleep(2)

    return claimed


def main():
    total = len(ACCOUNTS)
    success = 0
    fail = 0
    total_items = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for acc in ACCOUNTS:
            pid = acc.get("player_id") or acc.get("id")
            context = browser.new_context()
            page = context.new_page()
            try:
                items = run_one_account(page, pid)
                success += 1
                total_items += items
                print(f"[{pid}] 성공 ({items}개)")
            except Exception as e:
                fail += 1
                print(f"[{pid}] 실패: {e}")
            finally:
                context.close()

        browser.close()

    send_discord(total, success, fail, total_items)


if __name__ == "__main__":
    main()
