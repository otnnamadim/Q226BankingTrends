# Q2 2026 Banking Trends

The purpose of this project is to prepare an interactive trend analysis of key financial statement line items from the eight U.S. Globally Systemically Important Banks (G-SIBs), built entirely from public SEC filings. 

**Live site:** https://otnnamadim.github.io/Q226BankingTrends/

## Overview

This project charts historical trends in revenue, net interest income, operating margin and consumer credit quality for each of the eight (8) U.S. based G-SIBs:

| Ticker | Bank | SEC Filings |
| ------ | ---- | ---- |
| JPM | JPMorgan Chase | https://www.sec.gov/edgar/browse/?CIK=19617&owner=exclude |
| BAC | Bank of America | https://www.sec.gov/edgar/browse/?CIK=70858&owner=exclude |
| C | Citigroup | https://www.sec.gov/edgar/browse/?CIK=831001&owner=exclude |
| WFC | Wells Fargo | https://www.sec.gov/edgar/browse/?CIK=72971&owner=exclude |
| GS | Goldman Sachs | https://www.sec.gov/edgar/browse/?CIK=886982&owner=exclude |
| MS | Morgan Stanley | https://www.sec.gov/edgar/browse/?CIK=895421&owner=exclude |
| BK | Bank of New York Mellon Corp | https://www.sec.gov/edgar/browse/?CIK=1390777&owner=exclude |
| STT | State Street | https://www.sec.gov/edgar/browse/?CIK=93751&owner=exclude |

Every data series is pulled programmatically from each bank's SEC filings via the [EDGAR Company Facts API](https://www.sec.gov/edgar/sec-api-documentation) utilizing the company's CIK number to pull the XBRL tagged financial line items from their 10-Q filings. For the most recent quarter, the 8-K filing with the earnings data was utilized instead of the 10-Q when the quarterly report was not yet available. The result is a single self-contained page with interactive charts and plain-language commentary aimed at readers who aren't career analysts.

## Metrics

- **Total Revenue** — reported top-line operating revenue
- **Net Interest Income** — spread between interest earned and interest paid
- **Trading Revenue** — market-making and trading desk results
- **Net Income** — bottom-line earnings
- **EPS (Diluted)** — earnings per fully diluted share
- **Provision for Credit Losses** — forward-looking estimate of expected loan losses

Charts can be toggled between **quarterly** and **annual** frequency, and individual banks can be shown or hidden.

## A note on the data

- **Preliminary figures** from Q2 2026 earnings-release 8-Ks are marked with a ★ and kept visually separate from filed data. They are unaudited and are replaced automatically once the corresponding 10-Qs are filed and ingested by EDGAR.
- **Cross-bank comparability is limited.** Banks tag equivalent concepts under different `us-gaap` elements, and some filers stop tagging a concept when they change presentation. As a result, certain series (e.g. Trading Revenue for GS, Provision for Credit Losses for BAC/MS/STT) end earlier than others, and blank cells in the snapshot table indicate a discontinued or unmatched tag rather than an error. Reading the trend *within* a single institution is more reliable than benchmarking *levels* across banks.

## Repository structure

```
├── EdgarPipeline.py              # The data pipeline to connect with Company Facts API to populate the historical financial statement line items.
├── index.html                    # The dashboard: charts, commentary, and embedded data
├── Dashboard                     # Build / rendering logic for the page
├── Bank10-QSECPullw8KOverrides   # EDGAR data pull with 8-K preliminary overrides
├── deploy.yml                    # Deployment workflow
├── .github/workflows/            # CI / scheduled refresh
└── .nojekyll                     # Serve files as-is on GitHub Pages
```

## Running locally

The site is a single static HTML file with no build step required to view it. Clone the repo and open `index.html` in a browser, or serve the directory:

```bash
git clone https://github.com/otnnamadim/Q226BankingTrends.git
cd Q226BankingTrends
python3 -m http.server 8000
then visit http://localhost:8000
```

Charts are rendered with [Chart.js](https://www.chartjs.org/) loaded from a CDN, so an internet connection is needed on first load.

## Disclaimer

This project illustrates financial statement trends among the banking sector. It is **not investment advice**. Preliminary points are unaudited and may be revised in the filed 10-Q; figures should be verified against original SEC filings before being relied upon.

## Author

Built by [O. T. Nnamadim](https://www.otnnamadim.com)
