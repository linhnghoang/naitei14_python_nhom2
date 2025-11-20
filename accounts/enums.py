from django.db import models


class Status(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Role(models.TextChoices):
    USER = "USER", "User"
    ADMIN = "ADMIN", "Admin"
