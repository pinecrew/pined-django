from django.db import models


class TaskResult(models.Model):
    task = models.CharField()
    run = models.CharField()
    status = models.CharField()
    enqueued_at = models.DateTimeField()
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    arguments = models.JSONField()
    backend = models.CharField()
    errors = models.JSONField()
    worker = models.CharField()
    return_value = models.JSONField()
