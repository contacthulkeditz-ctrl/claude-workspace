#!/usr/bin/env python3
"""Build print-ready PDFs from the Batch #173 shot-list markdown.

Produces one PDF per source document plus a combined master PDF.
Rendering: markdown -> styled HTML -> Chromium (Playwright) -> PDF.
"""
import asyncio
import re
import sys
from pathlib import Path

import markdown
from playwright.async_api import async_playwright

BASE = Path(__file__).resolve().parent
OUT = BASE / "pdf"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

DOCS = [
    ("00-PRODUCTION-BIBLE.md", "Production Bible", "Analysis, locks, grade arc, prompt blocks, flow system"),
    ("01-HOOK-A.md", "Hook A (H1)", "0:00-0:20 - 7 shots - swap-test variant A"),
    ("02-HOOK-B.md", "Hook B (H2)", "0:00-0:20 - 6 shots - swap-test variant B"),
    ("03-BODY-PART-1.md", "Body Part 1", "0:20-3:00 - S01-S43 - stack, accident, labels"),
    ("04-BODY-PART-2.md", "Body Part 2", "3:00-5:52 - S44-S80 - copper, cert, transformation, close"),
]

BRAND = "House of Ayurveda - Batch #173"
FILM = "Three Days Off The Multivitamin (Story VSL)"

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }

:root {
  --ink:#1a1a1a; --muted:#6b6b6b; --rule:#d8d4cc; --paper:#ffffff;
  --accent:#8a4b2a; --accentbg:#fbf5f0; --code:#f6f4f0; --codeink:#25272b;
  --vo:#2f4858; --vobg:#f2f6f8; --key:#a03030; --keybg:#fdf3f2;
}

