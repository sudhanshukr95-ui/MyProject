import re
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


# ---------- Data Models ----------

@dataclass
class ScgFailure:
    time: str
    msg_id: str
    rb: int
    pci: int
    freq: int
    failure_type: str
    raw: str


@dataclass
class NrMl1Meas:
    time: str
    pci: int
    arfcn: int
    ssb_index: int
    cell_rsrp: float
    cell_rsrq: float
    beam_rsrp: float
    beam_rsrq: float
    raw: str

@dataclass
class RrcConfig:
    time: str
    pci: int
    freq: int
    t310: Optional[str]
    n310: Optional[str]
    n311: Optional[str]
    raw: str

# ---------- Regex Patterns ----------

SCG_HEADER = re.compile(
    r'(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+\[(?P<msg_id>0x[0-9A-F]+)\]\s+UL_DCCH\s*/\s*.*scgFailureInformationNR_r15',re.DOTALL)

SCG_META = re.compile(
    r'Radio Bearer ID\s*=\s*(?P<rb>\d+),\s*Physical Cell ID\s*=\s*(?P<pci>\d+).*?Freq\s*=\s*(?P<freq>\d+)',
    re.DOTALL
)

SCG_TYPE = re.compile(
    r'failureType-r15\s+(?P<ftype>[a-zA-Z0-9\-]+)'
)

ML1_TIME = re.compile(
    r'(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+\[0x[0-9A-F]+\]\s+NR5G ML1 Searcher Measurement Database Update Ext')

ML1_ARFCN = re.compile(r'Raster ARFCN =\s*(?P<arfcn>\d+)')
ML1_PCI = re.compile(r'Serving Cell PCI =\s*(?P<pci>\d+)')
ML1_SSB = re.compile(r'Serving SSB =\s*(?P<ssb>\d+)')
ML1_CELL_RSRP = re.compile(r'Cell Quality RSRP =\s*(?P<rsrp>-?\d+\.\d+)')
ML1_CELL_RSRQ = re.compile(r'Cell Quality RSRQ =\s*(?P<rsrq>-?\d+\.\d+)')
ML1_BEAM_RSRP = re.compile(r'NR2NR Filtered Tx Beam RSRP L3 =\s*(?P<rsrp>-?\d+\.\d+)')
ML1_BEAM_RSRQ = re.compile(r'NR2NR Filtered Tx Beam RSRQ L3 =\s*(?P<rsrq>-?\d+\.\d+)')

RRC_HEADER = re.compile(
    r'(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+\[(?P<msg_id>0x[0-9A-F]+)\]\s+DL_DCCH\s*/\s*RRCConnectionReconfiguration',re.DOTALL)

RRC_META = re.compile(
    r'Radio Bearer ID\s*=\s*(?P<rb>\d+),\s*Physical Cell ID\s*=\s*(?P<pci>\d+).*?Freq\s*=\s*(?P<freq>\d+)',
    re.DOTALL
)


# ---------- Parsing Functions ----------

def parse_scg_failure(block: str) -> Optional[ScgFailure]:
    h = SCG_HEADER.search(block)
    m = SCG_META.search(block)
    f = SCG_TYPE.search(block)
    if not (h and m and f):
        return None
    return ScgFailure(
        time=h.group("time"),
        msg_id=h.group("msg_id"),
        rb=int(m.group("rb")),
        pci=int(m.group("pci")),
        freq=int(m.group("freq")),
        failure_type=f.group("ftype"),
        raw=block.strip()
    )


def parse_nr_ml1_block(block: str) -> Optional[NrMl1Meas]:
    t = ML1_TIME.search(block)
    a = ML1_ARFCN.search(block)
    p = ML1_PCI.search(block)
    s = ML1_SSB.search(block)
    crp = ML1_CELL_RSRP.search(block)
    crq = ML1_CELL_RSRQ.search(block)
    brp = ML1_BEAM_RSRP.search(block)
    brq = ML1_BEAM_RSRQ.search(block)
    if not (t and a and p and s and crp and crq and brp and brq):
        return None
    return NrMl1Meas(
        time=t.group("time"),
        pci=int(p.group("pci")),
        arfcn=int(a.group("arfcn")),
        ssb_index=int(s.group("ssb")),
        cell_rsrp=float(crp.group("rsrp")),
        cell_rsrq=float(crq.group("rsrq")),
        beam_rsrp=float(brp.group("rsrp")),
        beam_rsrq=float(brq.group("rsrq")),
        raw=block.strip()
    )


def parse_rrc_config(block: str) -> Optional[RrcConfig]:
    h = RRC_HEADER.search(block)
    m = RRC_META.search(block)
    if not (h and m):
        return None
    t310 = None
    n310 = None
    n311 = None
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("t310 "):
            t310 = line.split()[1]
        elif line.startswith("n310 "):
            n310 = line.split()[1]
        elif line.startswith("n311 "):
            n311 = line.split()[1]
    return RrcConfig(
        time=h.group("time"),
        pci=int(m.group("pci")),
        freq=int(m.group("freq")),
        t310=t310,
        n310=n310,
        n311=n311,
        raw=block.strip()
    )


