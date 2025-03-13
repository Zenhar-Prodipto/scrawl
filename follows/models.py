from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

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