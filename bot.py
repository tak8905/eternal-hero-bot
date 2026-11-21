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


def run_one_account(page, user_id, user_pw):
    """1개 계정 작업: 로그인 -> 하단 무료 3개 담기 -> 구매 확인"""
    page.goto(URL, wait_until="networkidle")
    time.sleep(2)

    # [확인 필요 1] 로그인 절차 (실제 사이트 버튼/입력창에 맞게 수정)
    page.get_by_role("button", name="Sign In").click()
    page.fill('input[type="email"]', user_id)
    page.fill('input[type="password"]', user_pw)
    page.get_by_role("button", name="Log In").click()
    time.sleep(3)

    # [확인 필요 2] 화면 최하단 스크롤 후 무료 아이템 3개 담기
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    free_btns = page.locator('button:has-text("Free"), button:has-text("무료")')
    claimed = 0
    for i in range(min(free_btns.count(), 3)):
        free_btns.nth(i).click()
        claimed += 1
        time.sleep(1)

    # [확인 필요 3] 장바구니 열기 및 최종 확인 클릭
    page.locator('[aria-label="Cart"], .cart-button').first.click()
    time.sleep(1)
    page.get_by_role("button", name="확인").click()  # 영문일 경우 "Confirm" 등
    time.sleep(2)

    return claimed


def main():
    total = len(ACCOUNTS)
    success = 0
    fail = 0
    total_items = 0

    with sync_playwright() as p:
        # GitHub 서버에서는 화면 창이 없으므로 반드시 True로 실행합니다.
        browser = p.chromium.launch(headless=True)

        for acc in ACCOUNTS:
            context = browser.new_context()
            page = context.new_page()
            try:
                items = run_one_account(page, acc["id"], acc["pw"])
                success += 1
                total_items += items
                print(f"[{acc['id']}] 성공 ({items}개)")
            except Exception as e:
                fail += 1
                print(f"[{acc['id']}] 실패: {e}")
            finally:
                context.close()

        browser.close()

    send_discord(total, success, fail, total_items)


if __name__ == "__main__":
    main()
