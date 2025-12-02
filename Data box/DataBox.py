import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import math
import streamlit.components.v1 as components
from utils.textbreakdown import parse_lms_to_dic
from utils.textbreakdown import process_email_data
from utils.dic_data import defaults
from utils.dic_data import maker_data
import re
# ------------------ Session State Initialization ------------------
today = date.today().strftime('%Y-%m-%d')
for k, v in defaults.items():
    st.session_state.setdefault(k, v)
if "sofr_df" in st.session_state:
    sofr_df = st.session_state["sofr_df"]
else:
    st.warning("Please Import Interest Rate Info First")
if "raw_input" not in st.session_state:
    st.session_state.raw_input = ""
if "fundertype_slider" not in st.session_state:
    st.session_state.fundertype_slider = "Main"
if "ratetype_slider" not in st.session_state:
    st.session_state.ratetype_slider = "SOFR+"
if "prdtype_slider" not in st.session_state:
    st.session_state.prdtype_slider = "Regular"
# ------------------ Refresh Logic ------------------

# ------------------ Refresh Logic ------------------
def clear_text():
    # 1) 保留 'sofr_df'
    preserved = {}
    if "sofr_df" in st.session_state:
        preserved["sofr_df"] = st.session_state["sofr_df"]

    # 2) 删除除 'sofr_df' 之外的所有会话键
    for k in list(st.session_state.keys()):
        if k != "sofr_df":
            st.session_state.pop(k, None)

    # 3) 恢复保留项
    st.session_state.update(preserved)

    # 4) 让页面上的所有“文本框/文本域”立即显示为空
    #    （根据你的实际页面，把文本类控件的 key 都列进来）
    TEXT_KEYS = [
        "bulk_text",   # 主页面：LMS 数据粘贴区（textarea）
        "raw_input",   # 主页面：Email 数据粘贴区（textarea）
        "maker_name",  # 侧边栏：Maker Name（text_input）
        # 如果还有其他 text_input/textarea 的 key，继续加在这里
        # 例如： "remarks", "deal_note", ...
    ]
    for tk in TEXT_KEYS:
        st.session_state[tk] = ""  # 直接赋空串，控件会被清空

# ------------------ Utility ------------------
def on_bulk_text_change():
    text = st.session_state["bulk_text"]
    values = parse_lms_to_dic(text)

    for k in defaults.keys():
        if k in values:
            val = values[k]

            # For Date
            if k in {"sme_drawdown", "funder_drawdown", "last_funder_submission", "repayment_date"}:
                if isinstance(val, str):
                    try:
                        st.session_state[k] = datetime.strptime(val, "%Y-%m-%d").date()
                    except Exception:
                        pass
                elif isinstance(val, datetime):
                    st.session_state[k] = val.date()
                elif isinstance(val, date):
                    st.session_state[k] = val

            # For INT
            elif k in {"sme_tenor", "sme_mit"}:
                try:
                    st.session_state[k] = int(val)
                except Exception:
                    pass

            # For float
            elif k in {
                "repayment_amount","outstanding_principal","principal","bank_charge",
                "sme_sysint","sme_sysodint","waived_bankcharge","waived_smeint",
                "waived_smeodint","surcharge_item","rtb_sys","funder_sysint",
                "funder_intrate","platform_fee","spreading_sysint"
            }:
                try:
                    st.session_state[k] = float(val)
                except Exception:
                    pass

            # for str
            else:
                st.session_state[k] = str(val)

def adjust_drawdown(drawdown_date: datetime, t0_date: date = date(2025, 6, 23)) -> date:
    if drawdown_date >= t0_date:
        drawdown_date -= timedelta(days=1)
    return drawdown_date

def trunc(num, digits):
    factor = 10 ** digits
    return math.trunc(num * factor) / factor

def get_prdtype(drawdown_id):
    s = "" if drawdown_id is None else str(drawdown_id)
    s_norm = s.strip().upper()
    zero_overdue = ['-COS-PL','-COSB-PL','-VEH-PL','-3CP-PL','PLCOS','PLCOS','PLPV','PL3C','NSDPL']#nooverdue
    rfpo_code = ['-IMP-RF','-IMP-PO','-LOG-RF']#RFPO

    if any(code in s_norm for code in (c.upper() for c in zero_overdue)):
        return "PL-novd"
    if any(code in s_norm for code in (c.upper() for c in rfpo_code)) or s_norm.startswith(("F-", "P-")):
        return "RFPO"
    return "Regular"

    
