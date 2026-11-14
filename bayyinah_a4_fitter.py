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
.page.report-page .box-content,
.page.report-page .autofit-box,
.page.report-page .section-box,
.page.report-page .content-box,
.page.report-page .report-box,
.page.report-page .results-box,
.page.report-page .how-happened-box,
.page.report-page .liability-box,
.page.report-page [data-autofit],
.page.report-page [data-oldfit] {
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
.page.report-page .table-scroll,
.page.report-page td.actions-body,
.page.report-page td.autofit-box {
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  flex-shrink: 0 !important;
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
}
</style>
<script>
(function() {
  function unlockBoxes(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('[data-autofit]').forEach(function(el) {
      el.setAttribute('data-oldfit', el.getAttribute('data-autofit'));
      el.removeAttribute('data-autofit');
    });
    root.querySelectorAll(
      '.box-content, .autofit-box, .section-box, .content-box, .report-box, .liability-box, [data-oldfit], td.actions-body'
    ).forEach(function(el) {
      el.style.setProperty('height', 'auto', 'important');
      el.style.setProperty('max-height', 'none', 'important');
      el.style.setProperty('overflow', 'visible', 'important');
      el.style.setProperty('flex-shrink', '0', 'important');
      el.style.setProperty('padding-bottom', '10px', 'important');
    });
  }
  function fitReportPages(doc) {
    if (!doc) return;
    unlockBoxes(doc);
    var pages = doc.querySelectorAll('.report-page, div.page');
    pages.forEach(function(page) {
      var boxes = page.querySelectorAll(
        '.box-content, .autofit-box, .section-box, .content-box, .report-box, .liability-box, [data-oldfit], td.actions-body'
      );
      if (!boxes.length) return;
      var ruler = doc.createElement('div');
      ruler.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:294mm;visibility:hidden;pointer-events:none;';
      page.appendChild(ruler);
      var maxH = ruler.offsetHeight || 1110;
      page.removeChild(ruler);
      var footer = page.querySelector(':scope > [class*="footer"], :scope > footer');
      var body = page.querySelector('.page-body-flex, .page-body, .p2-body-flex, .p3-body-flex, [class*="-body-flex"]');
      var badges = page.querySelectorAll('.section-badge');
      page.style.setProperty('height', 'auto', 'important');
      page.style.setProperty('max-height', 'none', 'important');
      page.style.setProperty('overflow', 'visible', 'important');
      if (footer) footer.style.setProperty('margin-top', '6px', 'important');
      for (var fs = 12.5; fs >= 5.8 && page.scrollHeight > maxH; fs = +(fs - 0.35).toFixed(2)) {
        var lh = Math.max(1.12, +(1.55 - (12.5 - fs) * 0.05).toFixed(2));
        var padV = Math.max(3, Math.round(10 - (12.5 - fs) * 0.7));
        var padH = Math.max(6, Math.round(12 - (12.5 - fs) * 0.7));
        var gap = Math.max(2, Math.round(6 - (12.5 - fs) * 0.45));
        if (body) body.style.setProperty('gap', gap + 'px', 'important');
        badges.forEach(function(b) {
          b.style.setProperty('margin', Math.max(1, gap - 1) + 'px auto', 'important');
          b.style.setProperty('padding', '2px 10px', 'important');
          b.style.setProperty('font-size', Math.max(8, fs) + 'px', 'important');
        });
        boxes.forEach(function(bx) {
          if (bx.closest && bx.closest('.sign-table')) return;
          bx.style.setProperty('font-size', fs + 'px', 'important');
          bx.style.setProperty('line-height', String(lh), 'important');
          bx.style.setProperty('padding', padV + 'px ' + padH + 'px 10px ' + padH + 'px', 'important');
          bx.style.setProperty('height', 'auto', 'important');
          bx.style.setProperty('max-height', 'none', 'important');
          bx.style.setProperty('overflow', 'visible', 'important');
          bx.style.setProperty('flex-shrink', '0', 'important');
          bx.querySelectorAll('p, li, ul, ol, div, span, b, strong, td').forEach(function(ch) {
            if (ch.classList && ch.classList.contains('section-badge')) return;
            if (ch.closest && ch.closest('.sign-table')) return;
            ch.style.setProperty('font-size', fs + 'px', 'important');
            ch.style.setProperty('line-height', String(lh), 'important');
          });
        });
      }
      page.style.setProperty('min-height', '296mm', 'important');
      if (footer) footer.style.setProperty('margin-top', 'auto', 'important');
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
