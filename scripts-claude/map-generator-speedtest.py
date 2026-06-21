"""
Standalone script — run this LOCALLY (needs internet access for map tiles).

Generates two map figures from the Ookla speedtest CSVs, each comparing
ONE provider's event-day test against its baseline, colored by download
throughput (Mbit/s):

    O2-test.csv       vs.  O2-baseline.csv
    Telekom-test.csv  vs.  Telekom-baseline.csv

Exactly 4 files used in total. A small fixed lon-offset is applied so the
two (near-identical) point sets don't visually overlap on the map.

Note: these are sparse point sets (6-7 speedtests per file), not dense
traces — the map will show isolated colored markers along the route, not
a continuous line.

USAGE:
    1. Place this script in the same folder as your CSVs (or adjust the paths below).
    2. pip install pandas cartopy matplotlib   (if not already installed)
    3. python make_speedtest_maps.py
    4. It will write: map_speedtest_o2.png, map_speedtest_telekom.png (300 dpi)
       to the current folder.
    5. Upload those two PNGs back to Claude.

Adjust the paths in PROVIDER_CONFIG below to match your local folder layout
(defaults match the "data/clean/Speedtest/..." structure used so far).
"""
import pandas as pd
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ---------------- CONFIG ----------------
SPEED_COLS = ["Datum", "VerbTyp", "Lat", "Lon", "DL_Mbps", "BytesDL",
              "UL_Mbps", "BytesUL", "Latency", "Server", "IntIP", "ExtIP", "URL"]

# NOTE: O2-baseline.csv has NO header row in the original export, the other
# three files DO have a header row. has_header below reflects that quirk.
PROVIDER_CONFIG = [
    dict(provider="O2",
         event_file="data/clean/Speedtest/O2-test.csv", event_has_header=True,
         baseline_file="data/clean/Speedtest/O2-baseline.csv", baseline_has_header=False),
    dict(provider="Telekom",
         event_file="data/clean/Speedtest/Telekom-test.csv", event_has_header=True,
         baseline_file="data/clean/Speedtest/Telekom-baseline.csv", baseline_has_header=True),
]

METRIC = "DL_Mbps"
METRIC_LABEL = "Download speed [Mbit/s]"
CMAP_NAME = "RdYlGn"
ZOOM_LEVEL = 15
LON_OFFSET = 0.00018   # fixed offset in degrees longitude, applied opposite directions to each line
TILE_CACHE = "~/.cache/cartopy/tiles"

# Sane bounding box around the known route (Düsseldorf Rhine bank, Japan Day area).
# Rows outside this box are GPS glitches and are dropped before plotting.
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


def load_and_clean(path, has_header):
    df = pd.read_csv(path, header=0 if has_header else None, names=SPEED_COLS)
    df = df.rename(columns={"Lat": "latitude", "Lon": "longitude"})
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[
        (df.latitude.between(LAT_MIN, LAT_MAX)) &
        (df.longitude.between(LON_MIN, LON_MAX))
    ]
    return df


def make_map(event_df, baseline_df, metric, label, provider, event_label, baseline_label, out_path):
    fig, ax = plt.subplots(1, 1, figsize=(6, 7.5), subplot_kw=dict(projection=PC))
    ax.add_image(_CartoVoyager(cache=TILE_CACHE), ZOOM_LEVEL)

    # shared color scale across event & baseline for fair visual comparison
    vmin = min(event_df[metric].min(), baseline_df[metric].min())
    vmax = max(event_df[metric].max(), baseline_df[metric].max())
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    # event: offset west (-), baseline: offset east (+)
    sc1 = ax.scatter(
        event_df.longitude - LON_OFFSET, event_df.latitude,
        c=event_df[metric], cmap=CMAP_NAME, norm=norm,
        s=90, alpha=0.9, transform=PC,
        edgecolors="black", linewidths=0.6,
        marker="o", label=event_label,
    )
    ax.scatter(
        baseline_df.longitude + LON_OFFSET, baseline_df.latitude,
        c=baseline_df[metric], cmap=CMAP_NAME, norm=norm,
        s=90, alpha=0.9, transform=PC,
        edgecolors="black", linewidths=0.6,
        marker="^", label=baseline_label,
    )

    cbar = plt.colorbar(sc1, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label(label, fontsize=10)

    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.set_title(
        f"{provider} — Speedtest: {event_label} (west, circles) vs. {baseline_label} (east, triangles)",
        fontsize=9.5,
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, facecolor="white")
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    for cfg in PROVIDER_CONFIG:
        event_df = load_and_clean(cfg["event_file"], cfg["event_has_header"])
        baseline_df = load_and_clean(cfg["baseline_file"], cfg["baseline_has_header"])

        event_label = cfg["event_file"].split("/")[-1].replace(".csv", "")
        baseline_label = cfg["baseline_file"].split("/")[-1].replace(".csv", "")

        print(f"\n[{cfg['provider']}] event={cfg['event_file']} ({len(event_df)} rows)  "
              f"baseline={cfg['baseline_file']} ({len(baseline_df)} rows)")

        make_map(
            event_df, baseline_df, METRIC, METRIC_LABEL, cfg["provider"],
            event_label, baseline_label,
            out_path=f"map_speedtest_{cfg['provider'].lower()}.png",
        )

    print("\nDone. Upload map_speedtest_o2.png and map_speedtest_telekom.png back to Claude.")