# ---------- Utility ----------

def to_time(t: str) -> datetime:
    return datetime.strptime(t, "%H:%M:%S.%f")


# ---------- Failure Reason Engine (all 3GPP SCG types) ----------

def map_failure_type(ft: str) -> str:
    mapping = {
        "t310-Expiry": "SCG Radio Link Failure due to t310 expiry",
        "scg-RLF": "SCG Radio Link Failure (general RLF on NR leg)",
        "scg-BeamFailure": "SCG failure due to beam failure (SSB/CSI-RS beam lost)",
        "scg-BeamFailureRecoveryFailure": "Beam Failure Recovery did not succeed",
        "scg-ChangeFailure": "SCG change/reconfiguration failed",
        "scg-ResumeFailure": "SCG resume procedure failed",
        "scg-SuspendFailure": "SCG suspend procedure failed",
        "scg-AdditionFailure": "SCG addition (EN-DC setup) failed",
        "scg-ModificationFailure": "SCG modification failed",
        "scg-ReleaseFailure": "SCG release procedure failed",
        "scg-ConfigFailure": "SCG configuration could not be applied",
        "otherFailure": "Unspecified SCG failure",
    }
    return mapping.get(ft, f"SCG failure type: {ft}")


def determine_failure_reason(scg: ScgFailure,
                             ml1: Optional[NrMl1Meas],
                             rrc: Optional[RrcConfig]) -> str:
    reasons = [map_failure_type(scg.failure_type)]

    if ml1:
        if ml1.cell_rsrp < -120:
            reasons.append(f"Severely degraded NR RSRP ({ml1.cell_rsrp} dBm)")
        if ml1.cell_rsrq < -20:
            reasons.append(f"Severely degraded NR RSRQ ({ml1.cell_rsrq} dB)")
        if ml1.beam_rsrp < -120:
            reasons.append(f"Beam RSRP collapsed ({ml1.beam_rsrp} dBm)")

    if rrc and rrc.t310:
        reasons.append(f"Configured t310={rrc.t310}, n310={rrc.n310}, n311={rrc.n311}")

    return " | ".join(reasons)


# ---------- Main ----------

def main():
    filename = input("Enter QXDM text file name (e.g., scg_log.txt): ").strip()

    try:
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"File '{filename}' not found.")
        return

    scg_failures = []
    for block in text.split("value UL-DCCH-Message ::="):
        sf = parse_scg_failure(block)
        if sf:
            scg_failures.append(sf)

    ml1_meas_list = []
    for block in text.split("NR5G ML1 Searcher Measurement Database Update Ext"):
        m = parse_nr_ml1_block(block)
        if m:
            ml1_meas_list.append(m)

    rrc_cfg_list = []
    for block in text.split("RRCConnectionReconfiguration"):
        r = parse_rrc_config(block)
        if r:
            rrc_cfg_list.append(r)

    if not scg_failures:
        print("No SCG failures found.")
        return

    for scg in scg_failures:
        ml1_match = None
        t_fail = to_time(scg.time)
        min_delta = 999999.0

        for ml1 in ml1_meas_list:
            dt = to_time(ml1.time)
            delta = (t_fail - dt).total_seconds() * 1000
            if 0 <= delta < min_delta:
                min_delta = delta
                ml1_match = ml1

        rrc_match = rrc_cfg_list[-1] if rrc_cfg_list else None

        print("\n========== SCG FAILURE ==========")
        print(f"Time        : {scg.time}")
        print(f"FailureType : {scg.failure_type}")
        print(f"PCI         : {scg.pci}")
        print(f"Freq        : {scg.freq}")

        if ml1_match:
            print("--- ML1 Context ---")
            print(f"ML1 Time    : {ml1_match.time} (Δ ≈ {min_delta:.2f} ms)")
            print(f"Cell RSRP   : {ml1_match.cell_rsrp} dBm")
            print(f"Cell RSRQ   : {ml1_match.cell_rsrq} dB")
            print(f"Beam RSRP   : {ml1_match.beam_rsrp} dBm")
            print(f"Beam RSRQ   : {ml1_match.beam_rsrq} dB")

        if rrc_match:
            print("--- RRC Config ---")
            print(f"t310        : {rrc_match.t310}")
            print(f"n310        : {rrc_match.n310}")
            print(f"n311        : {rrc_match.n311}")

        reason = determine_failure_reason(scg, ml1_match, rrc_match)
        print("--- Failure Reason ---")
        print(reason)
        print("=================================\n")


if __name__ == "__main__":
    main()
