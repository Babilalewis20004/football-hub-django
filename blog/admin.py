from django.contrib import admin

# Register your models here.
from .models import Category
from .models import Post
from .models import Comment
from .models import Bookmark


admin.site.register(Category)
admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Bookmark)