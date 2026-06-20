"""
Global Equities Collector — DE-SKEW the US-heavy price lake toward global coverage.

Sources: Yahoo Finance v8 API (keyless, full history), same proven path as US equities.
Markets: HKEX, SSE/SZSE, TSE, NSE/BSE, KOSPI, TWSE, SGX, LSE, XETRA, Euronext, SIX,
         TSX, ASX, B3, JSE plus major non-US indices.

Output: gzip JSONL shards in /tmp/gx_stage/ → S3 prefix predict/prices/global_equities/
Schema per row: {symbol, market, date, open, high, low, close, volume}
"""
from __future__ import annotations

import gzip
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
STAGE = Path("/tmp/gx_stage")
S3_BUCKET = "mining-terminal-research-405844305300-us-east-1"
S3_PREFIX = "predict/prices/global_equities/"
SHARD_ROWS = 100_000       # rows per JSONL shard
RATE_LIMIT = 0.25          # seconds between requests (4 req/s)
MAX_RETRY = 3
TIMEOUT = 30
YF_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=0&period2=9999999999&events=history"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── universe definition ───────────────────────────────────────────────────────
# Format: (yahoo_symbol, market_code, description)
# Major indices first, then constituents by market

INDICES = [
    # ── Asia ──
    ("^HSI",   "HK",  "Hang Seng Index"),
    ("^HSCE",  "HK",  "Hang Seng China Enterprises"),
    ("^HSTECH","HK",  "Hang Seng Tech"),
    ("000001.SS","CN", "Shanghai SSE Composite"),
    ("000300.SS","CN", "CSI 300"),
    ("399001.SZ","CN", "Shenzhen Component"),
    ("399006.SZ","CN", "ChiNext Index"),
    ("^N225",  "JP",  "Nikkei 225"),
    ("^TOPIX", "JP",  "TOPIX"),
    ("^N100",  "JP",  "Nikkei 100"),
    ("^BSESN", "IN",  "BSE Sensex"),
    ("^NSEI",  "IN",  "Nifty 50"),
    ("^CNXIT", "IN",  "Nifty IT"),
    ("^KS11",  "KR",  "KOSPI"),
    ("^KQ11",  "KR",  "KOSDAQ"),
    ("^TWII",  "TW",  "Taiwan Weighted"),
    ("^STI",   "SG",  "Straits Times Index"),
    ("^AXJO",  "AU",  "ASX 200"),
    ("^AORD",  "AU",  "All Ordinaries"),
    # ── Europe ──
    ("^FTSE",  "UK",  "FTSE 100"),
    ("^FTMC",  "UK",  "FTSE 250"),
    ("^GDAXI", "DE",  "DAX"),
    ("^MDAXI", "DE",  "MDAX"),
    ("^SDAXI", "DE",  "SDAX"),
    ("^FCHI",  "FR",  "CAC 40"),
    ("^AEX",   "NL",  "AEX Amsterdam"),
    ("^BEL20", "BE",  "BEL 20"),
    ("^IBEX",  "ES",  "IBEX 35"),
    ("^SSMI",  "CH",  "SMI Switzerland"),
    ("^OMX",   "SE",  "OMX Stockholm"),
    ("^OMXC25","DK",  "OMX Copenhagen"),
    ("^OMXH25","FI",  "OMX Helsinki"),
    ("^ATX",   "AT",  "ATX Vienna"),
    ("^MIB",   "IT",  "FTSE MIB"),
    ("^PSI20", "PT",  "PSI-20 Portugal"),
    # ── Americas ──
    ("^GSPTSE","CA",  "TSX Composite"),
    ("^BVSP",  "BR",  "Bovespa"),
    ("^MXX",   "MX",  "IPC Mexico"),
    ("^MERV",  "AR",  "Merval Argentina"),
    # ── Other ──
    ("^J203",  "ZA",  "JSE All Share"),
    ("^TA125.TA","IL","Tel Aviv 125"),
    ("^NZ50",  "NZ",  "NZX 50"),
]

