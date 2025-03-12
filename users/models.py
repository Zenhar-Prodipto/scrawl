from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import JSONField
class Interest(models.Model):
    """
    Represents a single interest that users can associate with their profile.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="A unique interest name (e.g., 'tech', 'music')."
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Interest"
        verbose_name_plural = "Interests"

class User(AbstractUser):
    """
    Custom User model for Scrawl with extended profile fields.
    """
    email = models.EmailField(
        unique=True,
        blank=False,
        null=False,
        help_text="User's email address (required and unique)."
    )
    
    profile_picture = JSONField(
        blank=True, 
        null=True,
        default=dict,
        help_text="User's profile picture of different sizes"
        )
    
    interests = models.ManyToManyField(
        Interest,
        blank=True,
        related_name="users",
        help_text="User's selected interests."
    )
    
    # Fix the clashes by adding related_name
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='scrawl_users',  # Unique name for reverse lookup
        blank=True,
        help_text="The groups this user belongs to."
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='scrawl_users',  # Same unique name for consistency
        blank=True,
        help_text="Specific permissions for this user."
    )
    
    is_deleted = models.BooleanField(
        default=False,
        help_text="Boolean Field to detect if a user is deleted"
    )  
       
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="timestamp of delete "
    ) 
    

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        
        
    def __str__(self):
        return self.username