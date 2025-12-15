from django.contrib import admin
from .models import Bus, BusStop, GPSRecord, CrowdingRecord, ETARecord



@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("bus_id", "capacity")
    search_fields = ("bus_id",)


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ("stop_id", "name")
    search_fields = ("stop_id", "name")


@admin.register(GPSRecord)
class GPSRecordAdmin(admin.ModelAdmin):
    list_display = ("bus", "timestamp", "speed")
    list_filter = ("bus",)


@admin.register(CrowdingRecord)
class CrowdingRecordAdmin(admin.ModelAdmin):
    list_display = ("bus", "timestamp", "level", "occupancy_ratio")
    list_filter = ("bus", "level")


@admin.register(ETARecord)
class ETARecordAdmin(admin.ModelAdmin):
    list_display = ("bus", "stop", "source_timestamp", "eta_minutes", "distance_m", "computed_at")
    list_filter = ("bus", "stop")
