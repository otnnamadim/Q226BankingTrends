"""
Disclaimer: The companies detailed herein are not specific investment recommendations. The purpose of this code is to illustrate the functionality of the SEC's Company Facts API in extracting financial information in conducting financial statement analysis of the major U.S. money-center banks.

The file builds on the initial EDGAR SEC Pipeline I previously developed. The program includes:
  - An Investment Watchlist that defines the banks (all domestic / US-GAAP filers)
  - A METRIC_MAPPING dictionary with ordered fallback XBRL tags per metric, implementing the multi-tag fix identified in the original project notes
  - Trend extraction (quarterly + annual + both) rather than latest-value-only
  - A preliminary-overrides layer for 8-K earnings-release figures that have
    not yet been filed in XBRL (self-superseding once the 10-Q lands)

"""

import os
import time

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# 1. Watchlist: This listing includes the eight US-based Globally Systemically Important Banks. All are domestic filers reporting under US GAAP; as such, there's no distinction between the FPI & IFRS for this purposes.)
# ---------------------------------------------------------------------------

def investment_watchlist() -> pd.DataFrame:
    watchlist_banks = [
        {"category": "domestic", "company_name": "JPMorgan Chase & Co",              "ticker": "JPM", "cik": "0000019617"},
        {"category": "domestic", "company_name": "Bank of America Corp",             "ticker": "BAC", "cik": "0000070858"},
        {"category": "domestic", "company_name": "Citigroup Inc",                    "ticker": "C",   "cik": "0000831001"},
        {"category": "domestic", "company_name": "Wells Fargo & Co",                 "ticker": "WFC", "cik": "0000072971"},
        {"category": "domestic", "company_name": "Goldman Sachs Group Inc",          "ticker": "GS",  "cik": "0000886982"},
        {"category": "domestic", "company_name": "Morgan Stanley",                   "ticker": "MS",  "cik": "0000895421"},
        {"category": "domestic", "company_name": "Bank of New York Mellon Corp",     "ticker": "BK",  "cik": "0001390777"},
        {"category": "domestic", "company_name": "State Street Corp",                     "ticker": "STT", "cik": "0000093751"},
    ]
    return pd.DataFrame(watchlist_banks)


# ---------------------------------------------------------------------------
# 2. Metric mapping — ordered candidate XBRL tags per metric. This section includes the logic for mapping the XBRL tags for each bank as well as the fallback logic for each to ensure the financial statements are consistently.
# ---------------------------------------------------------------------------

