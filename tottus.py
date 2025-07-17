import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json

async def get_next_data_json():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-CL"
        )
        page = await context.new_page()
        await page.goto("https://www.tottus.cl/tottus-cl", timeout=60000)
        await page.wait_for_load_state("networkidle")
        html = await page.content()
        await browser.close()

        # Extraer el JSON del script
        soup = BeautifulSoup(html, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
        if script_tag:
            data_json = json.loads(script_tag.string)
            # Guarda el JSON en un archivo para usarlo en Jupyter
            with open("tottus_next_data.json", "w", encoding="utf-8") as f:
                json.dump(data_json, f, ensure_ascii=False, indent=2)
            print("JSON guardado en tottus_next_data.json")
        else:
            print("No se encontró el script __NEXT_DATA__")

if __name__ == "__main__":
    asyncio.run(get_next_data_json())