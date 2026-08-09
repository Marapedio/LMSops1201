from datetime import date, datetime, timedelta
import pandas as pd

defaults = {
    "drawdown_id": "",
    "repayment_id": "",
    "currency":"",
    "sme_drawdown":date(1999, 1, 1),
    "funder_drawdown": date(1999, 1, 1),
    "last_funder_submission": date(1999, 1, 1),
    "repayment_date": date(1999, 1, 1),
    "sme_tenor":int(90),
    "sme_mit":int(7),
    "repayment_amount":0.00,
    "outstanding_principal":0.00,
    "principal": 0.00,
    "bank_charge":0.00,
    "sme_intrate":"",
    "intmethod":"",
    "sme_sysint":0.00,
    "sme_sysodint":0.00,
    "waived_bankcharge": 0.00,
    "waived_smeint": 0.00,
    "waived_smeodint": 0.00,
    "surcharge_item": 0.00,
    "rtb_sys":0.00,
    "funder_id":"",
    "funder_sysint":0.00,
    "funder_intrate":0.00,
    "platform_fee":0.00,
    "funder_sysallocation":0.00,
    "spreading_sysint":0.00
}

maker_data = {
        "Date": "",
        "Repayment Date": "",
        "Drawdown ID": "",
        "Nature": "",
        "Funder Code": "",
        "Currency": "",
        "Principal": "",
        "Interest": "",
        "Platform Fee": "",
        "Spreading": "",
        "Total Amount": "",
        "Sub": "",
        "Transfer Acc": "",
        "CSV": "",
        "Maker": "",
        "Checker": "",
        "Approver": "",
        "Note": "",
        "Note2":""# this one is for csv reference number
    }

hibor_refixing_date = {
    date(2024, 9, 16): 1.8453,
    date(2024, 10, 15): 2.35242,
    date(2024, 11, 15): 3.72318,
    date(2024, 12, 16): 3.72121,
    date(2025, 1, 15): 2.83682,
    date(2025, 2, 17): 2.72545,
    date(2025, 3, 17): 1.99697,
    date(2025, 4, 15): 1.53121,
    date(2025, 5, 15): 1.65485,
    date(2025, 6, 16): 1.70455,
    date(2025, 7, 15): 1.74394,
    date(2025, 8, 15): 1.71,
    date(2025, 9, 15): 1.62909,
    date(2025, 10, 15): 1.72879,
    date(2025, 11, 17): 1.70727,
    date(2025, 12, 15): 1.78091,
    date(2026, 1, 15): 1.88152,
    date(2026, 2, 13): 1.66485,
    date(2026, 3, 16): 1.63697,
    date(2026, 4, 15): 1.53970,
    date(2026, 5, 15): 1.42212,
    date(2026, 6, 15): 1.46667,
    date(2026, 7, 15): 1.50,
}
hibor_refixing = []

effective_dates = sorted(hibor_refixing_date.keys())

for i, effective_date in enumerate(effective_dates):

    start_date = effective_date.fromordinal(
        effective_date.toordinal() + 1
    )

    if i < len(effective_dates) - 1:
        end_date = effective_dates[i + 1]
    else:
        end_date = date(2030, 12, 31)

    rate = hibor_refixing_date[effective_date]

    d = start_date

    while d <= end_date:
        hibor_refixing.append(
            {
                "Calculation Date": d,
                "HIBOR Refixing": rate,
            }
        )

        d = date.fromordinal(
            d.toordinal() + 1
        )
hibor_refixing_df = pd.DataFrame(hibor_refixing)



def hibor_cal(sme_drawdown, repayment_date, sofr_df, sme_mit_days, hibor_refixing_df):
    # Merge the two DataFrames on "Calculation Date"
    hibor_df = pd.merge(sofr_df, hibor_refixing_df, on="Calculation Date", how="left")
    hibor_df = hibor_df.loc[(hibor_df["Calculation Date"] >= sme_drawdown) &(hibor_df["Calculation Date"] <= repayment_date)]
    refixing_dates_hit = [ d for d in hibor_refixing_date.keys() if sme_drawdown <= d <= repayment_date]
    first_refixing_date = (min(refixing_dates_hit) if refixing_dates_hit else None)
    sme_drawdown_hibor = sofr_df.loc[sofr_df["Calculation Date"] == sme_drawdown,"Daily Calculated Blended HIBOR"].iloc[0]
    if (repayment_date - sme_drawdown).days + 1 <= sme_mit_days.days:
        hibor_df["Applied HIBOR"] = sme_drawdown_hibor
    elif first_refixing_date is not None:
        hibor_df["Applied HIBOR"] =  hibor_df.apply(
            lambda row: sme_drawdown_hibor
            if row["Calculation Date"] <= first_refixing_date
            else row["HIBOR Refixing"],
            axis=1
        )
    else:
        hibor_df["Applied HIBOR"] = sme_drawdown_hibor
    hibor_df = hibor_df[["Calculation Date","Applied HIBOR"]]
    return hibor_df
