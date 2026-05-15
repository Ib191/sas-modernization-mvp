"""
Generate synthetic raw input data + compute ground-truth outputs by mirroring
the SAS logic from the codebase. The CSV outputs are the "golden" files that
any modernized PySpark/SQL implementation must reproduce.

Run: python generate_data_and_truth.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

ROOT = Path(__file__).parent
INPUT = ROOT / "input_data"
TRUTH = ROOT / "ground_truth"
INPUT.mkdir(exist_ok=True)
TRUTH.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Generate raw demographics (DM)
# ---------------------------------------------------------------------------
N_SUBJ = 20
ARMS = ["PLACEBO", "DRUG_X_LOW", "DRUG_X_HI"]
SEXES = ["M", "F", "U"]
RACES = ["WHITE", "BLACK", "ASIAN", "OTHER"]
SITES = ["01", "02", "03", "04"]  # CHAR with leading zeros - matters later

def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")

dm_rows = []
for i in range(1, N_SUBJ + 1):
    usubjid = f"CTX-{i:03d}"
    arm = random.choice(ARMS)
    sex = random.choice(SEXES)
    race = random.choice(RACES)
    age = random.randint(22, 78)
    birth = date(2024, 1, 1) - timedelta(days=age * 365 + random.randint(0, 364))
    rfst = date(2024, 1, 15) + timedelta(days=random.randint(0, 60))
    rfen = rfst + timedelta(days=random.randint(28, 90))
    site = random.choice(SITES)
    # record creation date (used for dedup)
    rec_dt = rfst + timedelta(days=random.randint(0, 5))

    dm_rows.append({
        "USUBJID": usubjid, "AGE": age, "SEX": sex, "RACE": race,
        "ARM": arm, "SITEID": site,
        "BRTHDTC": iso(birth), "RFSTDTC": iso(rfst), "RFENDTC": iso(rfen),
        "RECORDCREATEDT": iso(rec_dt),
    })

# Inject 2 subjects with duplicate records (to exercise dedup)
for dup_id in ("CTX-005", "CTX-012"):
    base = next(r for r in dm_rows if r["USUBJID"] == dup_id)
    older = base.copy()
    older["AGE"] = base["AGE"] - 1   # stale data
    older["RECORDCREATEDT"] = iso(date.fromisoformat(base["RECORDCREATEDT"]) - timedelta(days=30))
    dm_rows.append(older)

# Inject 1 subject with missing AGE (must be derived from BRTHDTC)
for r in dm_rows:
    if r["USUBJID"] == "CTX-007":
        r["AGE"] = ""
        break

with open(INPUT / "dm.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(dm_rows[0].keys()))
    w.writeheader()
    w.writerows(dm_rows)


# ---------------------------------------------------------------------------
# 2. Generate site lookup
#    NOTE: SITE_ID is NUMERIC here, while DM.SITEID is CHAR with leading
#    zeros. The PROC SQL join in 03_derive_adsl.sas will silently coerce.
# ---------------------------------------------------------------------------
site_rows = [
    {"SITE_ID": 1, "SITE_NAME": "Boston Medical Ctr", "SITE_COUNTRY": "USA", "SITE_REGION": "NA"},
    {"SITE_ID": 2, "SITE_NAME": "Toronto General",    "SITE_COUNTRY": "CAN", "SITE_REGION": "NA"},
    {"SITE_ID": 3, "SITE_NAME": "Charite Berlin",     "SITE_COUNTRY": "DEU", "SITE_REGION": "EU"},
    {"SITE_ID": 4, "SITE_NAME": "Tokyo Univ Hosp",    "SITE_COUNTRY": "JPN", "SITE_REGION": "APAC"},
]
with open(INPUT / "site_lookup.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(site_rows[0].keys()))
    w.writeheader()
    w.writerows(site_rows)


# ---------------------------------------------------------------------------
# 3. Generate raw AE
#    Mix of severity codes - 'MILD'/'MODERATE'/'SEVERE', also '1'/'2'/'3',
#    and a few 'GRADE 1' style records that the cleaning code DROPS silently.
# ---------------------------------------------------------------------------
AE_TERMS = ["HEADACHE", "NAUSEA", "FATIGUE", "RASH", "DIZZINESS",
            "INSOMNIA", "DIARRHEA", "ARTHRALGIA", "FEVER", "COUGH"]
SEV_MIX = ["MILD","MILD","MILD","MODERATE","MODERATE","SEVERE",
           "1","2","3","MOD","SEV", "GRADE 1","GRADE 2"]  # last two: dropped

ae_rows = []
ae_counter = 0
for r in dm_rows:
    # only one record per subject for AEs (use the canonical, latest DM)
    if r["USUBJID"] in ("CTX-005","CTX-012") and r["AGE"] != "" and isinstance(r["AGE"], int) is False:
        # Skip the stale duplicate rows when generating AEs
        pass
    # We'll just iterate distinct subjects:
distinct_subj = []
seen = set()
for r in dm_rows:
    if r["USUBJID"] not in seen:
        seen.add(r["USUBJID"])
        distinct_subj.append(r)

for r in distinct_subj:
    n_ae = random.randint(0, 5)
    rfst = date.fromisoformat(r["RFSTDTC"])
    rfen = date.fromisoformat(r["RFENDTC"])
    for _ in range(n_ae):
        ae_counter += 1
        term = random.choice(AE_TERMS)
        sev = random.choice(SEV_MIX)
        # Some AEs start before treatment (so trtemfl=N), some after
        if random.random() < 0.2:
            # pre-treatment
            start = rfst - timedelta(days=random.randint(1, 14))
        else:
            start = rfst + timedelta(days=random.randint(0, max(1, (rfen - rfst).days)))
        # 30% have an end date
        end = (start + timedelta(days=random.randint(1, 10))) if random.random() < 0.5 else None
        # ~5% of records have a missing start date (will be deleted by cleaning)
        start_str = iso(start) if random.random() > 0.05 else ""
        # 15% serious
        ser = "Y" if random.random() < 0.15 else "N"
        ae_rows.append({
            "USUBJID": r["USUBJID"],
            "AETERM": term,
            "AESEV": sev,
            "AESER": ser,
            "AESTDTC": start_str,
            "AEENDTC": iso(end) if end else "",
        })

with open(INPUT / "ae.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(ae_rows[0].keys()))
    w.writeheader()
    w.writerows(ae_rows)

print(f"Wrote {len(dm_rows)} DM rows, {len(site_rows)} sites, {len(ae_rows)} AE rows")


# ===========================================================================
# COMPUTE GROUND TRUTH (Python mirror of the SAS logic)
# ===========================================================================

# ---- DM_CLEAN ----
def iso_to_date(s):
    if not s: return None
    try: return date.fromisoformat(s[:10])
    except: return None

def calc_age(birth, ref):
    if birth is None or ref is None: return None
    return (ref - birth).days // 365  # SAS uses 365.25 + floor; close enough for ints

def age_group(a):
    if a is None: return ""
    if a < 18:  return "< 18"
    if a < 40:  return "18-39"
    if a < 65:  return "40-64"
    return "65+"

# Stage with derivations
stage = []
for r in dm_rows:
    rfst = iso_to_date(r["RFSTDTC"])
    rfen = iso_to_date(r["RFENDTC"])
    brth = iso_to_date(r["BRTHDTC"])
    age_d = calc_age(brth, rfst)
    age = r["AGE"]
    age = int(age) if age != "" else age_d
    trtdurd = (rfen - rfst).days + 1 if (rfst and rfen) else None
    stage.append({
        "USUBJID": r["USUBJID"], "AGE": age, "AGE_DERIVED": age_d,
        "SEX": r["SEX"], "RACE": r["RACE"],
        "ARM": r["ARM"], "SITEID": r["SITEID"],
        "RFSTDT": rfst.isoformat() if rfst else "",
        "RFENDT": rfen.isoformat() if rfen else "",
        "TRTDURD": trtdurd if trtdurd is not None else "",
        "RECORDCREATEDT": r["RECORDCREATEDT"],
    })

# Dedup: latest record per subject (descending by RECORDCREATEDT)
stage.sort(key=lambda x: (x["USUBJID"], x["RECORDCREATEDT"]), reverse=True)
seen = set()
dedup = []
for r in stage:
    if r["USUBJID"] in seen: continue
    seen.add(r["USUBJID"]); dedup.append(r)
dedup.sort(key=lambda x: x["USUBJID"])

# Decode + agegrp + final keep
SEX_DECODE = {"M":"Male","F":"Female","U":"Unknown"}
ARM_DECODE = {"PLACEBO":"Placebo","DRUG_X_LOW":"Drug X 50mg","DRUG_X_HI":"Drug X 100mg"}
dm_clean = []
for r in dedup:
    dm_clean.append({
        "USUBJID": r["USUBJID"],
        "AGE": r["AGE"], "AGE_DERIVED": r["AGE_DERIVED"] or "",
        "AGEGRP": age_group(r["AGE"]),
        "SEX": r["SEX"], "SEX_DECODE": SEX_DECODE.get(r["SEX"], "Missing"),
        "RACE": r["RACE"],
        "ARM": r["ARM"], "ARM_DECODE": ARM_DECODE.get(r["ARM"], r["ARM"]),
        "RFSTDT": r["RFSTDT"], "RFENDT": r["RFENDT"], "TRTDURD": r["TRTDURD"],
        "SITEID": r["SITEID"],
    })
with open(TRUTH / "dm_clean.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(dm_clean[0].keys()))
    w.writeheader(); w.writerows(dm_clean)

# ---- AE_CLEAN ----
SEV_MAP = {
    "MILD":"MILD", "1":"MILD",
    "MODERATE":"MODERATE", "MOD":"MODERATE", "2":"MODERATE",
    "SEVERE":"SEVERE", "SEV":"SEVERE", "3":"SEVERE",
}
SEV_RANK = {"MILD":1, "MODERATE":2, "SEVERE":3}

ae_stage = []
for r in ae_rows:
    aestdt = iso_to_date(r["AESTDTC"])
    aeendt = iso_to_date(r["AEENDTC"])
    if aestdt is None: continue           # SAS deletes
    if not r["AETERM"]: continue
    sev_std = SEV_MAP.get(r["AESEV"].strip().upper(), "")
    sevn = SEV_RANK.get(sev_std)
    aedur = (aeendt - aestdt).days + 1 if aeendt else None
    ae_stage.append({
        "USUBJID": r["USUBJID"],
        "AETERM": r["AETERM"],
        "AESTDT": aestdt.isoformat(),
        "AEENDT": aeendt.isoformat() if aeendt else "",
        "AEDUR": aedur if aedur is not None else "",
        "AESEV": r["AESEV"],
        "AESEV_STD": sev_std,
        "AESEVN": sevn if sevn is not None else "",
        "AESER": r["AESER"],
    })

# Sort by USUBJID, AESTDT, AETERM and assign AESEQ
ae_stage.sort(key=lambda x: (x["USUBJID"], x["AESTDT"], x["AETERM"]))
last_subj = None; seq = 0
for r in ae_stage:
    if r["USUBJID"] != last_subj:
        seq = 0; last_subj = r["USUBJID"]
    seq += 1; r["AESEQ"] = seq

# Max severity per subject (LAST. by AESEVN ascending => highest rank)
# Note: missing AESEVN sorts first in SAS (treated as low), so will not be picked as max
max_sev = {}
ae_with_rank = sorted(
    [r for r in ae_stage],
    key=lambda x: (x["USUBJID"], x["AESEVN"] if x["AESEVN"] != "" else -1)
)
for r in ae_with_rank:
    max_sev[r["USUBJID"]] = (r["AESEV_STD"], r["AESEVN"])

ae_clean = []
for r in ae_stage:
    ms, mn = max_sev.get(r["USUBJID"], ("", ""))
    ae_clean.append({**r, "MAX_AESEV": ms, "MAX_AESEVN": mn})
# Order columns
ae_cols = ["USUBJID","AESEQ","AETERM","AESTDT","AEENDT","AEDUR",
           "AESEV","AESEV_STD","AESEVN","AESER","MAX_AESEV","MAX_AESEVN"]
with open(TRUTH / "ae_clean.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ae_cols)
    w.writeheader()
    for r in ae_clean: w.writerow({k: r.get(k, "") for k in ae_cols})


# ---- ADSL ----
# Site lookup join: DM.SITEID is "01","02"... ; SITE_LOOKUP.SITE_ID is 1,2,...
# SAS implicit cast: char "01" -> 1, joins succeed. PySpark will not. Mirror SAS.
site_by_id = {int(s["SITE_ID"]): s for s in site_rows}
adsl = []
for r in dm_clean:
    siteid_int = int(r["SITEID"])
    s = site_by_id.get(siteid_int, {})
    saffl = "Y" if r["RFSTDT"] else "N"
    ittfl = "Y" if (saffl == "Y" and r["ARM"] != "PLACEBO") else "N"
    adsl.append({**r,
                 "SITE_NAME": s.get("SITE_NAME",""),
                 "SITE_COUNTRY": s.get("SITE_COUNTRY",""),
                 "SITE_REGION": s.get("SITE_REGION",""),
                 "SAFFL": saffl, "ITTFL": ittfl})
adsl_cols = list(dm_clean[0].keys()) + ["SITE_NAME","SITE_COUNTRY","SITE_REGION","SAFFL","ITTFL"]
with open(TRUTH / "adsl.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=adsl_cols)
    w.writeheader(); w.writerows(adsl)

# Cohort treatment start date = max(RFSTDT) for SAFFL='Y'
trt_start_dt = max(r["RFSTDT"] for r in adsl if r["SAFFL"] == "Y")


# ---- ADAE ----
adsl_by_id = {r["USUBJID"]: r for r in adsl}
adae = []
for r in ae_clean:
    a = adsl_by_id.get(r["USUBJID"])
    if not a: continue
    aestdt = r["AESTDT"]
    rfst = a["RFSTDT"]; rfen = a["RFENDT"]
    trtemfl = "Y" if (aestdt and aestdt >= trt_start_dt) else "N"
    ontrtfl = "Y" if (aestdt and rfst and rfen and rfst <= aestdt <= rfen) else "N"
    if aestdt and rfst:
        astdy = (date.fromisoformat(aestdt) - date.fromisoformat(rfst)).days + 1
    else:
        astdy = ""
    adae.append({
        **r,
        "AGE": a["AGE"], "AGEGRP": a["AGEGRP"], "SEX": a["SEX"],
        "ARM": a["ARM"], "ARM_DECODE": a["ARM_DECODE"],
        "RFSTDT": rfst, "RFENDT": rfen,
        "SAFFL": a["SAFFL"], "ITTFL": a["ITTFL"],
        "TRTEMFL": trtemfl, "ONTRTFL": ontrtfl, "ASTDY": astdy,
    })
adae_cols = list(ae_clean[0].keys()) + ["AGE","AGEGRP","SEX","ARM","ARM_DECODE",
                                         "RFSTDT","RFENDT","SAFFL","ITTFL",
                                         "TRTEMFL","ONTRTFL","ASTDY"]
with open(TRUTH / "adae.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=adae_cols)
    w.writeheader()
    for r in adae: w.writerow({k: r.get(k, "") for k in adae_cols})


# ---- AE_SUMMARY ----
from collections import defaultdict
summ = defaultdict(lambda: {"n_events":0, "n_serious":0})
for r in adae:
    if r["TRTEMFL"] != "Y": continue
    key = (r["ARM"], r["ARM_DECODE"], r["AESEV_STD"])
    summ[key]["n_events"] += 1
    if r["AESER"] == "Y": summ[key]["n_serious"] += 1
ae_summary = [
    {"ARM": k[0], "ARM_DECODE": k[1], "SEVERITY": k[2],
     "N_EVENTS": v["n_events"], "N_SERIOUS": v["n_serious"]}
    for k, v in sorted(summ.items())
]
with open(TRUTH / "ae_summary.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(ae_summary[0].keys()))
    w.writeheader(); w.writerows(ae_summary)


# ---- AE_INCIDENCE (subject-level worst-case) ----
denom = defaultdict(int)
for r in adsl:
    if r["SAFFL"] == "Y":
        denom[(r["ARM"], r["ARM_DECODE"])] += 1

# Subject-level: their max severity from TE AEs
subj_max = {}
for r in adae:
    if r["TRTEMFL"] != "Y": continue
    key = r["USUBJID"]
    cur = subj_max.get(key, ("", -1, r["ARM"], r["ARM_DECODE"]))
    msn = r["MAX_AESEVN"] if r["MAX_AESEVN"] != "" else -1
    if msn > cur[1]:
        subj_max[key] = (r["MAX_AESEV"], msn, r["ARM"], r["ARM_DECODE"])

inc_buckets = defaultdict(int)
for sev, sevn, arm, armd in subj_max.values():
    inc_buckets[(arm, armd, sev, sevn)] += 1

ae_incidence = []
for (arm, armd, sev, sevn), n in sorted(inc_buckets.items()):
    total = denom.get((arm, armd), 0)
    rate = n / total if total else None
    ae_incidence.append({
        "ARM": arm, "ARM_DECODE": armd,
        "WORST_SEVERITY": sev, "WORST_SEVERITY_RANK": sevn,
        "N_SUBJ_WITH_AE": n, "N_SUBJ_TOTAL": total,
        "INCIDENCE_RATE": round(rate, 4) if rate is not None else "",
    })
with open(TRUTH / "ae_incidence.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(ae_incidence[0].keys()))
    w.writeheader(); w.writerows(ae_incidence)

print("Ground truth written.")
print(f"  dm_clean: {len(dm_clean)} rows")
print(f"  ae_clean: {len(ae_clean)} rows")
print(f"  adsl:     {len(adsl)} rows")
print(f"  adae:     {len(adae)} rows")
print(f"  ae_summary:   {len(ae_summary)} rows")
print(f"  ae_incidence: {len(ae_incidence)} rows")
print(f"  TRT_START_DT (cohort): {trt_start_dt}")
