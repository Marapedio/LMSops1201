import streamlit as st
import pandas as pd
from datetime import datetime

#Set the sofr format
def format_dataframe(df):
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
    return df
#data path 

DATA_PATH = "Tadata/updated_df.csv"#set it manually please

today = datetime.today().strftime('%Y%m%d')
# 缓存加载函数
@st.cache_data
def load_sofr_data():
    df = pd.read_csv(DATA_PATH)
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
            last_date = sofr_df["Calculation Date"].dropna().max()
            st.success(f"✅ Data loaded successfully! Last update date: {last_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            st.error(f"❌ Failed to load data：{e}")  
with col1:
    st.subheader("Update Interest Rate")
    # 上传新文件
    upload_file = st.file_uploader("Please upload the FP2.0 Interest Rate Excel", type=["xlsx"])
    update_target_df = sofr_df
    update_target_d= update_target_df.iloc[-1, 0]
    if upload_file is not None:
        try:
            update_info_df = format_dataframe(pd.read_excel(upload_file))
            update_info_df = update_info_df.rename(columns={
                'SOFR (SME)': 'SOFR',
                'HIBOR (SME)': 'Daily Calculated Blended HIBOR'
            })

            update_info_df = update_info_df.sort_values(by='Calculation Date')
            update_info_df = update_info_df[update_info_df['Calculation Date'] > update_target_d]

            updated_df = pd.concat([update_target_df, update_info_df], axis=0, ignore_index=True)
            last_date = updated_df["Calculation Date"].dropna().max()
            updated_df.to_csv(DATA_PATH, index=False)
            st.cache_data.clear()
            st.success(f"Updated: {last_date.strftime('%Y-%m-%d')}. 🔄 Please Re-import Interest Rate Info")

            # 生成 SOFR 数据
            sofr_csv_df = updated_df[['Calculation Date', 'SOFR', 'SOFR Date']].copy()
            sofr_csv_df['Calculation Date'] = pd.to_datetime(sofr_csv_df['Calculation Date'], errors='coerce').dt.strftime('%Y-%m-%d')

            # 生成 HIBOR 数据
            hibor_csv_df = updated_df[['Calculation Date', 'Daily Calculated Blended HIBOR', 'Effective Blended HIBOR for SME']].copy()
            hibor_csv_df = hibor_csv_df[hibor_csv_df['Calculation Date'] > pd.Timestamp('2024-08-18')]
            hibor_csv_df = hibor_csv_df.rename(columns={'Calculation Date': 'Record Date'})
            hibor_csv_df['Record Date'] = pd.to_datetime(hibor_csv_df['Record Date'], errors='coerce').dt.strftime('%Y-%m-%d')

            # 下载按钮
            subcol1, subcol2 = st.columns(2)

            with subcol1:
                st.write("SOFR Data")
                st.dataframe(sofr_csv_df)
                st.download_button(
                    label= "download sofr csv",
                    data=sofr_csv_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"sofr_{today}.csv",
                    mime='text/csv'
                )

            with subcol2:
                st.write("HIBOR Data")
                st.dataframe(hibor_csv_df)
                st.download_button(
                    label= "download hibor csv",
                    data=hibor_csv_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"hibor_{today}.csv",
                    mime='text/csv'
                )

        except Exception as e:
            st.error(f"❌ Failed to load data：{e}")





 


