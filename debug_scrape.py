# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.cardhobby.com.cn/market", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)

    print("=== Check search elements ===")
    kword = page.query_selector("#kword")
    print(f"#kword found: {kword is not None}")
    qbtn = page.query_selector("#qbtn")
    print(f"#qbtn found: {qbtn is not None}")

    if kword:
        page.fill("#kword", "欧文")
        if qbtn:
            page.click("#qbtn")
            time.sleep(5)

    print("\n=== Check card-info ===")
    card_info = page.query_selector_all(".card-info")
    print(f".card-info count: {len(card_info)}")

    print("\n=== Check various selectors ===")
    selectors = [
        ".card-info", ".card-item", ".card", ".item-card", ".product-card",
        ".goods-item", ".list-item", ".market-item", ".trade-item",
        "[class*=card]", "[class*=item]", "[class*=product]", "[class*=goods]",
        "[class*=list]", "[class*=market]", "[class*=trade]", "[class*=auction]",
        ".ci-row", ".ci-tile", ".price_size", ".ci-row.name", ".time",
        "button.btn-next", ".btn-next",
    ]
    for sel in selectors:
        try:
            elems = page.query_selector_all(sel)
            if len(elems) > 0:
                print(f"  {sel}: {len(elems)} elements")
        except Exception as e:
            print(f"  {sel}: ERROR - {e}")

    print("\n=== Page title ===")
    print(page.title())

    print("\n=== Page URL ===")
    print(page.url)

    html = page.content()
    print(f"\n=== Page HTML length: {len(html)} ===")

    # Save full HTML for analysis
    with open("/Users/donglin/Desktop/projects/card_env/debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Full HTML saved to debug_page.html")

    # Print relevant sections
    print("\n=== Looking for search-related elements ===")
    search_inputs = page.query_selector_all("input[type='text'], input[type='search'], input[name*='key'], input[name*='word'], input[name*='search'], input[placeholder*='搜索'], input[placeholder*='关键字']")
    for i, inp in enumerate(search_inputs):
        tag = inp.evaluate("el => el.outerHTML.substring(0, 200)")
        print(f"  Input {i}: {tag}")

    search_btns = page.query_selector_all("button[type='submit'], button[class*='search'], button[class*='btn'], input[type='submit'], a[class*='search']")
    for i, btn in enumerate(search_btns[:10]):
        tag = btn.evaluate("el => el.outerHTML.substring(0, 200)")
        print(f"  Button {i}: {tag}")

    browser.close()
