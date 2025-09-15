from django.db import models

class CheckEvent(models.Model):
    TYPE_CHOICES = (("IN","IN"), ("OUT","OUT"))
    type = models.CharField(max_length=3, choices=TYPE_CHOICES)
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    lat = models.FloatField()
    lng = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True)

    ua = models.TextField(blank=True)            # user-agent
    ip = models.GenericIPAddressField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-ts"]

    def __str__(self):
        return f"{self.type} @ {self.ts:%Y-%m-%d %H:%M:%S} ({self.lat:.6f},{self.lng:.6f})"
