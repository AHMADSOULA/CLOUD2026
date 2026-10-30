"""
automation/console.py
كل خطوات Google Cloud Console — بلا تصوير عادي
"""
import asyncio
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, context, sender=None, user_tag=None):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"

    async def _shot(self, page, caption: str = ""):
        """screenshot + send (غير عند الفشل)"""
        if not self.sender:
            return
        try:
            path = f"/tmp/shot_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=20000, animations="disabled")
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=caption[:1000])
                    log.info(f"📸 {caption}")
                except Exception as e:
                    log.warning(f"⚠️ reply_photo: {e}")
            import os
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ _shot: {e}")

    # ═══════════════════════════════════════
    # STEP 1
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1")
        await self._shot(page, "📸 الخطوة 2: صفحة Welcome قبل الضغط")

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(1000)

        # The Google welcome page may show a circular down-arrow control.
        # Click a visible scroll/down control if one is present.
        try:
            clicked = await page.evaluate("""
                () => {
                    const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                    const els = Array.from(document.querySelectorAll('button, [role="button"], a'));
                    for (const el of els) {
                        if (!visible(el) || el.disabled) continue;
                        const label = [el.innerText, el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-tooltip')]
                            .filter(Boolean).join(' ').toLowerCase();
                        const svg = el.querySelector('svg');
                        const icon = svg ? ((svg.getAttribute('aria-label') || '') + ' ' + (svg.innerHTML || '')).toLowerCase() : '';
                        const r = el.getBoundingClientRect();
                        const nearBottom = r.top > window.innerHeight * 0.45;
                        const downLabel = /scroll down|more|down|next|continue|read more/.test(label);
                        const downIcon = /arrow_downward|keyboard_arrow_down|expand_more|chevron_down/.test(icon);
                        if ((downLabel || downIcon) && nearBottom) {
                            el.click();
                            return {clicked: true, label: label.slice(0, 80), x: Math.round(r.x), y: Math.round(r.y)};
                        }
                    }
                    return {clicked: false};
                }
            """)
            if clicked and clicked.get("clicked"):
                log.info("✅ ضغط سهم النزول/التالي: %s", clicked.get("label", "button"))
                await page.wait_for_timeout(900)
                await self._shot(page, "📸 الخطوة 2: بعد الضغط على سهم النزول")
        except Exception as e:
            log.warning("⚠️ تعذر الضغط على سهم النزول: %s", str(e)[:150])

        # Also scroll the document and any internal scrollable panel to the bottom.
        try:
            await page.evaluate("""
                () => {
                    window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'});
                    const all = Array.from(document.querySelectorAll('body *'));
                    for (const el of all) {
                        const st = getComputedStyle(el);
                        if (/(auto|scroll)/.test(st.overflowY) && el.scrollHeight > el.clientHeight + 30) {
                            el.scrollTop = el.scrollHeight;
                        }
                    }
                }
            """)
            await page.keyboard.press("End")
            await page.wait_for_timeout(800)
            await self._shot(page, "📸 الخطوة 2: أسفل صفحة Welcome")
        except Exception as e:
            log.warning("⚠️ scroll: %s", str(e)[:150])

        # Click only an enabled, visible standard action button.
        for label in ["Next", "Continue", "I understand", "Agree and continue"]:
            try:
                button = page.get_by_role("button", name=label, exact=True).first
                if await button.is_visible(timeout=700) and await button.is_enabled():
                    await button.click(timeout=4000)
                    log.info("✅ تم الضغط على %s", label)
                    await page.wait_for_timeout(1000)
                    await self._shot(page, f"📸 بعد الضغط على {label}")
                    return
            except Exception:
                continue

        log.info("ℹ️ ما لقيتش زر Next ظاهر في هذه الصفحة")
        await self._shot(page, "📸 صفحة Welcome بعد محاولة النزول")

    # ═══════════════════════════════════════
    # STEP 2
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        """
        Google Cloud UI can vary by session. Treat the consent dialog as optional:
        click it only when it is actually visible; never force-enable a disabled
        button. Save a short diagnostic when the expected button is absent.
        """
        log.info("🚀 step2")

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass

        # Search common button labels without assuming the dialog always appears.
        button = None
        labels = [
            "Agree and continue",
            "Agree",
            "Accept",
            "Continue",
            "I agree",
        ]
        for label in labels:
            try:
                candidate = page.get_by_role("button", name=re.compile(
                    r"^\\s*" + re.escape(label) + r"\\s*$", re.I
                )).first
                if await candidate.is_visible(timeout=700):
                    button = candidate
                    log.info("✅ Consent button visible: %s", label)
                    break
            except Exception:
                continue

        if button is None:
            # The consent page may not be part of this session's flow.
            try:
                title = (await page.title())[:120]
                url = page.url[:250]
                body = await page.locator("body").inner_text(timeout=2000)
                body = " ".join(body.split())[:350]
                log.info(
                    "ℹ️ No consent button visible; continuing. title=%r url=%r body=%r",
                    title, url, body
                )
            except Exception:
                log.info("ℹ️ No consent dialog detected; continuing.")
            return False

        # If visible consent checkboxes are present, select them normally.
        # Do not click hidden controls or bypass disabled-state checks.
        try:
            checkboxes = page.get_by_role("checkbox")
            count = await checkboxes.count()
            for idx in range(min(count, 2)):
                item = checkboxes.nth(idx)
                try:
                    if await item.is_visible() and not await item.is_checked():
                        await item.click(timeout=1500)
                        await page.wait_for_timeout(250)
                except Exception:
                    continue
        except Exception:
            pass

        try:
            if await button.is_enabled():
                await button.click(timeout=5000)
                await page.wait_for_timeout(1200)
                log.info("✅ Consent accepted")
                return True
            log.warning("⚠️ Consent button is disabled; leaving page unchanged.")
            return False
        except Exception as exc:
            log.warning("⚠️ Could not click consent button: %s", str(exc)[:180])
            return False

    # ═══════════════════════════════════════
    # STEP 3
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        log.info("🚀 step3")

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        await page.goto(api_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        try:
            if "accounts.google.com" in page.url.lower():
                log.warning("⚠️ sign in — نتجاوزو")
                return
        except Exception:
            pass

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        try:
            await expect(enable_btn.or_(manage_btn)).to_be_visible(timeout=10000)
            if await enable_btn.is_visible():
                await enable_btn.click()
                try:
                    await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=45000)
                except Exception:
                    pass
            elif await manage_btn.is_visible():
                log.info("ℹ️ API مفعّل")
        except Exception as e:
            log.warning(f"⚠️ step3: {e}")

    # ═══════════════════════════════════════
    # STEP 4 — مع region
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image, region="us-central1"):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}&region={region}"
        )
        log.info(f"🌐 step4 — region={region}")

        await page.goto(run_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        image_found = False
        try:
            label = page.get_by_text("Container Image URL").first
            await label.click(timeout=10000)
            image_found = True
        except Exception:
            try:
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('*')) {
                            const t = (el.innerText || '').trim();
                            if (t.includes('Container Image URL') && t.length < 100) {
                                try { el.click(); return 'ok'; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if clicked:
                    image_found = True
            except Exception:
                pass

        if not image_found:
            try:
                inp = page.locator('input[type="text"]').first
                await inp.click(timeout=5000)
            except Exception as e:
                raise RuntimeError(f"فشل حقل: {e}")

        await page.wait_for_timeout(500)
        await page.keyboard.type(image, delay=30)

        await page.wait_for_timeout(2000)

        try:
            await page.get_by_role("radio", name="Allow public access").click(timeout=8000)
        except Exception:
            pass
        try:
            await page.get_by_role("radio", name="Instance-based").click(timeout=8000)
        except Exception:
            pass
        try:
            await page.get_by_role("button", name="Hide").click(timeout=1500)
        except Exception:
            pass

        await page.keyboard.press("End")
        await page.wait_for_timeout(800)

        try:
            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True, timeout=8000)
            log.info("✅ Create")
        except Exception as e:
            try:
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === 'create' || t === 'deploy') {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if not clicked:
                    raise RuntimeError(f"فشل Create: {e}")
            except Exception as e2:
                raise RuntimeError(f"فشل Create: {e2}")

    # ═══════════════════════════════════════
    # STEP 5
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5")

        link_locator = page.locator('a[href*="run.app"]')
        try:
            await link_locator.wait_for(state="visible", timeout=60000)
            final_url = await link_locator.get_attribute("href")
            return final_url
        except Exception:
            pass

        for i in range(30):
            try:
                url = await page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a');
                        for (const a of links) {
                            const href = a.href || '';
                            if (href.includes('.run.app')) return href.split('?')[0].split('#')[0];
                        }
                        const body = document.body.innerText || '';
                        const m = body.match(/https:\\/\\/[a-zA-Z0-9\\-]+\\.run\\.app/);
                        if (m) return m[0];
                        return null;
                    }
                """)
                if url:
                    return url
            except Exception:
                pass
            await page.wait_for_timeout(3000)

        raise RuntimeError("ما لقيناش رابط run.app")