# Major liquid equities per market — top constituents of major indices
# Hong Kong (HKEX) — Hang Seng + HSCEI top names
HK_EQUITIES = [
    "0001.HK","0002.HK","0003.HK","0005.HK","0006.HK","0011.HK","0012.HK","0016.HK","0017.HK",
    "0019.HK","0020.HK","0027.HK","0066.HK","0083.HK","0101.HK","0135.HK","0175.HK","0241.HK",
    "0267.HK","0268.HK","0285.HK","0291.HK","0388.HK","0489.HK","0669.HK","0688.HK","0700.HK",
    "0762.HK","0823.HK","0836.HK","0857.HK","0868.HK","0883.HK","0939.HK","0941.HK","0960.HK",
    "0968.HK","0981.HK","0992.HK","1038.HK","1044.HK","1088.HK","1093.HK","1109.HK","1113.HK",
    "1177.HK","1209.HK","1211.HK","1288.HK","1299.HK","1347.HK","1378.HK","1398.HK","1810.HK",
    "1876.HK","1928.HK","1997.HK","2007.HK","2018.HK","2020.HK","2057.HK","2269.HK","2313.HK",
    "2318.HK","2319.HK","2331.HK","2382.HK","2388.HK","2628.HK","3690.HK","3968.HK","3988.HK",
    "6098.HK","6160.HK","6618.HK","6690.HK","6862.HK","9618.HK","9633.HK","9888.HK","9988.HK",
    "9999.HK",
]

# China A-shares (Shanghai + Shenzhen) — CSI 300 top components via SS/SZ suffix
CN_EQUITIES = [
    "600000.SS","600016.SS","600028.SS","600030.SS","600036.SS","600048.SS","600050.SS","600104.SS",
    "600276.SS","600309.SS","600346.SS","600406.SS","600519.SS","600690.SS","600745.SS","600900.SS",
    "601012.SS","601088.SS","601166.SS","601169.SS","601186.SS","601211.SS","601229.SS","601288.SS",
    "601318.SS","601328.SS","601390.SS","601398.SS","601601.SS","601628.SS","601668.SS","601688.SS",
    "601727.SS","601766.SS","601800.SS","601857.SS","601899.SS","601919.SS","601939.SS","601988.SS",
    "603259.SS","603501.SS","603986.SS",
    # Shenzhen
    "000001.SZ","000002.SZ","000333.SZ","000568.SZ","000651.SZ","000725.SZ","000858.SZ","000895.SZ",
    "001979.SZ","002007.SZ","002024.SZ","002027.SZ","002049.SZ","002120.SZ","002230.SZ","002304.SZ",
    "002352.SZ","002415.SZ","002594.SZ","002714.SZ","003816.SZ","300015.SZ","300059.SZ","300122.SZ",
    "300124.SZ","300274.SZ","300347.SZ","300408.SZ","300413.SZ","300454.SZ","300498.SZ","300750.SZ",
    "300760.SZ","300763.SZ","300896.SZ","301236.SZ",
]

# Japan (TSE) — Nikkei 225 blue chips
JP_EQUITIES = [
    "4151.T","4502.T","4503.T","4519.T","4523.T","4528.T","4568.T","4578.T","4661.T","4689.T",
    "4704.T","4751.T","4755.T","4901.T","4911.T","5401.T","5108.T","5802.T","6098.T","6178.T",
    "6273.T","6301.T","6367.T","6501.T","6503.T","6504.T","6506.T","6594.T","6645.T","6702.T",
    "6723.T","6724.T","6752.T","6758.T","6762.T","6857.T","6861.T","6954.T","6971.T","6981.T",
    "7011.T","7013.T","7201.T","7203.T","7211.T","7267.T","7269.T","7270.T","7733.T","7741.T",
    "7751.T","7832.T","7974.T","8001.T","8002.T","8031.T","8035.T","8053.T","8058.T","8306.T",
    "8308.T","8316.T","8411.T","8591.T","8604.T","8630.T","8725.T","8766.T","8801.T","8802.T",
    "9020.T","9021.T","9022.T","9432.T","9433.T","9434.T","9437.T","9531.T","9532.T","9613.T",
    "9984.T",
]

