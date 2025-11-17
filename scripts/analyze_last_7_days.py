#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze last 7 days to assess charging effectiveness versus price thresholds
and identify missed selling opportunities, incorporating house consumption
patterns for predictability checks.

Primary data source: dashboard API at http://192.168.33.10:8080/
Fallbacks: out/daily_snapshots/ and out/energy_data/

Outputs (written to out/):
- charge_deferral_findings.csv
- sell_opportunity_findings.csv
- analysis_7d_summary.md

Usage:
  python3 scripts/analyze_last_7_days.py

Optional args:
  --base-url http://host:8080      Override dashboard base URL
  --days 7                         Number of days to analyze (default 7)
  --out-dir out                    Output directory
  --min-soc 0.2                    Minimum SOC reserve as fraction if not detectable (default 0.2)
  --sell-soc-threshold 0.5         SOC threshold for selling (default 0.5)
  --p25 0.25                       Low-price percentile (default 0.25)
  --p80 0.8                        High-price percentile (default 0.8)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import math
from pathlib import Path
import glob

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    import pandas as pd
    import numpy as np
except Exception as exc:  # pragma: no cover
    raise SystemExit("This script requires pandas and numpy. Please install them.") from exc

# Ensure we can import project modules from src/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from automated_price_charging import AutomatedPriceCharger  # type: ignore
except Exception:
    AutomatedPriceCharger = None  # type: ignore


DEFAULT_BASE_URL = "http://192.168.33.10:8080"


@dataclass
class Config:
    base_url: str
    days: int
    out_dir: str
    min_soc_reserve: float
    sell_soc_threshold: float
    p_low: float
    p_high: float


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Analyze last 7 days charging effectiveness and selling opportunities")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--out-dir", default="out")
    parser.add_argument("--min-soc", type=float, default=0.20)
    parser.add_argument("--sell-soc-threshold", type=float, default=0.50)
    parser.add_argument("--p25", type=float, default=0.25)
    parser.add_argument("--p80", type=float, default=0.80)
    args = parser.parse_args()
    return Config(
        base_url=args.base_url.rstrip("/"),
        days=args.days,
        out_dir=args.out_dir,
        min_soc_reserve=args.min_soc,
        sell_soc_threshold=args.sell_soc_threshold,
        p_low=args.p25,
        p_high=args.p80,
    )


def _safe_request_json(url: str, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    if requests is None:
        return None
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None


def load_historical(base_url: str) -> Optional[Dict[str, Any]]:
    return _safe_request_json(f"{base_url}/historical-data")


def load_decisions(base_url: str, days: int) -> Optional[List[Dict[str, Any]]]:
    # Prefer 7d range if available on API
    range_param = "7d" if days >= 7 else "24h"
    data = _safe_request_json(f"{base_url}/decisions?time_range={range_param}")
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "decisions" in data and isinstance(data["decisions"], list):
        return data["decisions"]
    return None


def load_price_series_from_files(days: int) -> pd.Series:
    """Fallback: build hourly price series from recent files in out/energy_data/.
    Accepts common fields: timestamp/time, price/price_pln/energy_price.
    """
    base = Path("out") / "energy_data"
    files: List[str] = []
    if base.exists():
        files.extend(sorted(glob.glob(str(base / "*.json")), reverse=True))
    records: List[Dict[str, Any]] = []
    for fp in files[:200]:  # cap to avoid scanning too much
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "decisions" in data and isinstance(data["decisions"], list):
                for d in data["decisions"]:
                    records.append(d)
            elif isinstance(data, list):
                records.extend(data)
        except Exception:
            continue
    # Fallback to charging schedule files if no decision records
    if not records:
        sched_files = sorted(glob.glob(str(Path("out") / "charging_schedule_*.json")), reverse=True)
        sched_records: List[Dict[str, Any]] = []
        for fp in sched_files[:30]:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Expect list of hourly entries with timestamp and price
                if isinstance(data, list):
                    for d in data:
                        sched_records.append(d)
                elif isinstance(data, dict) and "schedule" in data:
                    sched_records.extend(data.get("schedule", []))
            except Exception:
                continue
        if not sched_records:
            return pd.Series(dtype=float)
        sdf = pd.DataFrame.from_records(sched_records)
        ts_col = None
        for c in ("timestamp", "time", "ts", "date"):
            if c in sdf.columns:
                ts_col = c
                break
        if ts_col is None:
            return pd.Series(dtype=float)
        sdf[ts_col] = pd.to_datetime(sdf[ts_col], errors="coerce")
        sdf = sdf.dropna(subset=[ts_col]).rename(columns={ts_col: "timestamp"}).set_index("timestamp").sort_index()
        price_col = None
        for c in ("price", "price_pln", "market_price", "energy_price"):
            if c in sdf.columns:
                price_col = c
                break
        if price_col is None:
            return pd.Series(dtype=float)
        s = pd.to_numeric(sdf[price_col], errors="coerce")
        s = s[~s.isna()]
        if s.empty:
            return s
        end = s.index.max()
        start = end - pd.Timedelta(days=days)
        return s.loc[(s.index >= start) & (s.index <= end)].resample("H").mean()
    df = pd.DataFrame.from_records(records)
    # timestamp
    ts_col = None
    for c in ("timestamp", "time", "ts", "decision_time"):
        if c in df.columns:
            ts_col = c
            break
    if ts_col is None:
        return pd.Series(dtype=float)
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=[ts_col]).rename(columns={ts_col: "timestamp"}).set_index("timestamp").sort_index()
    # price
    price_col = None
    for c in ("price", "price_pln", "market_price", "energy_price"):
        if c in df.columns:
            price_col = c
            break
    if price_col is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(df[price_col], errors="coerce")
    s = s[~s.isna()]
    if s.empty:
        return s
    # restrict
    end = s.index.max()
    start = end - pd.Timedelta(days=days)
    s = s.loc[(s.index >= start) & (s.index <= end)]
    # hourly
    return s.resample("H").mean()