* { box-sizing:border-box; }
html { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body {
  font-family:"Bitstream Charter","DejaVu Serif",Georgia,serif;
  font-size:9.6pt; line-height:1.55; color:var(--ink); background:var(--paper);
  margin:0; hyphens:none;
}

/* ---------- cover ---------- */
.cover { height:245mm; display:flex; flex-direction:column; justify-content:space-between; break-after:page; }
.cover .top { padding-top:38mm; }
.cover .kicker {
  font-family:"Liberation Sans","DejaVu Sans",sans-serif; font-size:8pt; font-weight:700;
  letter-spacing:.20em; text-transform:uppercase; color:var(--accent); margin-bottom:9mm;
}
.cover h1 {
  font-family:"Liberation Sans","DejaVu Sans",sans-serif; font-size:30pt; font-weight:700;
  line-height:1.12; letter-spacing:-.015em; margin:0 0 5mm; color:var(--ink); border:0; padding:0;
}
.cover .film { font-size:12.5pt; color:var(--muted); font-style:italic; margin-bottom:11mm; }
.cover .blurb { font-size:10.5pt; max-width:132mm; color:#3a3a3a; border-left:2.5pt solid var(--accent); padding-left:6mm; }
.cover .meta { border-top:.6pt solid var(--rule); padding-top:5mm; font-family:"Liberation Sans","DejaVu Sans",sans-serif; font-size:8pt; color:var(--muted); }
.cover .meta b { color:var(--ink); font-weight:700; }
.cover .meta div { margin-bottom:1.6mm; }

/* ---------- headings ---------- */
h1,h2,h3,h4 { font-family:"Liberation Sans","DejaVu Sans",sans-serif; color:var(--ink); }
h1 {
  font-size:17pt; font-weight:700; letter-spacing:-.01em; margin:0 0 6mm;
  padding-bottom:3mm; border-bottom:1.8pt solid var(--accent); break-before:page; break-after:avoid;
}
h1:first-of-type { break-before:auto; }
h2 {
  font-size:12.5pt; font-weight:700; margin:9mm 0 3.5mm; padding:2.5mm 0 2.5mm 4mm;
  background:var(--accentbg); border-left:3pt solid var(--accent); break-after:avoid; break-inside:avoid;
}
h3 {
  font-size:10.5pt; font-weight:700; margin:6mm 0 2.5mm; padding-bottom:1.4mm;
  border-bottom:.6pt solid var(--rule); break-after:avoid; color:#111;
}
h4 { font-size:9.5pt; font-weight:700; margin:4mm 0 1.5mm; break-after:avoid; }

/* keep a whole shot together where it fits */
.shot { break-inside:avoid; margin-bottom:1mm; }

p { margin:0 0 2.6mm; }
strong { font-weight:700; }
em { font-style:italic; }
a { color:var(--accent); text-decoration:none; }

/* ---------- VO blockquote ---------- */
blockquote {
  margin:2.5mm 0 3mm; padding:2.6mm 4mm; background:var(--vobg);
  border-left:2.5pt solid var(--vo); color:var(--vo); break-inside:avoid;
}
blockquote p { margin:0 0 1.2mm; }
blockquote p:last-child { margin:0; }

/* ---------- prompt code blocks ---------- */
pre {
  background:var(--code); border:.6pt solid #e3ded5; border-left:2.5pt solid #b9b0a2;
  border-radius:1.2mm; padding:3mm 3.6mm; margin:2mm 0 3.4mm;
  font-family:"DejaVu Sans Mono","Liberation Mono",monospace; font-size:7.5pt; line-height:1.45;
  color:var(--codeink); white-space:pre-wrap; word-wrap:break-word; break-inside:avoid;
}
code {
  font-family:"DejaVu Sans Mono","Liberation Mono",monospace; font-size:8pt;
  background:#f0ede8; padding:.3mm 1mm; border-radius:.8mm; color:#5a3a22;
}
pre code { background:none; padding:0; font-size:inherit; color:inherit; }

/* ---------- tables ---------- */
table {
  width:100%; border-collapse:collapse; margin:3mm 0 4.5mm;
  font-family:"Liberation Sans","DejaVu Sans",sans-serif; font-size:8.1pt; break-inside:avoid;
}
th {
  background:#efece6; text-align:left; font-weight:700; color:#2a2a2a;
  padding:2.2mm 2.6mm; border-bottom:1pt solid #c9c2b6; vertical-align:bottom;
}
td { padding:2.2mm 2.6mm; border-bottom:.5pt solid #e6e1d8; vertical-align:top; line-height:1.45; }
tr:nth-child(even) td { background:#faf9f7; }

/* ---------- lists ---------- */
ul,ol { margin:0 0 3mm; padding-left:5.5mm; }
li { margin-bottom:1.4mm; }
li::marker { color:var(--accent); }

hr { border:0; border-top:.6pt solid var(--rule); margin:6mm 0; }

/* ---------- inline markers ---------- */
.key { color:var(--key); font-weight:700; }
.handoff { color:#4a5c3a; }
</style>
"""


def preprocess(md_text: str) -> str:
    """Normalise glyphs and markers that don't render well in the print fonts."""
    md_text = md_text.replace("⚑", "◆")          # flag -> diamond
    md_text = md_text.replace("→", "→")           # arrow is fine in DejaVu
    # strip the H1 title line; the cover page carries it
    md_text = re.sub(r"\A# .*\n", "", md_text)
    return md_text


def wrap_shots(html: str) -> str:
    """Group each h3 section into a .shot div so shots avoid splitting across pages."""
    parts = re.split(r"(?=<h3[ >])", html)
    out = []
    for part in parts:
        if part.startswith("<h3"):
            out.append(f'<div class="shot">{part}</div>')
        else:
            out.append(part)
    return "".join(out)


def cover_html(title: str, subtitle: str, doc_no: str, total: str) -> str:
    return f"""
<div class="cover">
  <div class="top">
    <div class="kicker">{BRAND}</div>
    <h1>{title}</h1>
    <div class="film">{FILM}</div>
    <div class="blurb">{subtitle}</div>
  </div>
  <div class="meta">
    <div><b>Document</b> &nbsp; {doc_no} of {total}</div>
    <div><b>Avatar</b> &nbsp; Supplement Graveyard &nbsp;&middot;&nbsp; Solution-Aware</div>
    <div><b>Format</b> &nbsp; Story VSL &nbsp;&middot;&nbsp; ~5:45 &nbsp;&middot;&nbsp; 9:16 vertical &nbsp;&middot;&nbsp; zero lip-sync</div>
    <div><b>Stack</b> &nbsp; Nano Banana Pro / GPT Image &rarr; image-to-video</div>
    <div><b>Branch</b> &nbsp; claude/ayurveda-batch-173-vsl-fb06lb</div>
  </div>
</div>
"""


def build_html(md_text: str, title: str, subtitle: str, doc_no: str, total: str) -> str:
    body = markdown.markdown(
        preprocess(md_text),
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )
    body = wrap_shots(body)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>{CSS}</head><body>
{cover_html(title, subtitle, doc_no, total)}
{body}
</body></html>"""


HEADER = """<div style="font-family:Liberation Sans,sans-serif;font-size:6.5pt;color:#9a9a9a;
width:100%;padding:0 16mm;display:flex;justify-content:space-between;">
<span>__BRAND__</span><span>__TITLE__</span></div>"""

FOOTER = """<div style="font-family:Liberation Sans,sans-serif;font-size:6.5pt;color:#9a9a9a;
width:100%;padding:0 16mm;display:flex;justify-content:space-between;">
<span>__FILM__</span>
<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>"""


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    total = str(len(DOCS))
    written = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME)
        page = await browser.new_page()

        for idx, (fname, title, subtitle) in enumerate(DOCS, start=1):
            src = BASE / fname
            if not src.exists():
                sys.exit(f"missing source: {src}")
            html = build_html(src.read_text(), title, subtitle, str(idx), total)

            tmp = OUT / (src.stem + ".html")
            tmp.write_text(html)
            await page.goto(tmp.as_uri(), wait_until="networkidle")

            dest = OUT / (src.stem + ".pdf")
            await page.pdf(
                path=str(dest),
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template=HEADER.replace("__BRAND__", BRAND).replace("__TITLE__", title),
                footer_template=FOOTER.replace("__FILM__", FILM),
                margin={"top": "18mm", "bottom": "20mm", "left": "0", "right": "0"},
            )
            tmp.unlink()
            written.append(dest)
            print(f"  {dest.name}")

        await browser.close()

    # combined master
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for pdf in written:
        reader = PdfReader(str(pdf))
        start = len(writer.pages)
        for p in reader.pages:
            writer.add_page(p)
        writer.add_outline_item(pdf.stem, start)

    master = OUT / "BATCH-173-VSL-SHOTLIST-COMPLETE.pdf"
    with open(master, "wb") as fh:
        writer.write(fh)
    print(f"  {master.name}  ({len(writer.pages)} pages)")


if __name__ == "__main__":
    asyncio.run(main())
