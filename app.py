import os
from datetime import datetime
import pandas as pd
from PIL import Image
import streamlit as st

# إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="نظام بينة - تقارير الحوادث المرورية",
    page_icon="🚔",
    layout="wide",
)

# العنوان الرئيسي
st.markdown(
    "<h1 style='text-align: center; color: #1E3A8A;'>نظام بَيِّنَة للتقارير المرورية</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<h3 style='text-align: center; color: #4B5563;'>قسم مرور العارضة - إدارة"
    " مرور جازان</h3>",
    unsafe_allow_html=True,
)
st.markdown("---")

# نموذج إدخال بيانات الحادث
st.sidebar.header("إعدادات التقرير والبيانات")
accident_no = st.sidebar.text_input("رقم الحادث المروري", "1447/001")
accident_date = st.sidebar.date_input(
    "تاريخ الحادث", datetime.now()
)
location = st.sidebar.text_input("موقع الحادث", "محافظة العارضة - الشارع العام")

st.write("### بيانات الأطراف والمركبات")
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

st.markdown("---")
st.markdown("### تفاصيل الحادث والمسؤولية")
accident_details = st.text_area(
    "وصف موجز لكيفية وقوع الحادث:",
    "نتيجة لعدم إعطاء الأولوية واصطدام المركبة الأولى بالمركبـة الثانية أثناء"
    " الانعطاف اليساري.",
)

liability_p1 = st.slider("نسبة المسؤولية على الطرف الأول (%)", 0, 100, 100)
liability_p2 = 100 - liability_p1
st.info(f"نسبة المسؤولية: الطرف الأول ({liability_p1}%) - الطرف الثاني ({liability_p2}%)")

if st.button("إصدار وتوليد التقرير النهائي", type="primary"):
    st.success("تم إعداد وتوثيق تقرير الحادث بنجاح!")
    st.balloons()
    
    # معاينة التقرير
    st.markdown("### معاينة بيانات التقرير المعتمد")
    report_data = {
        "رقم الحادث": [accident_no],
        "التاريخ": [str(accident_date)],
        "الموقع": [location],
        "الطرف الأول": [party1_name],
        "الطرف الثاني": [party2_name],
        "نسبة خطأ الأول": [f"{liability_p1}%"],
        "نسبة خطأ الثاني": [f"{liability_p2}%"],
    }
    df = pd.DataFrame(report_data)
    st.table(df)
