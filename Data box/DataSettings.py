
import streamlit as st
import pandas as pd
from datetime import datetime, date

# -------------------------------
# 小工具函数（统一日期类型 & 安全格式化）
# -------------------------------
def ensure_date_col(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """把指定列统一成 datetime.date（便于与 sofr_df 比较，不用 .dt）"""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors='coerce').dt.date
    return df

def to_ymd_string(series: pd.Series) -> pd.Series:
    """
    展示/导出用：统一转成 'YYYY-MM-DD' 字符串。
    兼容 datetime64/datetime.date/字符串/NaT。
    先 to_datetime 再 .dt.strftime，最后填空避免 NaT。
    """
    ser_ts = pd.to_datetime(series, errors='coerce')
    return ser_ts.dt.strftime('%Y-%m-%d').fillna('')

# -------------------------------
# 你原有的格式化（保留）
# -------------------------------
def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # 将第1列转成 Timestamp（后续我们再统一为 date）
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
    return df

# -------------------------------
# 配置与初始化
# -------------------------------
DATA_PATH = "Tadata/updated_df.csv"  # <-- 这里按你的实际路径设置

# today 用 date 类型；文件名时再格式化
today = date.today()

# 缓存加载函数（保持 Calculation Date 为 datetime.date）
@st.cache_data
def load_sofr_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    # 统一成 Timestamp 再转成 date（保持你设定好的 date 格式）
   df["Calculation Date"] = pd.to_datetime(df["Calculation Date"],errors="coerce",dayfirst=False).dt.date
    return df

# 预加载（如果文件不存在，这里会报错；你也可以包 try/except）
sofr_df = load_sofr_data()

# 会话状态
if "data_loaded" not in st.session_state:
    st.session_state["data_loaded"] = False
if "sofr_df" not in st.session_state:
    st.session_state["sofr_df"] = sofr_df

# -------------------------------
# UI 布局
# -------------------------------
col1, col2 = st.columns([3, 2])

# -------------------------------
# 加载按钮
# -------------------------------
with col2:
    if st.button("⚙️ Import Interest Rate Info"):
        try:
            sofr_df = load_sofr_data()
            st.session_state["sofr_df"] = sofr_df
            st.session_state["data_loaded"] = True

            # last_date 是 datetime.date
            last_date = sofr_df["Calculation Date"].dropna().max()
            st.success(f"✅ Data loaded successfully! Last update date: {last_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            st.error(f"❌ Failed to load data：{e}")

# -------------------------------
# 更新利率数据
# -------------------------------
with col1:
    st.subheader("Update Interest Rate")

    upload_file = st.file_uploader("Please upload the FP2.0 Interest Rate Excel", type=["xlsx"])

    # 取当前主数据（保持为 date 格式）
    update_target_df = st.session_state.get("sofr_df", sofr_df)

    # 最新已更新日期（用列名更稳，不用 iloc）
    update_target_d = update_target_df["Calculation Date"].dropna().max() if not update_target_df.empty else None

    if upload_file is not None:
        try:
            # 读取并初步格式化（第1列转 Timestamp）
            raw_df = pd.read_excel(upload_file)
            update_info_df = format_dataframe(raw_df)

            # 列名统一
            update_info_df = update_info_df.rename(columns={
                "SOFR (SME)": "SOFR",
                "HIBOR (SME)": "Daily Calculated Blended HIBOR"
            })

            # ✅ 将上传数据的日期列统一为 datetime.date（与 sofr_df 保持一致）
            update_info_df = ensure_date_col(update_info_df, ["Calculation Date", "SOFR Date"])

            # 排序（按 date）
            update_info_df = update_info_df.sort_values(by="Calculation Date")

            # ✅ 用 date 比较，保证两边类型一致
            if update_target_d is not None:
                update_info_df = update_info_df[update_info_df["Calculation Date"] > update_target_d]
            # else: 如果历史数据没有有效日期，则全部视为新增

            # 追加并保持日期列为 date
            updated_df = pd.concat([update_target_df, update_info_df], axis=0, ignore_index=True)
            updated_df = ensure_date_col(updated_df, ["Calculation Date", "SOFR Date"])

            # 去重（可选，防止重复日期导致计算偏差）
            updated_df = updated_df.drop_duplicates(subset=["Calculation Date"], keep="last")

            # 最后日期（仍为 date）
            last_date = updated_df["Calculation Date"].dropna().max()

            # 保存主 CSV（CSV 内是字符串；load_sofr_data 会再统一为 date）
            updated_df.to_csv(DATA_PATH, index=False)

            # 清缓存，让重新导入时生效
            st.cache_data.clear()

            st.success(f"Updated: {last_date.strftime('%Y-%m-%d')}. 🔄 Please Re-import Interest Rate Info")

            # -------------------------------
            # 生成 SOFR 数据（展示/下载用字符串）
            # -------------------------------
            sofr_csv_df = updated_df[["Calculation Date", "SOFR", "SOFR Date"]].copy()
            sofr_csv_df["Calculation Date"] = to_ymd_string(sofr_csv_df["Calculation Date"])
            if "SOFR Date" in sofr_csv_df.columns:
                sofr_csv_df["SOFR Date"] = to_ymd_string(sofr_csv_df["SOFR Date"])

            # -------------------------------
            # 生成 HIBOR 数据（筛选用 date；展示/导出用字符串）
            # -------------------------------
            hibor_csv_df = updated_df[
                ["Calculation Date", "Daily Calculated Blended HIBOR", "Effective Blended HIBOR for SME"]
            ].copy()

            # 截取：两边用 date
            cutoff_date = date(2024, 8, 18)
            hibor_csv_df = hibor_csv_df[hibor_csv_df["Calculation Date"] > cutoff_date]

            # 改列名并格式化展示
            hibor_csv_df = hibor_csv_df.rename(columns={"Calculation Date": "Record Date"})
            hibor_csv_df["Record Date"] = to_ymd_string(hibor_csv_df["Record Date"])

            # -------------------------------
            # 下载按钮
            # -------------------------------
            subcol1, subcol2 = st.columns(2)

            with subcol1:
                st.write("SOFR Data")
                st.dataframe(sofr_csv_df)
                st.download_button(
                    label="download sofr csv",
                    data=sofr_csv_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"sofr_{today.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

            with subcol2:
                st.write("HIBOR Data")
                st.dataframe(hibor_csv_df)
                st.download_button(
                    label="download hibor csv",
                    data=hibor_csv_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"hibor_{today.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

        except Exception as e:
            st.error(f"❌ Failed to load data：{e}")