# India (NSE) — Nifty 50 + Nifty Next 50
IN_EQUITIES = [
    "ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS",
    "BAJAJFINSV.NS","BAJFINANCE.NS","BHARTIARTL.NS","BPCL.NS","BRITANNIA.NS","CIPLA.NS","COALINDIA.NS",
    "DIVISLAB.NS","DRREDDY.NS","EICHERMOT.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS","HDFCLIFE.NS",
    "HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","IOC.NS",
    "ITC.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","LTIM.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS",
    "NTPC.NS","ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS","SBIN.NS","SUNPHARMA.NS","TATACONSUM.NS",
    "TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS","TRENT.NS","ULTRACEMCO.NS","UPL.NS",
    "WIPRO.NS",
    # Nifty Next 50 additions
    "ABB.NS","ADANIGREEN.NS","ADANIPOWER.NS","AMBUJACEM.NS","BANKBARODA.NS","BEL.NS","BOSCHLTD.NS",
    "CANBK.NS","CHOLAFIN.NS","COLPAL.NS","DABUR.NS","DLF.NS","GODREJCP.NS","HAVELLS.NS","HINDPETRO.NS",
    "ICICIPRULI.NS","IDBI.NS","INDIGO.NS","IRCTC.NS","JINDALSTEL.NS","LUPIN.NS","MARICO.NS",
    "MOTHERSON.NS","MUTHOOTFIN.NS","NAUKRI.NS","PIIND.NS","PIDILITIND.NS","PNB.NS","SAIL.NS",
    "SHREECEM.NS","SIEMENS.NS","SRF.NS","TATAPOWER.NS","TORNTPHARM.NS","TVSMOTOR.NS","VBL.NS",
    "VEDL.NS","VOLTAS.NS","ZOMATO.NS","ZYDUSLIFE.NS",
]

# Korea (KRX) — KOSPI top 50
KR_EQUITIES = [
    "005930.KS","000660.KS","051910.KS","005380.KS","006400.KS","035420.KS","000270.KS","068270.KS",
    "105560.KS","055550.KS","028260.KS","066570.KS","017670.KS","032830.KS","086790.KS","003550.KS",
    "051900.KS","096770.KS","034730.KS","015760.KS","316140.KS","009150.KS","018260.KS","207940.KS",
    "000810.KS","011200.KS","034020.KS","003670.KS","010130.KS","024110.KS","011170.KS","036570.KS",
    "030200.KS","090430.KS","032640.KS","139480.KS","071050.KS","078930.KS","267250.KS","033780.KS",
    "047050.KS","009830.KS","004020.KS","042700.KS","011780.KS","000720.KS","005490.KS","039490.KS",
    "069960.KS","010950.KS",
]

# Taiwan (TWSE)
TW_EQUITIES = [
    "2330.TW","2317.TW","2454.TW","2412.TW","2308.TW","2382.TW","2303.TW","2881.TW","2882.TW",
    "2886.TW","2891.TW","2892.TW","2884.TW","2885.TW","2887.TW","2002.TW","1301.TW","1303.TW",
    "1216.TW","2207.TW","2357.TW","2379.TW","3711.TW","2395.TW","3045.TW","4904.TW","2353.TW",
    "2801.TW","5871.TW","5876.TW","9910.TW","6505.TW","1326.TW","2327.TW","6669.TW","2345.TW",
    "2360.TW","3034.TW","2474.TW","2301.TW","2337.TW","2049.TW","1101.TW","2105.TW","2103.TW",
    "1102.TW","2610.TW","2615.TW","2618.TW","2914.TW",
]

# Singapore (SGX)
SG_EQUITIES = [
    "D05.SI","O39.SI","U11.SI","Z74.SI","C6L.SI","S68.SI","BN4.SI","A17U.SI","C52.SI","G13.SI",
    "H78.SI","C09.SI","F34.SI","V03.SI","BS6.SI","U96.SI","S63.SI","J37.SI","C38U.SI","N2IU.SI",
    "ME8U.SI","TS0U.SI","BUOU.SI","AJBU.SI","SK6U.SI","K71U.SI","T82U.SI","CWBU.SI","P40U.SI",
    "M44U.SI",
]

# UK (LSE) — FTSE 100 top names
UK_EQUITIES = [
    "HSBA.L","BP.L","SHEL.L","AZN.L","GSK.L","ULVR.L","RIO.L","AAL.L","BT-A.L","BARC.L",
    "LLOY.L","NWG.L","STAN.L","PRU.L","LGEN.L","AVIVA.L","HL.L","DGE.L","RKT.L","BATS.L",
    "IMB.L","CPG.L","VOD.L","BHP.L","GLEN.L","ANTO.L","EVR.L","FRES.L","MNDI.L","SMDS.L",
    "REL.L","EXPN.L","WPP.L","IPG.L","PSON.L","INTU.L","SGE.L","CRH.L","WTB.L","IHG.L",
    "MAB.L","PFC.L","WMH.L","BA.L","RR.L","ROLLS.L","QQ.L","MRO.L","WEIR.L","SMIT.L",
    "HLN.L","ABRDN.L","HSBA.L","MNG.L","BLND.L","LAND.L","SEGRO.L","PSN.L","VTY.L","BBOX.L",
    "III.L","3I.L","INFORMA.L","AUTO.L","JD.L","MKS.L","NEXT.L","OCDO.L","SPX.L","SBRY.L",
    "TSCO.L","DCC.L","BDEV.L","BWY.L","HILS.L","TW.L","PMO.L","OML.L","IMPERIAL.L","ENT.L",
]