def get_funder_type(funder_id):
    zero_intrate_funder = [ 'FP0056','FP0000']
    notzero_intrate_funder = ['FP0057','FP0053']
    if funder_id in zero_intrate_funder:
        return "Zero"
    elif funder_id in notzero_intrate_funder:
        return "Main"
    else:
        return "Main"
    
def get_rate_type(rate_info):
    if "sofr" in rate_info.lower():
        return "SOFR+"
    elif "hibor" in rate_info.lower():
        return "HIBOR+"
    else:
        return "Fixed"

# ------------------ Sider bar ------------------------------------
opstype = st.sidebar.selectbox("OpsType", ["Repayment", "Rollover"], index=0)
maker_name = st.sidebar.text_input("Maker Name")
# ------------------ Main PAGE: Column 1 ------------------------------------
st.header("Data Processer")
col1, col2 = st.columns([3, 2])
with col1:
    subcol1, subcol2, subcol3 = st.columns([3,1,1])
    with subcol1:
        data_source = st.radio("", ["LMS", "Email"], index=0, horizontal=True, label_visibility="collapsed")
    with subcol2:
        output_button = st.button("Output")
    with subcol3:
        clean_button = st.button("Clean",on_click=clear_text)
    if data_source == "LMS":
        raw_input = st.text_area("Paste Your Data Here",key="bulk_text", height=130,on_change=on_bulk_text_change)
    if data_source == "Email":
        raw_input = st.text_area("Paste Your Data Here", height=120, key="raw_input")
    #can we add warnings here?
