"""قواعد وفك قفل صناديق تقرير A4 + موازنة خط تدريجية دون zoom على الواجهة."""
from __future__ import annotations

import re
import streamlit.components.v1 as components

CLEAN_A4_ASSETS = """<!-- BAYYINAH_CLEAN_A4_START -->
<style id="BAYYINAH_CLEAN_A4_STYLE">
.page.report-page, .report-page.page, div.page.report-page {
  width: 210mm !important;
  min-height: 296mm !important;
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;
  box-sizing: border-box !important;
}
.page.report-page .page-body,
.page.report-page .page-body-flex,
.page.report-page .p2-body-flex,
.page.report-page .p3-body-flex,
.page.report-page .autofit-page-body,
.page.report-page [class*="-body-flex"] {
  flex: 1 0 auto !important;
  min-height: 0 !important;
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: flex-start !important;
  gap: 5px !important;
}
.page.report-page .box-content:not(table.sign-table),
.page.report-page .autofit-box:not(table.sign-table),
.page.report-page .section-box:not(table.sign-table),
.page.report-page .content-box:not(table.sign-table),
.page.report-page .report-box:not(table.sign-table),
.page.report-page .results-box,
.page.report-page .how-happened-box,
.page.report-page .liability-box,
.page.report-page [data-autofit]:not(table.sign-table),
.page.report-page [data-oldfit]:not(table.sign-table) {
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  flex-shrink: 0 !important;
  flex: 0 0 auto !important;
  padding-bottom: 10px !important;
  box-sizing: border-box !important;
  transform: none !important;
  display: block !important;
}
/* جدول معد التقرير: استثناء كامل من display:block على مستطيلات النصوص */
.page.report-page table.sign-table,
table.sign-table {
  display: table !important;
  table-layout: fixed !important;
  width: 100% !important;
  max-width: 100% !important;
  min-width: 100% !important;
  border-collapse: collapse !important;
  border-spacing: 0 !important;
  border: 1.5px solid #000 !important;
  box-shadow: none !important;
  outline: none !important;
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  flex: 0 0 auto !important;
  flex-shrink: 0 !important;
  padding: 0 !important;
  margin: 8px 0 0 0 !important;
  transform: none !important;
  direction: rtl !important;
  background: #fff !important;
}
.page.report-page table.sign-table col,
table.sign-table col {
  width: 33.33% !important;
}
.page.report-page table.sign-table thead,
.page.report-page table.sign-table tbody,
table.sign-table thead,
table.sign-table tbody {
  display: table-row-group !important;
}
.page.report-page table.sign-table tr,
table.sign-table tr {
  display: table-row !important;
}
.page.report-page table.sign-table th,
.page.report-page table.sign-table td,
table.sign-table th,
table.sign-table td {
  display: table-cell !important;
  width: 33.33% !important;
  padding: 8px 6px !important;
  box-sizing: border-box !important;
  vertical-align: top !important;
  text-align: center !important;
  border: 1px solid #000 !important;
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  float: none !important;
  position: static !important;
}
.page.report-page table.sign-table th[colspan],
table.sign-table th[colspan] {
  width: auto !important;
}
.page.report-page .table-scroll,
.page.report-page td.actions-body {
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  flex-shrink: 0 !important;
}
.page.report-page th.actions-title {
  text-align: center !important;
}
.page.report-page td.actions-body {
  direction: rtl !important;
  text-align: right !important;
  padding: 10px 14px !important;
  vertical-align: top !important;
}
.page.report-page td.actions-body .action-item {
  display: block !important;
  direction: rtl !important;
  text-align: right !important;
  line-height: 1.75 !important;
  margin: 0 0 4px 0 !important;
  padding-right: 1.5em !important;
  text-indent: -1.5em !important;
}
.page.report-page .section-badge {
  flex: 0 0 auto !important;
  margin: 3px auto !important;
}
.page.report-page > [class*="footer"],
.page.report-page > footer {
  position: relative !important;
  margin-top: auto !important;
  flex: 0 0 auto !important;
}
@media print {
  @page { size: A4 portrait; margin: 0mm !important; }
  .page.report-page, div.page.report-page {
    width: 210mm !important;
    min-height: 295mm !important;
    height: 296mm !important;
    max-height: 296mm !important;
    overflow: hidden !important;
    page-break-after: always !important;
  }
  .page.report-page:last-of-type { page-break-after: auto !important; }
  table.sign-table {
    display: table !important;
    table-layout: fixed !important;
    width: 100% !important;
    border-collapse: collapse !important;
  }
  table.sign-table tr { display: table-row !important; }
  table.sign-table th, table.sign-table td {
    display: table-cell !important;
    width: 33.33% !important;
    padding: 8px 6px !important;
  }
}
</style>
<script>
(function() {
  function unlockBoxes(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('[data-autofit]').forEach(function(el) {
      if (el.classList && el.classList.contains('sign-table')) return;
      if (el.closest && el.closest('table.sign-table')) return;
      el.setAttribute('data-oldfit', el.getAttribute('data-autofit'));
      el.removeAttribute('data-autofit');
    });
    root.querySelectorAll(
      '.box-content, .autofit-box, .section-box, .content-box, .report-box, .liability-box, [data-oldfit], td.actions-body'
    ).forEach(function(el) {
      if (el.classList && el.classList.contains('sign-table')) return;
      if (el.closest && el.closest('table.sign-table')) return;
      el.style.setProperty('height', 'auto', 'important');
      el.style.setProperty('max-height', 'none', 'important');
      el.style.setProperty('overflow', 'visible', 'important');
      el.style.setProperty('flex-shrink', '0', 'important');
      el.style.setProperty('padding-bottom', '10px', 'important');
      if (el.tagName !== 'TABLE' && el.tagName !== 'TR' && el.tagName !== 'TD' && el.tagName !== 'TH' && el.tagName !== 'THEAD' && el.tagName !== 'TBODY' && el.tagName !== 'COL' && el.tagName !== 'COLGROUP') {
        el.style.setProperty('display', 'block', 'important');
      }
    });
  }
  function hardenSignTables(doc) {
    if (!doc || !doc.querySelectorAll) return;
    doc.querySelectorAll('table.sign-table').forEach(function(table) {
      table.style.setProperty('display', 'table', 'important');
      table.style.setProperty('table-layout', 'fixed', 'important');
      table.style.setProperty('width', '100%', 'important');
      table.style.setProperty('max-width', '100%', 'important');
      table.style.setProperty('min-width', '100%', 'important');
      table.style.setProperty('border-collapse', 'collapse', 'important');
      table.style.setProperty('direction', 'rtl', 'important');
      table.querySelectorAll('col').forEach(function(col) {
        col.style.setProperty('width', '33.33%', 'important');
      });
      table.querySelectorAll('thead, tbody').forEach(function(g) {
        g.style.setProperty('display', 'table-row-group', 'important');
      });
      table.querySelectorAll('tr').forEach(function(tr) {
        tr.style.setProperty('display', 'table-row', 'important');
      });
      table.querySelectorAll('th, td').forEach(function(cell) {
        cell.style.setProperty('display', 'table-cell', 'important');
        if (!cell.hasAttribute('colspan')) {
          cell.style.setProperty('width', '33.33%', 'important');
        }
        cell.style.setProperty('padding', '8px 6px', 'important');
        cell.style.setProperty('float', 'none', 'important');
        cell.style.setProperty('position', 'static', 'important');
      });
    });
  }
  function fitReportPages(doc) {
    if (!doc) return;
    unlockBoxes(doc);
    hardenSignTables(doc);
    var pages = doc.querySelectorAll('.report-page, div.page');
    pages.forEach(function(page) {
      if (page.classList && page.classList.contains('photo-annex')) return;
      var boxes = page.querySelectorAll(
        '.box-content, .autofit-box, .section-box, .content-box, .report-box, .liability-box, [data-oldfit], td.actions-body'
      );
      if (!boxes.length) return;
      var ruler = doc.createElement('div');
      ruler.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:295mm;visibility:hidden;pointer-events:none;';
      page.appendChild(ruler);
      var maxH = ruler.offsetHeight || 1116;
      page.removeChild(ruler);
      var footer = page.querySelector(':scope > [class*="footer"], :scope > footer, .official-page-footer, .official-footer, .page-footer');
      var body = page.querySelector('.page-body-flex, .page-body, .p2-body-flex, .p3-body-flex, .autofit-page-body, [class*="-body-flex"]');
      var badges = page.querySelectorAll('.section-badge');
      page.style.setProperty('min-height', '0', 'important');
      page.style.setProperty('height', 'auto', 'important');
      page.style.setProperty('max-height', 'none', 'important');
      page.style.setProperty('overflow', 'visible', 'important');
      if (footer) footer.style.setProperty('margin-top', '8px', 'important');
      function applyFs(fs) {
        var lh = 1.42;
        if (body) body.style.setProperty('gap', '6px', 'important');
        badges.forEach(function(b) {
          b.style.setProperty('font-size', Math.max(12.5, fs) + 'px', 'important');
        });
        boxes.forEach(function(bx) {
          if (bx.closest && bx.closest('table.sign-table')) return;
          bx.style.setProperty('font-size', fs + 'px', 'important');
          bx.style.setProperty('line-height', String(lh), 'important');
          bx.style.setProperty('height', 'auto', 'important');
          bx.style.setProperty('max-height', 'none', 'important');
          bx.style.setProperty('overflow', 'visible', 'important');
          bx.style.setProperty('flex-shrink', '0', 'important');
          bx.querySelectorAll('p, li, ul, ol, div, span, b, strong, td').forEach(function(ch) {
            if (ch.classList && ch.classList.contains('section-badge')) return;
            if (ch.closest && ch.closest('table.sign-table')) return;
            ch.style.setProperty('font-size', fs + 'px', 'important');
            ch.style.setProperty('line-height', String(lh), 'important');
          });
        });
      }
      var fs = 13.5;
      var minFont = 10.5;
      applyFs(fs);
      if (page.scrollHeight > maxH + 0.5) {
        while (fs > minFont + 0.001) {
          fs = Math.max(minFont, +(fs - 0.25).toFixed(2));
          applyFs(fs);
          if (page.scrollHeight <= maxH + 0.5) break;
          if (fs <= minFont + 0.001) break;
        }
      }
      page.style.setProperty('min-height', '296mm', 'important');
      if (footer) footer.style.setProperty('margin-top', 'auto', 'important');
      hardenSignTables(page);
    });
  }
  window.__fitBayyinahCleanA4 = fitReportPages;
  function run() { fitReportPages(document); }
  [40, 180, 450, 900, 1600].forEach(function(ms) { setTimeout(run, ms); });
  window.addEventListener('load', run);
  window.addEventListener('beforeprint', run);
  window.addEventListener('resize', run);
})();
</script>
<!-- BAYYINAH_CLEAN_A4_END -->"""


def install_report_fitter():
    if getattr(components, "_bayyinah_a4_patched", False):
        return
    components._bayyinah_a4_patched = True
    orig_html = components.html

    def _patched_html(html, width=None, height=None, scrolling=False):
        if isinstance(html, str) and ("report-page" in html or "box-content" in html):
            if "BAYYINAH_CLEAN_A4_START" not in html:
                if re.search(r"</body\s*>", html, flags=re.I):
                    html = re.sub(
                        r"(</body\s*>)",
                        CLEAN_A4_ASSETS + r"\1",
                        html,
                        count=1,
                        flags=re.I,
                    )
                else:
                    html = html + CLEAN_A4_ASSETS
        return orig_html(html, width=width, height=height, scrolling=scrolling)

    components.html = _patched_html


def inject_into_report_html(html: str) -> str:
    if not isinstance(html, str) or "BAYYINAH_CLEAN_A4_START" in html:
        return html
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"(</body\s*>)", CLEAN_A4_ASSETS + r"\1", html, count=1, flags=re.I)
    return html + CLEAN_A4_ASSETS