# Germany (XETRA) — DAX + MDAX components
DE_EQUITIES = [
    "ADS.DE","AIR.DE","ALV.DE","BAYN.DE","BMW.DE","BAS.DE","BEIG.DE","CON.DE","1COV.DE","DB1.DE",
    "DBK.DE","DHL.DE","DPW.DE","DTE.DE","EOAN.DE","FME.DE","FRE.DE","HEI.DE","HEN3.DE","IFX.DE",
    "LIN.DE","MBG.DE","MRK.DE","MTX.DE","MUV2.DE","NWZGY.DE","P911.DE","PAH3.DE","PUM.DE","QIA.DE",
    "RWE.DE","SAP.DE","SHL.DE","SIE.DE","SRT3.DE","SY1.DE","SZG.DE","VOW3.DE","VNA.DE","ZAL.DE",
    "AFX.DE","AG1.DE","ARL.DE","BOSS.DE","COP.DE","DHER.DE","ECV.DE","EVT.DE","G1A.DE","GXI.DE",
    "HAG.DE","HFG.DE","HOT.DE","HHFA.DE","K+S.DE","LEG.DE","LHA.DE","MDG1.DE","NDX1.DE","NTCO.DE",
    "O2D.DE","PBB.DE","PSM.DE","RAA.DE","RRTL.DE","S92.DE","SDM.DE","SFQ.DE","SGL.DE","SKB.DE",
    "SLT.DE","SNH.DE","TLX.DE","VH2.DE","WION.DE","WCH.DE","ZIL2.DE",
]

# France (Euronext Paris) — CAC 40 + SBF 120
FR_EQUITIES = [
    "AI.PA","AIR.PA","ATO.PA","ACA.PA","BNP.PA","CAP.PA","CA.PA","CS.PA","ML.PA","DG.PA",
    "DSY.PA","ENGI.PA","EL.PA","ERF.PA","EN.PA","EDF.PA","EDEN.PA","GLE.PA","VIE.PA","HO.PA",
    "KER.PA","MC.PA","MTX.PA","ORA.PA","RI.PA","RNO.PA","SAF.PA","SGO.PA","SAN.PA","SU.PA",
    "STM.PA","SW.PA","TEP.PA","TTE.PA","UG.PA","URW.PA","VIV.PA","VK.PA","WLN.PA","FR.PA",
    "FP.PA","ADP.PA","AF.PA","ALSTOM.PA","AMUN.PA","ATD.PA","BI.PA","BIM.PA","BOL.PA","FGR.PA",
]

# Netherlands (Euronext Amsterdam) — AEX components
NL_EQUITIES = [
    "ASML.AS","INGA.AS","HEIA.AS","AKZA.AS","RDSA.AS","ABN.AS","NN.AS","WKL.AS","KPN.AS",
    "DSM.AS","PHIA.AS","UNA.AS","MT.AS","RAND.AS","IMCD.AS","AGN.AS","ADYEN.AS","OCI.AS",
    "URW.AS","BESI.AS","TKWY.AS","GLPG.AS","EXOR.AS","HAL.AS","AALB.AS","ASM.AS","STLAM.AS",
    "SBMO.AS","TOM2.AS","FLOW.AS",
]

# Switzerland (SIX) — SMI components
CH_EQUITIES = [
    "NESN.SW","NOVN.SW","ROG.SW","UBSG.SW","CSGN.SW","ZURN.SW","ABBN.SW","GIVN.SW","LONN.SW",
    "SIKA.SW","GEBN.SW","SCMN.SW","SRENH.SW","SLHN.SW","SREN.SW","CFR.SW","STMN.SW","HOLN.SW",
    "PGHN.SW","KUHN.SW","BAER.SW","LOGN.SW","TEMN.SW","ATEN.SW","EMMN.SW","VATN.SW","DKSH.SW",
    "LISN.SW","BALCHEM.SW","BUCKLE.SW",
]

