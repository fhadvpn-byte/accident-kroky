
[3528 lines collapsed]

    except Exception:
        return None
def generate_clean_print_html(how_text, results_text, show_numbers=False):
    page_counter_css = """
        @bottom-center {
            content: "صفحة " counter(page) " من " counter(pages);
            font-family: 'Tajawal', sans-serif;
            font-size: 10pt;
            color: #444;
        }
    """ if show_numbers else """
        @bottom-center { content: none !important; }
    """
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تقرير حادث مروري رسمي</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
            
            @page {{
                size: A4 portrait;
                margin: 12mm 15mm 18mm 15mm;
                {page_counter_css}
            }}
            body {{
                font-family: 'Tajawal', sans-serif;
                margin: 0;
                padding: 0;
                color: #000;
                background: #fff;
                direction: rtl;
                font-size: 12pt;
                line-height: 1.6;
            }}
            .report-container {{
                width: 100%;
                max-width: 190mm;
                margin: 0 auto;
            }}
            .report-box {{
                border: 1.5px solid #111;
                border-radius: 6px;
                padding: 12px 15px;
                margin-bottom: 12px;
                page-break-inside: avoid;
                break-inside: avoid;
                background-color: #fff;
            }}
            .section-title {{
                font-weight: 700;
                font-size: 13pt;
                background-color: #f1f5f9 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
                padding: 6px 10px;
                border-bottom: 1.5px solid #111;
                margin: -12px -15px 10px -15px;
                border-radius: 4px 4px 0 0;
            }}
            .content-text {{
                white-space: pre-wrap;
                text-align: justify;
            }}
            /* ضبط الصور والقرائن المرئية لتتلاءم مع الصفحة ولا تسبب صفحات فارغة */
            .evidence-image-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
                margin-top: 10px;
                page-break-inside: avoid;
                break-inside: avoid;
            }}
            .evidence-image-container img {{
                max-width: 45%;
                max-height: 60mm;
                object-fit: contain;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 3px;
            }}
            @media screen {{
                body {{
                    padding: 20px;
                    background: #e9ecef;
                }}
                .report-container {{
                    background: #fff;
                    padding: 15mm;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.15);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="report-container">
            <div class="report-box">
                <div class="section-title">أولاً: كيفية وقوع الحادث (الصياغة الفنية الدقيقة)</div>
                <div class="content-text">{how_text or "لم يتم إدخال نص."}</div>
            </div>
            <div class="report-box">
                <div class="section-title">ثانياً: نتائج الحادث والمسؤولية</div>
                <div class="content-text">{results_text or "لم يتم إدخال نص."}</div>
            </div>
        </div>
        <script>
            window.onload = function() {{
                setTimeout(function() {{ window.print(); }}, 400);
            }};
        </script>
    </body>
    </html>
    """
with tab5:
    st.subheader("📸 إرفاق صور موقع الحادث والمركبات للتقرير الرسمي")
    _max_accident_photos = 10

[217 lines collapsed]

    )
    page_number_css = ""
    body_class = ""
    clean_print_html = generate_clean_print_html(
        html.escape(acc_how or ""),