# ------------------ Maker df Preparation ------------------------------------
maker_df = pd.DataFrame([maker_data])
# ------------------ Main PAGE: Column 1 ------------------------------------
with col2:
    trade_panel= st.container(border=True)
    with trade_panel:
        tradepancol1,tradepancol2 = st.columns([2, 1])
        with tradepancol1:
            drawdown_id = st.session_state["drawdown_id"]
            st.metric(label="Drawdown ID: ", value=drawdown_id)
            currency = st.session_state["currency"]
            st.metric(label="Currency: ", value=currency)
            funder_id = st.session_state["funder_id"]
            st.metric(label="Funder ID: ", value=funder_id)
        with tradepancol2:
            xdj_switch = st.toggle("小店金", value=False)
            sme_intrate = st.session_state["sme_intrate"]
            st.metric(label="Calculation Method: ", value=sme_intrate)
            funder_intrate = st.session_state["funder_intrate"]
            if funder_intrate == 0:
                numbers = re.findall(r"\d+\.?\d*", sme_intrate)
                funder_intrate = float(numbers[-1]) if numbers else None
            st.metric(label="Interest Rate: ", value=funder_intrate)
         
    with st.expander("Date Information", expanded=True):
        #Repayment_date
        subcol1,subcol2 = st.columns([1, 1])
        with subcol1:
            sme_date_panel = st.container(border=True)
            with sme_date_panel:
                sme_drawdown = st.date_input("SME drawdown date",value=st.session_state["sme_drawdown"],key="sme_drawdown")
                sme_tenor = st.number_input("Tenor (days)", min_value=0, value=int(st.session_state["sme_tenor"]), step=1,key="sme_tenor")#needs to change to timedelta
                sme_tenor_days = timedelta(days=int(sme_tenor))
                expected_repaydate = sme_drawdown + sme_tenor_days
                sme_drawdown_cal = adjust_drawdown(sme_drawdown)
                sme_mit = st.number_input("MIT (days)", min_value=0, max_value=50,value=int(st.session_state["sme_mit"]), step=1,key="sme_mit")#needs to change to timedelta
                sme_mit_days = timedelta(days=int(sme_mit))
                mit_repaydate = sme_drawdown_cal + sme_mit_days
                repayment_date = st.date_input("Repayment date",value=st.session_state["repayment_date"],key="repayment_date")
                if opstype == "Rollover":
                    repayment_date -= timedelta(days=1)
        with subcol2:
            funder_date_panel = st.container(border=True)
            with funder_date_panel:
                outstanding_principal = st.number_input("Outstanding Principal", min_value=0.00, value=float(st.session_state["outstanding_principal"]), step=0.01,format="%.2f",key="outstanding_principal")
                funder_drawdown = st.date_input("Funder drawdown date",value=st.session_state["funder_drawdown"],key="funder_drawdown")
                funder_drawdown_cal = adjust_drawdown(funder_drawdown)
                last_funder_submission = st.date_input("Last Funder Submission Date",value=st.session_state["last_funder_submission"],key="last_funder_submission")
        
    with st.expander("SME Repayment", expanded=True):
        sme_repay_panel = st.container(border=True)
        with sme_repay_panel:
            pancol1,pancol2 = st.columns([1, 1])
            with pancol1:
                repayment_amount = st.number_input("Repayment", min_value=0.00, value=float(st.session_state["repayment_amount"]), step=0.01,format="%.2f",key="repayment_amount")
                bank_charge = st.number_input("Bank Charge", min_value=0.00, value=float(st.session_state["bank_charge"]), step=0.01,format="%.2f",key="bank_charge")
                sme_sysint = st.number_input("SME Interest", min_value=0.00, value=float(st.session_state["sme_sysint"]), step=0.01,format="%.2f",key="sme_sysint")
                sme_sysodint = st.number_input("SME Overdue Interest", min_value=0.00, value=float(st.session_state["sme_sysodint"]), step=0.01,format="%.2f",key="sme_sysodint")
                rtb_sys = st.number_input("Return to Borrower", min_value=0.00, value=float(st.session_state["rtb_sys"]), step=0.01,format="%.2f",key="rtb_sys")
            with pancol2:
                principal = st.number_input("Principal", min_value=0.00,  value=float(st.session_state["principal"]), step=0.01,format="%.2f",key="principal")
                waived_bankcharge = st.number_input("Waived Banks Charge",min_value = bank_charge *-1, max_value=0.00,  value=float(st.session_state["waived_bankcharge"]), step=0.01,format="%.2f",key="waived_bankcharge")
                waived_smeint = st.number_input("Waived SME Interest", min_value = sme_sysint *-1,max_value=0.00, value=float(st.session_state["waived_smeint"]), step=0.01,format="%.2f",key="waived_smeint")
                waived_smeodint = st.number_input("Waived Overdue SME Interest",min_value = sme_sysodint *-1, max_value=0.00, value=float(st.session_state["waived_smeodint"]), step=0.01,format="%.2f",key="waived_smeodint")
                surcharge_item = st.number_input("Surcharge Item", min_value=0.00, value=float(st.session_state["surcharge_item"]), step=0.01,format="%.2f",key="surcharge_item")
    with st.expander("Funder/Spreading Collection", expanded=True):    
        collect_panel = st.container(border=True)
        with collect_panel:
            colpancol1,colpancol2 = st.columns([1, 1])
            with colpancol1:
                funder_sysint = st.number_input("Funder Interest", min_value=0.00, value=float(st.session_state["funder_sysint"]), step=0.01,format="%.2f",key="funder_sysint")
                platform_fee = st.number_input("Platform Fee", max_value=0.00, value=float(st.session_state["platform_fee"]), step=0.01,format="%.2f",key="platform_fee")
            with colpancol2:
                funder_sysallocation= float(st.session_state["funder_sysallocation"])
                spreading_sysint = st.number_input("FundPark Spreading", value=float(st.session_state["spreading_sysint"]), step=0.01,format="%.2f",key="spreading_sysint")