# Canada (TSX) — S&P/TSX composite top names
CA_EQUITIES = [
    "RY.TO","TD.TO","ENB.TO","BNS.TO","BMO.TO","CP.TO","CNR.TO","MFC.TO","SU.TO","ABX.TO",
    "TRP.TO","BCE.TO","T.TO","CM.TO","CNQ.TO","CVE.TO","AEM.TO","FNV.TO","WPM.TO","K.TO",
    "ATD.TO","CSU.TO","SHOP.TO","L.TO","WN.TO","EMA.TO","FTS.TO","H.TO","IFC.TO","MRU.TO",
    "NTR.TO","POW.TO","PPL.TO","QSR.TO","RCI-B.TO","SAP.TO","SLF.TO","TOU.TO","WCN.TO","X.TO",
    "GIB-A.TO","EFN.TO","CCO.TO","DOO.TO","IAG.TO","LUNv.TO","IMO.TO","OVV.TO","PEY.TO","SNC.TO",
]

# Australia (ASX) — ASX 200 top names
AU_EQUITIES = [
    "BHP.AX","CBA.AX","CSL.AX","ANZ.AX","WBC.AX","NAB.AX","WES.AX","MQG.AX","RIO.AX","FMG.AX",
    "WOW.AX","TLS.AX","TCL.AX","GMG.AX","REA.AX","BXB.AX","SHL.AX","COL.AX","SCG.AX","STO.AX",
    "WDS.AX","OZL.AX","AMC.AX","AGL.AX","APA.AX","BSL.AX","CPU.AX","IAG.AX","IEL.AX","LLC.AX",
    "MIN.AX","MPL.AX","NCM.AX","NST.AX","NUF.AX","ORI.AX","ORG.AX","QAN.AX","QBE.AX","RMD.AX",
    "S32.AX","SEK.AX","SGP.AX","SUN.AX","TAH.AX","TWE.AX","VCX.AX","WOR.AX","WPL.AX","XRO.AX",
]

# Brazil (B3) — Bovespa top names
BR_EQUITIES = [
    "PETR3.SA","PETR4.SA","VALE3.SA","ITUB4.SA","BBDC4.SA","ABEV3.SA","BBAS3.SA","B3SA3.SA",
    "RENT3.SA","SUZB3.SA","JBSS3.SA","LREN3.SA","MGLU3.SA","EMBR3.SA","TOTS3.SA","ELET3.SA",
    "ELET6.SA","CMIG4.SA","SANB11.SA","BRAP4.SA","CSAN3.SA","RADL3.SA","AZUL4.SA","GOLL4.SA",
    "BEEF3.SA","BRFS3.SA","CVCB3.SA","ENBR3.SA","ENGIE3.SA","EQTL3.SA","HAPV3.SA","HGTX3.SA",
    "HYPE3.SA","IRBR3.SA","KLBN11.SA","MDIA3.SA","MULT3.SA","NTCO3.SA","PCAR3.SA","QUAL3.SA",
    "SBSP3.SA","TAEE11.SA","VBBR3.SA","VIVT3.SA","WEGE3.SA","YDUQ3.SA","COGN3.SA","CPLE6.SA",
    "CYRE3.SA","DXCO3.SA",
]

# South Africa (JSE) — JSE top names
ZA_EQUITIES = [
    "NPN.JO","AGL.JO","BTI.JO","GFI.JO","SBK.JO","FSR.JO","NED.JO","ABG.JO","SHP.JO","VOD.JO",
    "SOL.JO","ANG.JO","IMP.JO","DSY.JO","BID.JO","CFR.JO","MTN.JO","RNI.JO","SNH.JO","TBS.JO",
    "TRU.JO","WHL.JO","PIK.JO","SPP.JO","TFG.JO","REM.JO","LBH.JO","GRT.JO","BAW.JO","AVI.JO",
]

