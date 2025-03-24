import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pulseconnect.settings')
django.setup()

from polls.models import QuestionType

def add_question_types():
    question_types = [
        {'name': 'Multiple Choice', 'slug': 'multiple_choice', 'description': 'Select one or more answers from a list of options.'},
        {'name': 'True/False', 'slug': 'true_false', 'description': 'A question type with only two possible answers: true or false.'},
        {'name': 'Short Answer', 'slug': 'short_answer', 'description': 'A question type that requires a brief text response.'},
        {'name': 'Essay', 'slug': 'essay', 'description': 'A question type that allows for a longer, written response.'},
        {'name': 'Rating Scale', 'slug': 'rating_scale', 'description': 'A question type that asks respondents to rate something on a defined scale (e.g., 1 to 5).'},
        {'name': 'Likert Scale', 'slug': 'likert_scale', 'description': 'A question type that measures attitudes or opinions on a scale.'},
        {'name': 'Open Ended', 'slug': 'open_ended', 'description': 'A question type that allows for a free-text response.'},
    ]
    
    for question_type in question_types:
        obj, created = QuestionType.objects.get_or_create(**question_type)
        if created:
            print(f"Added: {obj.name}")
        else:
            print(f"Already exists: {obj.name}")

if __name__ == "__main__":
    add_question_types()