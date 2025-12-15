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

    def __str__(self):
        return f"{self.bus.bus_id} @ {self.timestamp}"
