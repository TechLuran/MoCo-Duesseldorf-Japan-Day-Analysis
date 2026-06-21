"""
Standalone script — run this LOCALLY (needs internet access for map tiles).

Plots WHERE handovers happen along the route: every time the serving cell
(cid) changes between consecutive PRIMARY scans, the GPS location of that
handover is marked on the map.

Each of the 3 Japan Day event slots is plotted against its OWN matching
baseline file (not a combined baseline) -- 3 slots x 2 providers = 6 maps:

    12-13            vs.  baseline             (no speedtest pauses in either)
    15-16            vs.  baseline             (no speedtest pauses in either)
    18-19-and-speed  vs.  baseline-and-speed    (both contain speedtest pauses)

...for both O2 and Telekom.

A handover is detected separately within each measurement loop (slot) --
the boundary between loops/files is never counted as a handover.

A small fixed lon-offset is applied so the two point sets don't visually
overlap on the map.

USAGE:
    1. Place this script next to your data folder (paths assume "data/clean/...").
    2. pip install pandas cartopy matplotlib   (if not already installed)
    3. python make_handover_maps.py
    4. It will write 6 PNGs (300 dpi) to the current folder, e.g.:
       map_handovers_o2_12-13.png, map_handovers_telekom_18-19.png, ...
    5. Upload those PNGs back to Claude.

Adjust the paths in PROVIDER_CONFIG below to match your local folder layout.
"""
import pandas as pd
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
import matplotlib.pyplot as plt

# ---------------- CONFIG ----------------
# Each event slot is paired with its OWN matching baseline file:
#   12-13 / 15-16           -> baseline.csv            (no speedtest pauses)
#   18-19-and-speed         -> baseline-and-speed.csv  (both have speedtest pauses)
PROVIDER_CONFIG = [
    dict(provider="O2",
         pairs=[
             ("12-13", "data/clean/O2/12-13.csv", "data/clean/O2/baseline.csv"),
             ("15-16", "data/clean/O2/15-16.csv", "data/clean/O2/baseline.csv"),
             ("18-19", "data/clean/O2/18-19-and-speed.csv", "data/clean/O2/baseline-and-speed.csv"),
         ]),
    dict(provider="Telekom",
         pairs=[
             ("12-13", "data/clean/Telekom/12-13.csv", "data/clean/Telekom/baseline.csv"),
             ("15-16", "data/clean/Telekom/15-16.csv", "data/clean/Telekom/baseline.csv"),
             ("18-19", "data/clean/Telekom/18-19-and-speed.csv", "data/clean/Telekom/baseline-and-speed.csv"),
         ]),
]

ZOOM_LEVEL = 15
LON_OFFSET = 0.00018   # fixed offset in degrees longitude, applied opposite directions to each line
TILE_CACHE = "~/.cache/cartopy/tiles"

EVENT_COLOR = "#E2004B"      # warm red -- event slot
BASELINE_COLOR = "#1F77B4"   # calm blue -- matching baseline

# Sane bounding box around the known route (Düsseldorf Rhine bank, Japan Day area).
# Rows outside this box are GPS glitches (e.g. cold GPS fix) and are dropped before plotting.
LAT_MIN, LAT_MAX = 51.215, 51.242
LON_MIN, LON_MAX = 6.760, 6.776

# Projection setup (same hack as the original notebook)
WGS84_SEMIMAJOR_AXIS = 6378137
PC = ccrs.PlateCarree(
    globe=ccrs.Globe(
        ellipse="sphere",
        semimajor_axis=WGS84_SEMIMAJOR_AXIS,
        semiminor_axis=WGS84_SEMIMAJOR_AXIS,
    )
)


class _CartoVoyager(cimgt.GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return f"https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"


def load_clean(path):
    df = pd.read_csv(path, dtype={"enb": str})
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df.connectionStatus == "PRIMARY"]
    df = df[
        (df.latitude.between(LAT_MIN, LAT_MAX)) &
        (df.longitude.between(LON_MIN, LON_MAX))
    ]
    return df


def handover_locations(path):
    """Find rows in this single file where cid changes vs. the previous row
    in time, and return only those handover rows (with their GPS location).
    The very first row is never counted as a handover."""
    df = load_clean(path)
    df = df.sort_values("timestamp")
    changed = df["cid"].ne(df["cid"].shift())
    return df[changed].iloc[1:]  # drop first row (not a real handover)


def make_map(event_ho, baseline_ho, provider, slot_label, baseline_label, out_path):
    fig, ax = plt.subplots(1, 1, figsize=(6, 7.5), subplot_kw=dict(projection=PC))
    ax.add_image(_CartoVoyager(cache=TILE_CACHE), ZOOM_LEVEL)

    ax.scatter(
        event_ho.longitude - LON_OFFSET, event_ho.latitude,
        c=EVENT_COLOR, s=26, alpha=0.75, transform=PC,
        edgecolors="black", linewidths=0.3,
        marker="o", label=f"{slot_label} handovers (n={len(event_ho)})",
    )
    ax.scatter(
        baseline_ho.longitude + LON_OFFSET, baseline_ho.latitude,
        c=BASELINE_COLOR, s=26, alpha=0.75, transform=PC,
        edgecolors="black", linewidths=0.3,
        marker="^", label=f"{baseline_label} handovers (n={len(baseline_ho)})",
    )

    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.set_title(
        f"{provider} {slot_label} — Handover locations: "
        f"Event (west, circles) vs. {baseline_label} (east, triangles)",
        fontsize=9.2,
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, facecolor="white")
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    for cfg in PROVIDER_CONFIG:
        for slot_label, event_file, baseline_file in cfg["pairs"]:
            event_ho = handover_locations(event_file)
            baseline_ho = handover_locations(baseline_file)
            baseline_label = baseline_file.split("/")[-1].replace(".csv", "")

            print(f"\n[{cfg['provider']} {slot_label}] event handovers={len(event_ho)}  "
                  f"({baseline_label}) baseline handovers={len(baseline_ho)}")

            out_name = f"map_handovers_{cfg['provider'].lower()}_{slot_label}.png"
            make_map(event_ho, baseline_ho, cfg["provider"], slot_label, baseline_label, out_path=out_name)

    print("\nDone. Upload all 6 map_handovers_*.png files back to Claude.")