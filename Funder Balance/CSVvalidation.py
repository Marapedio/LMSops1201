
# app.py
import streamlit as st
import pandas as pd
import re
import csv
from io import StringIO
from typing import List, Dict
from datetime import date

st.set_page_config(page_title="Approval → Transfers & CSV Reconcile", layout="wide")

# =========================
# 固定账户配置（你提供的）
# =========================
ACCOUNT_2691 = "001302691"
ACCOUNT_2685 = "001302685"
FUNDER_ACCOUNT_MAP: Dict[str, str] = {
    "FP0000": "001302728",
    "FP0056": "001302922",
    "FP0053": "001302895",
    "FP0057": "001302931",
}

# =========================
# 工具函数：列字母转索引，如 'A'->0, 'C'->2, 'AB'->27, 'AJ'->35（0-based）
# =========================
def col_letter_to_index(col_letter: str) -> int:
    col_letter = col_letter.strip().upper()
    idx = 0
    for ch in col_letter:
        if not ('A' <= ch <= 'Z'):
            raise ValueError(f"非法列字母: {col_letter}")
        idx = idx * 26 + (ord(ch) - ord('A') + 1)
    return idx - 1  # 0-based 索引

# =========================
# 右侧：输入与上传（col2）
# =========================
col1, col2 = st.columns([3, 1])