METRIC_MAPPING = {
    "Total Revenue": [
        "RevenuesNetOfInterestExpense",
        "Revenues",
        "RevenuesExcludingInterestAndDividends",
    ],
    "Net Interest Income": [
        "InterestIncomeExpenseNet",
        "InterestIncomeExpenseAfterProvisionForLoanLoss",
    ],
    "Investment Banking Fees": [
        "InvestmentBankingRevenue",
        "InvestmentBankingAdvisoryBrokerageAndUnderwritingFeesAndCommissions",
    ],
    "Trading Revenue": [
        "TradingGainsLosses",
        "PrincipalTransactionsRevenue",
        "TradingRevenueNetInterestIncomeTradingActivities",
    ],
    "Net Income": [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "EPS (Diluted)": [
        "EarningsPerShareDiluted",
        "EarningsPerShareBasic",
    ],
    "Assets Under Management": [
        "AssetsUnderManagementCarryingAmount",

    ],
    "Provision for Credit Losses": [
        "ProvisionForLoanLeaseAndOtherLosses",
        "ProvisionForCreditLossExpenseReversal",
        "ProvisionForLoanAndLeaseLosses",
        "ProvisionForDoubtfulAccounts",
    ],
    "Allowance for Credit Losses": [
        "FinancingReceivableAllowanceForCreditLosses",
        "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest",
        "LoansAndLeasesReceivableAllowance",
    ],
    "Net Charge-Offs": [
        "FinancingReceivableAllowanceForCreditLossesWriteOffs",
        "AllowanceForLoanAndLeaseLossesWriteOffsNet",

    ],
}

# Grouping used by the dashboard for layout / drill-down
METRIC_GROUPS = {
    "Total Revenue": ["Total Revenue", "Net Interest Income", "Investment Banking Fees", "Trading Revenue"],
    "Net Income": ["Net Income", "EPS (Diluted)"],
    "Assets Under Management": ["Assets Under Management"],
    "Consumer Credit Quality": ["Provision for Credit Losses", "Allowance for Credit Losses", "Net Charge-Offs"],
}

PRELIM_FORM_LABEL = "8-K (prelim)"

# These are all the manual overrides pulled from each company's 8-K. Within each SEC filing, the companies link a financial supplement that includes their detailed financial statement highlights.

MANUAL_FILED_LABEL = "10-Q (manual)"

OVERRIDE_LABELS = {PRELIM_FORM_LABEL, MANUAL_FILED_LABEL}


# ---------------------------------------------------------------------------
# 3. EDGAR connection — unchanged from the original pipeline
# ---------------------------------------------------------------------------

def get_company_facts(cik: str, user_agent: str) -> dict:
    padded_cik = cik.zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json"
    headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
    print(f"Fetching data from: {url}")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    assert isinstance(data, dict)
    return data


# ---------------------------------------------------------------------------
# 4. FSLI extraction — original function, plus a duration flag so quarterly
#    (10-Q) and annual (10-K) observations can be separated for trend charts
#
#    A merely-absent tag is an expected, benign event during fallback probing,
#    so it now returns an empty frame SILENTLY. Only genuine structural
#    anomalies (no us-gaap/ifrs facts block) are surfaced here; all-candidates-
#    failed gaps are reported once at end of run by build_bank_panel().
# ---------------------------------------------------------------------------

def extract_fsli_to_dataframe(company_json: dict, fsli_name: str,
                              verbose: bool = False) -> pd.DataFrame:
    facts = company_json.get("facts", {})
    if "us-gaap" in facts:
        accounting_standard = "us-gaap"
    elif "ifrs-full" in facts:
        accounting_standard = "ifrs-full"
    else:
        print("  [warn] No us-gaap / ifrs-full facts block found for this filer.")
        return pd.DataFrame()

    statements = facts[accounting_standard]
    if fsli_name not in statements:
        # Expected during fallback: tag simply isn't present. Not an error.
        if verbose:
            print(f"  [debug] tag '{fsli_name}' absent — trying next candidate")
        return pd.DataFrame()

    try:
        fsli_data = statements[fsli_name]
        unit_key = list(fsli_data["units"].keys())[0]
        df = pd.DataFrame(fsli_data["units"][unit_key])

        columns_to_keep = ["form", "fy", "fp", "start", "end", "val", "accn", "frame"]
        df = df[[col for col in columns_to_keep if col in df.columns]]
        df["accounting_standard"] = accounting_standard
        df["xbrl_tag"] = fsli_name
        df["unit"] = unit_key
        return df
    except (KeyError, IndexError, ValueError) as e:
        # Malformed units/structure for a tag that *does* exist — genuinely odd.
        print(f"  [warn] '{fsli_name}' present but could not be parsed: {e}")
        return pd.DataFrame()


def extract_metric_with_fallback(company_json: dict, metric_name: str) -> pd.DataFrame:
    """Try each candidate tag in METRIC_MAPPING order; return first non-empty result."""
    for tag in METRIC_MAPPING[metric_name]:
        df = extract_fsli_to_dataframe(company_json, tag)
        if not df.empty:
            df["metric"] = metric_name
            return df
    return pd.DataFrame()

# ---------------------------------------------------------------------------
# 5. Trend preparation — dedupe restatements, split annual vs quarterly
# ---------------------------------------------------------------------------

def prepare_trend(df: pd.DataFrame, frequency: str = "annual") -> pd.DataFrame:
    """
    frequency: 'annual' keeps FY observations from 10-K filings;
               'quarterly' keeps Q1-Q3 from 10-Qs plus derived/reported Q4.
    Duplicate (fy, fp) rows (restatements across filings) keep the most
    recent accession, i.e. the latest reported figure.

    NOTE on quarterly durations: income-statement items are kept when their
    period length is ~a single quarter (between 60 and 120 days). Filers that
    tag ONLY year-to-date (cumulative) durations for a line item will therefore
    be skipped for that item. The current seven banks all tag discrete quarters
    for the charted metrics, so this is not presently an issue, but it is the
    first thing to check if a specific bank/metric quarterly series goes empty
    after a future filer changes its tagging.
    """
    if df.empty:
        return df
    work = df.copy()
    if "start" in work.columns and "end" in work.columns:
        work["start"] = pd.to_datetime(work["start"], errors="coerce")
        work["end"] = pd.to_datetime(work["end"], errors="coerce")
        work["duration_days"] = (work["end"] - work["start"]).dt.days
    else:
        work["duration_days"] = None  # instant (balance-sheet) concepts

    is_instant = work["duration_days"].isna().all()

    if frequency == "annual":
        if is_instant:
            subset = work[work["form"] == "10-K"]
        else:
            subset = work[(work["form"] == "10-K") & (work["duration_days"] > 300)]
    else:  # quarterly
        if is_instant:
            subset = work[work["form"].isin(["10-Q", "10-K"])]
        else:
            subset = work[work["duration_days"].between(60, 120)]

    subset = (
        subset.sort_values("end")
        .drop_duplicates(subset=[c for c in ["fy", "fp", "end"] if c in subset.columns], keep="last")
        .reset_index(drop=True)
    )
    return subset


# ---------------------------------------------------------------------------
# 6. Preliminary overrides — This section pulls the manual data points from the preliminary__override.csv.This section is included because the second Quarter 10-Q filings are not actually populated within the Company Facts API JSON file for each company.
#    I manually prepared a Google Sheets file to summarize the Q2 2026 highlights from each bank's filings in order to have a comparable data set through 6-30 for each bank. The dashboard denotes these with an asterisk.
# ---------------------------------------------------------------------------

def load_preliminary_overrides(panel: pd.DataFrame,
                               path: str = "preliminary_override.csv") -> pd.DataFrame:
    if not os.path.exists(path):
        print(f"\n  [warn] Overrides file not found at '{os.path.abspath(path)}'.")
        nearby = [f for f in os.listdir(os.path.dirname(os.path.abspath(path)) or ".")
                  if "override" in f.lower() and f.endswith(".csv")]
        if nearby:
            print(f"  [warn] Did you mean one of these? {nearby}")
        print("  [warn] No preliminary/manual figures applied — panel contains filed data only.")
        return panel
    try:
        prelim = pd.read_csv(path, parse_dates=["start", "end"], comment="#")
    except Exception as e:
        print(f"Could not read {path}: {e} — skipping overrides.")
        return panel
    if prelim.empty:
        return panel

    required = {"ticker", "metric", "frequency", "fy", "fp", "start", "end", "val", "source"}
    missing_cols = required - set(prelim.columns)
    if missing_cols:
        print(f"{path} missing columns {missing_cols} — skipping overrides.")
        return panel

    # Validate against known tickers/metrics so typos fail loudly.
    # (This guard is exactly why MS/BK must be present in the watchlist: an MS
    #  override row against a watchlist without MS would discard ALL overrides.)
    known_tickers = set(investment_watchlist()["ticker"])
    bad_t = set(prelim["ticker"]) - known_tickers
    bad_m = set(prelim["metric"]) - set(METRIC_MAPPING)
    if bad_t or bad_m:
        print(f"Overrides skipped — unknown tickers {bad_t or '{}'} / metrics {bad_m or '{}'}. "
              f"Metric names must match METRIC_MAPPING keys exactly.")
        return panel

    prelim = prelim.copy()

    # Optional 'form_label' column distinguishes a filed-but-not-yet-ingested
    # 10-Q figure from a preliminary 8-K one. Absent column -> preliminary,
    # preserving the previous behaviour for existing override files.
    if "form_label" in prelim.columns:
        prelim["form"] = prelim["form_label"].fillna(PRELIM_FORM_LABEL)
        bad_labels = set(prelim["form"]) - OVERRIDE_LABELS
        if bad_labels:
            print(f"Overrides skipped — unknown form_label(s) {bad_labels}. "
                  f"Must be one of {OVERRIDE_LABELS}.")
            return panel
    else:
        prelim["form"] = PRELIM_FORM_LABEL

    prelim["xbrl_tag"] = "manual: " + prelim["source"].astype(str)
    prelim["unit"] = prelim.get("unit", "USD")
    prelim["accn"] = None
    prelim["company"] = prelim["ticker"].map(
        investment_watchlist().set_index("ticker")["company_name"])

    # Drop overrides that carry no value (e.g. an 8-K line the release didn't
    # disclose as a clean number) so they don't create empty prelim points.
    if prelim["val"].isna().any():
        n_empty = int(prelim["val"].isna().sum())
        print(f"Dropped {n_empty} preliminary override(s) with no value.")
        prelim = prelim[prelim["val"].notna()]

    panel = panel.copy()
    panel["end"] = pd.to_datetime(panel["end"], errors="coerce")

    filed_keys = set(zip(panel["ticker"], panel["metric"],
                         panel["frequency"], panel["end"]))
    keep_mask = [
        (r.ticker, r.metric, r.frequency, r.end) not in filed_keys
        for r in prelim.itertuples()
    ]
    superseded = len(prelim) - sum(keep_mask)
    prelim = prelim[keep_mask]

    if superseded:
        print(f"{superseded} override(s) superseded by filed data — dropped.")
    if prelim.empty:
        return panel
    for label, n in prelim["form"].value_counts().items():
        print(f"Applied {n} '{label}' override(s) from {path}")
    return pd.concat([panel, prelim], ignore_index=True)


# ---------------------------------------------------------------------------
# 6b. Coverage check — surface banks whose latest quarter lags the panel.
#     A whole filing missing from Company Facts (e.g. a Q1 10-Q that SEC has
#     not yet ingested) shows up as one bank stranded several quarters behind
#     its peers across ALL metrics. This makes that loud instead of silent.
# ---------------------------------------------------------------------------

def coverage_report(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        print("Coverage: panel is empty.")
        return panel
    q = panel[panel["frequency"] == "quarterly"].copy()
    if q.empty:
        return panel
    q["end"] = pd.to_datetime(q["end"], errors="coerce")
    panel_max = q["end"].max()
    print(f"\nQuarterly coverage (panel's latest quarter = {panel_max.date()}):")
    for ticker, g in q.groupby("ticker"):
        latest = g["end"].max()
        lag_q = (panel_max.to_period("Q") - latest.to_period("Q")).n
        flag = "" if lag_q == 0 else f"   <-- LAGS by {lag_q} quarter(s); filing likely not yet in Company Facts"
        print(f"  {ticker}: {latest.date()}{flag}")
    return panel


# ---------------------------------------------------------------------------
# 7. Batch pull — assemble one tidy DataFrame across all banks and metrics
# ---------------------------------------------------------------------------

def build_bank_panel(user_agent: str, frequency: str = "both",
                     apply_overrides: bool = True) -> pd.DataFrame:
    """Returns a long-format panel: ticker | company | metric | frequency | ... | val | xbrl_tag.

    frequency: 'annual', 'quarterly', or 'both' (both series, labeled in a
    'frequency' column, from a single EDGAR fetch per company).
    apply_overrides: merge preliminary_override.csv (8-K figures) if present.
    """
    valid = {"annual", "quarterly", "both"}
    if frequency not in valid:
        raise ValueError(f"frequency must be one of {valid}, got '{frequency}'")

    watchlist = investment_watchlist()
    frames, misses = [], []

    for _, row in watchlist.iterrows():
        try:
            facts = get_company_facts(row["cik"], user_agent)
        except requests.RequestException as e:
            print(f"Failed to fetch {row['ticker']}: {e}")
            continue

        for metric in METRIC_MAPPING:
            df = extract_metric_with_fallback(facts, metric)
            if df.empty:
                misses.append({"ticker": row["ticker"], "metric": metric})
                continue

            if frequency == "both":
                a = prepare_trend(df, frequency="annual")
                a["frequency"] = "annual"
                q = prepare_trend(df, frequency="quarterly")
                q["frequency"] = "quarterly"
                trend = pd.concat([a, q], ignore_index=True)
            else:
                trend = prepare_trend(df, frequency=frequency)
                trend["frequency"] = frequency

            trend["ticker"] = row["ticker"]
            trend["company"] = row["company_name"]
            frames.append(trend)

        time.sleep(0.5)  # stay polite with SEC servers as the watchlist grows

    if misses:
        # These are the ONLY genuine gaps (all candidate tags failed). AUM and
        # WFC/BK investment-banking / net-charge-offs are expected entries here.
        print("\nMetrics with no us-gaap tag match (candidates for extension-taxonomy review):")
        for m in misses:
            print(f"  - {m['ticker']}: {m['metric']}")

    if not frames:
        return pd.DataFrame()
    panel = pd.concat(frames, ignore_index=True)
    keep = ["ticker", "company", "metric", "frequency", "form", "fy", "fp",
            "start", "end", "val", "unit", "xbrl_tag", "accn"]
    panel = panel[[c for c in keep if c in panel.columns]]

    if apply_overrides:
        panel = load_preliminary_overrides(panel)
    return panel


if __name__ == "__main__":
    # SEC requires a real contact. Set SEC_USER_AGENT in your environment for
    # the public repo version; the fallback below is for local runs.
    USER_AGENT = os.environ.get("SEC_USER_AGENT", "Nnamadim CPA PLLC admin@otnnamadim.com")
    panel = build_bank_panel(USER_AGENT, frequency="both")
    if not panel.empty:
        coverage_report(panel)
        panel.to_csv("bank_panel.csv", index=False)
        n_prelim = (panel["form"] == PRELIM_FORM_LABEL).sum()
        n_manual = (panel["form"] == MANUAL_FILED_LABEL).sum()
        n_banks = panel["ticker"].nunique()
        print(f"\nSaved {len(panel)} rows to bank_panel.csv "
              f"({n_banks} banks, {n_prelim} preliminary, {n_manual} manual-filed)")
