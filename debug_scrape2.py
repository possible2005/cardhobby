# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.cardhobby.com.cn/market", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    page.wait_for_selector("#kword", timeout=15000)
    page.fill("#kword", "欧文")
    page.click("#qbtn")
    time.sleep(5)

    try:
        page.wait_for_selector(".card-info", timeout=15000)
        time.sleep(3)
    except:
        print("ERROR: .card-info not found after search!")
        browser.close()
        exit()

    card_elements = page.query_selector_all(".card-info")
    print(f"Total cards found: {len(card_elements)}")

    for i, card in enumerate(card_elements[:5]):
        print(f"\n=== Card {i+1} ===")
        
        title_elem = card.query_selector(".ci-row.ci-tile a")
        if title_elem:
            title = title_elem.get_attribute("title")
            href = title_elem.get_attribute("href")
            inner_text = title_elem.inner_text()
            print(f"  Title attr: {title}")
            print(f"  Href: {href}")
            print(f"  Inner text: {inner_text}")
        else:
            print("  Title elem NOT FOUND")
            # Try alternative selectors
            all_links = card.query_selector_all("a")
            print(f"  All links in card: {len(all_links)}")
            for j, link in enumerate(all_links[:3]):
                print(f"    Link {j}: href={link.get_attribute('href')}, text={link.inner_text()[:80]}")

        price_elem = card.query_selector(".ci-row.price.titletext.price_size")
        if price_elem:
            price_text = price_elem.inner_text()
            print(f"  Price raw: '{price_text}'")
        else:
            print("  Price elem NOT FOUND (.ci-row.price.titletext.price_size)")
            # Try alternatives
            price_alts = card.query_selector_all("[class*=price]")
            for j, pa in enumerate(price_alts[:3]):
                print(f"    Alt price {j}: class={pa.get_attribute('class')}, text={pa.inner_text()}")

        seller_elem = card.query_selector(".ci-row.name")
        if seller_elem:
            seller = seller_elem.inner_text()
            print(f"  Seller: {seller}")
        else:
            print("  Seller elem NOT FOUND")

        time_elem = card.query_selector(".time")
        if time_elem:
            end_time = time_elem.inner_text()
            print(f"  End time: {end_time}")
        else:
            print("  Time elem NOT FOUND")

    # Check pagination
    print("\n=== Pagination ===")
    next_button = page.query_selector("button.btn-next")
    if next_button:
        is_disabled = next_button.get_attribute("disabled") is not None or "disabled" in (next_button.get_attribute("class") or "")
        print(f"  Next button found, disabled: {is_disabled}")
        btn_html = next_button.evaluate("el => el.outerHTML")
        print(f"  Button HTML: {btn_html[:200]}")
    else:
        print("  Next button NOT FOUND")

    browser.close()
