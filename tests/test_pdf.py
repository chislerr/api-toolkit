import pytest

from apis.pdf import service as pdf_service


class FakePage:
    def __init__(self):
        self.goto_url = None
        self.content_html = None
        self.pdf_kwargs = None
        self.media = None
        self.route_handler = None

    async def route(self, pattern, handler):
        self.route_handler = handler

    async def goto(self, url, wait_until, timeout):
        self.goto_url = (url, wait_until, timeout)

    async def set_content(self, html, wait_until, timeout):
        self.content_html = (html, wait_until, timeout)

    async def wait_for_load_state(self, state, timeout):
        return None

    async def emulate_media(self, media):
        self.media = media

    async def pdf(self, **kwargs):
        self.pdf_kwargs = kwargs
        return b"%PDF-1.4 fake"


class FakeContext:
    def __init__(self):
        self.page = FakePage()
        self.closed = False

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self):
        self.context = FakeContext()

    async def new_context(self, **kwargs):
        return self.context


@pytest.mark.asyncio
async def test_html_to_pdf_from_html_uses_requested_options(monkeypatch):
    fake_browser = FakeBrowser()

    async def fake_get_browser():
        return fake_browser

    monkeypatch.setattr(pdf_service, "_get_browser", fake_get_browser)
    result = await pdf_service.html_to_pdf(
        html="<h1>Hello</h1>",
        page_size="Letter",
        margin_top="12mm",
        footer_html="<span>Footer</span>",
    )

    assert result.startswith(b"%PDF")
    assert fake_browser.context.page.content_html[0] == "<h1>Hello</h1>"
    assert fake_browser.context.page.pdf_kwargs["format"] == "Letter"
    assert fake_browser.context.page.pdf_kwargs["display_header_footer"] is True
    assert fake_browser.context.closed is True


@pytest.mark.asyncio
async def test_html_to_pdf_requires_input(monkeypatch):
    fake_browser = FakeBrowser()

    async def fake_get_browser():
        return fake_browser

    monkeypatch.setattr(pdf_service, "_get_browser", fake_get_browser)
    with pytest.raises(ValueError):
        await pdf_service.html_to_pdf()
