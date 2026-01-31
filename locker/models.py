from django.contrib.auth.models import User
from django.db import models


class ItemType(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Item(models.Model):
    type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name="loans")

    name = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    total_quantity = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Loan(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="loans")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loans")

    quantity = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    borrowed_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    expected_return = models.DateField(null=True, blank=True)

    checkout_note = models.TextField(blank=True)
    return_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} {self.item}"
