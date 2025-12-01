
import streamlit as st
import pandas as pd
from datetime import datetime, date  # ✅ 增加 date

# Set the SOFR format: 统一把上传数据的第1列转成 Timestamp
def format_dataframe(df):
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
    return df

# data path 
DATA_PATH = "Tadata/updated_df.csv"  # set it manually please

# ✅ today 改为 date 类型（用于文件名时再格式化成字符串）
today = date.today()

# 缓存加载函数
@st.cache_data
def load_sofr_data():
    df = pd.read_csv(DATA_PATH)
    # 统一成 Timestamp 再转成 date（保持你设定好的 date 格式）
    df['Calculation Date'] = pd.to_datetime(df['Calculation Date'], errors='coerce')
    df['Calculation Date'] = df['Calculation Date'].dt.date
    return df

sofr_df = load_sofr_data()

if "data_loaded" not in st.session_state:
    st.session_state["data_loaded"] = False

# -------------------------------
col1, col2 = st.columns([3,2])
# -------------------------------
# 加载按钮
# -------------------------------
with col2:
    if st.button("⚙️ Import Interest Rate Info"):
        try:
            sofr_df = load_sofr_data()
            st.session_state["sofr_df"] = sofr_df
            st.session_state["data_loaded"] = True

            last_date = sofr_df["Calculation Date"].dropna().max()  # 这里是 datetime.date
            # ✅ datetime.date 也支持 strftime
            st.success(f"✅ Data loaded successfully! Last update date: {last_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            st.error(f"❌ Failed to load data：{e}")  

with col1:
    st.subheader("Update Interest Rate")
    # 上传新文件
    upload_file = st.file_uploader("Please upload the FP2.0 Interest Rate Excel", type=["xlsx"])

    update_target_df = sofr_df   # 已是 date 类型
    update_target_d = update_target_df.iloc[-1, 0]  # 这是 datetime.date

    if upload_file is not None:
        try:
            # 读取并格式化上传文件（把第1列转成 Timestamp）
            update_info_df = format_dataframe(pd.read_excel(upload_file))

            # 列名统一
            update_info_df = update_info_df.rename(columns={
                'SOFR (SME)': 'SOFR',
                'HIBOR (SME)': 'Daily Calculated Blended HIBOR'
            })

            # ✅ 将上传数据的 'Calculation Date' 统一到 date 类型，用于与 sofr_df 比较
            update_info_df['Calculation Date'] = pd.to_datetime(
                update_info_df['Calculation Date'], errors='coerce'
            ).dt.date

            # 排序（按 date）
            update_info_df = update_info_df.sort_values(by='Calculation Date')

            # ✅ 用 date 比较，保证两边都是 date
            update_info_df = update_info_df[update_info_df['Calculation Date'] > update_target_d]

            # 追加（两边的 Calculation Date 都是 date，不会把列搞混到 object）
            updated_df = pd.concat([update_target_df, update_info_df], axis=0, ignore_index=True)

            # 计算最后日期（date）
            last_date = updated_df["Calculation Date"].dropna().max()

            # 保存：注意 CSV 里会存为字符串；没关系，load_sofr_data 会统一回 Timestamp→date
            updated_df.to_csv(DATA_PATH, index=False)

            # 清缓存，让下次 Import 生效
            st.cache_data.clear()

            st.success(f"Updated: {last_date.strftime('%Y-%m-%d')}. 🔄 Please Re-import Interest Rate Info")

            # -------------------------------
            # 生成 SOFR 数据（展示/下载时转字符串）
            # -------------------------------
            sofr_csv_df = updated_df[['Calculation Date', 'SOFR', 'SOFR Date']].copy()

            # Calculation Date：源是 date，展示为 yyyy-mm-dd
            sofr_csv_df['Calculation Date'] = pd.to_datetime(
                sofr_csv_df['Calculation Date'], errors='coerce'
            ).dt.strftime('%Y-%m-%d')

            # SOFR Date：可能是空或混合，统一格式化
            if 'SOFR Date' in sofr_csv_df.columns:
                sofr_csv_df['SOFR Date'] = pd.to_datetime(
                    sofr_csv_df['SOFR Date'], errors='coerce'
                ).dt.strftime('%Y-%m-%d')

            # -------------------------------
            # 生成 HIBOR 数据（统一用 date 进行筛选）
            # -------------------------------
            hibor_csv_df = updated_df[['Calculation Date', 'Daily Calculated Blended HIBOR', 'Effective Blended HIBOR for SME']].copy()

            # 这里源是 date，直接用 date 截取
            cutoff_date = date(2024, 8, 18)
            hibor_csv_df = hibor_csv_df[hibor_csv_df['Calculation Date'] > cutoff_date]

            # 改列名并格式化展示
            hibor_csv_df = hibor_csv_df.rename(columns={'Calculation Date': 'Record Date'})
            hibor_csv_df['Record Date'] = pd.to_datetime(
                hibor_csv_df['Record Date'], errors='coerce'
            ).dt.strftime('%Y-%m-%d')

            # -------------------------------
            # 下载按钮
            # -------------------------------
            subcol1, subcol2 = st.columns(2)

            with subcol1:
                st.write("SOFR Data")
                st.dataframe(sofr_csv_df)
                st.download_button(
                    label="download sofr csv",
                    data=sofr_csv_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"sofr_{today.strftime('%Y%m%d')}.csv",  # ✅ 用 date，再格式化
                    mime='text/csv'
                )

            with subcol2:
                st.write("HIBOR Data")
                st.dataframe(hibor_csv_df)
                st.download_button(
                    label="download hibor csv",
                    data=hibor_csv_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"hibor_{today.strftime('%Y%m%d')}.csv",  # ✅ 用 date，再格式化
                    mime='text/csv'
                )

        except Exception as e:

