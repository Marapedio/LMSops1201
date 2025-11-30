import streamlit as st
import os
from PIL import Image


#---logo setting
image_path = "00images/"
logo_img = image_path+"FPops.png"
icon_img = image_path+"penguin.png"
st.logo(logo_img, icon_image=icon_img)

data_processor = st.Page(
    "Data box/DataBox.py", title="Data Processor", icon=":material/hourglass:")

lianlian_preview = st.Page(
    "Data box/Lianlian.py", title="Lian Lian", icon=":material/upload:")

settings = st.Page(
    "Data box/DataSettings.py", title="SOFR Update", icon=":material/settings:")

funder_balance = st.Page(
    "Funder Balance/FunderBalance.py",title="Funder Balance",icon=":material/bug_report:")

csv_validation = st.Page(
    "Funder Balance/CSVvalidation.py",title="CSV Validation",icon=":material/info:")
data_pages = [data_processor,lianlian_preview,settings]
upload_pages = [funder_balance,csv_validation]
#---------------------------------------------------

page_dict = {
    "Data Processor": data_pages,
    "Others": upload_pages
}

st.markdown("""
    <style>
        .block-container {
            max-width: 90% !important;
            margin: 0 auto !important;
            padding-top: 4rem !important;
            padding-right: 5rem;
            padding-left: 0rem
        }
    </style>
    """, unsafe_allow_html=True)


st.set_page_config(layout="wide")  # 更宽的布局，减少折行

st.markdown("""
<style>
/* 基础字体和容器内边距 */
html, body, [data-testid="stAppViewContainer"] { font-size: 13px; }
.block-container { padding-top: 0.6rem; padding-bottom: 0.6rem; }

/* 标题、段落行距更紧 */
h1, h2, h3, h4 { margin-bottom: 0.4rem; }
.stMarkdown p { margin-bottom: 0.25rem; }

/* 列间距缩小 */
[data-testid="column"] { padding-right: 0.4rem; padding-left: 0.4rem; }

/* 输入控件：标签和输入框更小更紧 */
[data-testid="stDateInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextInput"] label { font-size: 12px; margin-bottom: 0.15rem; }

[data-testid="stDateInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    height: 25px;
    padding: 2px 6px;
    font-size: 12px;
}

/* 按钮更紧凑 */
[data-testid="baseButton-secondary"], [data-testid="baseButton-primary"] {
    padding: 0.2rem 0.6rem;
    font-size: 12px;
}

/* 表单容器的控件间距更小（如果使用 st.form） */
[data-testid="stForm"] { gap: 0.3rem; }
</style>
""", unsafe_allow_html=True)


st.markdown("""
<style>
/* 缩小 st.metric 的标签文字 */
[data-testid="stMetric"] label {
    font-size: 15px;         /* 默认大约14px，这里改小一点 */
    line-height: 1.2;
}

/* 缩小 st.metric 的主数值 */
[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 13px;
    font-weight: bold;           /* 默认大约24px，这里改小一些 */
    line-height: 1.2;
}

/* （可选）缩小 delta 图标和文字 */
[data-testid="stMetric"] div[data-testid="stMetricDelta"] svg {
    transform: scale(0.85);
}
[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)



pg = st.navigation(page_dict)

pg.run()