def build_universe() -> list[tuple[str, str, str]]:
    """Return list of (symbol, market, description)."""
    universe: list[tuple[str, str, str]] = list(INDICES)
    for sym in HK_EQUITIES:
        universe.append((sym, "HK", ""))
    for sym in CN_EQUITIES:
        universe.append((sym, "CN", ""))
    for sym in JP_EQUITIES:
        universe.append((sym, "JP", ""))
    for sym in IN_EQUITIES:
        universe.append((sym, "IN", ""))
    for sym in KR_EQUITIES:
        universe.append((sym, "KR", ""))
    for sym in TW_EQUITIES:
        universe.append((sym, "TW", ""))
    for sym in SG_EQUITIES:
        universe.append((sym, "SG", ""))
    for sym in UK_EQUITIES:
        universe.append((sym, "UK", ""))
    for sym in DE_EQUITIES:
        universe.append((sym, "DE", ""))
    for sym in FR_EQUITIES:
        universe.append((sym, "FR", ""))
    for sym in NL_EQUITIES:
        universe.append((sym, "NL", ""))
    for sym in CH_EQUITIES:
        universe.append((sym, "CH", ""))
    for sym in CA_EQUITIES:
        universe.append((sym, "CA", ""))
    for sym in AU_EQUITIES:
        universe.append((sym, "AU", ""))
    for sym in BR_EQUITIES:
        universe.append((sym, "BR", ""))
    for sym in ZA_EQUITIES:
        universe.append((sym, "ZA", ""))
    return universe


# ── fetch ─────────────────────────────────────────────────────────────────────

