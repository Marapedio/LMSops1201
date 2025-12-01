
import re
import pandas as pd
from datetime import date

def parse_lms_to_dic(raw_input: str) -> dict:
    """
    将 LMS 文本（按 Section/Tab 分隔）解析为字典。
    - 日期字段：返回 Python 的 datetime.date（标量转换，用 .date()）
    - 利率/金额：尽量转换为 float
    - 天数字段：转换为 int
    - 对 Waive Items：金额按 -abs(...) 处理
    - 对 Surcharge Items：将所有 value 汇总求和（非数值自动忽略）
    """

    # ---------- 1) 按 section 分割 ----------
    # 保持你的分割规则，确保原始字符串去掉首尾空白
    sections = re.split(r'\n(?=[A-Z][A-Za-z ]+\n)', raw_input.strip())

    # ---------- 2) 构建 DataFrame ----------
    rows = []
    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue
        title = lines[0].strip()
        # 逐行解析 field/value，以 \t 分隔；忽略无 \t 的行
        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) >= 2:
                field = parts[0].strip()
                value = parts[1].strip()
                rows.append({"field": field, "value": value, "section": title})

    df = pd.DataFrame(rows, columns=["field", "value", "section"])

    # ---------- 3) 值处理函数 ----------
    def process_value(field: str, value):
        # 空值处理
        if pd.isna(value) or (isinstance(value, str) and value.strip() == ""):
            return None

        field_lower = str(field).lower()

        # 日期字段：标量转换为 Timestamp 后取 .date()
        if 'date' in field_lower:
            ts = pd.to_datetime(value, dayfirst=True, errors='coerce')
            if pd.isna(ts):
                return None
            return pd.Timestamp(ts).date()

        # 利率字段：尽量转 float（允许 "x.xx" 或含逗号）
        elif 'Interest (I + OI)' in field:
            try:
                return float(str(value).replace(',', ''))
            except Exception:
                return None

        # 天数字段：转 int
        elif 'days' in field_lower:
            try:
                return int(str(value).replace(',', ''))
            except Exception:
                return None

        # 其他数值类：尝试转 float（去掉逗号、括号）
        else:
            sv = str(value).strip()
            # 处理会计负数样式 "(123.45)" → -123.45
            is_paren_negative = sv.startswith('(') and sv.endswith(')')
            sv_clean = sv.replace(',', '').strip('()')
            try:
                num = float(sv_clean)
                return -num if is_paren_negative else num
            except Exception:
                # 非数值，原样返回
                return value

    # 应用逐行转换
    if not df.empty:
        df['value'] = df.apply(lambda row: process_value(row['field'], row['value']), axis=1)

    # ---------- 4) 安全取值工具，避免 iloc[0] 越界 ----------
    def safe_pick(field_name: str, section_name: str, default=None):
        ser = df.loc[(df["field"] == field_name) & (df["section"] == section_name), "value"]
        if ser.empty:
            return default
        return ser.iloc[0]

    # ---------- 5) Waive Items 转负（若存在则 -abs(...)，否则为 0.0/None） ----------
    def negate_abs(val):
        if val is None or pd.isna(val):
            return 0.0
        try:
            return -abs(float(val))
        except Exception:
            return 0.0

    # ---------- 6) Surcharge Items 汇总 ----------
    surcharge_series = df.loc[df["section"] == "Surcharge Items", "value"]
    # 将可解析项转 float，失败的变为 NaN，然后 sum() 跳过 NaN
    surcharge_sum = pd.to_numeric(surcharge_series, errors='coerce').sum() if not surcharge_series.empty else 0.0

    # ---------- 7) 组装结果字典 ----------
    lms_data = {
        # 基本信息
        "drawdown_id": str(safe_pick("Drawdown ID", "Payment Details", default=None)),
        "currency": str(safe_pick("Repayment Currency", "Payment Details", default=None)),

        # 日期：均为 datetime.date 或 None
        "sme_drawdown": safe_pick("SME Disbursement Date", "Payment Details", default=None),
        "funder_drawdown": safe_pick("Funder Disbursement Date", "Funder Information", default=None),
        "last_funder_submission": safe_pick("Last Funder Submission Date", "Funder Information", default=None),
        "repayment_date": safe_pick("Repayment Date", "Payment Details", default=None),

        # 参数
        "sme_tenor": safe_pick("Tenor (Days)", "SME Information", default=None),
        "sme_mit": safe_pick("MIT (Days)", "SME Information", default=None),

        # 金额类
        "repayment_amount": safe_pick("Repayment Amount", "Payment Details", default=0.0),
        "outstanding_principal": safe_pick("Outstanding Principal", "SME Transaction", default=0.0),
        "principal": safe_pick("Principal", "SME Transaction", default=0.0),
        "bank_charge": safe_pick("Bank Charge", "Payment Details", default=0.0),

        # 利率/系统金额
        "sme_intrate": safe_pick("Interest Rate (% p.a.)", "SME Information", default=None),
        "sme_sysint": safe_pick("Interest", "SME Transaction", default=0.0),
        "sme_sysodint": safe_pick("Overdue Interest", "SME Transaction", default=0.0),

        # Waive Items：负号处理
        "waived_bankcharge": negate_abs(safe_pick("Bank Charge", "Waive Items", default=None)),
        "waived_smeint": negate_abs(safe_pick("Interest", "Waive Items", default=None)),
        "waived_smeodint": negate_abs(safe_pick("Overdue Interest", "Waive Items", default=None)),

        # Return to borrower
        "rtb_sys": safe_pick("Return to borrower", "SME Transaction", default=0.0),

        # 资金方
        "funder_id": str(safe_pick("Funder ID", "Funder Information", default=None)),
        "funder_sysint": safe_pick("Interest (I + OI)", "Funder Transaction", default=0.0),
        "funder_intrate": safe_pick("Interest Rate (% p.a.)", "Funder Information", default=None),
        "platform_fee": negate_abs(safe_pick("Platform Fee", "Funder Transaction", default=None)),
        "funder_sysallocation": float(safe_pick("Total Allocation", "Funder Transaction", default=None)),

        # FundPark
        "spreading_sysint": safe_pick("FundPark Spreading", "FundPark Transaction", default=0.0),

        # Surcharge Items 汇总
        "surcharge_item": float(surcharge_sum),
    }

    return lms_data