def fetch_price_series_via_charger(days: int) -> Optional[pd.Series]:
    """Use AutomatedPriceCharger to fetch last N days of price data and compute final prices.
    Returns hourly series in PLN/kWh.
    """
    if AutomatedPriceCharger is None:
        return None
    try:
        charger = AutomatedPriceCharger()
    except Exception:
        return None
    all_rows: List[Tuple[pd.Timestamp, float]] = []
    today = dt.datetime.now().date()
    for d in range(days):
        day = today - dt.timedelta(days=d)
        date_str = day.strftime('%Y-%m-%d')
        pdata = None
        try:
            pdata = charger.fetch_price_data_for_date(date_str)
        except Exception:
            pdata = None
        if not pdata or 'value' not in pdata:
            continue
        for item in pdata['value']:
            dtime_str = item.get('dtime')
            if not dtime_str:
                continue
            try:
                if ':' in dtime_str and dtime_str.count(':') == 2:
                    item_time = dt.datetime.strptime(dtime_str, '%Y-%m-%d %H:%M:%S')
                else:
                    item_time = dt.datetime.strptime(dtime_str, '%Y-%m-%d %H:%M')
            except ValueError:
                continue
            market_price_pln_mwh = float(item.get('csdac_pln', 0.0))
            try:
                final_price_pln_mwh = charger.calculate_final_price(market_price_pln_mwh, item_time)
            except Exception:
                final_price_pln_mwh = market_price_pln_mwh + 89.2  # fallback SC-only
            final_price_pln_kwh = final_price_pln_mwh / 1000.0
            all_rows.append((pd.Timestamp(item_time), float(final_price_pln_kwh)))
    if not all_rows:
        return None
    df = pd.DataFrame(all_rows, columns=['timestamp', 'price']).set_index('timestamp').sort_index()
    return df['price'].resample('H').mean()


def load_config_min_soc() -> Optional[float]:
    cfg_path = os.path.join("config", "master_coordinator_config.yaml")
    if not os.path.exists(cfg_path):
        return None
    try:
        import yaml  # lazy import, optional
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        # Try common places for min SOC
        for key in ["min_soc", "min_soc_reserve", "battery_min_soc", "safety_min_soc"]:
            v = cfg.get(key)
            if isinstance(v, (int, float)):
                return float(v) / (100.0 if v > 1 else 1.0)
        return None
    except Exception:
        return None


