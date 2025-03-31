import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pulseconnect.settings')
django.setup()

from gamification.models import Badge  # Adjust the import to your actual app name

def add_badges():
    badges = [
        {
            'name': 'Poll Creator',
            'description': 'Awarded for creating your first poll.',
            'icon': 'poll',
            'requirement_type': 'polls_created',
            'requirement_count': 1,
            'level': 'bronze',
        },
        {
            'name': 'Discussion Starter',
            'description': 'Awarded for starting your first discussion.',
            'icon': 'discussion',
            'requirement_type': 'discussions_created',
            'requirement_count': 1,
            'level': 'bronze',
        },
        {
            'name': 'Commentator',
            'description': 'Awarded for making your first comment.',
            'icon': 'comment',
            'requirement_type': 'comments_made',
            'requirement_count': 1,
            'level': 'bronze',
        },
        {
            'name': 'Poll Enthusiast',
            'description': 'Awarded for participating in 10 polls.',
            'icon': 'poll',
            'requirement_type': 'polls_participated',
            'requirement_count': 10,
            'level': 'silver',
        },
        {
            'name': 'Community Builder',
            'description': 'Awarded for creating 5 discussions.',
            'icon': 'discussion',
            'requirement_type': 'discussions_created',
            'requirement_count': 5,
            'level': 'silver',
        },
        {
            'name': 'Master Commenter',
            'description': 'Awarded for making 50 comments.',
            'icon': 'comment',
            'requirement_type': 'comments_made',
            'requirement_count': 50,
            'level': 'gold',
        },
        {
            'name': 'Poll Legend',
            'description': 'Awarded for creating 100 polls.',
            'icon': 'poll',
            'requirement_type': 'polls_created',
            'requirement_count': 100,
            'level': 'platinum',
        },
    ]
    
    for badge in badges:
        obj, created = Badge.objects.get_or_create(**badge)
        if created:
            print(f"Added: {obj.name}")
        else:
            print(f"Already exists: {obj.name}")

if __name__ == "__main__":
    add_badges()