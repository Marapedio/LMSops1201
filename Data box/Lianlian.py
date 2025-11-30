
import pandas as pd
import msoffcrypto
from io import BytesIO
import re
import streamlit as st


uploaded_file = st.file_uploader("Upload Lianlian Excel", type=["xlsx"])
if uploaded_file:
    try:
        office_file = msoffcrypto.OfficeFile(uploaded_file)
        office_file.load_key(password="llqbd2019")

        decrypted = BytesIO()
        office_file.decrypt(decrypted)

        sheets = pd.read_excel(decrypted, sheet_name=None, engine='openpyxl')
    # Duduction Date
        if 'Deduction' in sheets:
            deduction_df = sheets['Summary']
            required_columns = ['Company Name', 'Deduction Amount', 'Deduction Date']  # 请根据实际列名修改
            missing_cols = [col for col in required_columns if col not in deduction_df.columns]

            if missing_cols:
                st.warning(f"Deduction 表缺少以下列：{', '.join(missing_cols)}")
            else:
                #Date Format
                if pd.api.types.is_datetime64_any_dtype(deduction_df['Deduction Date']):
                    deduction_df['Deduction Date'] = deduction_df['Deduction Date'].dt.strftime('%Y-%m-%d')

                selected_df = deduction_df[required_columns]
                st.subheader("Deduction overview")
                st.dataframe(selected_df)

        else:
            st.warning("Empty Data, Please Check the Excel")

    # 第二部分：筛选四位数字表名中的 TRUNC P 和 Repaid Loan P
        combined_df = pd.DataFrame()
        for sheet_name, df in sheets.items():
            clean_name = sheet_name.replace(" ", "")
            if re.fullmatch(r"\d{4}", clean_name):
                if 'TRUNC P' in df.columns and 'Repaid Loan P' in df.columns:
                    filtered_df = df[df['TRUNC P'].notna() & df['Repaid Loan P'].notna()]
                    if not filtered_df.empty:
                        filtered_df['Sheet Name'] = sheet_name
                        combined_df = pd.concat([combined_df, filtered_df], ignore_index=True)

        if not combined_df.empty:
            for col in combined_df.select_dtypes(include=['datetime64[ns]']).columns:
                combined_df[col] = combined_df[col].dt.strftime('%Y-%m-%d')
            preview_data = combined_df[["Seller Name",
                                        "Trade Code",
                                        "Settle",
                                        "TRUNC P",
                                        "Repaid Loan P"]]

            st.subheader("Trades Overview")
            st.dataframe(preview_data)
                
            total_trunc_p = combined_df['TRUNC P'].sum()
            st.markdown(f"**Total Payment：** {total_trunc_p:,.2f}")
                
            preview_data['TRUNC P'] = pd.to_numeric(preview_data['TRUNC P'], errors='coerce')
            grouped = preview_data.groupby('Seller Name', as_index=False)['TRUNC P'].sum()
            st.write(grouped)


        else:
            st.warning("Empty Data, Please Check the Excel")



    except Exception as e:
        st.error(f"Failed：{e}")