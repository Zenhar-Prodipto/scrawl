from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User, Interest

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'get_interests')
    search_fields = ('username', 'email')

    def get_interests(self, obj):
        return ", ".join([interest.name for interest in obj.interests.all()])
    get_interests.short_description = "Interests"

@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)