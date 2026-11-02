import streamlit as st
import pandas as pd
from datetime import datetime

# إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="نظام بينة - تقارير الحوادث المرورية",
    page_icon="🚔",
    layout="wide"
)

# العنوان الرئيسي والشعار
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>نظام بَيِّنَة للتقارير المرورية</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #4B5563;'>قسم مرور العارضة - إدارة مرور جازان</h3>", unsafe_allow_html=True)
st.markdown("---")

# القائمة الجانبية لإدخال البيانات
st.sidebar.header("⚙️ الإعدادات الثابتة للقسم")
manager_dept = st.sidebar.text_input("إدارة مرور منطقة", "إدارة مرور منطقة جازان")
section_name = st.sidebar.text_input("القسم / الشعبة", "قسم مرور محافظة العارضة")

st.sidebar.markdown("---")
st.sidebar.header("📋 بيانات الحادث الأساسية")
accident_no = st.sidebar.text_input("رقم الحادث المروري", "1447/001")
accident_date = st.sidebar.date_input("تاريخ الحادث", datetime.now())
location = st.sidebar.text_input("موقع الحادث", "محافظة العارضة - الشارع العام")

# واجهة التطبيق الرئيسية
tab1, tab2, tab3 = st.tabs(["📝 (1): البيانات والأطراف", "⚖️ (2): تحديد المسؤولية", "📄 (3): معاينة وطباعة التقرير"])

with tab1:
    st.markdown("### بيانات الأطراف والمركبات")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### الطرف الأول")
        party1_name = st.text_input("اسم السائق الأول", "محمد علي العبدلي")
        party1_id = st.text_input("رقم الهوية / الإقامة (الأول)", "1098765432")
        party1_car = st.text_input("نوع ورقم لوحة المركبة (الأول)", "أ ب ج 1234")
        
    with col2:
        st.markdown("#### الطرف الثاني")
        party2_name = st.text_input("اسم السائق الثاني", "صالح أحمد القحطاني")
        party2_id = st.text_input("رقم الهوية / الإقامة (الثاني)", "1012345678")
        party2_car = st.text_input("نوع ورقم لوحة المركبة (الثاني)", "د هـ و 5678")

with tab2:
    st.markdown("### تفاصيل الحادث ونسب المسؤولية")
    accident_details = st.text_area("وصف موجز لكيفية وقوع الحادث:", "نتيجة لعدم إعطاء الأولوية واصطدام المركبة الأولى بالمركبة الثانية أثناء الانعطاف اليساري.")
    
    liability_p1 = st.slider("نسبة المسؤولية على الطرف الأول (%)", 0, 100, 100)
    liability_p2 = 100 - liability_p1
    st.info(f"توزيع نسب الخطأ: الطرف الأول ({liability_p1}%) - الطرف الثاني ({liability_p2}%)")

with tab3:
    st.markdown("### اعتماد وتصدير التقرير النهائي")
    if st.button("إصدار التقرير المعتمد", type="primary"):
        st.success("تم إعداد وتوثيق تقرير الحادث بنجاح تام وجاهز للرفع للجهات المختصة!")
        st.balloons()
        
        report_data = {
            "حقل البيانات": ["رقم الحادث", "التاريخ", "الموقع", "الطرف الأول", "الطرف الثاني", "نسبة خطأ الأول", "نسبة خطأ الثاني"],
            "التفاصيل": [accident_no, str(accident_date), location, party1_name, party2_name, f"{liability_p1}%", f"{liability_p2}%"]
        }
        df = pd.DataFrame(report_data)
        st.table(df)