def df_from_historical_payload(payload: Dict[str, Any]) -> pd.DataFrame:
    # Expecting keys like timestamps, soc, pv, load, price, import/export, etc.
    # Normalize to a common hourly time index
    records: List[Dict[str, Any]] = []
    # Case A: flat rows under common keys
    for key in ["data", "historical", "items", "rows", "points"]:
        if key in payload and isinstance(payload[key], list) and payload[key] and isinstance(payload[key][0], dict):
            for row in payload[key]:
                records.append(row)
            break
    # Case B: Chart-like series with {name, data:[[ts, value], ...]}
    if not records and isinstance(payload.get("series"), list):
        series_list = payload["series"]
        # Build a wide frame from series
        series_frames = []
        for s in series_list:
            name = str(s.get("name", "series")).lower()
            data = s.get("data")
            if isinstance(data, list) and data and isinstance(data[0], (list, tuple)) and len(data[0]) >= 2:
                sdf = pd.DataFrame(data, columns=["timestamp", name])
                sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], errors="coerce")
                sdf = sdf.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
                series_frames.append(sdf)
        if series_frames:
            df = pd.concat(series_frames, axis=1).sort_index()
            # Normalize frequency to hourly for our analysis
            df = df.resample("H").mean()
            return df
    if not records and all(k in payload for k in ("timestamps", "soc")):
        timestamps = payload.get("timestamps", [])
        for i, ts in enumerate(timestamps):
            row: Dict[str, Any] = {"timestamp": ts}
            for k, v in payload.items():
                if isinstance(v, list) and len(v) == len(timestamps) and k != "timestamps":
                    row[k] = v[i]
            records.append(row)

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    # Standardize timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        df = df.set_index("timestamp")
    else:
        # Try alternative
        for alt in ("time", "ts", "date"):
            if alt in df.columns:
                df[alt] = pd.to_datetime(df[alt], errors="coerce")
                df = df.dropna(subset=[alt]).sort_values(alt)
                df = df.set_index(alt)
                df.index.name = "timestamp"
                break
    # Coerce numeric
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors="ignore")
    # Resample hourly if too granular
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.freq is None or df.index.freq != "H":
            agg_map = {}
            for c in df.columns:
                agg_map[c] = "mean"
            df = df.resample("H").agg(agg_map)
    return df


def extract_price_series_from_payload(payload: Dict[str, Any]) -> Optional[pd.Series]:
    """Try multiple shapes to extract a price time series from historical-data payload."""
    # Try Chart-like series first
    if isinstance(payload.get("series"), list):
        for s in payload["series"]:
            name = str(s.get("name", "")).lower()
            if "price" in name:
                data = s.get("data")
                if isinstance(data, list) and data and isinstance(data[0], (list, tuple)):
                    sdf = pd.DataFrame(data, columns=["timestamp", "price"])  # type: ignore[arg-type]
                    sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], errors="coerce")
                    sdf = sdf.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
                    return pd.to_numeric(sdf["price"], errors="coerce").resample("H").mean()
    # Try flattened arrays
    if all(k in payload for k in ("timestamps",)):
        timestamps = payload.get("timestamps", [])
        if isinstance(timestamps, list) and timestamps:
            df = pd.DataFrame({"timestamp": timestamps})
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            # Any column containing 'price'
            price_cols = [k for k, v in payload.items() if k != "timestamps" and "price" in k.lower() and isinstance(v, list) and len(v) == len(timestamps)]
            for pc in price_cols:
                s = pd.to_numeric(pd.Series(payload[pc], index=df.index), errors="coerce")
                if not s.isna().all():
                    return s.resample("H").mean()
    # Try dict rows under common keys
    for key in ["data", "historical", "items", "rows", "points"]:
        if key in payload and isinstance(payload[key], list) and payload[key] and isinstance(payload[key][0], dict):
            df = pd.DataFrame.from_records(payload[key])
            # timestamp
            ts_col = None
            for c in ("timestamp", "time", "ts", "date"):
                if c in df.columns:
                    ts_col = c
                    break
            if ts_col is None:
                continue
            df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
            df = df.dropna(subset=[ts_col]).rename(columns={ts_col: "timestamp"}).set_index("timestamp").sort_index()
            # price columns
            price_cols = [c for c in df.columns if "price" in str(c).lower()]
            for pc in price_cols:
                s = pd.to_numeric(df[pc], errors="coerce")
                if not s.isna().all():
                    return s.resample("H").mean()
    return None


