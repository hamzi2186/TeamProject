from collections.abc import Awaitable, Callable

from app.services.ssrf import validate_public_url


class RenderingError(RuntimeError):
    pass


async def render_page(
    url: str,
    *,
    validator: Callable[[str], Awaitable[list[str]]] = validate_public_url,
    timeout_seconds: float = 20,
) -> str:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RenderingError("Playwright is not installed") from exc

    await validator(url)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(java_script_enabled=True)
        page = await context.new_page()

        async def guard(route) -> None:
            request_url = route.request.url
            if route.request.resource_type in {"image", "media", "font"}:
                await route.abort()
                return
            try:
                await validator(request_url)
            except Exception:
                await route.abort()
                return
            await route.continue_()

        await page.route("**/*", guard)
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(timeout_seconds * 1000),
            )
            await page.wait_for_timeout(750)
            return await page.content()
        except Exception as exc:
            raise RenderingError("JavaScript rendering failed") from exc
        finally:
            await context.close()
            await browser.close()
