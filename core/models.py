from django.db import models


class Bus(models.Model):
    bus_id = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField()
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Bus {self.bus_id}"


class BusStop(models.Model):
    stop_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name


class GPSRecord(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed = models.FloatField(help_text="Speed in km/h")
    weight = models.FloatField(null=True, blank=True, help_text="Vehicle load weight (kg), optional")

    def __str__(self):
        return f"{self.bus.bus_id} @ {self.timestamp}"


class CrowdingRecord(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    occupancy_ratio = models.FloatField(help_text="Estimated occupancy ratio (0-1+)")
    level = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.bus.bus_id} {self.level} @ {self.timestamp}"


class ETARecord(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    stop = models.ForeignKey(BusStop, on_delete=models.CASCADE)
    computed_at = models.DateTimeField(auto_now_add=True)
    source_timestamp = models.DateTimeField(help_text="Timestamp of the GPS record used")
    eta_seconds = models.IntegerField(null=True, blank=True)
    eta_minutes = models.FloatField(null=True, blank=True)
    distance_m = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.bus.bus_id} -> {self.stop.stop_id} ({self.eta_minutes} min)"
