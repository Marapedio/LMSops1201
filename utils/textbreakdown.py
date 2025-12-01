
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



def normalize_key(key: str) -> str:
    """统一键名：小写、去掉句点/冒号、合并空格。"""
    k = key.lower()
    k = re.sub(r"[\\.:]", "", k)
    k = re.sub(r"\\s+", " ", k).strip()
    return k

# 把各种可能的写法映射到“标准键名”
CANONICAL_KEY_MAP = {
    # Section 标题
    "1 repayment details": "1. Repayment Details",
    "2 settlement to funder": "2. Settlement to Funder",
    "3 fundpark allocation": "3. FundPark Allocation",
    "4 return to borrower": "4. Return to Borrower",

    # Repayment Details
    "repayment date": "Repayment Date",
    "trade code": "Trade Code",
    "payment currency": "Payment Currency",
    "actual received amount": "Actual Received Amount",
    "actural receviced amount": "Actual Received Amount",   # 邮件里的拼写
    "actural received amount": "Actual Received Amount",
    "actual receviced amount": "Actual Received Amount",
    "payment type": "Payment Type",
    "drawdown id": "Drawdown ID",

    # Settlement to Funder
    "funder sub account no": "Funder Sub Account No",       # 去掉句点后的统一写法
    "settled loan amount": "Settled Loan Amount",
    "settled interest": "Settled Interest",
    "settled pf": "Settled PF",
    "funder allocation": "Funder Allocation",

    # FundPark Allocation
    "fundpark allocation amount": "FundPark Allocation Amount",

    # Return to Borrower
    "rtb amount": "RTB Amount",
    "bank name": "Bank Name",
    "bank a/c name": "Bank A/C Name",
    "bank a/c number": "Bank A/C Number",
    "swift code": "SWIFT Code",
}

SECTION_PATTERN = re.compile(r"^(\\d)\\.\\s*(.+)$")

def process_email_data(text: str, today: str, maker_name: str) -> pd.DataFrame:
    """
    解析新格式邮件正文，并返回 maker_df（单行 DataFrame）。
    适配：Tab 分隔、键值分两行、拼写错误、大小写/标点差异。
    """
    lines = [l.rstrip() for l in text.splitlines()]
    parsed = {}
    current_section = None

    def canonical_section(name_raw: str) -> str:
        norm = normalize_key(name_raw)
        return CANONICAL_KEY_MAP.get(norm, name_raw.strip())

    def canonical_key(key_raw: str) -> str:
        norm = normalize_key(key_raw)
        return CANONICAL_KEY_MAP.get(norm, key_raw.strip())

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        # 捕获 Section 标题，例如 "1. Repayment Details"
        m = SECTION_PATTERN.match(line)
        if m:
            sec_raw = f"{m.group(1)}. {m.group(2)}"
            current_section = canonical_section(sec_raw)
            parsed.setdefault(current_section, {})
            continue

        if current_section is None:
            # 跳过章节之前的杂项
            continue

        # 解析键值：优先 Tab 分隔；否则视为“键在一行，值在下一行”
        if "\\t" in line:
            key, value = [x.strip() for x in line.split("\\t", 1)]
        else:
            key = line.strip()
            # 向前看下一条非空行作为 value
            value = ""
            j = i
            while j < len(lines):
                nxt = lines[j].strip()
                j += 1
                if nxt:
                    value = nxt
                    break
            i = j  # 指针前移到 value 之后

        ck = canonical_key(key)
        parsed.setdefault(current_section, {})[ck] = value.strip()

    # 便捷安全取值
    def get(sec: str, key: str) -> str:
        return parsed.get(sec, {}).get(key, "")

    data = {
        "Date": [today],
        "Repayment Date": [get("1. Repayment Details", "Repayment Date")],
        "Trade Code": [get("1. Repayment Details", "Trade Code")],
        "Nature": ["FP2.0"],
        "Funder Code": [get("2. Settlement to Funder", "Funder Sub Account No")],
        "Currency": [get("1. Repayment Details", "Payment Currency")],
        "Principal": [get("2. Settlement to Funder", "Settled Loan Amount")],
        "Interest": [get("2. Settlement to Funder", "Settled Interest")],
        "Platform Fee": [get("2. Settlement to Funder", "Settled PF")],
        "Spreading": [get("3. FundPark Allocation", "FundPark Allocation Amount")],
        "Total Amount": [get("1. Repayment Details", "Actual Received Amount")],
        "Sub": [""],
        "Transfer Acc": [""],
        "CSV": [""],
        "Maker": [maker_name],
        "Checker": [""],
        "Approver": ["N/A"],
    }

    maker_df = pd.DataFrame(data)