def df_from_decisions(decisions: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(decisions)
    if df.empty:
        return df
    # Normalize timestamp
    ts_col = None
    for c in ["timestamp", "time", "ts", "decision_time"]:
        if c in df.columns:
            ts_col = c
            break
    if ts_col is None:
        return pd.DataFrame()
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=[ts_col]).sort_values(ts_col)
    df = df.rename(columns={ts_col: "timestamp"})
    df = df.set_index("timestamp")
    # Standardize action and price columns when available
    for action_col in ["action", "decision", "type"]:
        if action_col in df.columns:
            df["action"] = df[action_col]
            break
    for price_col in ["price", "price_pln", "market_price", "energy_price"]:
        if price_col in df.columns:
            df["price"] = pd.to_numeric(df[price_col], errors="coerce")
            break
    return df


def restrict_last_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df
    end = df.index.max()
    start = end - pd.Timedelta(days=days)
    return df.loc[(df.index >= start) & (df.index <= end)]


def compute_percentile_bands(price_series: pd.Series, p_low: float, p_high: float) -> pd.DataFrame:
    if price_series.empty:
        return pd.DataFrame(index=price_series.index)
    # Rolling next-24h percentiles: shift(-1) window or centered approximation
    # We approximate with trailing window as a proxy for simplicity and robustness
    window = 24
    p25 = price_series.rolling(window=window, min_periods=max(4, window // 4)).quantile(p_low)
    p80 = price_series.rolling(window=window, min_periods=max(4, window // 4)).quantile(p_high)
    out = pd.DataFrame(index=price_series.index)
    out["price"] = price_series
    out["p25"] = p25
    out["p80"] = p80
    # Labels
    out["zone"] = np.where(out["price"] <= out["p25"], "low",
                        np.where(out["price"] >= out["p80"], "high", "mid"))
    return out


def model_load_patterns(df_hist: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    """Return hour-of-day baseline mean, p10, p90 and annotated frame with z-scores.

    Uses 'load' column if available; otherwise uses a proxy built from available fields.
    """
    series: Optional[pd.Series] = None
    if "load" in df_hist.columns:
        series = pd.to_numeric(df_hist["load"], errors="coerce")
    else:
        # Proxy: prefer grid_import + battery_discharge - pv_used if available
        candidates = []
        for cols in [
            ("grid_import", "battery_discharge", "pv_used"),
            ("grid_import", "battery_discharge", None),
            ("consumption", None, None),
            ("house_load", None, None),
        ]:
            if all((c is None or c in df_hist.columns) for c in cols):
                s = None
                if cols[2] is not None:
                    s = (pd.to_numeric(df_hist.get(cols[0], 0), errors="coerce").fillna(0)
                         + pd.to_numeric(df_hist.get(cols[1], 0), errors="coerce").fillna(0)
                         - pd.to_numeric(df_hist.get(cols[2], 0), errors="coerce").fillna(0))
                elif cols[1] is not None:
                    s = (pd.to_numeric(df_hist.get(cols[0], 0), errors="coerce").fillna(0)
                         + pd.to_numeric(df_hist.get(cols[1], 0), errors="coerce").fillna(0))
                else:
                    s = pd.to_numeric(df_hist.get(cols[0], 0), errors="coerce")
                candidates.append(s)
        if candidates:
            series = candidates[0]
    if series is None:
        series = pd.Series(index=df_hist.index, dtype=float)

    hod = series.groupby(series.index.hour)
    mean = hod.mean()
    p10 = hod.quantile(0.10)
    p90 = hod.quantile(0.90)

    # annotate frame
    annotated = df_hist.copy()
    annotated["load_proxy"] = series
    annotated["hod"] = annotated.index.hour
    annotated = annotated.join(mean.rename("load_hod_mean"), on="hod")
    annotated = annotated.join(p10.rename("load_hod_p10"), on="hod")
    annotated = annotated.join(p90.rename("load_hod_p90"), on="hod")
    with np.errstate(divide="ignore", invalid="ignore"):
        annotated["load_cv"] = (annotated["load_hod_p90"] - annotated["load_hod_p10"]) / (annotated["load_hod_mean"].replace(0, np.nan))
    return mean, p10, p90, annotated


def identify_charge_events(df_dec: pd.DataFrame) -> pd.DataFrame:
    if df_dec.empty:
        return df_dec
    df = df_dec.copy()
    if "action" in df.columns:
        # Normalize charge/discharge labels
        df["action_norm"] = df["action"].astype(str).str.lower()
    else:
        df["action_norm"] = "unknown"
    return df


def evaluate_deferral(
    df_events: pd.DataFrame,
    price_bands: pd.DataFrame,
    load_ann: pd.DataFrame,
    min_soc: float,
    p25_label: str = "low",
) -> pd.DataFrame:
    if df_events.empty or price_bands.empty:
        return pd.DataFrame()
    merged = df_events.join(price_bands, how="left")
    findings: List[Dict[str, Any]] = []
    for ts, row in merged.iterrows():
        action = str(row.get("action_norm", ""))
        price = row.get("price", np.nan)
        zone = row.get("zone", None)
        if not isinstance(price, (int, float, np.floating)) or math.isnan(price):
            continue
        # Consider only charge-like actions
        if "charge" not in action:
            continue
        # If not already low price, candidate for deferral
        if zone != p25_label:
            # Feasibility check: skip if load predictability for next hours is low (cv too high)
            la = load_ann.loc[:ts].tail(1)
            cv = float(la["load_cv"].iloc[0]) if not la.empty and not pd.isna(la["load_cv"].iloc[0]) else 0.0
            predictable = cv < 0.8  # heuristic threshold
            if not predictable:
                continue
            # Estimate savings vs median p25 in next day window using trailing p25 as proxy
            p25_value = price_bands.loc[:ts]["p25"].tail(24).median()
            if pd.isna(p25_value):
                continue
            potential_saving = max(0.0, float(price - p25_value))
            if potential_saving <= 0:
                continue
            findings.append({
                "timestamp": ts,
                "action": action,
                "price": float(price),
                "p25": float(p25_value),
                "estimated_price_saving_pln_per_kwh": round(potential_saving, 4),
            })
    return pd.DataFrame(findings).set_index("timestamp") if findings else pd.DataFrame()


def evaluate_selling(
    df_events: pd.DataFrame,
    price_bands: pd.DataFrame,
    sell_soc_threshold: float,
) -> pd.DataFrame:
    if price_bands.empty:
        return pd.DataFrame()
    # If decisions include SOC or not; we rely on price bands only for signaling windows
    candidates = price_bands[price_bands["zone"] == "high"].copy()
    if candidates.empty:
        return pd.DataFrame()
    # We do not know SOC time series here; list candidate windows and annotate policy
    candidates["soc_condition"] = f">= {int(sell_soc_threshold*100)}%"
    candidates["action_suggested"] = "sell"
    return candidates[["price", "p80", "action_suggested", "soc_condition"]]


def write_markdown_report(
    out_dir: str,
    deferral_df: pd.DataFrame,
    sell_df: pd.DataFrame,
    price_bands: pd.DataFrame,
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "analysis_7d_summary.md")
    lines: List[str] = []
    lines.append("# 7-Day Charging Effectiveness Summary\n")
    total = len(price_bands) if price_bands is not None else 0
    if not price_bands.empty:
        counts = price_bands["zone"].value_counts(dropna=False)
        low = int(counts.get("low", 0))
        mid = int(counts.get("mid", 0))
        high = int(counts.get("high", 0))
        lines.append(f"- Low-price hours (<= p25): {low}/{total}\n")
        lines.append(f"- High-price hours (>= p80): {high}/{total}\n")
        lines.append(f"- Mid-price hours: {mid}/{total}\n")
    lines.append("")
    lines.append("## Charge deferral candidates (price > p25)\n")
    lines.append(f"Rows: {0 if deferral_df is None else len(deferral_df)}\n")
    if deferral_df is not None and not deferral_df.empty:
        head = deferral_df.sort_values("estimated_price_saving_pln_per_kwh", ascending=False).head(5)
        for ts, r in head.iterrows():
            lines.append(f"- {ts}: price={r['price']:.4f}, p25={r['p25']:.4f}, potential_saving/kWh={r['estimated_price_saving_pln_per_kwh']:.4f}\n")
    lines.append("")
    lines.append("## Selling opportunity windows (price >= p80)\n")
    lines.append(f"Rows: {0 if sell_df is None else len(sell_df)}\n")
    if sell_df is not None and not sell_df.empty:
        head2 = sell_df.sort_values("price", ascending=False).head(5)
        for ts, r in head2.iterrows():
            lines.append(f"- {ts}: price={r['price']:.4f}, SOC condition={r['soc_condition']}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    cfg = parse_args()
    os.makedirs(cfg.out_dir, exist_ok=True)

    # Attempt to load min SOC from config if available
    detected_min_soc = load_config_min_soc()
    min_soc = detected_min_soc if detected_min_soc is not None else cfg.min_soc_reserve

    historical_payload = load_historical(cfg.base_url)
    decisions_payload = load_decisions(cfg.base_url, cfg.days)

    if historical_payload is None and decisions_payload is None:
        print("Warning: API not reachable; analysis will be limited.")

    df_hist = df_from_historical_payload(historical_payload) if historical_payload else pd.DataFrame()
    df_dec = df_from_decisions(decisions_payload) if decisions_payload else pd.DataFrame()

    # Restrict to last N days
    if not df_hist.empty:
        df_hist = restrict_last_days(df_hist, cfg.days)
    if not df_dec.empty:
        df_dec = restrict_last_days(df_dec, cfg.days)

    # Price series selection
    price_series = None
    # Try to extract price directly from payload shapes if available
    if historical_payload:
        ps = extract_price_series_from_payload(historical_payload)
        if ps is not None and not ps.isna().all() and len(ps) > 0:
            price_series = ps
    # If not found, inspect normalized historical dataframe
    if price_series is None and not df_hist.empty:
        for col in ["price", "price_pln", "final_price", "market_price", "energy_price", "csdac_price", "price_final"]:
            if col in df_hist.columns:
                price_series = pd.to_numeric(df_hist[col], errors="coerce")
                if not price_series.isna().all():
                    break
    if price_series is None and "price" in df_dec.columns:
        # Fallback: build hourly series from decisions
        price_series = pd.to_numeric(df_dec["price"], errors="coerce").resample("H").mean()
    if price_series is None or price_series.isna().all() or len(price_series) == 0:
        # Try project API via AutomatedPriceCharger (CSDAC + tariff-aware final prices)
        price_series = fetch_price_series_via_charger(cfg.days)
    if price_series is None or price_series.isna().all() or len(price_series) == 0:
        # Fallback from files
        price_series = load_price_series_from_files(cfg.days)
    if price_series is None or price_series.isna().all() or len(price_series) == 0:
        print("No price series available. Exiting.")
        return 1

    price_bands = compute_percentile_bands(price_series, cfg.p_low, cfg.p_high)

    # Load modeling
    _, _, _, load_ann = model_load_patterns(df_hist if not df_hist.empty else price_bands)

    # Events
    df_events = identify_charge_events(df_dec)

    # Analyses
    deferral_df = evaluate_deferral(df_events, price_bands, load_ann, min_soc)
    sell_df = evaluate_selling(df_events, price_bands, cfg.sell_soc_threshold)

    # Write outputs
    deferral_path = os.path.join(cfg.out_dir, "charge_deferral_findings.csv")
    sell_path = os.path.join(cfg.out_dir, "sell_opportunity_findings.csv")
    report_path = os.path.join(cfg.out_dir, "analysis_7d_summary.md")
    if deferral_df is not None and not deferral_df.empty:
        deferral_df.to_csv(deferral_path)
    else:
        # Write empty with header for consistency
        pd.DataFrame(columns=["timestamp","action","price","p25","estimated_price_saving_pln_per_kwh"]).to_csv(deferral_path, index=False)
    if sell_df is not None and not sell_df.empty:
        sell_df.to_csv(sell_path)
    else:
        pd.DataFrame(columns=["timestamp","price","p80","action_suggested","soc_condition"]).to_csv(sell_path, index=False)
    write_markdown_report(cfg.out_dir, deferral_df, sell_df, price_bands)

    print(f"Wrote: {deferral_path}")
    print(f"Wrote: {sell_path}")
    print(f"Wrote: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


