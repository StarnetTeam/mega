import asyncio
import sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def scrape_mycima():
    async with async_playwright() as p:
        # تشغيل المتصفح بإعدادات تجعل الكشف أصعب
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()

        print("[*] جاري الدخول إلى ماي سيما...")
        try:
            # التوجه للموقع والانتظار لتجاوز حماية Cloudflare تلقائياً
            await page.goto("https://mycima.gripe/", wait_until="networkidle", timeout=60000)
            
            # انتظار إضافي للتأكد من تجاوز صفحة "Just a moment"
            await page.wait_for_timeout(5000) 
            
            if "Just a moment" in await page.title():
                print("[!] صفحة الحماية لا تزال تظهر، جاري الانتظار لفترة أطول...")
                await page.wait_for_timeout(10000)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # البحث عن العناصر في الصفحة الرئيسية
            items = soup.select('div.GridItem')
            if not items:
                print("[!] لم يتم العثور على أي محتوى. قد يكون هناك حظر أو تغيير في هيكل الموقع.")
                await browser.close()
                return

            print(f"[+] تم العثور على {len(items)} عنصر جديد.")
            print("-" * 30)

            results = []

            # معالجة أول 5 عناصر كمثال
            for item in items[:5]:
                title_tag = item.select_one('div.Thumb--GridItem a')
                if not title_tag: continue
                
                name = title_tag.get('title', '').strip()
                detail_url = title_tag.get('href', '')

                # فتح صفحة التفاصيل في تبويب جديد
                detail_page = await context.new_page()
                try:
                    await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                    detail_soup = BeautifulSoup(await detail_page.content(), 'html.parser')
                    
                    # جلب الجودة
                    quality = "غير محددة"
                    q_tag = detail_soup.select_one('a[href*="/quality/"]')
                    if q_tag: quality = q_tag.text.strip()
                    
                    # جلب رابط التحميل 720p
                    download_link = "غير متوفر"
                    d_tags = detail_soup.find_all('a', href=True)
                    for d in d_tags:
                        text = d.text.lower()
                        if "720p" in text and ("تحميل" in text or "download" in text):
                            download_link = d['href']
                            break
                    
                    print(f"DONE: {name}")
                    results.append([name, quality, download_link])
                except Exception as e:
                    print(f"[!] خطأ في جلب {name}: {e}")
                finally:
                    await detail_page.close()

            # عرض النتائج النهائية
            print("\n" + "="*80)
            print(f"{'اسم المحتوى':<45} | {'الجودة':<15} | {'رابط التحميل 720p'}")
            print("="*80)
            for res in results:
                print(f"{res[0][:45]:<45} | {res[1]:<15} | {res[2]}")
            
        except Exception as e:
            print(f"[!] حدث خطأ غير متوقع: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(scrape_mycima())
