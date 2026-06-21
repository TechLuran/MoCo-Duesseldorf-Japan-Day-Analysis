"""
Standalone script — run this LOCALLY (needs internet access for map tiles).

Generates three map figures, each comparing ONE specific Telekom event slot
against its corresponding baseline file, colored by ONE specific metric:

    RSRP  ->  12-13.csv            vs.  baseline.csv
    RSRQ  ->  15-16.csv            vs.  baseline.csv
    SINR  ->  18-19-and-speed.csv  vs.  baseline-and-speed.csv

A small fixed lon-offset is applied so the two (near-identical) routes don't
visually overlap on the map.

USAGE:
    1. Place this script in the same folder as your CSVs (or adjust the paths below).
    2. pip install pandas cartopy matplotlib   (if not already installed)
    3. python make_telekom_maps.py
    4. It will write: map_rsrp.png, map_rsrq.png, map_sinr.png  (300 dpi)
       to the current folder.
    5. Upload those three PNGs back to Claude.

Adjust the paths in METRIC_CONFIG below to match your local folder layout
(defaults match the "clean/Telekom/..." structure used so far).
"""
import pandas as pd
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ---------------- CONFIG ----------------
# Each metric gets its own specific event file + matching baseline file.
METRIC_CONFIG = [
    dict(metric="rsrp", label="RSRP [dBm]",
         event_file="data/clean/O2/12-13.csv",
         baseline_file="data/clean/O2/baseline.csv"),
    dict(metric="rsrq", label="RSRQ [dB]",
         event_file="data/clean/O2/15-16.csv",
         baseline_file="data/clean/O2/baseline.csv"),
    dict(metric="sinr", label="SINR [dB]",
         event_file="data/clean/O2/18-19-and-speed.csv",
         baseline_file="data/clean/O2/baseline-and-speed.csv"),
]

CMAP_NAME = "RdYlGn"
ZOOM_LEVEL = 15
LON_OFFSET = 0.00018   # fixed offset in degrees longitude, applied opposite directions to each line
TILE_CACHE = "~/.cache/cartopy/tiles"

# Sane bounding box around the known route (Düsseldorf Rhine bank, Japan Day area).
# Rows outside this box are GPS glitches (e.g. cold GPS fix) and are dropped before plotting.
LAT_MIN, LAT_MAX = 51.215, 51.242
LON_MIN, LON_MAX = 6.760, 6.776

# Projection setup (same hack as your notebook)
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


def load_and_clean(path):
    df = pd.read_csv(path, dtype={"enb": str})
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df.connectionStatus == "PRIMARY"]
    # drop GPS glitches outside the known route bounding box
    df = df[
        (df.latitude.between(LAT_MIN, LAT_MAX)) &
        (df.longitude.between(LON_MIN, LON_MAX))
    ]
    return df


def make_map(event_df, baseline_df, metric, label, event_label, baseline_label, out_path):
    fig, ax = plt.subplots(1, 1, figsize=(6, 7.5), subplot_kw=dict(projection=PC))
    ax.add_image(_CartoVoyager(cache=TILE_CACHE), ZOOM_LEVEL)

    # shared color scale across both event & baseline for fair visual comparison
    vmin = min(event_df[metric].min(), baseline_df[metric].min())
    vmax = max(event_df[metric].max(), baseline_df[metric].max())
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    # event: offset west (-), baseline: offset east (+)
    sc1 = ax.scatter(
        event_df.longitude - LON_OFFSET, event_df.latitude,
        c=event_df[metric], cmap=CMAP_NAME, norm=norm,
        s=14, alpha=0.85, transform=PC,
        edgecolors="black", linewidths=0.15,
        marker="o", label=event_label,
    )
    ax.scatter(
        baseline_df.longitude + LON_OFFSET, baseline_df.latitude,
        c=baseline_df[metric], cmap=CMAP_NAME, norm=norm,
        s=14, alpha=0.85, transform=PC,
        edgecolors="black", linewidths=0.15,
        marker="^", label=baseline_label,
    )

    cbar = plt.colorbar(sc1, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label(label, fontsize=10)

    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.set_title(
        f"Telekom — {label.split(' [')[0]}: {event_label} (west, circles) vs. {baseline_label} (east, triangles)",
        fontsize=9.5,
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, facecolor="white")
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    for cfg in METRIC_CONFIG:
        event_df = load_and_clean(cfg["event_file"])
        baseline_df = load_and_clean(cfg["baseline_file"])

        event_label = cfg["event_file"].split("/")[-1].replace(".csv", "")
        baseline_label = cfg["baseline_file"].split("/")[-1].replace(".csv", "")

        print(f"\n[{cfg['metric']}] event={cfg['event_file']} ({len(event_df)} rows)  "
              f"baseline={cfg['baseline_file']} ({len(baseline_df)} rows)")

        make_map(
            event_df, baseline_df, cfg["metric"], cfg["label"],
            event_label, baseline_label,
            out_path=f"map_{cfg['metric']}.png",
        )

    print("\nDone. Upload map_rsrp.png, map_rsrq.png, map_sinr.png back to Claude.")