if output_button and raw_input.strip():
    if data_source == "LMS":
        with col1:
            outputsubcol1,outputsubcol2 = st.columns([1, 2])
            with outputsubcol1:
                st.session_state.fundertype_slider = get_funder_type(funder_id)
                st.session_state.ratetype_slider = get_rate_type(sme_intrate)
                st.session_state.prdtype_slider = get_prdtype(drawdown_id)
                fundertype = st.sidebar.select_slider("Funder Type", options=["Main", "Zero", "Fixed"], value=st.session_state.fundertype_slider,label_visibility="collapsed", key="fundertype_slider")
                ratetype = st.sidebar.select_slider("Rate Type", options=["SOFR+", "HIBOR+", "Fixed"],value=st.session_state.ratetype_slider,label_visibility="collapsed", key="ratetype_slider")
                prdtype = st.sidebar.select_slider("Product Type", options=["Regular", "PL-novd", "RFPO"],value=st.session_state.prdtype_slider,label_visibility="collapsed", key="prdtype_slider")

    #Calculation Part
        if prdtype == "RFPO":
            principal_cal = outstanding_principal
            sme_drawdown_cal = last_funder_submission if last_funder_submission != date(1999, 1, 1) else sme_drawdown_cal
        else:
            principal_cal = principal



        float_rate = 'Daily Calculated Blended HIBOR' if ratetype == 'HIBOR+' else 'SOFR'
        hdays = (repayment_date - sme_drawdown_cal).days
        regul_floatsum = sofr_df.loc[(sofr_df['Calculation Date'] > sme_drawdown_cal) & 
                                    (sofr_df['Calculation Date'] <= repayment_date), float_rate].sum()
        overdue_interest = 0
        if repayment_date <= mit_repaydate:
            note = "MIT"
            mit_fillrate = sofr_df.loc[(sofr_df['Calculation Date'] == repayment_date), float_rate].iloc[0]
            floatsum = (sme_mit  - hdays) * mit_fillrate + regul_floatsum
            hdays = sme_mit
        elif repayment_date > expected_repaydate:
            note = "Overdue"
            floatsum = regul_floatsum
            overdue_hdays = (repayment_date - expected_repaydate).days
            overduesum = sofr_df.loc[(sofr_df['Calculation Date'] > expected_repaydate) & 
                                    (sofr_df['Calculation Date'] <= repayment_date), float_rate].sum()
        else:
            note = "Normal"
            floatsum = regul_floatsum

        sme_interest = 0
        overdue_interest = 0
        if ratetype == "Fixed":
            floatsum = 0
            overduesum =0
        sme_interest = trunc((floatsum + funder_intrate * hdays) / 360 * principal_cal * 0.01, 2)
        if note == "Overdue":
            overdue_interest = trunc((overduesum + funder_intrate * overdue_hdays) / 360 * principal_cal * 0.01, 2)
        if note != "Overdue" or prdtype in ["PL-novd", "RFPO"]:
            overdue_interest = 0
        
        sme_allinterest = sme_interest + overdue_interest

    
        if prdtype == "RFPO" or funder_drawdown_cal == sme_drawdown_cal:
            funder_interest = sme_interest + overdue_interest
        else:
            funder_hdays = (repayment_date - funder_drawdown_cal).days
            funder_regul_floatsum = sofr_df.loc[(sofr_df['Calculation Date'] > funder_drawdown_cal) & (sofr_df['Calculation Date'] <= repayment_date), float_rate].sum()
            funder_overdue_interest = 0
            if ratetype == "Fixed":
                funder_regul_floatsum = 0
            if funder_drawdown <= expected_repaydate:
                funder_regulint = trunc((funder_regul_floatsum + funder_intrate * funder_hdays) / 360 * principal_cal * 0.01, 2)
                funder_odint = overdue_interest
                funder_interest = funder_regulint + funder_odint

            else:
                funder_overdue_hdays = (funder_drawdown_cal - repayment_date).days
                funder_overduesum = sofr_df.loc[(sofr_df['Calculation Date'] > funder_drawdown_cal) & 
                                            (sofr_df['Calculation Date'] <= repayment_date), float_rate].sum()
                if ratetype == "Fixed":
                    funder_regul_floatsum = 0

                funder_interest = trunc((funder_regul_floatsum + funder_intrate * funder_hdays) / 360 * principal_cal * 0.01, 2)*2