def process_email_data(text,today,maker_name):
    # Split according to the title number
    sections = text.split('\n')
    fp2_parsed_data = {}
    current_section = None

    for line in sections:
        if line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ')):
            current_section = line.strip()
            fp2_parsed_data[current_section] = {}
        elif current_section:
            key_value = line.split('\t')
            if len(key_value) == 2:
                key = key_value[0].strip()
                value = key_value[1].strip()
                fp2_parsed_data[current_section][key] = value
    
        # Convert the parsed data dictionary to a pandas DataFrame

 
    data = {
        "Date": [today],
        "Repayment Date": [fp2_parsed_data["1. Repayment Details"]["Repayment Date"]],
        "Trade Code": [fp2_parsed_data["1. Repayment Details"]["Trade Code"]],
        "Nature": "FP2.0",
        "Funder Code": [fp2_parsed_data["2. Settlement to Funder"]["Funder sub account no"]],
        "Currency": [fp2_parsed_data["1. Repayment Details"]["Payment Currency"]],
        "Principal": [fp2_parsed_data["2. Settlement to Funder"]["Settled Loan Amount"]],
        "Interest": [fp2_parsed_data["2. Settlement to Funder"]["Settled Interest"]],
        "Platform Fee": [fp2_parsed_data["2. Settlement to Funder"]["Settled PF"]],
        "Spreading": [fp2_parsed_data["3. FundPark Allocation"]["FundPark Allocation Amount"]],
        "Total Amount": [fp2_parsed_data["1. Repayment Details"]["Actual Received Amount"]],
        "Sub": [""],
        "Transfer Acc": "",
        "CSV": [""],
        "Maker": [maker_name],
        "Checker":[""],
        "Approver":["N/A"]
    }

    maker_df= pd.DataFrame(data)


    return maker_df