with col2:
    st.markdown("### 1) 粘贴无表头的 Approval 数据（从 Trade Code 到 Total Amount）")
    # 固定表头（无表头粘贴时用）
    EXPECTED_COLS: List[str] = [
        "Trade Code", "Nature", "Funder Code", "Currency",
        "Principal", "Interest", "Platform Fee", "Spreading", "Total Amount"
    ]
    ID_COLS = {"Trade Code", "Funder Code", "Currency", "Nature"}
    NUM_COLS = {"Principal", "Interest", "Platform Fee", "Spreading", "Total Amount"}

    txt = st.text_area(
        "Paste here (TSV/CSV; no header)",
        height=220,
        placeholder="Example: \nM-XXXX-41056\tRepayment\tFP0053\tUSD\t117000\t472.25\t0\t0\t117,472.25"
    )

    # MMDD 使用当天（固定）
    mmdd = date.today().strftime("%m%d")
    rpt_prefix = "RPTXX"
    intsp_prefix = "INTSP"

    st.markdown("#### 2) 在此上传 DBS CSV")
    uploaded_csv = st.file_uploader("Upload DBS CSV", type=["csv"])

    # ---------- 解析无表头的粘贴文本 ----------
    def parse_rows_no_header(s: str, expected_cols: List[str]) -> pd.DataFrame:
        s = s.strip("\n")
        if not s:
            return pd.DataFrame(columns=expected_cols)
        lines = [ln for ln in s.splitlines() if ln.strip()]
        sep = "\t" if any("\t" in ln for ln in lines) else ","
        rows = [ln.split(sep) for ln in lines]
        rows = [[cell.strip() for cell in r] for r in rows]
        target_len = len(expected_cols)
        normalized = []
        for r in rows:
            if len(r) < target_len:
                normalized.append(r + [""] * (target_len - len(r)))
            else:
                normalized.append(r[:target_len])
        df = pd.DataFrame(normalized, columns=expected_cols)
        return df

    # ---------- 清洗类型 ----------
    def clean_types(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in df.columns:
            df[c] = df[c].astype(str).str.strip()
        for c in df.columns:
            if c in ID_COLS:
                df[c] = df[c].astype("string")
        for c in df.columns:
            if c in NUM_COLS:
                s = df[c].astype("string").str.replace(",", "", regex=False).str.strip()
                s = s.replace({"": pd.NA})
                df[c] = s.astype(float)
        return df

    # ---------- 构建明细（Posting/金额；CODE 固定取 Trade Code 后 5 位；类型仅 RPTXX/INTSP） ----------
    def build_lines(df: pd.DataFrame, tol: float = 1e-6,
                    rpt_prefix: str = "RPTXX",
                    intsp_prefix: str = "INTSP",
                    mmdd: str = "0000") -> pd.DataFrame:
        df = df.copy()
        df["Trade Code Raw"] = df["Trade Code"].astype("string")
        p = df["Principal"].fillna(0.0)
        i = df["Interest"].fillna(0.0)
        f = df["Platform Fee"].fillna(0.0)
        s = df["Spreading"].fillna(0.0)
        df["RPTXX"] = (p + i + f).round(2)
        df["INTSP"] = s.round(2)

        last5 = df["Trade Code"].astype("string").str.extract(r"(\d{5})$")[0]
        df["TradeCodeLast5"] = last5
        df["CODE"] = last5
        df["Funder Code"] = df["Funder Code"].astype("string").str.strip()
        df["Currency"]    = df["Currency"].astype("string").str.strip()

        rows = []
        for _, r in df.iterrows():
            code = r["CODE"]
            fund = r["Funder Code"]
            ccy  = r["Currency"]
            tc_raw = r["Trade Code Raw"]
            code_missing = pd.isna(code) or str(code).strip() == ""

            # RPTXX 行
            amt_rpt = r["RPTXX"]
            if pd.notna(amt_rpt) and abs(float(amt_rpt)) > tol:
                posting = f"{rpt_prefix}{(code or '')}01{mmdd}" if not code_missing else ""
                rows.append({
                    "Type": "RPTXX",
                    "Posting": posting,
                    "CODE": code,
                    "MMDD": mmdd,
                    "Trade Code Raw": tc_raw,
                    "TradeCodeLast5": code,
                    "Funder Code": fund,
                    "Currency": ccy,
                    "Amount": float(amt_rpt)
                })

            # INTSP 行
            amt_sp = r["INTSP"]
            if pd.notna(amt_sp) and abs(float(amt_sp)) > tol:
                posting = f"{intsp_prefix}{(code or '')}01{mmdd}" if not code_missing else ""
                rows.append({
                    "Type": "INTSP",
                    "Posting": posting,
                    "CODE": code,
                    "MMDD": mmdd,
                    "Trade Code Raw": tc_raw,
                    "TradeCodeLast5": code,
                    "Funder Code": fund,
                    "Currency": ccy,
                    "Amount": float(amt_sp)
                })

        lines_df = pd.DataFrame(rows, columns=[
            "Type", "Posting", "CODE", "MMDD",
            "Trade Code Raw", "TradeCodeLast5", "Funder Code", "Currency", "Amount"
        ])
        return lines_df

    # ---------- 生成转账腿（保留 Valid；RPTXX/INTSP 路由规则） ----------
    def generate_transfers_full(
        lines_df: pd.DataFrame,
        account_2691: str,
        account_2685: str,
        funder_account_map: Dict[str, str],
        tol: float = 1e-6
    ) -> pd.DataFrame:
        rows = []
        for _, r in lines_df.iterrows():
            posting   = str(r.get("Posting", "")).strip()
            rtype     = str(r.get("Type", "")).strip()           # RPTXX / INTSP
            code      = r.get("CODE", None)
            funder    = str(r.get("Funder Code", "")).strip()
            ccy       = str(r.get("Currency", "")).strip()
            amount    = r.get("Amount", None)

            issue = []
            valid = True
            if code is None or str(code).strip() == "":
                issue.append("CODE missing (Trade Code must end with 5 digits)")
                valid = False
            if pd.isna(amount):
                issue.append("Amount is NA")
                valid = False
            else:
                try:
                    amount = float(amount)
                except Exception:
                    issue.append("Amount not numeric")
                    valid = False
            if not ccy:
                issue.append("Missing Currency")
                valid = False
            if valid and abs(amount) <= tol:
                issue.append("Amount ~ 0")
                valid = False

            debit = credit = None
            amt_out = None
            if valid:
                if rtype == "RPTXX":
                    target_acct = funder_account_map.get(funder)
                    if not target_acct:
                        issue.append(f"Funder {funder} not mapped")
                        valid = False
                    else:
                        debit  = ACCOUNT_2691
                        credit = target_acct
                        amt_out = abs(amount)
                elif rtype == "INTSP":
                    if amount < 0:
                        debit  = ACCOUNT_2685
                        credit = ACCOUNT_2691
                        amt_out = abs(amount)
                    else:
                        debit  = ACCOUNT_2691
                        credit = ACCOUNT_2685
                        amt_out = amount
                else:
                    issue.append("Unknown Type")
                    valid = False

            rows.append({
                "Trade Code Raw": r.get("Trade Code Raw", None),
                "Posting": posting,
                "Currency": ccy,
                "Amount": float(amt_out) if (valid and amt_out is not None) else None,
                "DebitAccount": debit,
                "CreditAccount": credit,
                "Valid": valid,
                "Issue": "; ".join(issue) if issue else ""
            })

        transfers_full_df = pd.DataFrame(rows)
        return transfers_full_df

    # ---------- 解析 CSV（按你指定的列字母抽取） ---------
def col_letter_to_index(col_letter: str) -> int:
    col_letter = col_letter.strip().upper()
    idx = 0
    for ch in col_letter:
        if not ('A' <= ch <= 'Z'):
            raise ValueError(f"非法列字母: {col_letter}")
        idx = idx * 26 + (ord(ch) - ord('A') + 1)
    return idx - 1  # 0-based

def parse_csv_by_letters(uploaded_csv) -> pd.DataFrame:
    """
    使用列字母抽取 CSV：
    C → DebitAccount, D → Currency, E → Key(前10位), P → CreditAccount,
    AB → Amount（更稳健的解析）, AJ → TradeCodeRaw
    - 允许：千位逗号、负号、括号负数、前后空白、夹杂货币符号。
    - 仅当确实无法解析成数值时，Amount 才为 None。
    """
    # 读取整份文本（支持 Streamlit UploadedFile 或路径）
    if hasattr(uploaded_csv, "getvalue"):
        text = uploaded_csv.getvalue().decode("utf-8", errors="replace")
    else:
        with open(uploaded_csv, "rb") as f:
            text = f.read().decode("utf-8", errors="replace")

    # 目标列索引
    c_i  = col_letter_to_index('C')   # Debit
    d_i  = col_letter_to_index('D')   # Currency
    e_i  = col_letter_to_index('E')   # Key source (前10位)
    p_i  = col_letter_to_index('P')   # Credit
    ab_i = col_letter_to_index('AB')  # Amount
    aj_i = col_letter_to_index('AJ')  # TradeCodeRaw

    def parse_amount_relaxed(raw: str):
        """
        更宽松的金额解析：
        - 移除非数字/符号的前缀（如 'USD ', '$'）
        - 允许千位逗号
        - 允许负号 '-'
        - 允许括号负数 '(1,234.56)' → -1234.56
        - 允许前后空白
        - 若为空或无法转 float，返回 None
        """
        if raw is None:
            return None
        s = str(raw).strip()
        if s == "":
            return None

        # 括号负数记号
        is_paren_negative = s.startswith("(") and s.endswith(")")
        if is_paren_negative:
            s = s[1:-1]  # 去掉括号

        # 去掉可能的货币符号/文本（保留数字、逗号、小数点、负号）
        s = re.sub(r"[^\d,\.\-]", "", s)

        # 去掉千位逗号
        s = s.replace(",", "")

        # 空检查
        if s in ("", "-", "."):
            return None

        try:
            val = float(s)
            if is_paren_negative:
                val = -val
            return val
        except Exception:
            return None

    rows = []
    for r_idx, cols in enumerate(csv.reader(StringIO(text), delimiter=",", quotechar='"')):
        if not cols:
            continue

        # 安全取值：不足列时返回 ""
        def safe_get(i):
            return cols[i].strip() if i < len(cols) and cols[i] is not None else ""

        c_debit   = safe_get(c_i)
        d_ccy     = safe_get(d_i)
        e_key_src = safe_get(e_i)
        p_credit  = safe_get(p_i)
        ab_amt    = safe_get(ab_i)     # ← 仍保留你的这行，保证不会越界
        aj_trade  = safe_get(aj_i)

        # 使用更宽松的金额解析
        amt = parse_amount_relaxed(ab_amt)

        # E 列前 10 位作为 key
        e_key = e_key_src[:10] if e_key_src else ""

        rows.append({
            "CSV_RowIndex": r_idx,
            "CSV_Key_E10": e_key,           # 与 Posting 前10位比对
            "CSV_Debit": c_debit,
            "CSV_Credit": p_credit,
            "CSV_Currency": d_ccy,
            "CSV_Amount": amt,              # 更稳妥地读到了数值
            "CSV_TradeCodeRaw": aj_trade,
            "CSV_E_Full": e_key_src,
            "CSV_AB_Raw": ab_amt            # 保留原始 AB 文本以便排查
        })

    csv_view = pd.DataFrame(rows)
    for col in ["CSV_Debit", "CSV_Credit", "CSV_Currency", "CSV_Key_E10", "CSV_TradeCodeRaw", "CSV_E_Full", "CSV_AB_Raw"]:
        csv_view[col] = csv_view[col].astype("string")
        
    return csv_view

    # ---------- 对账：按 Posting 前10位 ↔ CSV E 前10位 比对 ----------
def reconcile_by_letter_columns(transfers_full_view: pd.DataFrame,
                                    csv_view: pd.DataFrame,
                                    amount_tol: float = 0.01) -> pd.DataFrame:
        tf = transfers_full_view.copy()
        tf["PostingKey"] = tf["Posting"].astype("string").str[:10]
        for col in ["Trade Code Raw", "Posting", "Currency", "DebitAccount", "CreditAccount"]:
            tf[col] = tf[col].astype("string")

        merged = tf.merge(
            csv_view,
            how="left",
            left_on="PostingKey",
            right_on="CSV_Key_E10",
            suffixes=("_TF", "_CSV")
        )

        def status_row(r):
            # Key 没接上 → CSV 缺失
            if pd.isna(r.get("CSV_Debit")) and pd.isna(r.get("CSV_Credit")) and pd.isna(r.get("CSV_Amount")):
                return "MISSING_IN_CSV"

            debit_ok = (str(r.get("DebitAccount", "")) == str(r.get("CSV_Debit", "")))
            credit_ok= (str(r.get("CreditAccount","")) == str(r.get("CSV_Credit","")))
            ccy_ok   = (str(r.get("Currency","")) == str(r.get("CSV_Currency","")))
            amt_tf   = r.get("Amount", None)
            amt_csv  = r.get("CSV_Amount", None)
            amt_ok   = (pd.notna(amt_tf) and pd.notna(amt_csv) and abs(float(amt_tf) - float(amt_csv)) <= amount_tol)

            if debit_ok and credit_ok and ccy_ok and amt_ok:
                return "OK"
            if not debit_ok:
                return "ACCOUNT_DEBIT_MISMATCH"
            if not credit_ok:
                return "ACCOUNT_CREDIT_MISMATCH"
            if not ccy_ok:
                return "CURRENCY_MISMATCH"
            if not amt_ok:
                return "AMOUNT_MISMATCH"
            return "UNKNOWN"

        merged["MatchStatus"] = merged.apply(status_row, axis=1)

        out_cols = [
            "MatchStatus",
            "PostingKey", "CSV_Key_E10",
            "Posting", "CSV_E_Full",
            "Currency", "CSV_Currency",
            "Amount", "CSV_Amount",
            "DebitAccount", "CSV_Debit",
            "CreditAccount", "CSV_Credit",
            "Trade Code Raw", "CSV_TradeCodeRaw",
        ]
        for c in out_cols:
            if c not in merged.columns:
                merged[c] = pd.NA
        result = merged[out_cols]
        return result

# =========================
# 左侧：展示（col1）
# =========================
with col1:
    st.markdown("#### Transfers")
    if txt.strip():
        # 解析 → 清洗 → 明细
        raw_df   = parse_rows_no_header(txt, EXPECTED_COLS)
        df_clean = clean_types(raw_df)
        lines_df = build_lines(df_clean, rpt_prefix=rpt_prefix, intsp_prefix=intsp_prefix, mmdd=mmdd)

        # 生成转账（保留 Valid）
        transfers_full = generate_transfers_full(lines_df, ACCOUNT_2691, ACCOUNT_2685, FUNDER_ACCOUNT_MAP)

        # 👉 只展示你指定的列顺序
        transfers_full_view = transfers_full[[
            "Trade Code Raw","Posting","Currency","Amount","DebitAccount","CreditAccount","Valid"
        ]]
        st.dataframe(transfers_full_view, use_container_width=True)

        # ===== 如果右侧已上传 CSV，则进行比对并展示所有信息 =====
        st.markdown("### 与 CSV 的比对结果（按列字母规则）")
        if uploaded_csv:
            csv_view = parse_csv_by_letters(uploaded_csv)
            recon_df = reconcile_by_letter_columns(transfers_full_view, csv_view, amount_tol=0.01)
            st.dataframe(recon_df, use_container_width=True)
        else:
            st.info("请在右侧文字框下面上传 DBS CSV 后，这里将显示比对结果。")



# st.title("可编辑 DataFrame 示例")

# df = pd.DataFrame({
#     "tradecode": ["Alice", "Bob"],
#     "funder": [25, 30],
#     "zz": ["Maker", "Checker"],
#     "active": [True, False],
# })

# # 让用户在页面上编辑
# edited_df = st.data_editor(
#     df,
#     num_rows="dynamic",  # 允许新增/删除行
#     use_container_width=True
# )

# st.subheader("编辑后的结果")
# st.write(edited_df)
