import csv
import math
import datetime as dt
import io
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse
from django.db.models import OuterRef, Subquery
from openpyxl import Workbook

from .forms import CSVUploadForm
from .models import Bus, BusStop, GPSRecord, CrowdingRecord, ETARecord
import json
from django.db.models import Max

def home(request):
    return render(request, "core/home.html")


def upload_csv(request):
    """
    Upload a CSV and insert rows into Bus/BusStop/GPSRecord,
    and derive CrowdingRecord + ETARecord.

    Expected CSV header (case-sensitive):
      bus_id,timestamp,lat,lon,speed,capacity,weight,stop_id,stop_name,stop_lat,stop_lon

    Required columns:
      bus_id,timestamp,lat,lon,speed,capacity,weight

    Notes:
      - timestamp supports ISO8601 with 'Z', e.g. 2025-12-15T01:00:00Z
      - weight is in kg; crowding uses 75 kg/person as a simple assumption
      - ETA is computed only if stop_id exists AND the stop exists in DB (created/updated from CSV row)
    """
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]

            # Decode CSV (utf-8-sig handles Excel BOM cleanly)
            try:
                decoded = f.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                messages.error(request, "CSV must be UTF-8 encoded.")
                return redirect("upload_csv")

            reader = csv.DictReader(io.StringIO(decoded))

            required = {"bus_id", "timestamp", "lat", "lon", "speed", "capacity", "weight"}
            if not reader.fieldnames:
                messages.error(request, "CSV file appears to have no header row.")
                return redirect("upload_csv")

            # Normalize header whitespace (common gotcha)
            fieldnames = [fn.strip() for fn in reader.fieldnames]
            if set(fieldnames) != set(reader.fieldnames):
                # Rebuild reader with stripped headers
                reader = csv.DictReader(io.StringIO(decoded))
                reader.fieldnames = fieldnames

            if not required.issubset(set(reader.fieldnames)):
                messages.error(
                    request,
                    "Missing required columns. Need: bus_id,timestamp,lat,lon,speed,capacity,weight",
                )
                return redirect("upload_csv")

            created_gps = 0
            created_crowding = 0
            created_eta = 0
            skipped = 0
            total = 0
            first_error = None

            for row in reader:
                total += 1

                try:
                    # ---- Parse / validate base fields ----
                    bus_id = (row.get("bus_id") or "").strip()
                    if not bus_id:
                        raise ValueError("empty bus_id")

                    # robust timestamp parse (supports trailing Z)
                    ts_raw = (row.get("timestamp") or "").strip()
                    if not ts_raw:
                        raise ValueError("empty timestamp")
                    ts = dt.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))

                    lat = float((row.get("lat") or "").strip())
                    lon = float((row.get("lon") or "").strip())
                    speed = float((row.get("speed") or "").strip())
                    capacity = int(float((row.get("capacity") or "").strip()))
                    weight_str = (row.get("weight") or "").strip()
                    weight = float(weight_str) if weight_str != "" else None

                    # ---- Upsert Bus ----
                    bus, _ = Bus.objects.get_or_create(
                        bus_id=bus_id,
                        defaults={"capacity": capacity},
                    )
                    if bus.capacity != capacity:
                        bus.capacity = capacity
                        bus.save(update_fields=["capacity"])

                    # ---- Upsert BusStop (optional) ----
                    stop_id = (row.get("stop_id") or "").strip()
                    stop_obj = None
                    if stop_id:
                        stop_name = (row.get("stop_name") or stop_id).strip()

                        # If stop_lat/stop_lon missing, keep previous values if stop exists
                        stop_lat_raw = (row.get("stop_lat") or "").strip()
                        stop_lon_raw = (row.get("stop_lon") or "").strip()

                        defaults = {"name": stop_name}
                        if stop_lat_raw != "" and stop_lon_raw != "":
                            defaults["latitude"] = float(stop_lat_raw)
                            defaults["longitude"] = float(stop_lon_raw)

                        stop_obj, _ = BusStop.objects.update_or_create(
                            stop_id=stop_id,
                            defaults=defaults,
                        )

                    # ---- Create GPSRecord ----
                    gps = GPSRecord.objects.create(
                        bus=bus,
                        timestamp=ts,
                        latitude=lat,
                        longitude=lon,
                        speed=speed,
                        weight=weight,
                    )
                    created_gps += 1

                    # ---- Create CrowdingRecord ----
                    if gps.weight is not None and bus.capacity > 0:
                        est_passengers = gps.weight / 75.0
                        occ = est_passengers / float(bus.capacity)
                        lvl = crowding_level(occ)
                        CrowdingRecord.objects.create(
                            bus=bus,
                            timestamp=gps.timestamp,
                            occupancy_ratio=occ,
                            level=lvl,
                        )
                        created_crowding += 1

                    # ---- Create ETARecord ----
                    if stop_obj is not None:
                        distance = haversine_m(gps.latitude, gps.longitude, stop_obj.latitude, stop_obj.longitude)
                        speed_mps = max(0.0, gps.speed) * 1000.0 / 3600.0
                        if speed_mps >= 1.0:
                            eta_s = int(distance / speed_mps)
                            ETARecord.objects.create(
                                bus=bus,
                                stop=stop_obj,
                                source_timestamp=gps.timestamp,
                                eta_seconds=eta_s,
                                eta_minutes=eta_s / 60.0,
                                distance_m=distance,
                            )
                        else:
                            ETARecord.objects.create(
                                bus=bus,
                                stop=stop_obj,
                                source_timestamp=gps.timestamp,
                                eta_seconds=None,
                                eta_minutes=None,
                                distance_m=distance,
                            )
                        created_eta += 1

                except Exception as e:
                    skipped += 1
                    if first_error is None:
                        # keep the first error only (avoid spamming)
                        first_error = f"{type(e).__name__}: {e}"
                    continue

            msg = (
                f"Upload complete. Read {total} rows, inserted {created_gps} GPS records, "
                f"{created_crowding} crowding records, {created_eta} ETA records, skipped {skipped} rows."
            )
            if first_error:
                msg += f" First error: {first_error}"
            messages.success(request, msg)
            return redirect("upload_csv")
    else:
        form = CSVUploadForm()

    return render(request, "core/upload.html", {"form": form})


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2) + math.cos(p1)*math.cos(p2)*(math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def crowding_level(occupancy_ratio: float) -> str:
    if occupancy_ratio < 0.5:
        return "LOW"
    if occupancy_ratio < 0.8:
        return "MEDIUM"
    if occupancy_ratio < 1.0:
        return "HIGH"
    return "OVERCROWDED"


def dashboard(request):
    # show latest crowding + latest ETA per bus
    buses = Bus.objects.all().order_by("bus_id")
    stops = BusStop.objects.all().order_by("stop_id")

    selected_stop_id = request.GET.get("stop_id") or ""
    selected_stop = BusStop.objects.filter(stop_id=selected_stop_id).first() if selected_stop_id else None

    cards = []
    chart_labels = []
    crowding_series = {}  # bus_id -> [ratios]
    eta_series = {}       # bus_id -> [minutes]

    # choose last N records per bus for plotting
    N = 20

    for bus in buses:
        latest_c = CrowdingRecord.objects.filter(bus=bus).order_by("-timestamp").first()
        latest_eta = None
        if selected_stop:
            latest_eta = ETARecord.objects.filter(bus=bus, stop=selected_stop).order_by("-source_timestamp").first()

        cards.append({
            "bus_id": bus.bus_id,
            "capacity": bus.capacity,
            "latest_level": latest_c.level if latest_c else "N/A",
            "latest_occ": round(latest_c.occupancy_ratio, 3) if latest_c else None,
            "latest_eta_min": round(latest_eta.eta_minutes, 1) if (latest_eta and latest_eta.eta_minutes is not None) else None,
        })

        # build time series
        c_qs = list(CrowdingRecord.objects.filter(bus=bus).order_by("-timestamp")[:N])
        c_qs.reverse()
        crowding_series[bus.bus_id] = [round(x.occupancy_ratio, 3) for x in c_qs]

        if selected_stop:
            e_qs = list(ETARecord.objects.filter(bus=bus, stop=selected_stop).order_by("-source_timestamp")[:N])
            e_qs.reverse()
            eta_series[bus.bus_id] = [round(x.eta_minutes, 2) if x.eta_minutes is not None else None for x in e_qs]
        else:
            eta_series[bus.bus_id] = []

        # shared labels: use the first bus's crowding timestamps if available
        if not chart_labels and c_qs:
            chart_labels = [x.timestamp.isoformat() for x in c_qs]

    context = {
        "cards": cards,
        "stops": stops,
        "selected_stop_id": selected_stop_id,
        "chart_labels_json": json.dumps(chart_labels),
        "crowding_series_json": json.dumps(crowding_series),
        "eta_series_json": json.dumps(eta_series),
    }
    return render(request, "core/dashboard.html", context)

def export_xlsx(request):
    """
    Export latest crowding + latest ETA (for selected stop) to an .xlsx file.

    Usage:
      /export.xlsx?stop_id=S001
    """
    stop_id = (request.GET.get("stop_id") or "").strip()
    stop = BusStop.objects.filter(stop_id=stop_id).first() if stop_id else None

    # Subqueries to fetch latest crowding per bus
    latest_crowding_qs = CrowdingRecord.objects.filter(bus=OuterRef("pk")).order_by("-timestamp")
    latest_level = Subquery(latest_crowding_qs.values("level")[:1])
    latest_occ = Subquery(latest_crowding_qs.values("occupancy_ratio")[:1])
    latest_c_ts = Subquery(latest_crowding_qs.values("timestamp")[:1])

    buses = Bus.objects.all().annotate(
        crowding_level=latest_level,
        occupancy_ratio=latest_occ,
        crowding_timestamp=latest_c_ts,
    ).order_by("bus_id")

    # Prepare workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Latest Status"

    header = [
        "bus_id",
        "capacity",
        "crowding_level",
        "occupancy_ratio",
        "crowding_timestamp",
        "stop_id",
        "stop_name",
        "eta_minutes",
        "distance_m",
        "eta_source_timestamp",
    ]
    ws.append(header)

    for bus in buses:
        eta_minutes = None
        distance_m = None
        eta_source_ts = None

        if stop is not None:
            latest_eta = (
                ETARecord.objects.filter(bus=bus, stop=stop)
                .order_by("-source_timestamp")
                .first()
            )
            if latest_eta:
                eta_minutes = latest_eta.eta_minutes
                distance_m = latest_eta.distance_m
                eta_source_ts = latest_eta.source_timestamp

        ws.append([
            bus.bus_id,
            bus.capacity,
            bus.crowding_level or "N/A",
            float(bus.occupancy_ratio) if bus.occupancy_ratio is not None else None,
            bus.crowding_timestamp.isoformat() if bus.crowding_timestamp else None,
            stop.stop_id if stop else None,
            stop.name if stop else None,
            float(eta_minutes) if eta_minutes is not None else None,
            float(distance_m) if distance_m is not None else None,
            eta_source_ts.isoformat() if eta_source_ts else None,
        ])

    # Return as file download
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="smart_bus_export.xlsx"'
    wb.save(response)
    return response