def fetch_symbol(client: httpx.Client, sym: str) -> list[dict[str, Any]]:
    """Fetch full OHLCV history for one symbol from Yahoo Finance v8 API."""
    url = YF_URL.format(sym=sym.replace("^", "%5E"))
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            if attempt:
                time.sleep(2 ** attempt)
            resp = client.get(url, headers=HEADERS, timeout=TIMEOUT)
            # 404 = symbol not found — don't retry
            if resp.status_code == 404:
                log.debug("NOT FOUND %s (404)", sym)
                return []
            # 429 = rate limit — back off and retry
            if resp.status_code == 429:
                log.warning("Rate limited on %s, backing off", sym)
                time.sleep(10 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return []
            r = result[0]
            timestamps = r.get("timestamp", [])
            if not timestamps:
                return []
            ohlcv = r.get("indicators", {}).get("quote", [{}])[0]
            opens  = ohlcv.get("open",   [None] * len(timestamps))
            highs  = ohlcv.get("high",   [None] * len(timestamps))
            lows   = ohlcv.get("low",    [None] * len(timestamps))
            closes = ohlcv.get("close",  [None] * len(timestamps))
            vols   = ohlcv.get("volume", [None] * len(timestamps))

            rows = []
            for ts, o, h, lo, c, v in zip(timestamps, opens, highs, lows, closes, vols):
                if c is None:          # skip rows with no close (missing day)
                    continue
                date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                rows.append({
                    "symbol": sym,
                    "date":   date_str,
                    "open":   round(o, 6)  if o  is not None else None,
                    "high":   round(h, 6)  if h  is not None else None,
                    "low":    round(lo, 6) if lo is not None else None,
                    "close":  round(c, 6),
                    "volume": int(v) if v is not None else None,
                })
            return rows
        except httpx.HTTPStatusError as exc:
            # Non-retryable client errors
            if exc.response.status_code in (400, 401, 403, 404):
                log.debug("Non-retryable %d for %s", exc.response.status_code, sym)
                return []
            last_exc = exc
            log.debug("fetch %s attempt %d HTTP %d", sym, attempt + 1, exc.response.status_code)
        except (httpx.RequestError, json.JSONDecodeError) as exc:
            last_exc = exc
            log.debug("fetch %s attempt %d failed: %s", sym, attempt + 1, exc)
    log.warning("FAILED %s after %d attempts: %s", sym, MAX_RETRY, last_exc)
    return []


# ── shard writer ──────────────────────────────────────────────────────────────

class ShardWriter:
    def __init__(self, stage: Path, prefix: str = "gx"):
        self.stage   = stage
        self.prefix  = prefix
        self.shard_n = 0
        self.buf: list[dict] = []
        self.paths: list[Path] = []
        stage.mkdir(parents=True, exist_ok=True)

    def add(self, rows: list[dict]) -> None:
        self.buf.extend(rows)
        while len(self.buf) >= SHARD_ROWS:
            self._flush(self.buf[:SHARD_ROWS])
            self.buf = self.buf[SHARD_ROWS:]

    def _flush(self, rows: list[dict]) -> None:
        p = self.stage / f"{self.prefix}_shard{self.shard_n:04d}.jsonl.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        log.info("wrote shard %s (%d rows, %.1f KB)", p.name, len(rows), p.stat().st_size / 1024)
        self.paths.append(p)
        self.shard_n += 1

    def close(self) -> list[Path]:
        if self.buf:
            self._flush(self.buf)
            self.buf = []
        return self.paths


# ── S3 upload ─────────────────────────────────────────────────────────────────

def s3_upload(local: Path, s3_key: str) -> int:
    """Upload to S3, return size in bytes."""
    import subprocess
    dest = f"s3://{S3_BUCKET}/{s3_key}"
    subprocess.run(["aws", "s3", "cp", str(local), dest], check=True, capture_output=True)
    return local.stat().st_size


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    STAGE.mkdir(parents=True, exist_ok=True)
    universe = build_universe()
    log.info("Universe: %d symbols across %d markets",
             len(universe), len(set(m for _, m, _ in universe)))

    # Direct connections only — Yahoo Finance v8 works without proxy
    # (Floxy DC proxy blocks Yahoo; residential proxy would add cost overhead)
    log.info("Direct connections (no proxy — Yahoo v8 is keyless and accessible)")
    client_kwargs: dict = {}

    writer = ShardWriter(STAGE, prefix="gx")

    # Per-market stats
    market_stats: dict[str, dict] = {}
    gaps: dict[str, str] = {}

    total_attempted = 0
    total_success   = 0
    total_empty     = 0
    total_rows      = 0

    with httpx.Client(**client_kwargs) as client:
        for i, (sym, market, desc) in enumerate(universe):
            total_attempted += 1
            if i % 50 == 0:
                log.info("Progress: %d/%d symbols | rows so far: %d", i, len(universe), total_rows)

            rows = fetch_symbol(client, sym)
            time.sleep(RATE_LIMIT)

            if not rows:
                total_empty += 1
                gaps[sym] = "empty"
                continue

            # Attach market code to each row
            for r in rows:
                r["market"] = market

            total_success += 1
            total_rows += len(rows)

            # Update market stats
            dates = [r["date"] for r in rows]
            ms = market_stats.setdefault(market, {
                "symbols": [], "total_rows": 0,
                "date_min": dates[0], "date_max": dates[-1],
            })
            ms["symbols"].append(sym)
            ms["total_rows"] += len(rows)
            if dates[0] < ms["date_min"]:
                ms["date_min"] = dates[0]
            if dates[-1] > ms["date_max"]:
                ms["date_max"] = dates[-1]

            writer.add(rows)

    shard_paths = writer.close()
    log.info("Wrote %d shards, %d total rows", len(shard_paths), total_rows)

    # Upload shards to S3
    s3_total_bytes = 0
    uploaded = []
    for p in shard_paths:
        key = S3_PREFIX + p.name
        sz = s3_upload(p, key)
        s3_total_bytes += sz
        uploaded.append(key)
        log.info("uploaded %s → s3://%s/%s (%d KB)", p.name, S3_BUCKET, key, sz // 1024)
        p.unlink()  # delete local after upload

    # Build manifest
    manifest = {
        "generated": datetime.now(tz=timezone.utc).isoformat(),
        "source": "Yahoo Finance v8 API (keyless, full history)",
        "total_rows": total_rows,
        "total_bytes_s3": s3_total_bytes,
        "s3_prefix": f"s3://{S3_BUCKET}/{S3_PREFIX}",
        "n_symbols_attempted": total_attempted,
        "n_symbols_success": total_success,
        "n_symbols_empty": total_empty,
        "n_shards": len(shard_paths),
        "markets": {
            mkt: {
                "n_symbols": len(ms["symbols"]),
                "total_rows": ms["total_rows"],
                "date_min": ms["date_min"],
                "date_max": ms["date_max"],
            }
            for mkt, ms in sorted(market_stats.items())
        },
        "gaps": gaps,
    }

    manifest_path = STAGE / "_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    s3_upload(manifest_path, S3_PREFIX + "_manifest.json")
    manifest_path.unlink()

    log.info("Done. %d symbols, %d rows, %.1f MB compressed on S3",
             total_success, total_rows, s3_total_bytes / 1_000_000)
    print(json.dumps({
        "markets": {m: v["n_symbols"] for m, v in manifest["markets"].items()},
        "total_symbols": total_success,
        "total_rows": total_rows,
        "s3_prefix": manifest["s3_prefix"],
        "s3_bytes": s3_total_bytes,
        "n_shards": len(shard_paths),
    }, indent=2))


if __name__ == "__main__":
    main()
