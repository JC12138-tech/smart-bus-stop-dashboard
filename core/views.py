import csv
import io
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.dateparse import parse_datetime

from .forms import CSVUploadForm
from .models import Bus, BusStop, GPSRecord


def home(request):
    return render(request, "core/home.html")


def upload_csv(request):
    """
    Upload a CSV and insert rows into Bus/BusStop/GPSRecord.
    Expected columns (header required):
      bus_id,timestamp,lat,lon,speed,capacity,stop_id,stop_name,stop_lat,stop_lon

    Minimal required for GPSRecord:
      bus_id,timestamp,lat,lon,speed,capacity
    BusStop fields are optional.
    """
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            try:
                decoded = f.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                messages.error(request, "CSV must be UTF-8 encoded.")
                return redirect("upload_csv")

            reader = csv.DictReader(io.StringIO(decoded))
            required = {"bus_id", "timestamp", "lat", "lon", "speed", "capacity"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                messages.error(
                    request,
                    "Missing required columns. Need: bus_id,timestamp,lat,lon,speed,capacity",
                )
                return redirect("upload_csv")

            created_gps = 0
            for row in reader:
                bus_id = row["bus_id"].strip()
                capacity = int(float(row["capacity"]))
                bus, _ = Bus.objects.get_or_create(
                    bus_id=bus_id,
                    defaults={"capacity": capacity},
                )
                # keep capacity updated if it changes
                if bus.capacity != capacity:
                    bus.capacity = capacity
                    bus.save(update_fields=["capacity"])

                # Optional bus stop info
                stop_id = (row.get("stop_id") or "").strip()
                if stop_id:
                    stop_defaults = {
                        "name": (row.get("stop_name") or stop_id).strip(),
                        "latitude": float(row.get("stop_lat") or 0.0),
                        "longitude": float(row.get("stop_lon") or 0.0),
                    }
                    BusStop.objects.update_or_create(stop_id=stop_id, defaults=stop_defaults)

                ts = parse_datetime(row["timestamp"].strip())
                if ts is None:
                    # fallback: allow unix seconds
                    try:
                        import datetime as dt
                        ts = dt.datetime.fromtimestamp(float(row["timestamp"]))
                    except Exception:
                        continue

                GPSRecord.objects.create(
                    bus=bus,
                    timestamp=ts,
                    latitude=float(row["lat"]),
                    longitude=float(row["lon"]),
                    speed=float(row["speed"]),
                )
                created_gps += 1

            messages.success(request, f"Upload complete. Inserted {created_gps} GPS records.")
            return redirect("upload_csv")
    else:
        form = CSVUploadForm()

    return render(request, "core/upload.html", {"form": form})
