from django.db import models


class TimeStampedModel(models.Model):
    """
    Modelo base abstracto que proporciona campos de timestamp
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """
    Modelo base abstracto con campos adicionales comunes
    """
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True