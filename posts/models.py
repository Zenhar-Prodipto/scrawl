from django.db import models
from users.models import User

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Post(models.Model):
    PRIVACY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),  # Private means followers-only
    )

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    text = models.TextField(blank=True, default='')
    tags = models.ManyToManyField(Tag, related_name='posts')
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='public')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),  # For faster lookups by user
            models.Index(fields=['created_at']),  # For sorting by creation time
        ]

    def __str__(self):
        return f"Post {self.id} by {self.user.username} (Tag: {self.tag})"
    
    
class PostImage(models.Model):
    id = models.AutoField(primary_key=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='post_images')
    image_url = models.URLField(max_length=500)  # URL from image upload API
    order = models.PositiveIntegerField(default=0)  # For ordering images

    class Meta:
        indexes = [
            models.Index(fields=['post']),  # For faster lookups by post
        ]
        ordering = ['order']  # Default ordering by order field

    def __str__(self):
        return f"Image for Post {self.post.id} (Order: {self.order})"
    

    
class Like(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Prevent duplicate likes
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['post']),
        ]

    def __str__(self):
        return f"{self.user.username} likes Post {self.post.id}"
    
class Comment(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField(blank=False, null=False)  # Comment can't be empty
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.user.username} on Post {self.post.id}"
    
class Save(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='saves')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Prevent duplicate saves
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['post']),
        ]

    def __str__(self):
        return f"{self.user.username} saved Post {self.post.id}"