#allocation part
        
        waived_interest = waived_smeint + waived_smeodint
        waived_interest = waived_interest * -1
        waived_bankcharge = waived_bankcharge * -1
        if xdj_switch == 0:
            funder_interest += surcharge_item - waived_interest
            if funder_interest >= waived_bankcharge and fundertype == "Main":
                funder_interest -= waived_bankcharge

        if platform_fee != 0:
            platform_fee = funder_interest * 0.01
        else:
            platform_fee = 0

        if xdj_switch:
            funder_interest += surcharge_item
            if funder_interest >= waived_bankcharge and fundertype == "Main":
                funder_interest -= waived_bankcharge

        if fundertype == "Zero":
            funder_interest = 0

        spreading = (sme_interest + overdue_interest) + surcharge_item - waived_bankcharge - waived_interest - funder_interest

        with col1:
            #for calcu
            threshold = 0.02
            def check_differences(system,calculation, threshold):
                status = "ok" if abs(calculation - system) < threshold else "err"
                return abs(calculation - system), f"{status}: {round(calculation - system,2)}"
            smegap, sme_checker= check_differences( sme_sysint + sme_sysodint ,sme_allinterest, threshold)
            fundergap,funder_checker= check_differences(funder_sysint,funder_interest, threshold)
            spreadinggap,spreading_checker = check_differences(spreading_sysint,spreading, threshold)

            resubcol1, resubcol2, resubcol3, resubcol4 = st.columns([1, 3, 3, 3])
            with resubcol1:
                st.badge(" Checker:",color="blue")
            with resubcol2:
                st.metric(label="SME:", value=f"{sme_checker}")
            with resubcol3:
                st.metric(label="Funder:", value=f"{funder_checker}")
            with resubcol4:
                st.metric(label="Spreading:", value=f"{spreading_checker}")

            warnings = []
            if outstanding_principal - principal < 10 and outstanding_principal - principal > 0.01:
                warnings.append("⚠️ Fully settle failed: outstanding_principal - principal_amount < 10")

            left = principal + funder_sysint - platform_fee + spreading_sysint
            right = repayment_amount - bank_charge
            if abs(left - right)>0.001:
                warnings.append(f"⚠️ Condition failed: cash flow mismatch — left side {left:.2f} ≠ right side {right:.2f}")
            if rtb_sys != 0:
                warnings.append(f"⚠️ Condition failed: rtb_sys should be 0, but is {rtb_sys}")
            if fundertype == "Main" and funder_sysint == 0:
                warnings.append("⚠️ Funder code violation: funder type is 'Main' but Funder interest is 0 — main funders are expected to earn interest.")
            if fundertype == "Zero" and funder_sysint != 0:
                warnings.append(f"⚠️ Funder code violation: funder type is 'Zero' but Funder interest is {funder_sysint} — zero-interest funders should not earn interest.")
            st.session_state.warnings = warnings
            if warnings:
                with st.expander("⚠️ Warnings"):
                    for w in warnings:
                        st.warning(w)


            maker_df["Date"] = today
            maker_df["Nature"] = "FP2.0"if data_source  == "Email" else opstype,
            maker_df["Maker"] =maker_name
            maker_df['Repayment Date'] = repayment_date
            maker_df["Drawdown ID"] = drawdown_id
            maker_df["Funder Code"] = funder_id
            maker_df["Currency"] = currency
            maker_df["Principal"] = principal
            maker_df["Interest"] = funder_sysint
            maker_df["Platform Fee"] = platform_fee
            maker_df["Spreading"] = spreading_sysint
            maker_df["Sub"] = bank_charge
            maker_df["Total Amount"] = repayment_amount - bank_charge
            mxgap =  max(smegap,fundergap,spreadinggap)
            checker = "ok" if mxgap < threshold else "err"
            maker_df["Checker"] = f"{checker}: {round(mxgap,2)}"
    if data_source == "Email":
        with col1:
            maker_df = process_email_data(raw_input,today,maker_name)
    with col1:
        st.dataframe(maker_df)
           
  
        second_row = maker_df.iloc[0]
        row_str = '\t'.join([str(v) for v in second_row.values])
                        #For Copy Botton
        styled_button = f"""
                    <style>
                        .copy-btn {{
                            background-color: #ffffffff;
                            color: #5063b8ff;
                            border: 2px solid #e6f1fbff";
                            padding: 1em 1em;
                            border-radius: 0.5em;
                            font-size: 1em;
                            font-family: sans-serif; 
                            cursor: pointer;
                            transition: background-color 0.3s ease;
                        }}
                        .copy-btn:hover {{
                            background-color: #e6f1fbff;
                        }}
                        .copy-msg {{
                            margin-top: 0.5em;
                            color: #00BCD4;
                            font-weight: bold;
                        }}
                    </style>
                    <button class="copy-btn" onclick="navigator.clipboard.writeText(`{row_str}`); document.getElementById('copied').innerText='Copied';">
                        Copy the trade info
                    </button>
                    <div id="copied" class="copy-msg"></div>
                    """

        components.html(styled_button, height=120)

        st.write("SME Interest",sme_interest)
        st.write("SME Overdue Interest",overdue_interest)

if output_button and not raw_input.strip():
    with col1:
        st.warning("please paste the data first")
        









































    





















