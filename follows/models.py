from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q, F  # Add this import

class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='following',  # Access: user.following.all()
        verbose_name='Follower',
        help_text='The user who is following another user.'
    )
    followed = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followers',  # Access: user.followers.all()
        verbose_name='Followed',
        help_text='The user being followed.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp of when the follow was created.'
    )

    class Meta:
        # Unique follower-followed pair
        constraints = [
            models.UniqueConstraint(
                fields=['follower', 'followed'],
                name='unique_follow'
            ),
            # Prevent self-follows
            models.CheckConstraint(
                check=~models.Q(follower=models.F('followed')),
                name='no_self_follow'
            )
        ]
        # Index for performance on lookups
        indexes = [
            models.Index(fields=['follower']),
            models.Index(fields=['followed']),
        ]
        verbose_name = 'Follow'
        verbose_name_plural = 'Follows'

    def clean(self):
        # Double-check self-follow at model level (optional, since constraint handles it)
        if self.follower == self.followed:
            raise ValidationError("Users cannot follow themselves.")
        super().clean()

    def __str__(self):
        return f"{self.follower.username} follows {self.followed.username}"
    
class FollowRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('denied', 'Denied'),
        ('cancelled', 'Cancelled'),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_requests',
        verbose_name='Requester',
        help_text='The user sending the follow request.'
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_requests',
        verbose_name='Target',
        help_text='The user receiving the follow request.'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Status of the follow request.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp of when the request was created.'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp of when the request was last updated.'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['requester', 'target'],
                name='unique_follow_request'
            ),
            models.CheckConstraint(
                check=~Q(requester=F('target')),
                name='no_self_request'
            )
        ]
        indexes = [
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['target', 'status']),
        ]
        verbose_name = 'Follow Request'
        verbose_name_plural = 'Follow Requests'

    def clean(self):
        if self.requester == self.target:
            raise ValidationError("Users cannot send follow requests to themselves.")
        super().clean()

    def __str__(self):
        return f"{self.requester.username} requested to follow {self.target.username}"