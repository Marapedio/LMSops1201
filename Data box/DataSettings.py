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

            # ✅ 统一已有数据的日期类型
            for col in ["Calculation Date", "SOFR Date"]:
                if col in sofr_df.columns:
                    sofr_df[col] = pd.to_datetime(sofr_df[col], errors='coerce')

            st.session_state["sofr_df"] = sofr_df
            st.session_state["data_loaded"] = True

            last_date = sofr_df["Calculation Date"].dropna().max()
            # 注意：last_date 可能为 NaT，先判断
            if pd.notna(last_date):
                st.success(f"✅ Data loaded successfully! Last update date: {last_date.strftime('%Y-%m-%d')}")
            else:
                st.warning("⚠️ Data loaded, but no valid Calculation Date found.")
        except Exception as e:
            st.error(f"❌ Failed to load data：{e}")  

with col1:
    st.subheader("Update Interest Rate")
    upload_file = st.file_uploader("Please upload the FP2.0 Interest Rate Excel", type=["xlsx"])

    # 从会话拿到已有数据（或你之前的变量）
    update_target_df = st.session_state.get("sofr_df", None)
    if update_target_df is None:
        st.info("ℹ️ Please import interest rate info first.")
    else:
        # ✅ 统一已有数据的日期类型（防止上面没跑到或历史数据异常）
        for col in ["Calculation Date", "SOFR Date"]:
            if col in update_target_df.columns:
                update_target_df[col] = pd.to_datetime(update_target_df[col], errors='coerce')

        # 最新已更新日期（确保为 datetime）
        update_target_d = update_target_df["Calculation Date"].dropna().max()

        if upload_file is not None:
            try:
                # 读取并格式化上传文件
                raw_df = pd.read_excel(upload_file)
                update_info_df = format_dataframe(raw_df)

                # 列名统一
                update_info_df = update_info_df.rename(columns={
                    'SOFR (SME)': 'SOFR',
                    'HIBOR (SME)': 'Daily Calculated Blended HIBOR'
                })

                # ✅ 统一上传数据的日期类型
                for col in ["Calculation Date", "SOFR Date"]:
                    if col in update_info_df.columns:
                        update_info_df[col] = pd.to_datetime(update_info_df[col], errors='coerce')

                # 排序
                update_info_df = update_info_df.sort_values(by='Calculation Date')

                # ✅ 仅保留新日期（两边保证为 datetime 后再比较）
                if pd.notna(update_target_d):
                    update_info_df = update_info_df.loc[update_info_df['Calculation Date'] > update_target_d]
                else:
                    # 如果历史数据没有有效日期，则全部视为新增
                    pass

                # 追加并去重（可选，但推荐）
                updated_df = pd.concat([update_target_df, update_info_df], axis=0, ignore_index=True)
                updated_df = updated_df.sort_values(by="Calculation Date")
                updated_df = updated_df.drop_duplicates(subset=["Calculation Date"], keep="last")

                # 成功提示日期
                last_date = updated_df["Calculation Date"].dropna().max()

                # 保存主 CSV（主数据仍保持 datetime 类型）
                updated_df.to_csv(DATA_PATH, index=False)
                st.cache_data.clear()

                if pd.notna(last_date):
                    st.success(f"Updated: {last_date.strftime('%Y-%m-%d')}. 🔄 Please Re-import Interest Rate Info")
                else:
                    st.warning("⚠️ Updated, but no valid Calculation Date found.")

                # -------------------------------
                # 生成 SOFR 数据（界面展示/下载时格式化）
                # -------------------------------
                sofr_csv_df = updated_df[['Calculation Date', 'SOFR', 'SOFR Date']].copy()
                sofr_csv_df['Calculation Date'] = pd.to_datetime(sofr_csv_df['Calculation Date'], errors='coerce').dt.strftime('%Y-%m-%d')
                if 'SOFR Date' in sofr_csv_df.columns:
                    sofr_csv_df['SOFR Date'] = pd.to_datetime(sofr_csv_df['SOFR Date'], errors='coerce').dt.strftime('%Y-%m-%d')

                # -------------------------------
                # 生成 HIBOR 数据（界面展示/下载时格式化）
                # -------------------------------
                hibor_csv_df = updated_df[['Calculation Date', 'Daily Calculated Blended HIBOR', 'Effective Blended HIBOR for SME']].copy()
                hibor_csv_df['Calculation Date'] = pd.to_datetime(hibor_csv_df['Calculation Date'], errors='coerce')

                # 筛选日期（保证使用 datetime 比较）
                hibor_csv_df = hibor_csv_df.loc[hibor_csv_df['Calculation Date'] > pd.Timestamp('2024-08-18')]

                # 改列名并格式化
                hibor_csv_df = hibor_csv_df.rename(columns={'Calculation Date': 'Record Date'})
                hibor_csv_df['Record Date'] = pd.to_datetime(hibor_csv_df['Record Date'], errors='coerce').dt.strftime('%Y-%m-%d')

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
                        file_name=f"sofr_{today}.csv",
                        mime='text/csv'
                    )

                with subcol2:
                    st.write("HIBOR Data")
                    st.dataframe(hibor_csv_df)
                    st.download_button(
                        label="download hibor csv",
                        data=hibor_csv_df.to_csv(index=False).encode('utf-8'),
                        file_name=f"hibor_{today}.csv",
                        mime='text/csv'
                    )

            except Exception as e:
                st.error(f"❌ Failed to load data：{e}")
