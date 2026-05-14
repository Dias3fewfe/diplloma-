"""Live packet capture and CICIDS2017-compatible flow feature extraction.

Requires scapy + Npcap (Windows) or libpcap (Linux/macOS).
Must run with administrator / root privileges to open raw sockets.

Usage:
    cap = FlowCapture(on_flow_complete=my_callback)
    cap.start(interface="eth0")   # interface=None -> scapy default
    ...
    cap.stop()
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

try:
    from scapy.all import IP, TCP, UDP, conf, get_if_list, sniff
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

FLOW_TIMEOUT = 30.0       # seconds of inactivity before a flow is finalised
MAX_FLOW_DURATION = 120.0  # hard cap on flow lifetime


# ---------------------------------------------------------------------------
# Per-flow statistics accumulator
# ---------------------------------------------------------------------------

@dataclass
class FlowRecord:
    """Accumulates packet-level statistics for one bidirectional flow."""

    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str

    start_time: float = field(default_factory=time.monotonic)
    last_time:  float = field(default_factory=time.monotonic)

    # Forward (src→dst) packets
    fwd_sizes:        list = field(default_factory=list)
    fwd_times:        list = field(default_factory=list)
    fwd_header_bytes: int  = 0
    fwd_psh_flags:    int  = 0
    fwd_urg_flags:    int  = 0
    fwd_data_pkts:    int  = 0  # act_data_pkt_fwd
    fwd_min_seg:      int  = 0  # min_seg_size_forward
    init_win_fwd:     int  = 0  # Init_Win_bytes_forward

    # Backward (dst→src) packets
    bwd_sizes:        list = field(default_factory=list)
    bwd_times:        list = field(default_factory=list)
    bwd_header_bytes: int  = 0
    bwd_psh_flags:    int  = 0
    bwd_urg_flags:    int  = 0
    init_win_bwd:     int  = 0  # Init_Win_bytes_backward

    # TCP flag totals across all packets
    fin_flags: int = 0
    syn_flags: int = 0
    rst_flags: int = 0
    psh_flags: int = 0
    ack_flags: int = 0
    urg_flags: int = 0
    cwe_flags: int = 0
    ece_flags: int = 0

    # All-packet combined lists
    all_sizes: list = field(default_factory=list)
    all_times: list = field(default_factory=list)

    _fwd_syn_seen: bool = False
    _bwd_syn_seen: bool = False

    def add_packet(
        self,
        is_forward: bool,
        size: int,
        timestamp: float,
        ip_hdr_len: int = 20,
        transport_hdr_len: int = 20,
        flags: int = 0,
        win_size: int = 0,
        payload_len: int = 0,
    ) -> None:
        """Record one packet into this flow."""
        self.last_time = timestamp
        self.all_sizes.append(size)
        self.all_times.append(timestamp)
        hdr = ip_hdr_len + transport_hdr_len

        if is_forward:
            self.fwd_sizes.append(size)
            self.fwd_times.append(timestamp)
            self.fwd_header_bytes += hdr
            if flags & 0x08:
                self.fwd_psh_flags += 1
            if flags & 0x20:
                self.fwd_urg_flags += 1
            if payload_len > 0:
                self.fwd_data_pkts += 1
                if self.fwd_min_seg == 0 or payload_len < self.fwd_min_seg:
                    self.fwd_min_seg = payload_len
            if not self._fwd_syn_seen and (flags & 0x02):
                self.init_win_fwd = win_size
                self._fwd_syn_seen = True
        else:
            self.bwd_sizes.append(size)
            self.bwd_times.append(timestamp)
            self.bwd_header_bytes += hdr
            if flags & 0x08:
                self.bwd_psh_flags += 1
            if flags & 0x20:
                self.bwd_urg_flags += 1
            if not self._bwd_syn_seen and (flags & 0x02):
                self.init_win_bwd = win_size
                self._bwd_syn_seen = True

        if flags:
            self.fin_flags += bool(flags & 0x01)
            self.syn_flags += bool(flags & 0x02)
            self.rst_flags += bool(flags & 0x04)
            self.psh_flags += bool(flags & 0x08)
            self.ack_flags += bool(flags & 0x10)
            self.urg_flags += bool(flags & 0x20)
            self.ece_flags += bool(flags & 0x40)
            self.cwe_flags += bool(flags & 0x80)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _stats(values: list) -> tuple[float, float, float, float]:
    """Return (mean, std, max, min) or all-zeros for an empty list."""
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    a = np.array(values, dtype=float)
    return float(a.mean()), float(a.std()), float(a.max()), float(a.min())


def _iat(timestamps: list) -> tuple[float, float, float, float, float]:
    """Return (total, mean, std, max, min) IAT in microseconds."""
    if len(timestamps) < 2:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    iats = np.diff(sorted(timestamps)) * 1e6
    return float(iats.sum()), float(iats.mean()), float(iats.std()), float(iats.max()), float(iats.min())


def extract_features(flow: FlowRecord) -> dict[str, float]:
    """Compute CICIDS2017-compatible feature dict from a completed FlowRecord."""
    dur_us = max((flow.last_time - flow.start_time) * 1e6, 1.0)
    dur_s  = dur_us / 1e6

    n_fwd, n_bwd = len(flow.fwd_sizes), len(flow.bwd_sizes)
    n_tot = n_fwd + n_bwd
    fb, bb = sum(flow.fwd_sizes), sum(flow.bwd_sizes)
    tot_b = fb + bb

    fwm, fws, fwx, fwn = _stats(flow.fwd_sizes)
    bwm, bws, bwx, bwn = _stats(flow.bwd_sizes)
    alm, als, alx, aln = _stats(flow.all_sizes)

    fi_tot, fi_m, fi_s, fi_x, fi_n = _iat(flow.fwd_times)
    bi_tot, bi_m, bi_s, bi_x, bi_n = _iat(flow.bwd_times)
    ai_tot, ai_m, ai_s, ai_x, ai_n = _iat(flow.all_times)

    bps  = tot_b / dur_s if dur_s else 0.0
    pps  = n_tot / dur_s if dur_s else 0.0
    fpps = n_fwd / dur_s if dur_s else 0.0
    bpps = n_bwd / dur_s if dur_s else 0.0
    du_r = bb / fb if fb else 0.0
    apkt = tot_b / n_tot if n_tot else 0.0
    afwd = fb / n_fwd if n_fwd else 0.0
    abwd = bb / n_bwd if n_bwd else 0.0
    pvar = float(np.var(flow.all_sizes)) if flow.all_sizes else 0.0

    return {
        "Destination Port":          float(flow.dst_port),
        "Flow Duration":             dur_us,
        "Total Fwd Packets":         float(n_fwd),
        "Total Backward Packets":    float(n_bwd),
        "Total Length of Fwd Packets": float(fb),
        "Total Length of Bwd Packets": float(bb),
        "Fwd Packet Length Max":     fwx,
        "Fwd Packet Length Min":     fwn,
        "Fwd Packet Length Mean":    fwm,
        "Fwd Packet Length Std":     fws,
        "Bwd Packet Length Max":     bwx,
        "Bwd Packet Length Min":     bwn,
        "Bwd Packet Length Mean":    bwm,
        "Bwd Packet Length Std":     bws,
        "Flow Bytes/s":              bps,
        "Flow Packets/s":            pps,
        "Flow IAT Mean":             ai_m,
        "Flow IAT Std":              ai_s,
        "Flow IAT Max":              ai_x,
        "Flow IAT Min":              ai_n,
        "Fwd IAT Total":             fi_tot,
        "Fwd IAT Mean":              fi_m,
        "Fwd IAT Std":               fi_s,
        "Fwd IAT Max":               fi_x,
        "Fwd IAT Min":               fi_n,
        "Bwd IAT Total":             bi_tot,
        "Bwd IAT Mean":              bi_m,
        "Bwd IAT Std":               bi_s,
        "Bwd IAT Max":               bi_x,
        "Bwd IAT Min":               bi_n,
        "Fwd PSH Flags":             float(flow.fwd_psh_flags),
        "Bwd PSH Flags":             float(flow.bwd_psh_flags),
        "Fwd URG Flags":             float(flow.fwd_urg_flags),
        "Bwd URG Flags":             float(flow.bwd_urg_flags),
        "Fwd Header Length":         float(flow.fwd_header_bytes),
        "Bwd Header Length":         float(flow.bwd_header_bytes),
        "Fwd Packets/s":             fpps,
        "Bwd Packets/s":             bpps,
        "Min Packet Length":         aln,
        "Max Packet Length":         alx,
        "Packet Length Mean":        alm,
        "Packet Length Std":         als,
        "Packet Length Variance":    pvar,
        "FIN Flag Count":            float(flow.fin_flags),
        "SYN Flag Count":            float(flow.syn_flags),
        "RST Flag Count":            float(flow.rst_flags),
        "PSH Flag Count":            float(flow.psh_flags),
        "ACK Flag Count":            float(flow.ack_flags),
        "URG Flag Count":            float(flow.urg_flags),
        "CWE Flag Count":            float(flow.cwe_flags),
        "ECE Flag Count":            float(flow.ece_flags),
        "Down/Up Ratio":             du_r,
        "Average Packet Size":       apkt,
        "Avg Fwd Segment Size":      afwd,
        "Avg Bwd Segment Size":      abwd,
        "Fwd Header Length.1":       float(flow.fwd_header_bytes),
        "Fwd Avg Bytes/Bulk":        0.0,
        "Fwd Avg Packets/Bulk":      0.0,
        "Fwd Avg Bulk Rate":         0.0,
        "Bwd Avg Bytes/Bulk":        0.0,
        "Bwd Avg Packets/Bulk":      0.0,
        "Bwd Avg Bulk Rate":         0.0,
        "Subflow Fwd Packets":       float(n_fwd),
        "Subflow Fwd Bytes":         float(fb),
        "Subflow Bwd Packets":       float(n_bwd),
        "Subflow Bwd Bytes":         float(bb),
        "Init_Win_bytes_forward":    float(flow.init_win_fwd),
        "Init_Win_bytes_backward":   float(flow.init_win_bwd),
        "act_data_pkt_fwd":          float(flow.fwd_data_pkts),
        "min_seg_size_forward":      float(flow.fwd_min_seg),
        "Active Mean":  0.0, "Active Std":  0.0,
        "Active Max":   0.0, "Active Min":  0.0,
        "Idle Mean":    0.0, "Idle Std":    0.0,
        "Idle Max":     0.0, "Idle Min":    0.0,
    }


# ---------------------------------------------------------------------------
# Capture engine
# ---------------------------------------------------------------------------

class FlowCapture:
    """Background packet sniffer that finalises flows and calls a callback.

    Args:
        on_flow_complete: Called with (flow_meta: dict, prediction: dict)
                          when a flow is ready for scoring.
        interface:        Network interface name. None = scapy default.
    """

    def __init__(
        self,
        on_flow_complete: Callable[[dict, dict], None],
        interface: Optional[str] = None,
    ) -> None:
        self._callback   = on_flow_complete
        self._interface  = interface
        self._flows: dict[tuple, FlowRecord] = {}
        self._lock       = threading.Lock()
        self._running    = False
        self.stats       = {"packets_seen": 0, "flows_finalized": 0, "intrusions": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, interface: Optional[str] = None) -> None:
        """Start sniffing in a daemon background thread."""
        if not SCAPY_AVAILABLE:
            raise RuntimeError(
                "scapy is not installed. Run: pip install scapy\n"
                "On Windows, also install Npcap from https://npcap.com/"
            )
        if self._running:
            return
        if interface:
            self._interface = interface
        self._running = True
        threading.Thread(target=self._sniff_loop,   daemon=True).start()
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def stop(self) -> None:
        """Signal the sniff loop to exit on the next timeout tick."""
        self._running = False

    def list_interfaces(self) -> list[str]:
        """Return available network interface names."""
        if not SCAPY_AVAILABLE:
            return []
        try:
            return get_if_list()
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal loops
    # ------------------------------------------------------------------

    def _sniff_loop(self) -> None:
        while self._running:
            try:
                sniff(
                    iface=self._interface,
                    prn=self._process_packet,
                    timeout=1.0,
                    store=False,
                )
            except Exception:
                time.sleep(1)

    def _cleanup_loop(self) -> None:
        while self._running:
            time.sleep(5)
            self._expire_flows()

    # ------------------------------------------------------------------
    # Packet processing
    # ------------------------------------------------------------------

    def _process_packet(self, pkt) -> None:
        if IP not in pkt:
            return
        self.stats["packets_seen"] += 1

        ip  = pkt[IP]
        now = time.monotonic()

        if TCP in pkt:
            proto = "TCP"
            t    = pkt[TCP]
            sp, dp = t.sport, t.dport
            flags = int(t.flags)
            win   = t.window
            t_hdr = (t.dataofs * 4) if hasattr(t, "dataofs") else 20
            pay   = len(t.payload)
        elif UDP in pkt:
            proto = "UDP"
            t    = pkt[UDP]
            sp, dp = t.sport, t.dport
            flags, win, t_hdr, pay = 0, 0, 8, len(t.payload)
        else:
            return

        ip_hdr = (ip.ihl * 4) if hasattr(ip, "ihl") else 20
        size   = len(pkt)

        fwd_key = (ip.src, ip.dst, sp, dp, proto)
        rev_key = (ip.dst, ip.src, dp, sp, proto)

        flow_to_finalize = None
        with self._lock:
            if fwd_key in self._flows:
                flow, key, is_fwd = self._flows[fwd_key], fwd_key, True
            elif rev_key in self._flows:
                flow, key, is_fwd = self._flows[rev_key], rev_key, False
            else:
                flow = FlowRecord(
                    src_ip=ip.src, dst_ip=ip.dst,
                    src_port=sp,   dst_port=dp,
                    protocol=proto,
                )
                self._flows[fwd_key] = flow
                key, is_fwd = fwd_key, True

            flow.add_packet(
                is_forward=is_fwd, size=size, timestamp=now,
                ip_hdr_len=ip_hdr, transport_hdr_len=t_hdr,
                flags=flags, win_size=win, payload_len=pay,
            )

            # Finalise TCP flow on FIN or RST
            if proto == "TCP" and (flags & 0x01 or flags & 0x04):
                flow_to_finalize = self._flows.pop(key, None)
                if flow_to_finalize:
                    self.stats["flows_finalized"] += 1

        if flow_to_finalize:
            threading.Thread(
                target=self._predict_and_emit,
                args=(flow_to_finalize,),
                daemon=True,
            ).start()

    def _expire_flows(self) -> None:
        now = time.monotonic()
        to_finalize = []
        with self._lock:
            for key, flow in list(self._flows.items()):
                if (now - flow.last_time > FLOW_TIMEOUT
                        or now - flow.start_time > MAX_FLOW_DURATION):
                    to_finalize.append(self._flows.pop(key))
                    self.stats["flows_finalized"] += 1
        for flow in to_finalize:
            threading.Thread(
                target=self._predict_and_emit, args=(flow,), daemon=True
            ).start()

    # ------------------------------------------------------------------
    # Prediction + callback
    # ------------------------------------------------------------------

    def _predict_and_emit(self, flow: FlowRecord) -> None:
        from backend.pipeline.predict import get_feature_names, predict_single

        raw = extract_features(flow)
        try:
            known = get_feature_names()
            result = predict_single({k: raw.get(k, 0.0) for k in known})
        except Exception:
            return

        if result["prediction"] == "INTRUSION":
            self.stats["intrusions"] += 1

        meta = {
            "src_ip":   flow.src_ip,
            "dst_ip":   flow.dst_ip,
            "src_port": flow.src_port,
            "dst_port": flow.dst_port,
            "protocol": flow.protocol,
            "packets":  len(flow.fwd_sizes) + len(flow.bwd_sizes),
            "bytes":    sum(flow.fwd_sizes)  + sum(flow.bwd_sizes),
        }
        self._callback(meta, result)
